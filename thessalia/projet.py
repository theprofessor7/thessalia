"""Examen de l'application : un dossier qui contient tout, du sujet aux résultats.

    examens/<nom>/
        examen.yaml            source unique (docs/FORMAT_SUJET.md), et son logo éventuel
        produit/               sujets et corrigés PDF, zones, rapports verif-zones
            gabarits/          gabarit de chaque langue (relu dans le PDF)
            corriges/          key / vocab / bareme de chaque langue
        scans/<classe>.pdf     copies scannées d'une classe, et <classe>.json (langue du sujet distribué)
        classes/<classe>/      résultats de la lecture (comme sorties/<classe> avec `process`)
        decisions.sqlite       décisions de correction de cet examen
        listes/, verite/       liste des élèves (.xlsx, sinon la liste commune data/listes), attributions des
                               copies et vérité apprise, de cet examen
        notes/notes.xlsx       notes finales (l'ancien classeur est gardé, daté)

Le dossier `examens/` est hors dépôt : il contient des copies d'élèves.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .sujet.modele import examen
from .sujet.source import ErreurSujet

RACINE = Path("examens")
SOURCES = {".yaml", ".yml", ".png", ".jpg", ".jpeg", ".svg", ".gif"}    # fichiers dont dépendent les PDF produits
VALIDATION_MIN = 30     # lectures vérifiées par l'enseignant, sans aucun écart, avant de valider un sujet
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
        # seulement la source et ses images (pas decisions.sqlite, modifié à chaque correction)
        sources = [p.stat().st_mtime for p in self.dir.iterdir()
                   if p.is_file() and p.suffix.lower() in SOURCES]
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
                "gabarit": self.gabarits / f"gabarit_{base}.json", "key": self.corriges / f"{base}.key.json",
                "vocab": self.corriges / f"{base}.vocab.json"}

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
            ligne["courtes"] = (self.classes_dir / nom / "short_answers.csv").exists()
            if res.exists():
                r = json.loads(res.read_text(encoding="utf-8"))
                ligne.update(copies=r.get("n_copies"), a_revoir=sum(c.get("n_review", 0) for c in r.get("copies", [])),
                             lue_avant=res.stat().st_mtime < scan.stat().st_mtime)
            out.append(ligne)
        return out

    def stockage(self):
        """Décisions, vérité d'apprentissage et attributions des copies de CET examen (pas de data/)."""
        return {"db": self.dir / "decisions.sqlite", "truth_dir": self.dir / "verite", "lists_dir": self.dir / "listes"}
        # (même rangement que correction.stockage_examen, qui s'applique à toute classe de l'examen)

    def dossiers_lus(self):
        return [self.classes_dir / c["classe"] for c in self.classes() if c["lue"]]

    # ---------------------------------------------------------------- étapes lourdes
    def lire_courtes(self, log=print):
        """Réponses courtes de chaque classe lue, par TrOCR (local, gratuit), avec le vocabulaire de sa langue.
        Sujet nouveau : tant que son corrigé n'est pas validé par une mesure, tout part en revue avec la lecture
        proposée (cf. ocr_run.lecture_validee)."""
        from .apprentissage import modele_ecriture
        from .ocr_run import run as ocr
        dossiers = self.dossiers_lus()
        if not dossiers:
            raise SystemExit("aucune classe lue")
        modele = modele_ecriture()     # lecteur affiné et adopté (page Apprentissage), sinon le modèle d'origine
        if modele:
            log(f"lecteur d'écriture affiné : {modele}")
        for d in dossiers:
            info = json.loads((self.scans / f"{d.name}.json").read_text(encoding="utf-8"))
            log(f"=== {d.name} ({info['langue'].upper()})")
            if getattr(log, "progression", None):
                log.progression(None)
            ocr(d, self.fichiers(info["langue"])["vocab"], "trocr", log=log,
                backend_kw={"model": modele} if modele else None)
        # noms écrits sur les copies : propositions pour « Identifier les copies »
        from .identite import run as noms
        log("=== noms des élèves")
        if getattr(log, "progression", None):
            log.progression(None)
        try:
            noms(dossiers, lists_dir=self.stockage()["lists_dir"])
        except SystemExit as e:
            log(f"noms non lus : {e}")

    def preparer(self, log=print):
        """Lecture approfondie (code transcrit et pré-coché, réponses courtes relues) avec les modèles Ollama
        présents ; ses messages (print) arrivent dans le journal de la tâche. Son début et sa fin sont notés : une
        lecture interrompue (pause, Thessalia fermé) se voit à la page de l'examen, qui propose de la reprendre."""
        from .preparer import run
        dossiers = self.dossiers_lus()
        if not dossiers:
            raise SystemExit("aucune classe lue")
        self._noter_approfondie(etat="en cours", debut=time.strftime("%Y-%m-%d %H:%M"))
        run(dossiers)
        self._noter_approfondie(etat="terminée", fin=time.strftime("%Y-%m-%d %H:%M"))

    def _noter_approfondie(self, **valeurs):
        p = self.dir / "lecture_approfondie.json"
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        d.update(valeurs)
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    def approfondie(self):
        """Où en est la lecture approfondie : None si jamais lancée, sinon {etat, cadres, relues} (cadres de code
        transcrits, réponses courtes relues, toutes classes) ; etat « en cours » sans tâche qui tourne = interrompue."""
        p = self.dir / "lecture_approfondie.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))

        def compte(nom):
            n = 0
            for c in self.dossiers_lus():
                f = c / nom
                if f.exists():
                    try:
                        n += len(json.loads(f.read_text(encoding="utf-8")))
                    except ValueError:
                        pass
            return n
        return dict(d, cadres=compte("code_lectures.json"), relues=compte("lectures_secondaires.json"))

    # ---------------------------------------------------------------- validation de la lecture
    def mesure_lecture(self):
        """Par langue : les lectures que la machine aurait acceptées d'office (sujet pas encore validé) et que
        l'enseignant a déjà décidées, comparées à sa décision (points identiques ou non). Rien n'est jamais
        validé sans cette mesure : {langue: {base, validee, n, justes, ecarts: [(classe, copie, champ, lu, verdict)],
        possible, pourquoi}}."""
        from .correction import Classe, Decisions
        from .ocr_run import NOUVEAU
        ex, err = self.controle()
        if err:
            return {}
        out = {}
        for langue in ex.langues:
            f = self.fichiers(langue)
            key = json.loads(f["key"].read_text(encoding="utf-8")) if f["key"].exists() else {}
            out[langue] = {"base": f["base"], "validee": key.get("lecture_validee") is True,
                           "mesure": key.get("lecture_validee_mesure"), "n": 0, "justes": 0, "ecarts": []}
        dec, exams = Decisions(self.stockage()["db"]), {}
        for d in self.dossiers_lus():
            meta = self.scans / f"{d.name}.json"
            langue = json.loads(meta.read_text(encoding="utf-8")).get("langue") if meta.exists() else None
            if langue not in out:
                continue
            c = Classe(d, exams, dec)
            for it in c.short_items(use_memory=False):
                if it.get("raison") != NOUVEAU or it.get("origine") != "enseignant":
                    continue
                prop = it["proposition"]
                machine = c.exam.points_verdict(c.exam.verdict(prop or "", it["champ"]), prop, it["champ"], it["max"])
                m = out[langue]
                m["n"] += 1
                if it["points"] is not None and abs(machine - it["points"]) < 1e-6:
                    m["justes"] += 1
                else:
                    m["ecarts"].append((c.name, it["copie"], it["champ"], prop, it["verdict"]))
        for m in out.values():
            if m["validee"]:
                m.update(possible=False, pourquoi="déjà validé")
            elif m["n"] < VALIDATION_MIN:
                m.update(possible=False, pourquoi=f"{m['n']} lecture(s) vérifiée(s) par vous, il en faut au moins "
                                                  f"{VALIDATION_MIN} : corriger d'abord des réponses courtes dans l'outil")
            elif m["ecarts"]:
                m.update(possible=False, pourquoi=f"{len(m['ecarts'])} lecture(s) que la machine aurait acceptées "
                                                  "avec une note différente de la vôtre : le sujet reste en revue")
            else:
                m.update(possible=True, pourquoi=None)
        return out

    def valider_lecture(self, langue: str):
        """Le corrigé de cette langue est déclaré « lecture validée », avec la mesure qui le justifie ; les lectures
        déjà faites sont à relancer (rapide : elles sont en cache) pour que les réponses sûres passent acceptées.
        Produire à nouveau le sujet efface la validation (nouveau corrigé, nouvelle mesure)."""
        import time
        m = self.mesure_lecture().get(langue)
        if not m:
            raise ValueError(f"langue inconnue : {langue}")
        if not m["possible"]:
            raise ValueError(f"validation refusée : {m['pourquoi']}")
        p = self.fichiers(langue)["key"]
        key = json.loads(p.read_text(encoding="utf-8"))
        key["lecture_validee"] = True
        key["lecture_validee_mesure"] = {"date": time.strftime("%Y-%m-%d %H:%M"), "verifiees": m["n"],
                                         "justes": m["justes"]}
        p.write_text(json.dumps(key, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return m

    # ---------------------------------------------------------------- réglages
    def reglages(self) -> dict:
        """Réglages généraux (page Réglages), sauf ceux que l'examen garde dans son reglages.json."""
        from .reglages import DEFAUTS, lire
        p = self.dir / "reglages.json"
        propres = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        return {**lire(), **{k: v for k, v in propres.items() if k in DEFAUTS}}

    def regler(self, **valeurs):
        r = self.reglages()
        from .reglages import DEFAUTS
        r.update({k: v for k, v in valeurs.items() if k in DEFAUTS})
        (self.dir / "reglages.json").write_text(json.dumps(r, indent=1), encoding="utf-8")

    @property
    def notes_xlsx(self) -> Path:
        return self.dir / "notes" / "notes.xlsx"

    def exporter_notes(self, log=print):
        """Classeur des notes finales (l'ancien est gardé, daté)."""
        from .excel import run
        dossiers = self.dossiers_lus()
        if not dossiers:
            raise SystemExit("aucune classe lue")
        return run(dossiers, self.notes_xlsx, db=self.stockage()["db"], log=log,
                   arrondi=self.reglages()["arrondi_demi_point"])

    def controle_noms(self):
        """Avant l'export : copies attribuées, sans élève, à risque (cf. verif_noms.risques), et si l'enseignant a
        vérifié CES risques-là (signature : une attribution changée redemande la vérification). None sans classe lue."""
        import hashlib

        from .identite import lire_attributions, lire_convoques, lire_liste
        from .verif_noms import risques
        dossiers = self.dossiers_lus()
        if not dossiers:
            return None
        lists = self.stockage()["lists_dir"]
        try:
            liste = lire_liste(lists_dir=lists)
        except (ValueError, OSError):
            liste = {}
        attributions, sans = [], 0
        for d in dossiers:
            att = lire_attributions(d.name, lists)
            ids = [c["copy_id"] for c in json.loads((d / "results.json").read_text(encoding="utf-8"))["copies"]]
            attributions += [(d.name, cid, e) for cid, e in sorted(att.items())]
            sans += sum(cid not in att for cid in ids)
        r = risques(attributions, liste, convoques={d.name: lire_convoques(d.name, lists) for d in dossiers}) if liste else {}
        a_risque = sorted(f"{cl}/{cid}={e}={'|'.join(r[(cl, cid)])}" for cl, cid, e in attributions if r.get((cl, cid)))
        signature = hashlib.sha256(chr(10).join(a_risque).encode()).hexdigest()[:16]
        p = self.dir / "noms_verifies.json"
        vu = json.loads(p.read_text(encoding="utf-8")).get("signature") if p.exists() else None
        return {"attribuees": len(attributions), "sans": sans, "risques": len(a_risque), "signature": signature,
                "verifie": bool(a_risque) and vu == signature}

    def noms_verifies(self):
        """L'enseignant a relu les copies à risque : l'export ne le redemande plus tant qu'elles ne changent pas."""
        c = self.controle_noms()
        if c:
            (self.dir / "noms_verifies.json").write_text(json.dumps({"signature": c["signature"]}), encoding="utf-8")

    def liste(self):
        """Liste des élèves utilisée : {nom, propre} (propre = celle de l'examen), {erreur} ou None."""
        from .identite import fichier_liste
        try:
            p = fichier_liste(self.stockage()["lists_dir"])
        except ValueError as e:
            return {"erreur": str(e)}
        if p is None:
            return None
        return {"nom": p.name, "propre": p.parent.resolve() == (self.dir / "listes").resolve()}

    def deposer_liste(self, contenu: bytes) -> int:
        """Liste des élèves de cet examen (.xlsx : colonnes NOM, Prénom, Classe) ; l'ancienne est gardée, datée."""
        import time
        from .identite import lire_liste
        if not contenu.startswith(b"PK"):
            raise ValueError("la liste doit être un classeur Excel (.xlsx)")
        d = self.dir / "listes"
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "~$nouvelle_liste.xlsx"      # « ~$ » : jamais pris pour la liste pendant la vérification
        tmp.write_bytes(contenu)
        try:
            groupes = lire_liste(tmp)
        except Exception as e:
            raise ValueError(f"liste illisible : {e}")
        finally:
            tmp.unlink(missing_ok=True)
        if not groupes:
            raise ValueError("aucun élève lu : colonnes attendues NOM, Prénom, Classe")
        for p in d.glob("*.xlsx"):
            p.rename(p.with_name(p.stem + f".avant-{time.strftime('%Y%m%d-%H%M%S')}.bak"))
        (d / "liste_eleves.xlsx").write_bytes(contenu)
        return sum(len(v) for v in groupes.values())


def outils():
    """Ce qui est installé sur ce PC pour les étapes lourdes (tout est facultatif)."""
    from importlib.util import find_spec
    from .lecteur_code import modeles_ollama
    return {"trocr": bool(find_spec("torch") and find_spec("transformers")), "ollama": modeles_ollama()}


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
