"""Mise à jour de Thessalia depuis l'application (page « Réglages ») : l'équivalent de « git pull, relancer
l'installeur » de MODE_EMPLOI, en un clic.

Prudence d'abord : rien n'est écrasé. Avance rapide seulement (`git pull --ff-only`) ; refus si un fichier suivi
par git a été modifié sur ce PC (la liste est donnée). Les examens, scans, décisions et réglages (`examens/`,
`data/`) sont hors git : une mise à jour n'y touche jamais. Les bibliothèques ne sont réinstallées que si
`pyproject.toml` a changé. Le code déjà chargé reste celui d'avant : il faut relancer Thessalia, ce qui est dit
à la fin (pas de redémarrage automatique : `git pull` peut réécrire Thessalia.bat pendant que Windows l'exécute).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

DEPOT = Path(__file__).resolve().parent.parent


def _git(*args, verifier=True):
    r = subprocess.run(["git", *args], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    if verifier and r.returncode:
        raise SystemExit(f"git {args[0]} a échoué : {(r.stderr or r.stdout).strip()[:400]}")
    return r.stdout.rstrip()          # pas strip : « git status --porcelain » commence par un espace


def possible():
    """None si la mise à jour en un clic est possible, sinon la raison (en clair)."""
    if shutil.which("git") is None:
        return "git n'est pas installé sur ce PC (voir MODE_EMPLOI, « Installer, une fois »)"
    if not (DEPOT / ".git").exists():
        return "ce dossier Thessalia n'a pas été obtenu par « git clone » (MODE_EMPLOI, « Installer, une fois »)"
    return None


def version():
    """Commit en place et sa date, pour la page Réglages (sans réseau)."""
    if possible():
        return None
    r = _git("log", "-1", "--format=%h|%cd", "--date=format:%d/%m/%Y", verifier=False)
    return dict(zip(("commit", "date"), r.split("|"))) if "|" in r else None


def mettre_a_jour(log=print):
    raison = possible()
    if raison:
        raise SystemExit(f"Mise à jour impossible : {raison}.")
    log("Recherche des nouveautés…")
    _git("fetch", "--quiet")
    amont = _git("rev-parse", "--abbrev-ref", "@{u}", verifier=False)
    if not amont:
        raise SystemExit("Mise à jour impossible : la branche locale ne suit aucune branche distante.")
    nouveautes = _git("log", "--format=%s", "HEAD..@{u}").splitlines()
    if not nouveautes:
        log("Thessalia est déjà à jour.")
        return
    modifies = [ligne[3:] for ligne in _git("status", "--porcelain", "--untracked-files=no").splitlines()]
    if modifies:
        raise SystemExit("Mise à jour refusée : des fichiers de Thessalia ont été modifiés sur ce PC "
                         f"({', '.join(modifies[:8])}{'…' if len(modifies) > 8 else ''}). Rien n'a été touché. "
                         "Demander à l'auteur avant de les annuler.")
    log(f"{len(nouveautes)} nouveauté{'s' if len(nouveautes) > 1 else ''} :")
    for s in reversed(nouveautes[:40]):
        log("  · " + s)
    avant = _git("rev-parse", "HEAD")
    _git("pull", "--ff-only", "--quiet")
    if "pyproject.toml" in _git("diff", "--name-only", avant, "HEAD").splitlines():
        _reinstaller(log)
    log("Mise à jour installée. Pour l'utiliser : fermer la fenêtre noire de Thessalia, puis relancer Thessalia.")


def _reinstaller(log):
    from .extensions import _executer

    extras = "serveur,trocr" if find_spec("torch") and find_spec("transformers") else "serveur"
    log(f"Bibliothèques à mettre à jour ({extras}), quelques minutes…")
    env = dict(os.environ)
    tmp = Path(sys.prefix) / "tmp"           # comptes Windows de l'école : pas de « $ » dans TEMP (cf. installer.py)
    tmp.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
    if _executer([sys.executable, "-m", "pip", "install", "-e", f"{DEPOT}[{extras}]"], log, env):
        raise SystemExit("Le code est à jour mais l'installation des bibliothèques a échoué (connexion internet ?) : "
                         "fermer Thessalia et double-cliquer sur l'installeur.")
