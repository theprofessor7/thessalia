"""Bilan de la chaîne locale du code après une classe : `python -m thessalia code-bilan sorties/<classe> […]`.

Comme `bilan` et `ocr --truth` pour TrOCR : ce que les décisions de l'enseignant disent de la machine, pour savoir
quoi améliorer avant la classe suivante. Référence : `Classe.code_labels()` (critères décidés cadre par cadre,
transcriptions corrigées avec T ; jamais les lots « auto: »).

  - critères pré-cochés par les tests : justes, **à tort** (l'enseignant ne l'a pas coché : test trop lâche, à
    resserrer en priorité), oubliés (l'enseignant l'a coché, le test non : tolérance ou réparation à ajouter),
    sans test (jugement) ;
  - programmes qui ne tournent pas, réparations du modèle refusées par le contrôle ;
  - transcription locale contre la transcription corrigée par l'enseignant (ressemblance, cadres exacts).

`--essai` lit la base d'essai (`data/correction_essai.sqlite`, banc à l'aveugle) au lieu de la base principale.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher

from .code_tests import FICHIER


def bilan_classe(c):
    tests = c._json(c.dir / FICHIER)
    lus = c._json(c.dir / "code_lectures.json")
    vrai = c.code_labels()
    par = {}
    exemples = {"a_tort": [], "oublis": [], "refus": []}
    for cle, v in vrai["criteres"].items():
        f = cle.split("_", 1)[-1]
        q = par.setdefault(f, dict(cadres=0, testes=0, justes=0, a_tort=0, oublis=0, sans_test=0, plante=0, refus=0))
        q["cadres"] += 1
        t = tests.get(cle)
        if not t:
            continue
        q["testes"] += 1
        q["plante"] += not t["tourne"]
        if t.get("refus_modele"):
            q["refus"] += 1
            exemples["refus"].append(f"{cle} ({t['refus_modele']})")
        choix = set(v["choix"]) - {"grave"}
        for cid, ok in t["criteres"].items():
            if ok and cid in choix:
                q["justes"] += 1
            elif ok:
                q["a_tort"] += 1
                exemples["a_tort"].append(f"{cle} critère {cid}")
            elif cid in choix:
                q["oublis"] += 1
                exemples["oublis"].append(f"{cle} critère {cid}" + ("" if t["tourne"] else " (ne tourne pas)"))
        q["sans_test"] += len(choix - set(t["criteres"]))
    sims, exacts = [], 0
    for cle, texte in vrai["transcriptions"].items():
        m = (lus.get(cle) or {}).get("code")
        if m is None:
            continue
        sims.append(SequenceMatcher(None, m, texte).ratio())
        exacts += m.strip() == texte.strip()
    return par, exemples, sims, exacts


def run(dossiers, essai=False):
    from .correction import Classe, Decisions, Memory
    from .serve import ESSAI_DB, _classes
    exams = {}
    db = Decisions(ESSAI_DB) if essai else Decisions()
    for d in _classes(dossiers):
        c = Classe(d, exams, db, memory=Memory())
        par, ex, sims, exacts = bilan_classe(c)
        print(f"== {c.name} : {sum(q['cadres'] for q in par.values())} cadres jugés par l'enseignant cadre par cadre")
        if not par:
            print("  rien à mesurer (aucune décision hors lots « auto: », ou pas de `precocher`)")
        for f in sorted(par):
            q = par[f]
            print(f"  {f:6} cadres testés {q['testes']}/{q['cadres']} · critères justes {q['justes']} · "
                  f"À TORT {q['a_tort']} · oubliés {q['oublis']} · sans test {q['sans_test']} · "
                  f"ne tournent pas {q['plante']} (réparation refusée {q['refus']})")
        for k, titre in (("a_tort", "À TORT (test trop lâche : à resserrer)"), ("oublis", "oubliés (tolérance ou réparation à ajouter)"),
                         ("refus", "réparations du modèle refusées par le contrôle")):
            if ex[k]:
                print(f"  {titre} : " + " ; ".join(ex[k]))
        if sims:
            print(f"  transcription locale / corrigée par l'enseignant : {len(sims)} cadres, ressemblance moyenne "
                  f"{sum(sims) / len(sims):.0%}, {exacts} exacts")
