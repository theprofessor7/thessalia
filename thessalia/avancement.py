"""Avancement d'une tâche longue, pour la jauge de l'application.

Les modules de calcul (lecture du code, second lecteur, pré-cochage…) appellent `signaler(fait, total, texte)` ; la
tâche de l'application branche ici sa jauge (`brancher`) le temps de son exécution. En ligne de commande, rien n'est
branché : `signaler` ne fait rien et seuls les messages habituels s'affichent.
"""
from __future__ import annotations

_jauge = None
_prefixe = ""


def brancher(fn):
    """fn(pc, texte) : jauge de la tâche en cours (pc None : jauge qui défile) ; None pour débrancher."""
    global _jauge, _prefixe
    _jauge, _prefixe = fn, ""


def etape(prefixe=""):
    """Préfixe des textes de la jauge (« étape 1/3 · ») : une tâche en plusieurs étapes dit où elle en est."""
    global _prefixe
    _prefixe = prefixe


def attendre(texte=""):
    """Travail en cours sans mesure encore (chargement d'un modèle, premier élément) : la jauge défile."""
    if _jauge is not None:
        _jauge(None, _prefixe + texte)


def signaler(fait, total, texte=""):
    if _jauge is not None and total:
        _jauge(100 * fait // total, _prefixe + texte)
