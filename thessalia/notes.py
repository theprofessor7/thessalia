"""Notes partielles : QCM + réponses courtes (sur 9 pour le sujet Socle Python).

    python -m thessalia notes sorties/booster/supB_1 sorties/booster/supB_2 … -t GABARIT -k CORRIGE -v VOCAB
        [-o sorties/notes/B.csv]

Source de chaque réponse courte, dans l'ordre :
  1. la vérité validée `data/truth/<dossier>.short_truth.json` (clés cNN_qX.Y) ; « ? » final = en attente ;
  2. sinon la lecture de `ocr` (`short_answers.csv`) : réponse acceptée = notée, « ?… » = en attente.

Règle globale de l'enseignant (18 octobre 2026), comparaison au corrigé (`short_answers`) :
  juste        identique (espaces en trop aux bords, guillemets typographiques ignorés ; « _ » = espace en q7),
               ou équivalence décidée par l'enseignant (Error = ERREUR toute casse, Zero = Zéro) : 100 %
  forme        écart de forme seulement : casse (`grand`), parenthèses (`print()`), guillemets (`"427"`),
               espaces : 50 %. Pas en q7 (texte) : on y demande l'affichage exact, l'espace compte (`X Y`
               pour `XY` = `end=""` non compris), donc tout écart y est faux
  faux         tout le reste, dont « 2,5 » pour « 2.5 » (virgule décimale) : 0
  vide         zone vide : 0
  en attente   pas encore validée : pas de points, la note est marquée incomplète
Exceptions possibles dans le corrigé (`short_accept` / `short_reject` par champ), non utilisées à ce jour.

Points d'une question répartis également entre ses blancs (q2 = 0,75 pt -> 6 x 0,125), comme pour les QCM.
Note QCM reprise de `results.json` (questions en revue = en attente).
Identité : `data/listes/<dossier>.csv` (colonnes copie;etudiant), sinon le numéro de copie.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path

from .common import load_json
from .grade import grade_copy
from .vocab import normalize

TRUTH_DIR = Path("data/truth")
LISTS_DIR = Path("data/listes")

# décision de l'enseignant (14 octobre 2026) : langue d'examen, pas une faute ; toute casse
EQUIV_GROUPS = [{"erreur", "error"}, {"zéro", "zero"}]

JUSTE, FORME, FAUX, VIDE, ATTENTE = "juste", "forme", "faux", "vide", "en attente"
RATE = {JUSTE: 1.0, FORME: 0.5, FAUX: 0.0, VIDE: 0.0}  # règle globale de l'enseignant


def clean(s: str, kind: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    if kind == "text":
        s = s.replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def _equiv(a: str, b: str) -> bool:
    a, b = a.casefold(), b.casefold()
    return any(a in g and b in g for g in EQUIV_GROUPS)


def judge(answer, expected: str, kind: str, accept=(), reject=()) -> str:
    """Statut d'une réponse courte face au corrigé (voir l'en-tête du module)."""
    if answer is None:
        return ATTENTE
    a, e = clean(answer, kind), clean(expected, kind)
    if not a:
        return VIDE
    if a == e or a in {clean(x, kind) for x in accept} or _equiv(a, e):
        return JUSTE
    if a in {clean(x, kind) for x in reject}:
        return FAUX
    if kind == "text":
        return FAUX  # q7 : affichage exact demandé, la casse et les espaces font partie de la réponse
    # casse, guillemets, parenthèses finales, espaces (normalize ne touche ni aux chiffres ni à la virgule :
    # « 2,5 » reste différent de « 2.5 »)
    return FORME if normalize(a, kind) == normalize(e, kind) else FAUX


def _fmt(x) -> str:
    return "" if x is None else f"{x:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def _short_fields(template: dict) -> dict:
    by_q = {q["num"]: q for q in template["questions"]}
    fields = [f for p in template["pages"] for f in p["fields"] if f["type"] == "short_text"]
    count = Counter(f["question"] for f in fields)
    return {f["id"]: (by_q.get(f["question"], {}).get("points") or 0) / count[f["question"]] for f in fields}


def _readings(results_dir: Path) -> dict:
    """{copy_id: {champ: réponse ou None (en revue)}} d'après short_answers.csv."""
    path = results_dir / "short_answers.csv"
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            cid = row.pop("copy")
            out[cid] = {k: (None if v.startswith("?") else v) for k, v in row.items()}
    return out


def _students(name: str, lists_dir: Path) -> dict:
    path = lists_dir / f"{name}.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as fh:
        return {r["copie"]: r["etudiant"] for r in csv.DictReader(fh, delimiter=";")}


def _regrade_qcm(result_path: Path, num: int, qcm_truth: dict, template: dict, key: dict):
    """Note QCM recalculée avec les QCM en revue validés par l'enseignant (« ? » = toujours en attente)."""
    if not result_path.exists():
        return None
    answers = load_json(result_path).get("answers", {})
    changed = False
    for fid, ans in answers.items():
        t = qcm_truth.get(f"c{num:02d}_{fid}")
        if ans.get("status") == "review" and t is not None and not t.endswith("?"):
            ans.update(status="ok", selected=[x for x in t.split(",") if x])
            changed = True
    return grade_copy(answers, template, key) if changed else None


