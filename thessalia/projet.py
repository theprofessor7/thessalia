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


IMPORT = "importe.json"   # examen dont le sujet vient d'ailleurs (générateur d'un collègue) : voir `importer`


class ExamenImporte:
    """Ce que l'application lit d'un examen importé (à la place de la source YAML) : identifiant, langues, titre,
    questions et points, d'après le gabarit de la première langue."""

    def __init__(self, info, gabarits):
        self.langues = list(info["langues"])
        self.id = info["langues"][self.langues[0]]["exam_id"]
        self.entete = {"titre": {l: info.get("titre", self.id) for l in self.langues}}
        g = json.loads((gabarits / info["langues"][self.langues[0]]["gabarit"]).read_text(encoding="utf-8"))
        self._questions = g["questions"]
        self.points = sum(q.get("points") or 0 for q in self._questions)

    def questions(self):
        return self._questions


def nom_valide(nom: str) -> bool:
    return bool(RE_NOM.match(nom or "")) and ".." not in nom


def nom_depuis_fichier(fichier: str) -> str:
    """Nom d'examen tiré du nom de la source : « Midterm bis écrit.yaml » -> « Midterm_bis_ecrit »."""
    import unicodedata
    base = unicodedata.normalize("NFKD", Path(fichier or "").stem).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("_.-")[:60]
    return base or "examen"


