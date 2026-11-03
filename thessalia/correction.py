"""Correction : état de chaque réponse d'une classe (verdict, origine, décidé ou non) et notes.

Moteur de la commande `serve` (sans Flask : testable seul). On juge des VERDICTS (juste / forme / faux /
vide), pas des transcriptions : l'enseignant décide si c'est juste, il n'a pas à recopier ce qui est écrit.

Origine du verdict d'une réponse courte, par ordre de priorité :
  enseignant    décision prise dans l'outil (base `data/correction.sqlite`)
  vérité        vérité validée `data/truth/<classe>.short_truth.json` (pages de validation antérieures)
  acceptée      lecture acceptée par `ocr` (règles mesurées) : verdict de la lecture
  deux lecteurs lecture en revue, mais un second lecteur indépendant et sûr donne le même verdict
                (fichier optionnel `<classe>/lectures_secondaires.json`, rempli par n'importe quel lecteur)
  mémoire       lecture en revue que l'enseignant a jugée au moins MEMORY_MIN fois dans les AUTRES classes
                (même sujet, même champ, même lecture), avec le même verdict au moins MEMORY_SHARE des fois :
                chaque classe corrigée aide la suivante. Seuil de 95 % choisi par l'enseignant le 19 octobre,
                en connaissance de cause : mesure classe par classe sur A à D, 580 réponses décidées sur 1 514
                pour 6 verdicts différents des siens (unanimité : 438 pour 2) ; « gagner du temps » contre
                environ 1 réponse mal notée sur 100 décidées par la mémoire (surtout favorisée à tort).
  proposé       sinon : NON décidé (l'enseignant confirme ou change). Verdict pré-sélectionné : son verdict le
                plus fréquent pour cette lecture dans les autres classes (dès 3 fois), sinon celui de la lecture.
Nombre décimal en revue : si `<classe>/separateur.json` existe (`separateur --indices`), le séparateur de la
proposition suit le détecteur point/virgule (virgule si P(virgule) >= 0,5 ; mesuré le 20 octobre : 27 erreurs
de séparateur sur 240 contre 46). Ce n'est qu'une proposition : un tel décimal n'est jamais décidé par la
mémoire, l'enseignant le juge toujours.
Une zone détectée vide reste proposée (« vide ? ») : une écriture très pâle peut être prise pour du vide
(mesuré le 19 octobre : 4 réponses justes sur 42 vides détectés, supC 1 et 2).

Règle de notation : `notes.judge` (règle globale de l'enseignant du 18 octobre). QCM : `grade.grade_copy`.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from .common import load_json
from .grade import grade_copy
from .vocab import other_separator
from .notes import ATTENTE, FAUX, FORME, ILLISIBLE, JUSTE, PARTIEL, RATE, VIDE, judge, points_partiels

TRUTH_DIR = Path("data/truth")
LISTS_DIR = Path("data/listes")
DB_PATH = Path("data/correction.sqlite")
SECOND = "lectures_secondaires.json"


def mise_en_forme(attendu, *lectures):
    """Vrai si un espace (ou « _ ») compte dans la réponse : sortie d'un programme (q7). Le verdict se juge alors sur
    la vignette, jamais sur deux lectures d'accord (mesuré sur supD_2 : 11 erreurs sur 135, toutes de ce type)."""
    return any(x and re.search(r"[\s_]", str(x).strip()) for x in (attendu, *lectures))


SEPARATEUR = "separateur.json"
ESPACE_SERRE = 0.5    # écart (en hauteurs de lettre) sous lequel « X Y » est proposé « XY » (cf. _espace)
ALTERNATIVES = 3      # autres lectures proposées en un clic (touches 6, 7, 8)
VERDICTS = (JUSTE, FORME, FAUX, VIDE, ILLISIBLE, PARTIEL)
MEMORY_MIN = 10       # jugements des autres classes nécessaires pour décider seul
MEMORY_SHARE = 0.95   # part minimale du verdict majoritaire (choix de l'enseignant, 19 octobre)
SUGGEST_MIN = 3       # jugements nécessaires pour pré-sélectionner son verdict le plus fréquent


class Memory:
    """Verdicts de l'enseignant par (champ, lecture), classe par classe. Une classe ne consulte que les
    autres : la mesure du 19 octobre a été faite ainsi (une classe ne se renforce pas elle-même)."""

    def __init__(self, minimum=MEMORY_MIN, share=MEMORY_SHARE):
        self.minimum, self.share, self.table, self.dirty = minimum, share, {}, True

    def rebuild(self, classes):
        from collections import Counter
        table = {}
        for c in classes:
            for it in c.short_items(use_memory=False):
                if (it["lecture"] != "review" or it["origine"] not in ("vérité", "enseignant") or not it["proposition"]
                        or it["verdict"] == ILLISIBLE):  # « illisible » tient à l'image, pas à la lecture
                    continue
                # par sujet (FR et EN diffèrent), sauf les champs de même corrigé d'une traduction exacte
                k = (c.memory_id(it["champ"]), it["champ"], c.exam.clean(it["proposition"], it["champ"]))
                table.setdefault(k, {}).setdefault(c.name, Counter())[it["verdict"]] += 1
        self.table, self.dirty = table, False

    def history(self, exam_id, classe, fid, lecture):
        """Verdicts de l'enseignant pour cette lecture dans les autres classes : (verdict majoritaire, nombre, total)."""
        from collections import Counter
        tot = Counter()
        for name, cnt in (self.table.get((exam_id, fid, lecture)) or {}).items():
            if name != classe:
                tot.update(cnt)
        if not tot:
            return None
        v, n = tot.most_common(1)[0]
        return v, n, sum(tot.values())

    def lookup(self, exam_id, classe, fid, lecture):
        """(verdict, nombre, total) si la mémoire des autres classes est assez fournie et assez nette, sinon None."""
        h = self.history(exam_id, classe, fid, lecture)
        return h if h and h[2] >= self.minimum and h[1] / h[2] >= self.share else None