def grade_class(results_dir, template: dict, key: dict, vocab: dict, truth_dir=TRUTH_DIR, lists_dir=LISTS_DIR):
    results_dir = Path(results_dir)
    name = results_dir.name
    res = load_json(results_dir / "results.json")
    truth_path = Path(truth_dir) / f"{name}.short_truth.json"
    truth = load_json(truth_path) if truth_path.exists() else None
    readings = _readings(results_dir)
    students = _students(name, Path(lists_dir))
    expected = key.get("short_answers", {})
    accept, reject = key.get("short_accept", {}), key.get("short_reject", {})
    kinds = {k: v.get("kind", "enum") for k, v in vocab.get("fields", {}).items()}
    pts = {f: p for f, p in _short_fields(template).items() if f in expected}

    rows, details = [], []
    qcm_path = Path(truth_dir) / f"{name}.qcm_truth.json"
    qcm_truth = load_json(qcm_path) if qcm_path.exists() else {}
    for c in res["copies"]:
        cid = c["copy_id"]
        num = int(cid.split("_")[-1])
        g = c.get("grade") or {}
        if qcm_truth and g.get("pending"):
            g = _regrade_qcm(results_dir / cid / "result.json", num, qcm_truth, template, key) or g
        qcm, qcm_max, qcm_wait = g.get("total"), g.get("max", 0), len(g.get("pending", []))
        short, short_max, counts = 0.0, 0.0, Counter()
        for fid, p in pts.items():
            short_max += p
            if truth is not None and f"c{num:02d}_{fid}" in truth:
                ans, src = truth[f"c{num:02d}_{fid}"], "vérité"
                if ans.endswith("?"):
                    ans = None
            else:
                ans, src = readings.get(cid, {}).get(fid), "lecture"
                if cid not in readings:
                    src = "non lue"
            st = judge(ans, expected[fid], kinds.get(fid, "enum"), accept.get(fid, ()), reject.get(fid, ()))
            got = None if st == ATTENTE else p * RATE[st]
            short += got or 0.0
            counts[st] += 1
            details.append({"copie": cid, "champ": fid, "reponse": "" if ans is None else ans,
                            "attendu": expected[fid], "statut": st, "points": got, "max": p, "source": src})
        wait = counts[ATTENTE] + qcm_wait
        rows.append({"classe": name, "copie": cid, "etudiant": students.get(cid, f"{name}_{cid}"),
                     "qcm": qcm, "qcm_max": qcm_max, "courtes": short, "courtes_max": short_max,
                     "total": (qcm or 0) + short, "max": qcm_max + short_max,
                     "en_attente": wait, "forme": counts[FORME],
                     "etat": "complète" if wait == 0 else "incomplète",
                     "source": "vérité validée" if truth is not None else "lecture automatique"})
    return rows, details


NOTE_COLS = [("classe", "classe"), ("copie", "copie"), ("etudiant", "étudiant"), ("qcm", "QCM"),
             ("courtes", "réponses courtes"), ("total", "total"), ("max", "sur"), ("en_attente", "en attente"),
             ("forme", "écarts de forme"), ("etat", "état"), ("source", "source")]


def write_notes(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:  # BOM : accents corrects dans Excel
        w = csv.writer(fh, delimiter=";")
        w.writerow([t for _, t in NOTE_COLS])
        for r in rows:
            w.writerow([_fmt(r[k]) if isinstance(r[k], float) else r[k] for k, _ in NOTE_COLS])


def write_details(details, path: Path):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["copie", "champ", "réponse", "attendu", "statut", "points", "max", "source"])
        for d in details:
            w.writerow([d["copie"], d["champ"], d["reponse"], d["attendu"], d["statut"], _fmt(d["points"]),
                        _fmt(d["max"]), d["source"]])


def run(dirs, template_path, key_path, vocab_path, out=None):
    template, key, vocab = load_json(template_path), load_json(key_path), load_json(vocab_path)
    all_rows, all_details = [], []
    for d in dirs:
        d = Path(d)
        rows, details = grade_class(d, template, key, vocab)
        write_notes(rows, d / "notes.csv")
        write_details(details, d / "notes_detail.csv")
        done = sum(r["etat"] == "complète" for r in rows)
        print(f"{d.name} : {len(rows)} copies, {done} notes complètes ({rows[0]['source'] if rows else '-'}) "
              f"-> {d / 'notes.csv'}")
        all_rows += rows
        all_details += [dict(x, copie=f"{d.name}/{x['copie']}") for x in details]
    st = Counter(x["statut"] for x in all_details)
    print(f"réponses courtes : {st[JUSTE]} justes, {st[FORME]} écarts de forme (50 %), {st[FAUX]} fausses, "
          f"{st[VIDE]} vides, {st[ATTENTE]} en attente")
    forms = Counter((x["champ"], x["reponse"]) for x in all_details if x["statut"] == FORME)
    if forms:
        print("  écarts de forme : " + ", ".join(f"{f} « {a} » x{n}" for (f, a), n in sorted(forms.items())))
    if out:
        write_notes(all_rows, Path(out))
        print(f"-> {out}")
    return all_rows
