"""Contrôle des attributions avant l'export (page « Vérifier les noms » de l'application) : les copies à risque
passent en tête, avec la raison.

  - nom proche   l'élève attribué a un nom très proche d'un autre élève du groupe (DUBOIS / DUBOST) ;
  - proche d'un absent   l'élève attribué est à deux rangs ou moins d'un absent dans la liste du groupe,
                ou son nom commence par les deux mêmes lettres : une erreur de clic sur une ligne voisine
                laisse un présent « absent » (MERLIN / MESNIL : trois rangs, même début « ME ») ;
  - autre groupe   l'élève attribué n'est pas du groupe de la classe où la copie a été scannée.
Mesuré le 23 octobre 2026 sur 314 copies : les 3 erreurs d'attribution trouvées à la main sont toutes en tête.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from .correction import group_of
from .identite import _norm

SEUIL_PROCHE = 0.75     # ressemblance de NOM au-delà de laquelle deux élèves d'un groupe sont « proches »
RANGS_ABSENT = 2        # distance (dans la liste triée du groupe) à un absent


def _nom(eleve):
    parts = eleve.split(" ")
    k = next((i for i, w in enumerate(parts) if not w.isupper()), len(parts))
    return " ".join(parts[:k]) or eleve


def risques(attributions, liste, seuil=SEUIL_PROCHE, rangs=RANGS_ABSENT, convoques=None):
    """attributions : [(classe, copie, élève)] ; liste : {groupe: [élèves]} -> {(classe, copie): [raisons]}.
    convoques : {classe: [élèves]} pour une session à part (BIS) : seuls les convoqués comptent comme absents
    possibles, et un convoqué n'est pas « d'un autre groupe »."""
    convoques = convoques or {}
    groupe_de = {e: g for g, es in liste.items() for e in es}
    pris = {e for _, _, e in attributions}
    attendus = set().union(*map(set, convoques.values())) if any(convoques.values()) else set(groupe_de)
    out = {}
    for cl, cid, e in attributions:
        raisons = []
        g = groupe_de.get(e)
        if g is None:
            raisons.append("élève absent de la liste")
        else:
            eleves = sorted(liste[g])
            proches = [x for x in eleves if x != e
                       and SequenceMatcher(None, _norm(_nom(e)), _norm(_nom(x))).ratio() >= seuil]
            if proches:
                raisons.append("nom proche de " + ", ".join(proches))
            i = eleves.index(e)
            debut = _norm(_nom(e))[:2]
            absents = [x for j, x in enumerate(eleves) if x not in pris and x in attendus
                       and (abs(j - i) <= rangs or _norm(_nom(x))[:2] == debut)]
            if absents:
                raisons.append("proche d'un absent : " + ", ".join(absents))
            if g != group_of(cl) and e not in convoques.get(cl, ()):
                raisons.append(f"élève du groupe {g}, copie scannée en {group_of(cl)}")
        out[(cl, cid)] = raisons
    return out
