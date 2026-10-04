"""Notation des QCM à partir d'un corrigé (optionnel).

Corrigé JSON :
    {
      "exam_id": "socle-python-2026-FR",
      "scoring": {"default": "exact", "q1": "per_option"},
      "answers": {"q1": ["a", "c", "e", "g"], "q4.1": ["F"], "q9": ["b"]}
    }

Barème : les points de la question (lus dans le PDF) sont répartis également
entre ses sous-champs QCM (q4 = 0,75 pt -> 6 x 0,125 pt).
Règles :
    exact       tout ou rien
    per_option  fraction des cases dans le bon état (cochée / non cochée)
Un champ en statut "review" n'est pas noté (statut "pending") tant qu'un
humain ne l'a pas validé.
"""
from __future__ import annotations


def grade_copy(answers: dict, template: dict, key: dict) -> dict:
    by_q = {q["num"]: q for q in template["questions"]}
    omr_fields = {}
    for p in template["pages"]:
        for f in p["fields"]:
            if f["type"] in ("mcq", "truefalse"):
                omr_fields[f["id"]] = f
    per_q_count = {}
    for fid, f in omr_fields.items():
        per_q_count[f["question"]] = per_q_count.get(f["question"], 0) + 1

    scoring = key.get("scoring", {})
    details, total, max_total, pending = {}, 0.0, 0.0, []
    for fid, expected in key.get("answers", {}).items():
        f = omr_fields.get(fid)
        if f is None:
            continue
        q = by_q.get(f["question"], {})
        pts = (q.get("points") or 0) / per_q_count[f["question"]]
        max_total += pts
        res = answers.get(fid)
        if res is None:
            details[fid] = {"status": "missing", "points": 0.0, "max": pts}
            continue
        if res["status"] == "review":
            pending.append(fid)
            details[fid] = {"status": "pending", "points": None, "max": pts}
            continue
        rule = scoring.get(fid, scoring.get(f"q{f['question']}", scoring.get("default", "exact")))
        sel, exp = set(res["selected"]), set(expected)
        if rule == "per_option":
            all_opts = [o["id"] for o in f["options"]]
            ok = sum((o in sel) == (o in exp) for o in all_opts)
            got = pts * ok / len(all_opts)
        else:
            got = pts if sel == exp else 0.0
        total += got
        details[fid] = {"status": "graded", "points": round(got, 3), "max": round(pts, 3),
                        "selected": sorted(sel), "expected": sorted(exp)}
    return {"total": round(total, 3), "max": round(max_total, 3), "pending": pending, "details": details}
