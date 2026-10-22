"""Bilan d'un groupe corrigé : ce que les décisions de l'enseignant disent de la machine.

`python -m thessalia bilan NA NB [--dossiers sorties/booster …]`. Lecture seule de `data/correction.sqlite`.

Mesures sur les lectures que l'enseignant a vérifiées (confirmées ou tapées, donc surtout les cas difficiles) :
  proposition juste       la proposition qu'il a VUE (indices séparateur et espace compris) = ce qui est écrit
  dans les boutons        proposition fausse, mais la bonne lecture était parmi les « ou : » (touches 6, 7, 8)
  lecture brute v3 / v2   premier candidat de chaque modèle TrOCR (caches `ocr_lectures_*_v3/v2.json`) juste
  mémoire                 réponses que la mémoire des verdicts aurait décidées seule
  séparateur, espace      indices du détecteur point/virgule et de l'espace de q7.3 : justes, changés à raison
La proposition « vue » est recalculée sans les décisions (une réponse décidée ne passe plus par les indices),
avec la mémoire actuelle : les chiffres d'un groupe ancien bougent un peu quand d'autres classes s'ajoutent.
"""
from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from .correction import Classe, Decisions, Memory, DB_PATH

MODELES = ("v3", "v2")


def mesurer(classes, vierge, memory, groupe):
    S, orig, sep, esp, faute = Counter(), Counter(), Counter(), Counter(), Counter()
    q14 = Counter()
    exams = {}
    for c in classes:
        if c.group != groupe:
            continue
        vu = {i["cle"]: i for i in Classe(c.dir, exams, vierge, memory=memory).short_items()}
        dec = c.decisions.of(c.name)
        caches = {}
        for m in MODELES:
            p = c.dir / f"ocr_lectures_trocr_data_models_trocr_{m}.json"
            caches[m] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        for it in c.short_items():
            S["reponses"] += 1
            orig[it["origine"]] += 1
            d, v = dec.get(it["cle"]), vu[it["cle"]]
            S["memoire"] += v["origine"] == "mémoire"
            if not d or d.get("texte") is None or v["proposition"] is None:
                continue
            f = it["champ"]

            def cl(x):
                return c.exam.clean(str(x), f)

            t = cl(d["texte"])
            S["verifiees"] += 1
            if cl(v["proposition"]) == t:
                S["prop_juste"] += 1
            else:
                S["prop_fausse"] += 1
                faute[f] += 1
                S["dans_boutons"] += t in {cl(a) for a in v.get("alternatives") or []}
            for m, cache in caches.items():
                cand = (cache.get(it["cle"]) or {}).get("candidates") or []
                S[f"brut_{m}"] += bool(cand) and cl(cand[0][0]) == t
            if "p_virgule" in v:
                lm = v.get("lecture_machine")
                sep["indices"] += 1
                sep["juste"] += cl(v["proposition"]) == t
                sep["brut_juste"] += cl(lm or v["proposition"]) == t
                if lm:
                    sep["changees"] += 1
                    sep["a_raison"] += cl(v["proposition"]) == t
            if "ecart" in v:
                k = "X Y" if " " in str(v["proposition"]) else "XY"
                esp[(k, cl(v["proposition"]) == t)] += 1
            if f.startswith("q14") and cl(v["proposition"]) != t:
                q14[(str(v["proposition"]), d["texte"])] += 1
    return S, orig, sep, esp, faute, q14


def _pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f} %)" if b else "—"


def run(groupes, dossiers=("sorties/booster",), db_path=DB_PATH):
    from .serve import _classes

    reel, exams, memory = Decisions(db_path), {}, Memory()
    classes = [Classe(p, exams, reel, memory=memory) for p in _classes(dossiers)]
    memory.rebuild(classes)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:  # Windows : base encore ouverte
        vierge = Decisions(Path(tmp) / "vide.sqlite")   # aucune décision : ce que l'enseignant a vu
        for g in groupes:
            S, orig, sep, esp, faute, q14 = mesurer(classes, vierge, memory, g)
            if not S["reponses"]:
                print(f"\nGroupe {g} : aucune classe trouvée.")
                continue
            print(f"\n=== Groupe {g} : {S['reponses']} réponses courtes · origine finale : "
                  + ", ".join(f"{k} {n}" for k, n in orig.most_common()))
            print(f"  lectures vérifiées par l'enseignant : {S['verifiees']}")
            print(f"  proposition juste                   : {_pct(S['prop_juste'], S['verifiees'])}")
            print(f"  bonne lecture dans les boutons      : {_pct(S['dans_boutons'], S['prop_fausse'])} des propositions fausses")
            print("  lecture brute juste                 : " + " · ".join(f"{m} {S[f'brut_{m}']}" for m in MODELES))
            print(f"  décidées par la mémoire             : {S['memoire']}")
            if sep["indices"]:
                print(f"  séparateur (décimaux avec indice)   : proposition juste {sep['juste']}/{sep['indices']}, "
                      f"lecture brute {sep['brut_juste']} ; changées {sep['changees']}, à raison {sep['a_raison']}")
            if esp:
                print("  espace q7.3 (lecture juste)         : " + " · ".join(
                    f"{k} proposé {esp[(k, True)]}/{esp[(k, True)] + esp[(k, False)]}" for k in ("X Y", "XY")
                    if esp[(k, True)] + esp[(k, False)]))
            print("  propositions fausses par champ      : " + ", ".join(f"{f} {n}" for f, n in faute.most_common(8)))
            if q14:
                print("  q14 (proposé → écrit)               : " + ", ".join(f"{a} → {b}" for (a, b), n in q14.most_common(8)))