def group_of(name: str) -> str:
    """supA_3 -> A, supc_1 -> C, supNA_2 -> NA, sup_nb_4 -> NB, supD -> D (regroupement voulu par l'enseignant)."""
    m = re.match(r"sup_?([a-z]+?)(?:_|\d|$)", name, re.I)
    if not m:
        return name
    g = m.group(1).upper()
    return g if len(g) <= 2 else g[0]


# ---------------------------------------------------------------- décisions de l'enseignant (SQLite)

class Decisions:
    """Décisions prises dans l'outil : une ligne par réponse (classe, clé cNN_qX.Y)."""

    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS decision (
                classe TEXT, cle TEXT, verdict TEXT, texte TEXT, options TEXT, maj REAL,
                PRIMARY KEY (classe, cle))""")

    def _db(self):
        return sqlite3.connect(self.path, timeout=10)

    def of(self, classe: str) -> dict:
        with self._db() as db:
            rows = db.execute("SELECT cle, verdict, texte, options FROM decision WHERE classe=?", (classe,))
            return {k: {"verdict": v, "texte": t, "options": None if o is None else json.loads(o)}
                    for k, v, t, o in rows}

    def set(self, classe, cle, verdict=None, texte=None, options=None, clear_verdict=False):
        """Enregistre ce qui est fourni et GARDE le reste : la note (verdict) et la lecture (texte vérifié)
        sont deux décisions distinctes ; choisir un verdict n'efface pas la lecture tapée, et inversement."""
        with self._db() as db:
            old = db.execute("SELECT verdict, texte, options FROM decision WHERE classe=? AND cle=?",
                             (classe, cle)).fetchone() or (None, None, None)
            db.execute("INSERT OR REPLACE INTO decision VALUES (?,?,?,?,?,?)",
                       (classe, cle, verdict if verdict is not None else (None if clear_verdict else old[0]),
                        texte if texte is not None else old[1],
                        json.dumps(options) if options is not None else old[2], time.time()))

    def clear(self, classe, cle):
        with self._db() as db:
            db.execute("DELETE FROM decision WHERE classe=? AND cle=?", (classe, cle))


# ---------------------------------------------------------------- examen (gabarit, corrigé, vocabulaire)

@dataclass
class Exam:
    template: dict
    key: dict
    vocab: dict
    points: dict = field(default_factory=dict)   # champ court -> points
    prompts: dict = field(default_factory=dict)
    fields: dict = field(default_factory=dict)   # id -> champ du gabarit
    bareme: dict = field(default_factory=dict)   # code : {champ: {points, criteres}}, + "malus"

    @classmethod
    def load(cls, exam_id, keys_dir="keys", templates_dir="templates"):
        def find(folder, suffix):
            for p in sorted(Path(folder).glob(f"*{suffix}")):
                try:
                    if load_json(p).get("exam_id") == exam_id:
                        return load_json(p)
                except Exception:
                    continue
            raise SystemExit(f"Aucun fichier *{suffix} pour l'examen « {exam_id} » dans {folder}/")
        ex = cls(find(templates_dir, ".json"), find(keys_dir, ".key.json"), find(keys_dir, ".vocab.json"))
        by_q = {q["num"]: q for q in ex.template["questions"]}
        shorts = [f for p in ex.template["pages"] for f in p["fields"] if f["type"] == "short_text"]
        count = {}
        for f in shorts:
            count[f["question"]] = count.get(f["question"], 0) + 1
        expected = ex.key.get("short_answers", {})
        for f in shorts:
            if f["id"] in expected:
                ex.points[f["id"]] = (by_q.get(f["question"], {}).get("points") or 0) / count[f["question"]]
                ex.prompts[f["id"]] = f.get("prompt") or ""
        ex.points.update(points_champs(ex.key, ex.template))
        ex.fields = {f["id"]: f for p in ex.template["pages"] for f in p["fields"]}
        # barème du code : celui du sujet, sinon celui du sujet dont il est la traduction exacte
        for eid in (exam_id, ex.key.get("traduction_de")):
            b = _bareme(eid, keys_dir) if eid else None
            if b:
                _verifier_bareme(b, ex.template)
                ex.bareme = b
                break
        return ex

    def kind(self, fid):
        return self.vocab.get("fields", {}).get(fid, {}).get("kind", "text")

    def clean(self, answer, fid):
        from .notes import clean
        return clean(str(answer), self.kind(fid))

    def verdict(self, answer, fid):
        if answer is None:
            return None
        k = self.key.get("short_answers", {})
        return judge(answer, k[fid], self.kind(fid), self.key.get("short_accept", {}).get(fid, ()),
                     self.key.get("short_reject", {}).get(fid, ()), self.key.get("short_forme", {}).get(fid, ()),
                     self.key.get("short_partiel", {}).get(fid))

    def points_verdict(self, verdict, answer, fid, pts):
        """Points d'un verdict ; « partiel » : ceux que le corrigé prévoit pour cette réponse précise."""
        if verdict == PARTIEL:
            return points_partiels(answer, self.kind(fid), self.key.get("short_partiel", {}).get(fid))
        return pts * RATE.get(verdict, 0.0)


