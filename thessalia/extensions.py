"""Extensions de l'application (page « Réglages ») : ce qui s'installe en plus, en un clic, comme des modules.

- Lecteur d'écriture (TrOCR) : bibliothèques torch / transformers (pip, dans l'environnement de Thessalia) et
  poids du modèle microsoft/trocr-base-handwritten (Hugging Face), environ 2 Go en tout.
- Ollama et ses modèles : voir thessalia/ollama_local.py.

Tout se télécharge une fois ; la correction se fait ensuite sans internet.
"""
from __future__ import annotations

import os
import subprocess
import sys
from importlib import invalidate_caches
from importlib.util import find_spec
from pathlib import Path

from . import ollama_local

TROCR = "microsoft/trocr-base-handwritten"
PAQUETS_TROCR = ["torch>=2.1", "transformers>=4.40", "sentencepiece"]


def _cache_hf() -> Path:
    base = os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface"
    return Path(base) / "hub" / ("models--" + TROCR.replace("/", "--"))


def trocr_etat():
    invalidate_caches()
    biblio = bool(find_spec("torch") and find_spec("transformers"))
    return {"biblio": biblio, "poids": _cache_hf().exists(), "installe": biblio and _cache_hf().exists()}


def _executer(cmd, log, env=None):
    """Lance une commande et recopie sa sortie, ligne à ligne, dans le journal de la tâche."""
    p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", env=env)
    for ligne in p.stdout:
        ligne = ligne.rstrip()
        if ligne and not ligne.startswith(("  Downloading", "  Using cached", "Requirement already")):
            log(ligne[:200])
    return p.wait()


def installer_trocr(log=print):
    env = dict(os.environ)
    # comptes Windows gérés de l'école (« $IM7000-… ») : un « $ » dans TEMP fait échouer certaines installations
    tmp = Path(sys.prefix) / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
    if not trocr_etat()["biblio"]:
        log("Installation des bibliothèques (torch, transformers : environ 1 Go, plusieurs minutes)…")
        if _executer([sys.executable, "-m", "pip", "install", *PAQUETS_TROCR], log, env):
            raise SystemExit("l'installation des bibliothèques a échoué (connexion internet ? message ci-dessus)")
    log(f"Téléchargement du modèle {TROCR} (environ 1,3 Go)…")
    code = ("from transformers import TrOCRProcessor, VisionEncoderDecoderModel as M; "
            f"TrOCRProcessor.from_pretrained('{TROCR}'); M.from_pretrained('{TROCR}'); print('modèle prêt')")
    if _executer([sys.executable, "-c", code], log, env):
        raise SystemExit("le téléchargement du modèle a échoué (connexion internet ? message ci-dessus)")
    if not trocr_etat()["installe"]:
        raise SystemExit("installation terminée mais le lecteur d'écriture reste introuvable : relancer Thessalia")
    log("Lecteur d'écriture prêt.")


def etat():
    """Cartes de la page Réglages, dans l'ordre d'affichage."""
    t, o = trocr_etat(), ollama_local.etat()
    cartes = [{"id": "trocr", "nom": "Lecteur d'écriture", "taille": "2 Go",
               "description": "Lit les réponses courtes et les noms écrits à la main (étape 4 d'un examen).",
               "installe": t["installe"], "actions": [] if t["installe"] else [("installer", "Installer")]},
              {"id": "ollama", "nom": "Ollama", "taille": "1 Go",
               "description": "Logiciel gratuit qui fait tourner sur ce PC les modèles de la lecture approfondie (code manuscrit, relecture).",
               "installe": o["installe"],
               "etat": "démarré" if o["lance"] else ("arrêté" if o["installe"] else None),
               "actions": ([("installer", "Installer" if o["windows"] else "Télécharger")] if not o["installe"]
                           else [] if o["lance"] else [("demarrer", "Démarrer")])}]
    for m in o["modeles"]:
        cartes.append({"id": m["nom"], "nom": m["nom"], "taille": m["taille"], "modele": True,
                       "description": m["role"][:1].upper() + m["role"][1:] + ".", "installe": m["present"],
                       "requis": "Ollama démarré" if not o["lance"] else None,
                       "actions": [("supprimer", "Supprimer")] if m["present"] else
                                  [("telecharger", "Télécharger")] if o["lance"] else []})
    return cartes


def agir(ident, action, log=print):
    if ident == "trocr" and action == "installer":
        return installer_trocr(log)
    if ident == "ollama" and action == "installer":
        return ollama_local.installer(log)
    if ident == "ollama" and action == "demarrer":
        return ollama_local.demarrer(log)
    if action == "telecharger":
        return ollama_local.telecharger_modele(ident, log)
    if action == "supprimer":
        return ollama_local.supprimer_modele(ident, log)
    raise SystemExit(f"action inconnue : {ident} / {action}")
