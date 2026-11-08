"""Sujet source unique (docs/FORMAT_SUJET.md) : lecture stricte, contrôle, fichiers de corrigé.

    python -m thessalia sujet examen.yaml                       contrôle seulement
    python -m thessalia sujet examen.yaml --langue fr --gabarit templates/x.json -o keys/x
                                                                écrit keys/x.key.json, .vocab.json, .bareme.json
    python -m thessalia sujet examen.yaml --produire sorties/sujets/x
                                                                toutes les langues : sujet et corrigé PDF (Typst),
                                                                zones, gabarit lu dans le PDF, corrigés ; refusé si
                                                                une zone n'est pas conforme au PDF ou si le gabarit
                                                                ne colle pas à la source
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
    if getattr(a, "produire", None):
        return produire_tout(ex, Path(a.source), Path(a.produire))
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


def produire_tout(ex, source, dossier, gabarits=None, corriges=None, log=print):
    """Sujets, corrigés PDF, zones (dans `dossier`), gabarits (`gabarits`) et fichiers de corrigé (`corriges`) de
    toutes les langues ; SystemExit avec la raison si un contrôle échoue."""
    from ..template_builder import build_template
    from ..verif_zones import controler
    from .mise_en_page import produire

    gabarits, corriges = Path(gabarits or dossier), Path(corriges or dossier)
    gabarits.mkdir(parents=True, exist_ok=True)
    corriges.mkdir(parents=True, exist_ok=True)
    premier = None
    for langue in ex.langues:
        c = produire(ex, source, dossier, langue)
        base = f"{ex.id}_{langue.upper()}"
        gab = build_template(c["sujet"], exam_id=base)
        gp = gabarits / f"gabarit_{base}.json"
        gp.write_text(json.dumps(gab, ensure_ascii=False, indent=1), encoding="utf-8")
        rapport, ok = controler(c["sujet"], c["zones"])
        (dossier / f"verif_zones_{base}.md").write_text(rapport, encoding="utf-8")
        err = confronter(ex, gab)
        if not ok:
            err.append(f"zones non conformes au PDF : voir {dossier / f'verif_zones_{base}.md'}")
        if err:
            raise SystemExit(f"{langue} : REFUSÉ\n" + "\n".join("  - " + m for m in err))
        key, vocab, bareme = fichiers(ex, langue, base, source.name, premier)
        for suffixe, contenu in ((".key.json", key), (".vocab.json", vocab), (".bareme.json", bareme)):
            if contenu is not None:
                texte = json.dumps(contenu, ensure_ascii=False, indent=1) + "\n"
                (corriges / f"{base}{suffixe}").write_text(texte, encoding="utf-8")
        n = sum(len(p["fields"]) for p in gab["pages"])
        log(f"{langue} : {gab['page_count']} pages, {n} champs, zones conformes ; {c['sujet'].name}, "
              f"{c['corrige'].name}, {gp.name}, {base}.key.json")
        premier = premier or base
