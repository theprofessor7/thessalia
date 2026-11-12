"""Avancement d'une tâche longue, pour la jauge de l'application.

Les modules de calcul (lecture du code, second lecteur, pré-cochage…) appellent `signaler(fait, total, texte)` ; la
tâche de l'application branche ici sa jauge (`brancher`) le temps de son exécution. En ligne de commande, rien n'est
branché : `signaler` ne fait rien et seuls les messages habituels s'affichent.
"""
from __future__ import annotations

_jauge = None


def brancher(fn):
    """fn(pc, texte) : jauge de la tâche en cours ; None pour débrancher."""
    global _jauge
    _jauge = fn


def signaler(fait, total, texte=""):
    if _jauge is not None and total:
        _jauge(100 * fait // total, texte)