def _bareme(exam_id, keys_dir="keys"):
    for p in sorted(Path(keys_dir).glob("*.bareme.json")):
        b = load_json(p)
        if b.get("exam_id") == exam_id:
            return b
    return None


def points_champs(key, template):
    """Points par blanc fixés par le corrigé (`points_champs`, ex. q5 = 0,50 liste + 0,25 len) au lieu du partage
    égal ; refusé si la somme ne fait pas les points de la question (sinon notes fausses en silence)."""
    pc = key.get("points_champs", {})
    if not pc:
        return {}
    by_q = {q["num"]: q.get("points") or 0 for q in template["questions"]}
    champs = {f["id"]: f for p in template["pages"] for f in p["fields"] if f["type"] == "short_text"}
    for fid in pc:
        if fid not in champs:
            raise SystemExit(f"Corrigé, points_champs : champ inconnu du gabarit « {fid} ».")
    for q in {champs[f]["question"] for f in pc}:
        ids = [f for f, c in champs.items() if c["question"] == q]
        if any(f not in pc for f in ids) or abs(sum(pc[f] for f in ids) - by_q.get(q, 0)) > 1e-9:
            raise SystemExit(f"Corrigé, points_champs : q{q} doit donner des points à {', '.join(ids)} "
                             f"pour un total de {by_q.get(q)} pt.")
    return dict(pc)


def _verifier_bareme(b, template):
    """Un barème faux donnerait des notes fausses en silence : critères = points du champ, champs d'une
    question = points de la question (gabarit)."""
    by_q = {q["num"]: q.get("points") or 0 for q in template["questions"]}
    champs = {f["id"]: f for p in template["pages"] for f in p["fields"]}
    par_q = {}
    for fid, c in b.get("champs", {}).items():
        if fid not in champs:
            raise SystemExit(f"Barème : champ inconnu du gabarit « {fid} ».")
        tot = sum(x["points"] for x in c["criteres"])
        if abs(tot - c["points"]) > 1e-9:
            raise SystemExit(f"Barème {fid} : critères {tot} ≠ points du champ {c['points']}.")
        q = champs[fid]["question"]
        par_q[q] = par_q.get(q, 0) + c["points"]
    for q, tot in par_q.items():
        if abs(tot - by_q.get(q, 0)) > 1e-9:
            raise SystemExit(f"Barème q{q} : {tot} pt ≠ {by_q.get(q)} pt dans le gabarit.")


CODE_ENCRE = "code_encre.json"
CODE_TESTS = "code_tests.json"   # cf. code_tests.py
CODE_VIDE = 2.0       # ‰ d'écriture sous lequel un cadre est proposé vide (mesuré le 22 octobre : vides < 1,2 ;
                      # réponse au crayon pâle de q18 : 40 ; q16 : saut de 1,1 à 3,5)


# ---------------------------------------------------------------- classe

def _transcription_enseignant(d):
    """Transcription d'un cadre de code corrigée par l'enseignant (touche T), ou None. Les décisions validées en
    lot pendant la correction du Booster portent un marqueur « auto: … » dans ce champ : ce n'est pas du code."""
    t = (d or {}).get("texte")
    return None if t is None or t.startswith("auto:") else t


def _num(cid):
    return int(cid.split("_")[-1])


