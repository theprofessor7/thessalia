"""Comparaison d'une lecture à la vérité, pour mesurer les lecteurs (page Apprentissage : affinage du lecteur
d'écriture et du lecteur de chiffres). Une lecture compte juste si elle donne la même note que la vérité.
"""
from __future__ import annotations

from .vocab import normalize, parse_number


def _eq(lu, vrai):
    """Même valeur, ou équivalence de la notation (notes._equiv, dans le sens lecture -> vérité) : `Error` lu pour
    `ERREUR` n'est pas une faute, mais `Zéro` lu pour `Zero` (copie EN) en est une, comme dans la note."""
    from .notes import _equiv
    return lu == vrai or _equiv(lu, vrai)


def same(a, b, kind):
    """a : lecture, b : vérité."""
    if kind == "number":
        na, nb = parse_number(a) or normalize(a, kind), parse_number(b) or normalize(b, kind)
        return _eq(na, nb)
    if kind == "text":
        return normalize(a, "enum") == normalize(b, "enum")  # tolérant aux espaces pour le texte
    return _eq(normalize(a, kind), normalize(b, kind))
