"""Évaluation : résultats du pipeline vs vérité terrain (truth.json).

Métriques (celles à suivre sur les vrais scans aussi, avec une vérité saisie
à la main sur un échantillon) :
    cases       exactitude case par case sur les décisions automatiques
    questions   % de questions décidées automatiquement ET justes
    revue       % de questions envoyées en revue humaine
    erreurs     questions décidées automatiquement mais fausses (le chiffre
                critique : c'est ce qui passe sans contrôle)
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from .common import load_json


def main(results_dir, truth_path):
    truth = load_json(truth_path)
    res_dir = Path(results_dir)
    q_stats = Counter()
    box_ok = box_n = 0
    errors, reviews = [], Counter()
    mark_stats = Counter()
    for ct in truth["copies"]:
        rp = res_dir / ct["copy_id"] / "result.json"
        if not rp.exists():
            q_stats["copie_absente"] += len(ct["answers"])
            continue
        r = load_json(rp)
        for fid, t in ct["answers"].items():
            got = r["answers"].get(fid)
            exp = set(t["selected"])
            multi_err = t["mode"] == "single" and len(exp) > 1
            if got is None:
                q_stats["absente"] += 1
                continue
            for oid, o in got["options"].items():
                mk = t["marks"].get(oid, "none")
                if o["state"] == "ambiguous":
                    mark_stats[(mk, "revue")] += 1
                    continue
                pred = o["state"] in ("checked", "full")
                box_n += 1
                ok = pred == (oid in exp)
                box_ok += ok
                mark_stats[(mk, "ok" if ok else "ERREUR")] += 1
            if got["status"] == "review":
                q_stats["revue"] += 1
                reviews["plusieurs cases (attendu)" if multi_err else "ambiguë"] += 1
            elif set(got["selected"]) == exp:
                q_stats["auto_juste"] += 1
            else:
                q_stats["auto_FAUX"] += 1
                errors.append((ct["copy_id"], fid, sorted(exp), got["selected"],
                               {k: v["fill"] for k, v in got["options"].items()}, t["marks"]))
    n = sum(q_stats.values())
    auto = q_stats["auto_juste"] + q_stats["auto_FAUX"]
    print(f"Questions QCM : {n}")
    print(f"  décidées automatiquement : {auto} ({100 * auto / max(n, 1):.1f} %)")
    print(f"     dont justes           : {q_stats['auto_juste']} ({100 * q_stats['auto_juste'] / max(auto, 1):.2f} %)")
    print(f"     dont FAUSSES          : {q_stats['auto_FAUX']}")
    print(f"  envoyées en revue        : {q_stats['revue']} ({100 * q_stats['revue'] / max(n, 1):.1f} %) {dict(reviews)}")
    for k in ("absente", "copie_absente"):
        if q_stats[k]:
            print(f"  {k}: {q_stats[k]}")
    print(f"Cases (hors revue) : {box_ok}/{box_n} justes ({100 * box_ok / max(box_n, 1):.2f} %)")
    print("Par type de marque :")
    kinds = sorted({k for k, _ in mark_stats})
    for kd in kinds:
        print(f"  {kd:12s} " + "  ".join(f"{s}={mark_stats[(kd, s)]}" for s in ("ok", "revue", "ERREUR")
                                          if mark_stats[(kd, s)]))
    for e in errors[:20]:
        print("  ERREUR", *e)
    return q_stats