def _douteux_ancien(dossier):
    """Classe lue avant que results.json note l'alerte : « GABARIT DOUTEUX » en tête de review.csv."""
    import re
    p = dossier / "review.csv"
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        debut = f.read(2000)
    m = re.search(r"GABARIT DOUTEUX : score de reconnaissance médian ([0-9.]+)", debut)
    return float(m.group(1)) if m else None


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

    @property
    def importe(self):
        """Description d'un examen importé (importe.json), sinon None."""
        p = self.dir / IMPORT
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def controle(self):
        """(examen, None) si la source passe le contrôle strict, sinon (None, [erreurs]). Examen importé : ses
        fichiers fournis (PDF, gabarit, corrigé) tiennent lieu de source."""
        imp = self.importe
        if imp is not None:
            manque = [f"{l} : {n} absent" for l, d in imp["langues"].items()
                      for k, n in (("sujet", d["sujet"]), ) if not (self.produit / n).exists()]
            manque += [f"{l} : {d[k]} absent" for l, d in imp["langues"].items()
                       for k, dossier in (("gabarit", self.gabarits), ("key", self.corriges), ("vocab", self.corriges))
                       if not (dossier / d[k]).exists()]
            return (None, manque) if manque else (ExamenImporte(imp, self.gabarits), None)
        if self.source is None:
            return None, ["pas de fichier .yaml dans le dossier de l'examen"]
        try:
            return examen(self.source), None
        except ErreurSujet as e:
            return None, e.erreurs

    def images_inutilisees(self):
        """Images déposées avec la source mais jamais nommées dedans (ex. logo sans « logo: ») : ignorées à la production."""
        if self.importe is not None or self.source is None:
            return []
        texte = self.source.read_text(encoding="utf-8", errors="replace")
        return sorted(f.name for f in self.dir.iterdir()
                      if f.is_file() and f.suffix.lower() in SOURCES - {".yaml", ".yml"} and f.name not in texte)

    def produit_a_jour(self) -> bool:
        """Les PDF et corrigés produits sont-ils plus récents que la source (et ses images) ?"""
        if self.importe is not None:
            return True                  # sujet importé : ses PDF sont fournis, jamais reproduits
        if self.source is None or not self.corriges.is_dir():
            return False
        faits = [p.stat().st_mtime for p in self.corriges.glob("*.key.json")]
        # seulement la source et ses images (pas decisions.sqlite, modifié à chaque correction)
        sources = [p.stat().st_mtime for p in self.dir.iterdir()
                   if p.is_file() and p.suffix.lower() in SOURCES]
        return bool(faits) and min(faits) >= max(sources)

    def produire(self, log=print):
        from .sujet import produire_tout

        if self.importe is not None:
            raise SystemExit("Sujet importé : ses PDF, gabarit et corrigé sont fournis, rien à produire.")
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
        imp = self.importe
        if imp is not None:
            d = imp["langues"][langue]
            return {"base": d["exam_id"], "sujet": self.produit / d["sujet"], "corrige_pdf": self.produit / "-",
                    "gabarit": self.gabarits / d["gabarit"], "key": self.corriges / d["key"],
                    "vocab": self.corriges / d["vocab"]}
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
                             lue_avant=res.stat().st_mtime < scan.stat().st_mtime,
                             gabarit_douteux=r.get("gabarit_douteux") or _douteux_ancien(self.classes_dir / nom))
            out.append(ligne)
        return out

    def stockage(self):
        """Décisions, vérité d'apprentissage et attributions des copies de CET examen (pas de data/)."""
        return {"db": self.dir / "decisions.sqlite", "truth_dir": self.dir / "verite", "lists_dir": self.dir / "listes"}
        # (même rangement que correction.stockage_examen, qui s'applique à toute classe de l'examen)

    def dossiers_lus(self):
        return [self.classes_dir / c["classe"] for c in self.classes() if c["lue"]]

    APPRIS_MIN = 2      # une lecture tapée sur au moins 2 copies : erreur d'élève, pas une écriture isolée

    def vocab_appris(self, langue, log=print):
        """Vocabulaire de la langue, enrichi des lectures tapées par l'enseignant (« corriger la lecture ») dans
        les classes de cette langue : une erreur fréquente ({prix} pour {prix:.2f}) devient une mauvaise réponse
        plausible, que le lecteur propose ensuite d'emblée au lieu d'une lecture fantaisiste. Écrit à côté du
        vocabulaire d'origine (`<sujet>.vocab.appris.json`), qui n'est jamais modifié. Champs numériques exclus."""
        from types import SimpleNamespace

        from .correction import Decisions, lectures_tapees
        base = self.fichiers(langue)["vocab"]
        doc = json.loads(base.read_text(encoding="utf-8"))
        noms = []
        for c in self.classes():
            meta = self.scans / f"{c['classe']}.json"
            if c["lue"] and meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("langue") == langue:
                noms.append(c["classe"])
        dec = Decisions(self.stockage()["db"])
        classes = [SimpleNamespace(name=n, decisions=dec) for n in noms]
        ajouts = []
        for fid, spec in doc.get("fields", {}).items():
            if spec.get("kind") == "number" or "values" not in spec:
                continue
            for t, n in lectures_tapees(classes, fid).most_common():
                if n >= self.APPRIS_MIN and t not in spec["values"]:
                    spec["values"].append(t)
                    ajouts.append(f"{fid} « {t} » ({n})")
            if spec.get("kind") == "enum":
                spec["values"].sort()
        if not ajouts:
            return base
        out = base.with_name(base.name[:-len(".json")] + ".appris.json")
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"lectures apprises ajoutées au vocabulaire ({langue.upper()}) : " + ", ".join(ajouts))
        return out

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
            ocr(d, self.vocab_appris(info["langue"], log), model=modele, log=log)
        # noms écrits sur les copies : propositions pour « Identifier les copies »
        from .identite import run as noms
        log("=== noms des élèves")
        if getattr(log, "progression", None):
            log.progression(None)
        try:
            noms(dossiers, lists_dir=self.stockage()["lists_dir"])
        except SystemExit as e:
            log(f"noms non lus : {e}")

    def preparer(self, log=print, rapide=False, en_ligne=False):
        """Lecture approfondie (code transcrit et pré-coché, réponses courtes relues) avec les modèles Ollama
        présents ; ses messages (print) arrivent dans le journal de la tâche. Son début et sa fin sont notés : une
        lecture interrompue (pause, Thessalia fermé) se voit à la page de l'examen, qui propose de la reprendre.
        `rapide` : transcription du code et pré-cochage par les règles seulement (sans réparateur ni relecture des
        réponses courtes) ; quelques heures de moins sur un PC sans carte graphique. `en_ligne` : code seulement,
        transcrit par le service en ligne des Réglages (payant, quelques minutes)."""
        from .preparer import run
        dossiers = self.dossiers_lus()
        if not dossiers:
            raise SystemExit("aucune classe lue")
        self._noter_approfondie(etat="en cours", debut=time.strftime("%Y-%m-%d %H:%M"), rapide=rapide or en_ligne,
                                en_ligne=en_ligne)
        if en_ligne:
            log("Code seulement, transcrit par le service en ligne, puis pré-coché par les règles (les réponses "
                "courtes ne sont pas relues).")
        elif rapide:
            log("Code seulement : transcription du code et pré-cochage par les règles (sans réparateur ni relecture "
                "des réponses courtes).")
        run(dossiers, sans_courtes=rapide, sans_reparateur=rapide, en_ligne=en_ligne)
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
        """Réglages généraux (page Réglages) : les mêmes pour tous les examens de ce PC."""
        from .reglages import lire
        return lire()

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
        from .correction import group_of
        attributions, sans, par_groupe = [], 0, {}
        for d in dossiers:
            att = lire_attributions(d.name, lists)
            ids = [c["copy_id"] for c in json.loads((d / "results.json").read_text(encoding="utf-8"))["copies"]]
            attributions += [(d.name, cid, e) for cid, e in sorted(att.items())]
            n = sum(cid not in att for cid in ids)
            sans += n
            if n:
                par_groupe[group_of(d.name)] = par_groupe.get(group_of(d.name), 0) + n
        r = risques(attributions, liste, convoques={d.name: lire_convoques(d.name, lists) for d in dossiers}) if liste else {}
        a_risque = sorted(f"{cl}/{cid}={e}={'|'.join(r[(cl, cid)])}" for cl, cid, e in attributions if r.get((cl, cid)))
        signature = hashlib.sha256(chr(10).join(a_risque).encode()).hexdigest()[:16]
        p = self.dir / "noms_verifies.json"
        vu = json.loads(p.read_text(encoding="utf-8")).get("signature") if p.exists() else None
        return {"attribuees": len(attributions), "sans": sans, "sans_par_groupe": par_groupe,
                "risques": len(a_risque), "signature": signature,
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
    return ([Projet(d) for d in sorted(racine.iterdir()) if d.is_dir() and not d.name.startswith(".")]
            if racine.is_dir() else [])


CORBEILLE = ".corbeille"


def mettre_a_la_corbeille(nom: str, racine=RACINE) -> Path:
    """« Supprimer » un examen : il part dans examens/.corbeille/<nom>-<date>, avec tout son contenu (copies lues,
    décisions, notes), et se restaure d'un clic. Rien n'est effacé du disque par l'application."""
    import time
    d = Path(racine) / nom
    if not nom_valide(nom) or not d.is_dir():
        raise ValueError(f"examen introuvable : {nom}")
    dest = Path(racine) / CORBEILLE / f"{nom}-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    d.rename(dest)
    return dest


def corbeille(racine=RACINE):
    """Examens supprimés, du plus récent au plus ancien : [{dossier, nom, date}]."""
    c = Path(racine) / CORBEILLE
    out = []
    for d in sorted(c.iterdir(), reverse=True) if c.is_dir() else []:
        nom, quand = d.name[:-16], d.name[-15:]          # <nom>-AAAAMMJJ-HHMMSS
        out.append({"dossier": d.name, "nom": nom,
                    "date": f"{quand[6:8]}/{quand[4:6]}/{quand[:4]} {quand[9:11]}h{quand[11:13]}"})
    return out


def restaurer(dossier: str, racine=RACINE) -> Projet:
    src = Path(racine) / CORBEILLE / dossier
    if not src.is_dir() or "/" in dossier or "\\" in dossier or ".." in dossier:
        raise ValueError("examen introuvable dans la corbeille")
    nom = dossier[:-16]
    dest = Path(racine) / nom
    if dest.exists():
        raise ValueError(f"un examen « {nom} » existe déjà : renommez-le ou supprimez-le d'abord")
    src.rename(dest)
    return Projet(dest)


def importer(nom: str, titre: str, langues: dict, racine=RACINE, autres=()) -> Projet:
    """Examen dont le sujet a été produit ailleurs (générateur d'un collègue) et déjà imprimé.

    langues : {langue: {"pdf": PDF imprimé, "gabarit": gabarit Thessalia lu dans CE PDF (`thessalia template`),
    "key": corrigé .key.json, "vocab": .vocab.json}} ; autres : fichiers du corrigé en plus (barème du code
    .bareme.json, tests .tests.py). Refusé si un gabarit n'a pas été construit sur le PDF donné (empreinte
    SHA-256) : un gabarit d'une autre version lirait les cases au mauvais endroit, sans erreur visible."""
    import hashlib
    import shutil
    if not nom_valide(nom):
        raise ValueError("nom de l'examen : lettres, chiffres, _ - . (ex. midterm_2026)")
    d = Path(racine) / nom
    if d.exists():
        raise ValueError(f"l'examen « {nom} » existe déjà")
    desc = {"titre": titre, "langues": {}}
    for langue, f in langues.items():
        g = json.loads(Path(f["gabarit"]).read_text(encoding="utf-8"))
        empreinte = hashlib.sha256(Path(f["pdf"]).read_bytes()).hexdigest()
        if g.get("source_sha256") and g["source_sha256"] != empreinte:
            raise ValueError(f"{langue} : le gabarit {Path(f['gabarit']).name} n'a pas été construit sur "
                             f"{Path(f['pdf']).name} (autre version du PDF ?)")
        for k in ("key", "vocab"):
            eid = json.loads(Path(f[k]).read_text(encoding="utf-8")).get("exam_id")
            if eid != g["exam_id"]:
                raise ValueError(f"{langue} : {Path(f[k]).name} est pour « {eid} », pas « {g['exam_id']} »")
        desc["langues"][langue] = {"exam_id": g["exam_id"], "sujet": f"sujet_{g['exam_id']}.pdf",
                                   "gabarit": f"gabarit_{g['exam_id']}.json", "key": f"{g['exam_id']}.key.json",
                                   "vocab": f"{g['exam_id']}.vocab.json"}
    p = Projet(d)
    for dossier in (p.produit, p.gabarits, p.corriges):
        dossier.mkdir(parents=True, exist_ok=True)
    for langue, f in langues.items():
        n = desc["langues"][langue]
        shutil.copy2(f["pdf"], p.produit / n["sujet"])
        shutil.copy2(f["gabarit"], p.gabarits / n["gabarit"])
        shutil.copy2(f["key"], p.corriges / n["key"])
        shutil.copy2(f["vocab"], p.corriges / n["vocab"])
    for a in autres:
        shutil.copy2(a, p.corriges / Path(a).name)
    (d / IMPORT).write_text(json.dumps(desc, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def importer_fichiers(nom: str, titre: str, langues: dict, racine=RACINE, autres=()):
    """Import en une fois (accueil de l'application ou `thessalia importer`) : pour chaque langue, le PDF imprimé,
    le corrigé `.key.json` et le vocabulaire `.vocab.json` ; facultatifs : le fichier de zones du générateur
    (contrôlé contre le PDF, refusé s'il ne colle pas) et un gabarit déjà construit (sinon lu dans le PDF).

    Refusé (ValueError, avec la raison) si le corrigé ou le vocabulaire nomment des champs absents du sujet.
    Renvoie (Projet, résumé lisible : questions, points, champs sans corrigé) : les points sont ceux lus dans le
    PDF, à vérifier par l'enseignant."""
    import tempfile

    from .template_builder import build_template
    from .verif_zones import controler
    if not langues:
        raise ValueError("au moins une langue : PDF du sujet, corrigé .key.json, vocabulaire .vocab.json")
    lignes = []
    with tempfile.TemporaryDirectory() as tmp:
        prets = {}
        for langue, f in langues.items():
            for k, nom_f in (("pdf", "PDF du sujet"), ("key", "corrigé .key.json"), ("vocab", "vocabulaire .vocab.json")):
                if not f.get(k) or not Path(f[k]).is_file():
                    raise ValueError(f"{langue} : {nom_f} manquant")
            try:
                key = json.loads(Path(f["key"]).read_text(encoding="utf-8"))
                vocab = json.loads(Path(f["vocab"]).read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                raise ValueError(f"{langue} : corrigé ou vocabulaire illisible ({e})")
            if not key.get("exam_id"):
                raise ValueError(f"{langue} : le corrigé n'a pas d'« exam_id »")
            if f.get("zones"):
                rapport, ok = controler(f["pdf"], f["zones"])
                if not ok:
                    lr = [l for l in rapport.splitlines() if l.strip()]
                    i = next((j for j, l in enumerate(lr) if "Résultat" in l), 0)
                    raise ValueError(f"{langue} : les zones du générateur ne collent pas au PDF "
                                     f"(rapport complet : thessalia verif-zones)\n" + "\n".join(lr[i:i + 10]))
            if f.get("gabarit"):
                g = json.loads(Path(f["gabarit"]).read_text(encoding="utf-8"))
            else:
                try:
                    g = build_template(str(f["pdf"]), exam_id=key["exam_id"])
                except Exception as e:     # PDF sans les repères du format Thessalia, scanné, protégé…
                    raise ValueError(f"{langue} : PDF du sujet illisible comme sujet Thessalia ({e})")
            champs = {c["id"] for p in g["pages"] for c in p["fields"]}
            nommes = (set(key.get("answers", {})) | set(key.get("short_answers", {}))
                      | set(vocab.get("fields", {})))
            absents = sorted(nommes - champs)
            if absents:
                raise ValueError(f"{langue} : le corrigé nomme des champs absents du sujet : {', '.join(absents[:10])}"
                                 " (corrigé d'une autre version du sujet ?)")
            gp = Path(tmp) / f"{langue}_gabarit.json"
            gp.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
            prets[langue] = {"pdf": f["pdf"], "gabarit": gp, "key": f["key"], "vocab": f["vocab"]}
            courts = sorted(c["id"] for p in g["pages"] for c in p["fields"] if c["type"] == "short_text")
            sans = [c for c in courts if c not in key.get("short_answers", {})]
            pts = sum(q.get("points") or 0 for q in g["questions"])
            lignes.append(f"{langue.upper()} : {g['page_count']} pages, {len(g['questions'])} questions, "
                          f"{f'{pts:g}'.replace('.', ',')} points (lus dans le PDF : à vérifier), {len(champs)} zones"
                          + (f" ; sans corrigé : {', '.join(sans)}" if sans else ""))
            lignes.append("   " + " · ".join(f"q{q['num']} " + f"{q.get('points') or 0:g}".replace(".", ",")
                                              for q in g["questions"]))
        p = importer(nom, titre, prets, racine=racine, autres=autres)
    return p, "\n".join(lignes)


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
