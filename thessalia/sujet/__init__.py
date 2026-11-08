"""Sujet source unique (docs/FORMAT_SUJET.md) : lecture stricte, contrôle, fichiers de corrigé.

    python -m thessalia sujet examen.yaml                       contrôle seulement
    python -m thessalia sujet examen.yaml --langue fr --gabarit templates/x.json -o keys/x
                                                                écrit keys/x.key.json, .vocab.json, .bareme.json
"""
from __future__ import annotations

import json
from pathlib import Path

from .corrige import confronter, fichiers
from .modele import examen
from .source import ErreurSujet


def run(a):
    try:
        ex = examen(a.source)
    except ErreurSujet as e:
        print(f"Sujet refusé : {len(e.erreurs)} erreur(s) dans {a.source}")
        for m in e.erreurs:
            print("  -", m)
        raise SystemExit(1)
    qs = ex.questions()
    n = {t: sum(q.type == t for q in qs) for t in ("qcm", "vrai_faux", "blancs", "code", "redaction")}
    print(f"Sujet {ex.id} : {len(ex.exercices)} exercices, {len(qs)} questions, {ex.points:g} points, langues "
          f"{', '.join(ex.langues)} ; " + ", ".join(f"{k} {v}" for k, v in n.items() if v))
    if not a.out:
        return
    if a.langue not in ex.langues:
        raise SystemExit(f"--langue : une des langues du sujet ({', '.join(ex.langues)})")
    gab = json.loads(Path(a.gabarit).read_text(encoding="utf-8"))
    err = confronter(ex, gab)
    try:
        key, vocab, bareme = fichiers(ex, a.langue, gab["exam_id"], Path(a.source).name, a.traduction_de)
    except ErreurSujet as e:
        err += e.erreurs
    if err:
        print(f"Corrigé refusé : {len(err)} écart(s) avec le gabarit {a.gabarit}")
        for m in err:
            print("  -", m)
        raise SystemExit(1)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for suffixe, contenu in ((".key.json", key), (".vocab.json", vocab), (".bareme.json", bareme)):
        if contenu is not None:
            p = out.with_name(out.name + suffixe)
            p.write_text(json.dumps(contenu, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"  -> {p}")
