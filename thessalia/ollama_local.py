"""Ollama et ses modèles, installés depuis l'application en un clic (plus de commandes à taper).

Ollama est un logiciel gratuit qui fait tourner sur ce PC les modèles de la lecture approfondie (`preparer`) :
lecteur du code manuscrit, second lecteur des réponses courtes, réparateur. Rien n'est envoyé sur internet pendant
la correction ; internet ne sert qu'à télécharger Ollama et les modèles, une fois.

- Windows : l'installeur officiel (https://ollama.com/download/OllamaSetup.exe) est téléchargé puis lancé en mode
  silencieux ; il s'installe pour l'utilisateur, sans droits d'administrateur, et démarre Ollama.
- macOS, Linux : la page de téléchargement d'Ollama s'ouvre (installation non automatisée, pas testée ici).
- Modèles : téléchargés par Ollama lui-même (api/pull), progression dans le journal de la tâche.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"
INSTALLEUR_WINDOWS = "https://ollama.com/download/OllamaSetup.exe"
PAGE = "https://ollama.com/download"

# (modèle, rôle, taille approximative) ; l'ordre est celui de l'affichage
MODELES = [
    ("qwen3-vl:8b-instruct", "lit le code écrit à la main", "6 Go"),
    ("qwen3-vl:4b-instruct", "relit les réponses courtes en revue", "3 Go"),
    ("qwen3:14b", "répare les petites fautes du code avant les tests (facultatif)", "9 Go"),
]


def executable():
    """Chemin d'ollama s'il est installé, sinon None."""
    p = shutil.which("ollama")
    if p:
        return p
    if os.name == "nt":
        q = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        return str(q) if q.exists() else None
    for q in ("/usr/local/bin/ollama", "/Applications/Ollama.app/Contents/Resources/ollama"):
        if Path(q).exists():
            return q
    return None


def modeles_installes():
    """Noms des modèles présents, ou None si Ollama ne répond pas."""
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3) as r:
            return [m["name"] for m in json.load(r)["models"]]
    except Exception:
        return None


def etat():
    installes = modeles_installes()
    return {"installe": executable() is not None or installes is not None, "lance": installes is not None,
            "windows": os.name == "nt",
            "modeles": [{"nom": n, "role": r, "taille": t, "present": bool(installes) and n in installes}
                        for n, r, t in MODELES]}


def _attendre(log, secondes=90):
    t0 = time.time()
    while time.time() - t0 < secondes:
        if modeles_installes() is not None:
            return True
        time.sleep(2)
    return False


def demarrer(log=print):
    """Lance Ollama s'il est installé mais arrêté (il tourne ensuite en arrière-plan)."""
    if modeles_installes() is not None:
        return True
    exe = executable()
    if exe is None:
        raise SystemExit("Ollama n'est pas installé.")
    log("Démarrage d'Ollama…")
    drapeaux = {"creationflags": 0x00000008 | 0x00000200} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **drapeaux)
    if not _attendre(log, 30):
        raise SystemExit("Ollama ne démarre pas : le lancer depuis le menu Démarrer, puis réessayer.")
    log("Ollama est démarré.")
    return True


def installer(log=print):
    """Windows : télécharge et installe Ollama sans question. Ailleurs : ouvre la page de téléchargement."""
    if etat()["installe"]:
        log("Ollama est déjà installé.")
        return demarrer(log)
    if os.name != "nt":
        webbrowser.open(PAGE)
        raise SystemExit(f"Sur ce système, installer Ollama depuis la page qui vient de s'ouvrir ({PAGE}), "
                         "puis revenir ici pour les modèles.")
    dest = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    log(f"Téléchargement de l'installeur d'Ollama ({INSTALLEUR_WINDOWS})…")
    _telecharger(INSTALLEUR_WINDOWS, dest, log)
    log("Installation (quelques minutes, sans question ; une fenêtre de progression peut apparaître)…")
    r = subprocess.run([str(dest), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=False)
    if r.returncode != 0:
        raise SystemExit(f"l'installeur d'Ollama s'est arrêté (code {r.returncode}) : l'installer depuis {PAGE}")
    try:
        dest.unlink()
    except OSError:
        pass
    if not _attendre(log, 90):
        demarrer(log)
    log("Ollama est installé et démarré. Reste à télécharger les modèles.")


class _Progres:
    """Avancement d'un téléchargement : jauge de la page si elle existe (log.progression), sinon une ligne
    du journal tous les 10 %."""

    def __init__(self, log):
        self.log, self.jauge, self.dernier = log, getattr(log, "progression", None), -10

    def __call__(self, fait, total, unite=1e9, nom="Go"):
        if not total:
            return
        pc = int(fait * 100 / total)
        texte = f"{fait / unite:.1f} / {total / unite:.1f} {nom}"
        if self.jauge:
            self.jauge(pc, texte)
        elif pc >= self.dernier + 10:
            self.log(f"  {pc} % ({texte})")
            self.dernier = pc


def _telecharger(url, dest, log):
    progres = _Progres(log)
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
        total, fait = int(r.headers.get("Content-Length") or 0), 0
        while True:
            bloc = r.read(1 << 20)
            if not bloc:
                break
            f.write(bloc)
            fait += len(bloc)
            progres(fait, total, 1e6, "Mo")


def telecharger_modele(nom, log=print):
    """Télécharge un modèle par Ollama ; relancer reprend où le téléchargement s'était arrêté."""
    if nom not in {n for n, _, _ in MODELES}:
        raise SystemExit(f"modèle inconnu : {nom}")
    demarrer(log)
    log(f"Téléchargement de {nom} (une fois ; plusieurs Go, cela peut prendre longtemps)…")
    req = urllib.request.Request(OLLAMA + "/api/pull", data=json.dumps({"model": nom, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    progres, couches, dernier = _Progres(log), {}, None
    with urllib.request.urlopen(req, timeout=600) as r:
        for ligne in r:
            if not ligne.strip():
                continue
            m = json.loads(ligne)
            if m.get("error"):
                raise SystemExit(f"Ollama : {m['error']}")
            if m.get("total") and m.get("digest"):     # un modèle = plusieurs fichiers : avancement global
                couches[m["digest"]] = (m.get("completed", 0), m["total"])
                progres(sum(c for c, _ in couches.values()), sum(t for _, t in couches.values()))
                continue
            st = m.get("status", "")
            if st != dernier and not st.startswith("pulling "):
                log(f"  {st}")
                dernier = st
    if nom not in (modeles_installes() or []):
        raise SystemExit(f"{nom} : téléchargement terminé mais modèle absent d'Ollama")
    log(f"{nom} est prêt.")


def supprimer_modele(nom, log=print):
    """Retire un modèle d'Ollama (libère sa place sur le disque) ; il se retélécharge d'un clic."""
    if nom not in {n for n, _, _ in MODELES}:
        raise SystemExit(f"modèle inconnu : {nom}")
    req = urllib.request.Request(OLLAMA + "/api/delete", data=json.dumps({"model": nom}).encode(), method="DELETE",
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except Exception as e:
        raise SystemExit(f"{nom} : suppression impossible ({e})")
    log(f"{nom} supprimé.")


if __name__ == "__main__":       # essai : python -m thessalia.ollama_local
    json.dump(etat(), sys.stdout, ensure_ascii=False, indent=1)
