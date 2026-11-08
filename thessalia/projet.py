"""Examen de l'application : un dossier qui contient tout, du sujet aux résultats.

    examens/<nom>/
        examen.yaml            source unique (docs/FORMAT_SUJET.md), et son logo éventuel
        produit/               sujets et corrigés PDF, zones, rapports verif-zones
            gabarits/          gabarit de chaque langue (relu dans le PDF)
            corriges/          key / vocab / bareme de chaque langue
        scans/<classe>.pdf     copies scannées d'une classe, et <classe>.json (langue du sujet distribué)
        classes/<classe>/      résultats de la lecture (comme sorties/<classe> avec `process`)
        decisions.sqlite       décisions de correction de cet examen
        listes/, verite/       attributions des copies (copie;etudiant) et vérité apprise, de cet examen

Le dossier `examens/` est hors dépôt : il contient des copies d'élèves.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .sujet.modele import examen
from .sujet.source import ErreurSujet

RACINE = Path("examens")
RE_NOM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,60}$")


def nom_valide(nom: str) -> bool:
    return bool(RE_NOM.match(nom or "")) and ".." not in nom


class Projet:
    def __init__(self, dossier):
        self.dir = Path(dossier)
        self.nom = self.dir.name
        self.produit = self.dir / "produit"
        self.gabarits = self.produit / "gabarits"
        self.corriges = self.produit / "corriges"
        self.scans = self.dir / "scans"
        self.classes_dir = self.dir / "classes"

    # ---------------------------------------------------------------- source
    @property
    def source(self) -> Path | None:
        cands = sorted(self.dir.glob("*.yaml")) + sorted(self.dir.glob("*.yml"))
        return cands[0] if cands else None

    def controle(self):
        """(examen, None) si la source passe le contrôle strict, sinon (None, [erreurs])."""
        if self.source is None:
            return None, ["pas de fichier .yaml dans le dossier de l'examen"]
        try:
            return examen(self.source), None
        except ErreurSujet as e:
            return None, e.erreurs

    def produit_a_jour(self) -> bool:
        """Les PDF et corrigés produits sont-ils plus récents que la source (et ses images) ?"""
        if self.source is None or not self.corriges.is_dir():
            return False
        faits = [p.stat().st_mtime for p in self.corriges.glob("*.key.json")]
        sources = [p.stat().st_mtime for p in self.dir.iterdir() if p.is_file()]
        return bool(faits) and min(faits) >= max(sources)

    def produire(self, log=print):
        from .sujet import produire_tout

        ex, err = self.controle()
        if err:
            raise SystemExit("Source refusée :\n" + "\n".join("  - " + m for m in err))
        produire_tout(ex, self.source, self.produit, self.gabarits, self.corriges, log=log)
        return ex

    def fichiers(self, langue: str):
        """Chemins du sujet, gabarit et corrigé d'une langue (après `produire`)."""
        ex, err = self.controle()
        if err:
            raise SystemExit("Source refusée")
        base = f"{ex.id}_{langue.upper()}"
        return {"base": base, "sujet": self.produit / f"sujet_{base}.pdf", "corrige_pdf": self.produit / f"corrige_{base}.pdf",
                "gabarit": self.gabarits / f"gabarit_{base}.json", "key": self.corriges / f"{base}.key.json"}

    def pdfs(self):
        return sorted(self.produit.glob("*.pdf")) if self.produit.is_dir() else []

    # ---------------------------------------------------------------- classes
    def deposer(self, classe: str, langue: str, contenu: bytes):
        if not nom_valide(classe):
            raise ValueError("nom de classe : lettres, chiffres, _ - . (ex. supA_1)")
        ex, err = self.controle()
        if err or langue not in ex.langues:
            raise ValueError(f"langue : une de {', '.join(ex.langues) if ex else '?'}")
        if not contenu.startswith(b"%PDF"):
            raise ValueError("le fichier déposé n'est pas un PDF")
        self.scans.mkdir(parents=True, exist_ok=True)
        (self.scans / f"{classe}.pdf").write_bytes(contenu)
        (self.scans / f"{classe}.json").write_text(json.dumps({"langue": langue}), encoding="utf-8")

    def traiter(self, classe: str, log=print):
        """Lecture des copies d'une classe (QCM, grille, vignettes) avec le gabarit de sa langue."""
        from .pipeline import Processor

        info = json.loads((self.scans / f"{classe}.json").read_text(encoding="utf-8"))
        f = self.fichiers(info["langue"])
        if not f["gabarit"].exists():
            raise SystemExit("sujet pas encore produit : produire les PDF d'abord")
        proc = Processor(f["gabarit"], f["sujet"], answer_key=f["key"], log=log)
        return proc.run([self.scans / f"{classe}.pdf"], self.classes_dir / classe)

    def classes(self):
        """Une ligne par classe déposée : langue, lue ou non, copies, points à revoir, alerte de gabarit."""
        out = []
        for scan in sorted(self.scans.glob("*.pdf")) if self.scans.is_dir() else []:
            nom = scan.stem
            meta = self.scans / f"{nom}.json"
            langue = json.loads(meta.read_text(encoding="utf-8")).get("langue") if meta.exists() else None
            res = self.classes_dir / nom / "results.json"
            ligne = {"classe": nom, "langue": langue, "lue": res.exists(), "copies": None, "a_revoir": None,
                     "taille_mo": round(scan.stat().st_size / 1e6, 1)}
            if res.exists():
                r = json.loads(res.read_text(encoding="utf-8"))
                ligne.update(copies=r.get("n_copies"), a_revoir=sum(c.get("n_review", 0) for c in r.get("copies", [])),
                             lue_avant=res.stat().st_mtime < scan.stat().st_mtime)
            out.append(ligne)
        return out

    def stockage(self):
        """Décisions, vérité d'apprentissage et attributions des copies de CET examen (pas de data/)."""
        return {"db": self.dir / "decisions.sqlite", "truth_dir": self.dir / "verite", "lists_dir": self.dir / "listes"}

    def dossiers_lus(self):
        return [self.classes_dir / c["classe"] for c in self.classes() if c["lue"]]


def projets(racine=RACINE):
    racine = Path(racine)
    return [Projet(d) for d in sorted(racine.iterdir()) if d.is_dir()] if racine.is_dir() else []


def creer(nom: str, source_yaml: bytes, racine=RACINE, fichiers=None) -> Projet:
    """Nouvel examen à partir d'un fichier source (et de ses images éventuelles : {nom: contenu})."""
    if not nom_valide(nom):
        raise ValueError("nom de l'examen : lettres, chiffres, _ - . (ex. midterm_2026)")
    d = Path(racine) / nom
    if d.exists():
        raise ValueError(f"l'examen « {nom} » existe déjà")
    d.mkdir(parents=True)
    (d / "examen.yaml").write_bytes(source_yaml)
    for n, contenu in (fichiers or {}).items():
        if nom_valide(n):
            (d / n).write_bytes(contenu)
    return Projet(d)
