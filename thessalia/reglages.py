"""Réglages généraux de l'application (page « Réglages ») : `data/reglages.json`, propres à ce PC.

Un examen peut garder ses propres valeurs dans `examens/<nom>/reglages.json` ; sinon il suit ces réglages.
"""
from __future__ import annotations

import json
from pathlib import Path

FICHIER = Path("data/reglages.json")
DEFAUTS = {"arrondi_demi_point": True}


def lire(fichier=None) -> dict:
    p = Path(fichier or FICHIER)
    lu = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {k: lu.get(k, v) for k, v in DEFAUTS.items()}


def ecrire(fichier=None, **valeurs) -> dict:
    p = Path(fichier or FICHIER)
    r = lire(p)
    r.update({k: v for k, v in valeurs.items() if k in DEFAUTS})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(r, indent=1), encoding="utf-8")
    return r