class Classe:
    def __init__(self, results_dir, exams: dict, decisions: Decisions, truth_dir=TRUTH_DIR, lists_dir=LISTS_DIR,
                 memory: Memory | None = None):
        self.memory = memory
        self.dir = Path(results_dir)
        self.name = self.dir.name
        self.group = group_of(self.name)
        res = load_json(self.dir / "results.json")
        self.exam_id = res["exam_id"]
        if self.exam_id not in exams:
            exams[self.exam_id] = Exam.load(self.exam_id)
        self.exam: Exam = exams[self.exam_id]
        # traduction exacte d'un autre sujet (`traduction_de` dans le corrigé, décision de l'enseignant le
        # 21 octobre pour le sujet EN) : la mémoire des verdicts est commune pour les champs de même corrigé
        src = self.exam.key.get("traduction_de")
        self.partage = set()
        if src:
            if src not in exams:
                exams[src] = Exam.load(src)
            autre = exams[src].key.get("short_answers", {})
            self.partage = {f for f, v in self.exam.key.get("short_answers", {}).items() if autre.get(f) == v}
            self.source = src
        self.copy_ids = [c["copy_id"] for c in res["copies"]]
        self.decisions = decisions
        self.truth_dir, self.lists_dir = Path(truth_dir), Path(lists_dir)
        self._docs = {}

    def memory_id(self, fid):
        """Sujet sous lequel la mémoire des verdicts range ce champ."""
        return self.source if fid in self.partage else self.exam_id

    # sources --------------------------------------------------------------
    def doc(self, cid):
        if cid not in self._docs:
            p = self.dir / cid / "result.json"
            self._docs[cid] = load_json(p) if p.exists() else {"fields": {}, "answers": {}, "pages": {}}
        return self._docs[cid]

    def _json(self, path):
        return load_json(path) if Path(path).exists() else {}

    def students(self):
        p = self.lists_dir / f"{self.name}.csv"
        if not p.exists():
            return {}
        import csv
        with open(p, encoding="utf-8-sig") as fh:
            return {r["copie"]: r["etudiant"] for r in csv.DictReader(fh, delimiter=";")}

    # état des réponses courtes ----------------------------------------------
    def short_items(self, use_memory=True):
        truth = self._json(self.truth_dir / f"{self.name}.short_truth.json")
        second = self._json(self.dir / SECOND)
        sep = self._json(self.dir / SEPARATEUR)
        dec = self.decisions.of(self.name)
        items = []
        for cid in self.copy_ids:
            n, doc = _num(cid), self.doc(cid)
            for fid, pts in self.exam.points.items():
                key = f"c{n:02d}_{fid}"
                info = doc.get("fields", {}).get(fid, {})
                o = info.get("ocr") or {}
                st = o.get("status")
                prop = "" if st == "blank" else o.get("value")
                it = {"classe": self.name, "copie": cid, "num": n, "cle": key, "champ": fid, "max": pts,
                      "img": (info.get("crop") or "").replace("\\", "/"), "box": info.get("box_px"),
                      "proposition": prop, "lecture": st or "absente", "raison": o.get("reason"),
                      "texte": None, "attendu": self.exam.key.get("short_answers", {}).get(fid)}
                d, t, s2 = dec.get(key), truth.get(key), second.get(key)
                if d and (d.get("verdict") or d.get("texte") is not None):
                    # texte tapé par l'enseignant : son verdict se calcule ; sinon son verdict cliqué
                    v = d["verdict"] or self.exam.verdict(d["texte"], fid)
                    it.update(verdict=v, origine="enseignant", decide=True, texte=d.get("texte"))
                elif t is not None and not t.endswith("?"):
                    it.update(verdict=self.exam.verdict(t, fid), origine="vérité", decide=True, texte=t)
                elif not info.get("crop"):
                    it.update(verdict=None, origine="page absente", decide=False)
                elif st == "ok":
                    it.update(verdict=self.exam.verdict(prop, fid), origine="acceptée", decide=True)
                elif st == "blank":
                    it.update(verdict=VIDE, origine="vide ?", decide=False)
                else:
                    indice = self._separateur(it, sep.get(key)) or self._espace(it, info, fid)
                    prop = it["proposition"]
                    v = self.exam.verdict(prop or "", fid)
                    agree = (s2 is not None and s2.get("sur") and prop is not None
                             and not mise_en_forme(it["attendu"], prop, s2.get("lecture"))
                             and self.exam.verdict(s2.get("lecture", ""), fid) == v)
                    hist = (self.memory.history(self.memory_id(fid), self.name, fid, self.exam.clean(prop, fid))
                            if use_memory and self.memory and prop else None)
                    if hist:
                        it["historique"] = {"verdict": hist[0], "n": hist[1], "total": hist[2]}
                    if agree:
                        it.update(verdict=v, origine="deux lecteurs", decide=True)
                    elif (hist and not indice and hist[2] >= self.memory.minimum
                          and hist[1] / hist[2] >= self.memory.share):
                        it.update(verdict=hist[0], origine="mémoire", decide=True)
                    elif hist and hist[2] >= SUGGEST_MIN:
                        it.update(verdict=hist[0], origine="proposé", decide=False)  # son verdict le plus fréquent
                    else:
                        it.update(verdict=v, origine="proposé", decide=False)
                    it["second"] = None if s2 is None else s2.get("lecture")
                it["alternatives"] = self._alternatives(it, o, fid) if st and st != "blank" else []
                lu = it["texte"] if it["texte"] is not None else it["proposition"]
                it["points"] = None if it["verdict"] is None else self.exam.points_verdict(it["verdict"], lu, fid, pts)
                items.append(it)
        return items

    def _alternatives(self, it, o, fid, n=ALTERNATIVES):
        """Autres lectures de la machine, de la plus probable à la moins probable, distinctes de la proposition
        (après nettoyage) : un clic les prend comme lecture, sans rien taper. Jamais pré-sélectionnées.
        Décimal : l'autre séparateur d'abord. Mesuré le 20 octobre sur 279 lectures corrigées à la main :
        la bonne était la 2e lecture 110 fois, la 3e ou 4e 72 fois."""
        prop = it["proposition"]
        cands = [it.get("lecture_machine")] + ([other_separator(str(prop))] if prop else [])
        cands += list(o.get("suggestions") or []) + [c[0] for c in o.get("candidates") or []]
        seen = {self.exam.clean(str(prop), fid)} if prop is not None else set()
        out = []
        for c in cands:
            if c is None or not str(c).strip():
                continue
            k = self.exam.clean(str(c), fid)
            if k in seen:
                continue
            seen.add(k)
            out.append(str(c).strip())
            if len(out) == n:
                break
        return out

    def _espace(self, it, info, fid):
        """Lecture qui ne diffère du corrigé que par des espaces (`X Y` pour `XY`, q7.3) : le moteur met un
        espace presque toujours. On mesure le plus grand blanc entre lettres (en hauteurs d'écriture) et on
        propose le corrigé si l'écart est serré. Indice seulement, jamais décidé par la mémoire.
        Mesuré le 20 octobre sur 84 verdicts de l'enseignant (q7.3, FR) : écart < 0,5 : 18 XY / 9 faux ;
        >= 0,5 : 7 XY / 50 faux ; >= 1,1 : 1 XY (tache) / 35 faux."""
        prop, att = it["proposition"], it.get("attendu")
        if (not prop or not att or " " in att or " " not in str(prop) or str(prop).replace(" ", "") != att
                or not info.get("clean")):
            return False
        import cv2
        import numpy as np
        img = cv2.imread(str(self.dir / info["clean"].replace("\\", "/")), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False
        ink = img < 160
        ys, xs = np.nonzero(ink)
        if len(xs) < 20:
            return False
        col = ink[:, xs.min():xs.max() + 1].any(0)
        runs, r = [0], 0
        for v in col:
            if not v:
                r += 1
            else:
                runs.append(r)
                r = 0
        e = max(runs) / (ys.max() - ys.min() + 1)
        it["ecart"] = round(float(e), 2)
        if e < ESPACE_SERRE:
            it["lecture_machine"] = prop
            it["proposition"] = att
        txt = f"{e:.2f}".replace(".", ",")
        it["raison"] = (f"espace mesuré {txt} × hauteur : « {it['proposition']} » proposé "
                        f"(serré si < {str(ESPACE_SERRE).replace('.', ',')}), à vérifier")
        return True

    @staticmethod
    def _separateur(it, s):
        """Séparateur de la proposition d'un décimal d'après le détecteur (indice, jamais décision).
        Retourne True si l'indice s'applique (entrée à jour pour cette lecture)."""
        prop = it["proposition"]
        if not s or s.get("p_virgule") is None or not prop or s.get("lecture") != prop or not other_separator(prop):
            return False
        p = float(s["p_virgule"])
        want = "," if p >= 0.5 else "."
        if want not in prop:
            it["proposition"] = other_separator(prop)
            it["lecture_machine"] = prop
        it["p_virgule"] = p
        sens = "virgule proposée" if want == "," else "point proposé"
        it["raison"] = (f"nombre décimal : {sens} par le détecteur de séparateur "
                        f"(P(virgule) = {p:.2f}), à vérifier".replace(f"{p:.2f}", f"{p:.2f}".replace(".", ",")))
        return True

    # QCM en revue ----------------------------------------------------------------
    def qcm_items(self):
        truth = self._json(self.truth_dir / f"{self.name}.qcm_truth.json")
        dec = self.decisions.of(self.name)
        items = []
        for cid in self.copy_ids:
            n, doc = _num(cid), self.doc(cid)
            reasons = {r["item"]: r for r in doc.get("review", [])}
            answers = doc.get("answers", {})
            # QCM d'une page absente du scan (ou illisible) : sans réponse lue. Il est à décider sur le papier,
            # sinon `grade_copy` le compte 0 en silence et la note passe « complète » (supNA_2 copie 12, q9).
            absents = {} if not doc.get("pages") else {
                fid: {"type": f["type"], "status": "review", "mode": f.get("mode", "multi"), "selected": [],
                      "absent": True, "options": {o["id"]: {"label": o.get("label", o["id"]), "state": "absent"}
                                                  for o in f["options"]}}
                for fid, f in self.exam.fields.items()
                if f["type"] in ("mcq", "truefalse") and fid not in answers}
            for fid, ans in list(answers.items()) + list(absents.items()):
                if ans.get("type") not in ("mcq", "truefalse") or ans.get("status") != "review":
                    continue
                key = f"c{n:02d}_{fid}"
                d, t = dec.get(key), truth.get(key)
                it = {"classe": self.name, "copie": cid, "num": n, "cle": key, "champ": fid, "qcm": True, "verdict": None,
                      "mode": ans.get("mode", "multi"), "raison": reasons.get(fid, {}).get("reason"),
                      "img": f"{cid}/crops/qcm_{fid}.jpg" if (self.dir / cid / "crops" / f"qcm_{fid}.jpg").exists() else "",
                      "overlay": (reasons.get(fid, {}).get("overlay") or "").replace("\\", "/"),
                      "options": [{"id": k, "label": o.get("label", k), "state": o["state"]}
                                  for k, o in ans["options"].items()],
                      "proposition": sorted(ans.get("selected", [])),
                      "attendu": sorted(self.exam.key.get("answers", {}).get(fid, []))}
                if d and d.get("verdict") == ILLISIBLE:
                    # copie papier inutilisable (page absente, cases illisibles) : 0 point, pas de cases cochées
                    it.update(choix=[], verdict=ILLISIBLE, origine="enseignant", decide=True)
                elif d and d.get("options") is not None:
                    it.update(choix=d["options"], origine="enseignant", decide=True)
                elif t is not None and not t.endswith("?"):
                    it.update(choix=[x for x in t.split(",") if x], origine="vérité", decide=True)
                elif ans.get("absent"):
                    it.update(choix=[], origine="page absente", decide=False,
                              raison="page absente du scan : cocher d'après la copie papier")
                else:
                    it.update(choix=it["proposition"], origine="proposé", decide=False)
                items.append(it)
        return items

    # code (barème) ----------------------------------------------------------------
    def _encre(self):
        """‰ d'écriture de chaque cadre de code, calculé une fois (`<classe>/code_encre.json`)."""
        if getattr(self, "_encre_cache", None) is None:
            p = self.dir / CODE_ENCRE
            data = self._json(p)
            manque = [(cid, fid) for cid in self.copy_ids for fid in self.exam.bareme.get("champs", {})
                      if fid not in data.get(cid, {}) and (self.doc(cid).get("fields", {}).get(fid) or {}).get("crop")]
            if manque:
                import cv2
                from .code_vide import encre
                for cid, fid in manque:
                    crop = self.doc(cid)["fields"][fid]["crop"].replace("\\", "/")
                    data.setdefault(cid, {})[fid] = round(encre(cv2.imread(str(self.dir / crop), cv2.IMREAD_GRAYSCALE)), 2)
                p.write_text(json.dumps(data, indent=1), encoding="utf-8")
            self._encre_cache = data
        return self._encre_cache

    def code_items(self):
        """Cadres de code notés au barème. Décision : `options` = critères cochés (+ « grave » pour le malus),
        verdict « vide » = 0. Cadre presque sans écriture : « vide ? » proposé, jamais décidé seul."""
        b = self.exam.bareme.get("champs", {})
        if not b:
            return []
        malus = self.exam.bareme.get("malus")
        dec, enc = self.decisions.of(self.name), self._encre()
        lus = self._json(self.dir / "code_lectures.json")   # transcriptions (option `transcrire`)
        tests = self._json(self.dir / CODE_TESTS)          # pré-cochage par exécution (commande `precocher`)
        # page de chaque cadre : l'élève écrit souvent sous le cadre imprimé, la page entière le montre
        page_de = {f["id"]: pg["page"] for pg in self.exam.template["pages"] for f in pg["fields"]}
        items = []
        for cid in self.copy_ids:
            n, doc = _num(cid), self.doc(cid)
            for fid, bar in b.items():
                key = f"c{n:02d}_{fid}"
                info = doc.get("fields", {}).get(fid) or {}
                e = enc.get(cid, {}).get(fid)
                d = dec.get(key)
                # transcription corrigée par l'enseignant (texte) : prime sur celle de la machine
                verifiee = _transcription_enseignant(d)
                lu = verifiee if verifiee is not None else (lus.get(key) or {}).get("code")
                it = {"classe": self.name, "copie": cid, "num": n, "cle": key, "champ": fid, "code": True,
                      "img": (info.get("crop") or "").replace("\\", "/"), "box": info.get("box_px"), "max": bar["points"], "encre": e,
                      "criteres": bar["criteres"], "malus": malus, "choix": [], "verdict": None,
                      "attendu": None, "proposition": None, "raison": None,
                      "transcription": lu, "transcription_verifiee": verifiee is not None}
                pg = f"{cid}/pages/p{page_de.get(fid, 0):02d}_overlay.jpg"
                if (self.dir / pg).exists():
                    it["page"] = pg
                t = tests.get(key)
                if t and t.get("lecture") == lu:           # tests faits sur CETTE transcription seulement
                    it["tests"] = {"criteres": t["criteres"], "essais": t["essais"], "tourne": t["tourne"],
                                   "execute": t["execute"], "reparation": t["reparation"],
                                   "refus_modele": t.get("refus_modele")}
                    ids = {c["id"] for c in bar["criteres"]}
                    it["tests"]["complet"] = set(t["criteres"]) == ids and all(t["criteres"].values())
                if d and (d.get("verdict") or d.get("options") is not None):
                    it.update(origine="enseignant", decide=True, choix=d.get("options") or [],
                              verdict=d.get("verdict"))
                elif not info.get("crop"):
                    it.update(origine="page absente", decide=False)
                elif e is not None and e < CODE_VIDE:
                    it.update(origine="vide ?", decide=False, verdict=VIDE,
                              raison=f"presque rien d'écrit ({str(e).replace('.', ',')} ‰)")
                elif lu is not None and lu.strip() == "(vide)":
                    it.update(origine="vide ?", decide=False, verdict=VIDE, raison="transcription : (vide)")
                elif "tests" in it:
                    # critères dont les tests passent : PRÉ-COCHÉS, jamais validés seuls (l'enseignant confirme)
                    tt = it["tests"]
                    it.update(origine="tests", decide=False, choix=sorted(c for c, ok in tt["criteres"].items() if ok))
                    if not tt["tourne"]:
                        it["raison"] = "ne s'exécute pas, même après réparation des fautes tolérées : infraction lourde ?"
                    elif tt["complet"]:
                        it["raison"] = None
                elif (lus.get(key) or {}).get("criteres_proposes") is not None:
                    # lecture (session ou service en ligne) : critères PRÉ-COCHÉS, jamais validés seuls
                    l = lus[key]
                    it.update(origine="proposé", decide=False, choix=list(l["criteres_proposes"]),
                              raison=l.get("doute") or None)
                    if l.get("code", "").strip() == "(vide)":
                        it.update(verdict=VIDE, choix=[])
                else:
                    it.update(origine="à noter", decide=False)
                it["points"] = self._points_code(it)
                items.append(it)
        return items

    def all_items(self):
        return self.short_items() + self.qcm_items() + self.code_items()

    def _points_code(self, it):
        if it["verdict"] in (VIDE, ILLISIBLE):
            return 0.0
        pts = sum(c["points"] for c in it["criteres"] if c["id"] in it["choix"])
        if it.get("malus") and it["malus"]["id"] in it["choix"]:
            pts += it["malus"]["points"]
        return round(min(max(pts, 0.0), it["max"]), 3)

    # notes --------------------------------------------------------------------
    def notes(self):
        shorts, qcms, codes = self.short_items(), self.qcm_items(), self.code_items()
        students = self.students()
        by_copy = {}
        for it in shorts:
            by_copy.setdefault(it["copie"], []).append(it)
        q_by_copy = {}
        for it in qcms:
            q_by_copy.setdefault(it["copie"], []).append(it)
        key = self.exam.key
        rows = []
        for cid in self.copy_ids:
            answers = json.loads(json.dumps(self.doc(cid).get("answers", {})))
            wait_q = 0
            for it in q_by_copy.get(cid, []):
                if it.get("verdict") == ILLISIBLE:
                    answers.pop(it["champ"], None)  # compté 0 (« missing ») même avec la règle par option
                elif it["decide"]:
                    answers.setdefault(it["champ"], {}).update(status="ok", selected=it["choix"])
                else:
                    wait_q += 1
            g = grade_copy(answers, self.exam.template, key) if key.get("answers") else {"total": 0, "max": 0}
            its = by_copy.get(cid, [])
            court = sum(i["points"] or 0 for i in its if i["decide"])
            provisoire = sum(i["points"] or 0 for i in its)
            wait_c = sum(not i["decide"] for i in its)
            cs = [i for i in codes if i["copie"] == cid]
            code = sum(i["points"] for i in cs if i["decide"])
            wait_k = sum(not i["decide"] for i in cs)
            mx = g.get("max", 0) + sum(i["max"] for i in its) + sum(i["max"] for i in cs)
            attente = wait_c + wait_q + wait_k
            rows.append({"classe": self.name, "copie": cid, "etudiant": students.get(cid, f"{self.name}_{cid}"),
                         "qcm": g.get("total", 0), "courtes": court, "code": code,
                         "total": g.get("total", 0) + court + code,
                         "provisoire": g.get("total", 0) + provisoire + code, "max": mx,
                         "en_attente": attente, "etat": "complète" if attente == 0 else "incomplète"})
        return rows

    # copies à reprendre sur le papier ---------------------------------------------------
    def a_la_main(self):
        """Copies dont une page manque au scan ou est illisible, avec les réponses touchées encore à décider
        et les points en jeu (cf. `report.copies_a_la_main`)."""
        from .report import copies_a_la_main
        docs = [self.doc(cid) | {"copy_id": cid} for cid in self.copy_ids]
        liste = copies_a_la_main(docs, self.exam.template)
        if not liste:
            return []
        items = {}
        for it in self.short_items() + self.qcm_items() + self.code_items():
            items.setdefault(it["copie"], {})[it["champ"]] = it
        qmax = grade_copy({}, self.exam.template, self.exam.key)["details"] if self.exam.key.get("answers") else {}
        for c in liste:
            its = [items.get(c["copie"], {}).get(f) for f in c["champs"]]
            c.update(classe=self.name, groupe=self.group, num=_num(c["copie"]),
                     points=round(sum(self.exam.points.get(f) or qmax.get(f, {}).get("max", 0)
                                    or self.exam.bareme.get("champs", {}).get(f, {}).get("points", 0) for f in c["champs"]), 3),
                     restants=[i["champ"] for i in its if i and not i["decide"]],
                     decides=[{"champ": i["champ"], "verdict": i.get("verdict") or ", ".join(i.get("choix") or []) or "aucune case"}
                              for i in its if i and i["decide"]])
        return liste

    # étiquettes pour l'affinage ------------------------------------------------------
    def labels(self):
        """Transcriptions sûres pour affiner le lecteur (format de --truth : {cNN_qX.Y: texte}).

        Seulement ce que l'enseignant a vérifié : vérité validée, texte qu'il a tapé, ou réponse qu'il a
        jugée juste quand la lecture brute du moteur ET la valeur retenue sont exactement le corrigé
        (un `Error` lu puis rapproché en `ERREUR` n'en fait pas partie). Jamais les acceptées non revues,
        ni la mémoire, ni le second lecteur : le modèle n'apprend pas de ses propres décisions."""
        truth = self._json(self.truth_dir / f"{self.name}.short_truth.json")
        dec = self.decisions.of(self.name)
        out = {k: v for k, v in truth.items() if not v.endswith("?")}
        expected = self.exam.key.get("short_answers", {})
        for cid in self.copy_ids:
            n, doc = _num(cid), self.doc(cid)
            for fid in self.exam.points:
                key = f"c{n:02d}_{fid}"
                d = dec.get(key)
                if not d:
                    continue
                if d.get("texte") is not None:   # lecture tapée dans l'outil : prime sur une vérité antérieure
                    out[key] = d["texte"]
                    continue
                if key in out:
                    continue
                o = doc.get("fields", {}).get(fid, {}).get("ocr") or {}
                raw = (o.get("candidates") or [[None]])[0][0]
                if (d.get("verdict") == JUSTE and o.get("value") is not None and raw is not None
                        and self.exam.clean(o["value"], fid) == self.exam.clean(raw, fid)
                        == self.exam.clean(expected[fid], fid)):
                    out[key] = o["value"]
        return out

    def save_labels(self):
        """Écrit `data/truth/<classe>.appris.json` (format de --truth) : suivi (`ocr --truth`) et affinage
        s'en servent directement, sans export ni copie à la main. Rien n'est écrit pour une classe sans
        aucune lecture vérifiée."""
        code = self.code_labels()
        if code["transcriptions"] or code["criteres"]:
            self._ecrire(self.truth_dir / f"{self.name}.code_appris.json", code)
        lab = self.labels()
        if not lab:
            return None
        return self._ecrire(self.truth_dir / f"{self.name}.appris.json", lab)

    @staticmethod
    def _ecrire(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        return path

    def code_labels(self, avec_auto=False):
        """Vérité du code pour faire progresser la chaîne locale (`data/truth/<classe>.code_appris.json`) :
        transcriptions corrigées par l'enseignant (touche T) et critères qu'il a décidés cadre par cadre.
        Jamais une décision validée en lot pendant la session (marqueur « auto: ») : ce sont des propositions de
        Claude, pas des jugements de l'enseignant. Jamais une transcription de la machine non corrigée."""
        champs = self.exam.bareme.get("champs", {})
        out = {"transcriptions": {}, "criteres": {}}
        for cle, d in self.decisions.of(self.name).items():
            if cle.split("_", 1)[-1] not in champs:
                continue
            t = _transcription_enseignant(d)
            if t is not None:
                out["transcriptions"][cle] = t
            if (d.get("texte") or "").startswith("auto:") and not avec_auto:   # `code-bilan --avec-auto` seulement
                continue
            if d.get("verdict") or d.get("options") is not None:
                out["criteres"][cle] = {"choix": [] if d.get("verdict") else (d.get("options") or []),
                                        "verdict": d.get("verdict")}
        return out

    # suivi de la machine ---------------------------------------------------------------
    def suivi(self):
        """Ce que les décisions de l'enseignant disent de la machine : lectures vérifiées (bien lues ou
        corrigées), erreurs d'acceptation (réponse acceptée d'office qu'il a corrigée), mémoire contredite."""
        dec = self.decisions.of(self.name)
        st = {"classe": self.name, "groupe": self.group, "copies": len(self.copy_ids), "reponses": 0, "acceptees": 0,
              "verifiees": 0, "bien_lues": 0, "corrigees": 0, "acceptees_fausses": 0, "memoire": 0,
              "memoire_contredite": 0}
        erreurs = []
        for it in self.short_items():
            st["reponses"] += 1
            st["acceptees"] += it["lecture"] == "ok"
            st["memoire"] += it["origine"] == "mémoire"
            d = dec.get(it["cle"])
            if not d:
                continue
            prop = it["proposition"]
            if d.get("texte") is not None and prop is not None:
                st["verifiees"] += 1
                if self.exam.clean(d["texte"], it["champ"]) == self.exam.clean(str(prop), it["champ"]):
                    st["bien_lues"] += 1
                else:
                    st["corrigees"] += 1
                    erreurs.append({"classe": self.name, "copie": it["copie"], "cle": it["cle"], "champ": it["champ"],
                                    "img": it["img"], "machine": prop, "ecrit": d["texte"], "lecture": it["lecture"]})
            if it["lecture"] == "ok" and prop is not None:   # acceptée d'office puis changée par l'enseignant
                rule = self.exam.verdict(prop, it["champ"])
                if (d.get("texte") is not None and self.exam.clean(d["texte"], it["champ"]) != self.exam.clean(prop, it["champ"])) \
                        or (d.get("verdict") and d["verdict"] != rule):
                    st["acceptees_fausses"] += 1
            if self.memory and d.get("verdict") and prop:
                m = self.memory.lookup(self.memory_id(it["champ"]), self.name, it["champ"], self.exam.clean(prop, it["champ"]))
                if m and m[0] != d["verdict"]:
                    st["memoire_contredite"] += 1
        return st, erreurs

    # décisions ---------------------------------------------------------------------
    def decide(self, cle, verdict=None, texte=None, options=None):
        """Une lecture tapée DIFFÉRENTE de la lecture actuelle (sans verdict cliqué en même temps) fait recalculer
        la note à partir d'elle : un « = attendu » de bloc corrigé ensuite au cas par cas se réajuste. « Bien lu »
        (même lecture) garde le verdict déjà choisi (ex. une indulgence de l'enseignant)."""
        if verdict is not None and verdict not in VERDICTS:
            raise ValueError(f"verdict inconnu : {verdict}")
        # QCM : cocher des cases après « illisible » remplace ce verdict
        clear = options is not None and verdict is None
        if texte is not None and verdict is None:
            cur = next((i for i in self.short_items(use_memory=False) if i["cle"] == cle), None)
            if cur is not None:
                lu = cur["texte"] if cur["texte"] is not None else cur["proposition"]
                clear = self.exam.clean(texte, cur["champ"]) != self.exam.clean(str(lu if lu is not None else ""), cur["champ"])
        self.decisions.set(self.name, cle, verdict, texte, options, clear_verdict=clear)

    def undo(self, cle):
        """Annule la note. Pour un cadre de code, la transcription corrigée par l'enseignant est gardée."""
        d = self.decisions.of(self.name).get(cle)
        self.decisions.clear(self.name, cle)
        if _transcription_enseignant(d) is not None and cle.split("_", 1)[-1] in self.exam.bareme.get("champs", {}):
            self.decisions.set(self.name, cle, texte=d["texte"])

    def corriger_transcription(self, cle, texte):
        """Transcription d'un cadre de code corrigée par l'enseignant : enregistrée (texte de la décision, la note
        n'est pas touchée), puis tests relancés aussitôt sur elle (règles seules : quelques secondes)."""
        from .code_tests import FICHIER, charger_tests, precocher_cadre
        fid = cle.split("_", 1)[-1]
        if fid not in self.exam.bareme.get("champs", {}):
            raise ValueError(f"{cle} n'est pas un cadre de code")
        self.decisions.set(self.name, cle, texte=texte)
        tests = charger_tests(self.exam_id)
        if not tests:
            return
        p = self.dir / FICHIER
        data = self._json(p)
        r = precocher_cadre(texte, fid, tests)
        if r is None:
            data.pop(cle, None)
        else:
            data[cle] = r
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
