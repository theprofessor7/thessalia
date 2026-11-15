"""Sujet source unique (docs/FORMAT_SUJET.md) : lecture stricte, contrôle, production.

`produire_tout` (page de l'examen, « Produire les sujets ») : pour chaque langue, sujet et corrigé PDF (Typst),
zones, gabarit lu dans le PDF et fichiers de corrigé (.key.json, .vocab.json, .bareme.json) ; refusé si une zone
n'est pas conforme au PDF ou si le gabarit ne colle pas à la source.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .corrige import confronter, fichiers


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
    # tests d'exécution du code (tests_python) : copiés avec les corrigés, l'examen se suffit à lui-même
    for q in ex.questions():
        t = q.donnees.get("tests_python")      # rangé dans les données de la question (modele.q_code)
        if t:
            src = next((p for p in (Path(source).parent / t, Path(t)) if p.is_file()), None)
            if src is None:
                raise SystemExit(f"q{q.num} : fichier de tests introuvable : {t} (cherché à côté de la source)")
            if src.resolve() != (corriges / src.name).resolve():
                shutil.copyfile(src, corriges / src.name)
