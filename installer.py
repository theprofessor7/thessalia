"""Installation de Thessalia (Windows, macOS, Linux) : à relancer sans risque, par exemple après une mise à jour.

    Windows : double-cliquer sur installer.bat (ou : py installer.py)
    macOS / Linux : ./installer.sh (ou : python3 installer.py)

    --lecteur oui|non : installer ou non le lecteur d'écriture (TrOCR, ~2 Go) sans poser la question

Uniquement Python et sa bibliothèque standard : aucun script PowerShell, rien à autoriser de plus que Python.
"""
import argparse
import functools
import os
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
WINDOWS = os.name == "nt"
print = functools.partial(print, flush=True)     # messages dans l'ordre, entre ceux de pip
PY = ICI / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")


def arret(message):
    print(f"\nÉCHEC : {message}")
    sys.exit(1)


def lancer(*args, **kw):
    return subprocess.run([str(a) for a in args], cwd=ICI, **kw).returncode


def main():
    a = argparse.ArgumentParser(description="Installation de Thessalia")
    a.add_argument("--lecteur", choices=["oui", "non"], help="lecteur d'écriture (TrOCR, ~2 Go)")
    args = a.parse_args()

    print(f"=== Thessalia : installation dans {ICI}")
    if sys.version_info < (3, 10):
        arret(f"Python {sys.version.split()[0]} est trop ancien : il faut Python 3.10 ou plus récent "
              "(https://www.python.org/downloads/).")
    print(f"Python {sys.version.split()[0]} trouvé.")
    if "$" in str(ICI):
        arret("le chemin du dossier contient « $ », ce que l'installation de Python refuse. "
              "Cloner Thessalia ailleurs, par exemple C:\\Thessalia.")

    # 1. Environnement propre à Thessalia (.venv), sans toucher au reste du PC
    if not PY.exists():
        print("Création de l'environnement .venv…")
        if lancer(sys.executable, "-m", "venv", ".venv"):
            arret("création de .venv impossible (message ci-dessus)")

    # 2. Lecteur d'écriture : facultatif (gros téléchargement)
    lecteur = args.lecteur
    if lecteur is None:
        deja = lancer(PY, "-c", "import importlib.util as u, sys; "
                                "sys.exit(not (u.find_spec('torch') and u.find_spec('transformers')))") == 0
        if deja:
            lecteur = "oui"
        else:
            print("\nLecteur d'écriture (réponses courtes lues automatiquement) : ~2 Go à télécharger.")
            print("Sans lui, tout fonctionne, les réponses courtes se corrigent à la main dans l'outil.")
            try:
                r = input("L'installer ? (o/N) ")
            except EOFError:
                r = ""
            lecteur = "oui" if r.strip().lower().startswith(("o", "y")) else "non"

    # 3. Bibliothèques. Comptes Windows gérés de l'école (« $IM7000-… ») : un « $ » dans le dossier temporaire fait
    #    échouer setuptools (« invalid variable ») ; on travaille dans un dossier temporaire à nous
    env = dict(os.environ)
    tmp = ICI / ".venv" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
    extras = "serveur,trocr" if lecteur == "oui" else "serveur"
    print(f"\nInstallation des bibliothèques ({extras}), quelques minutes…")
    lancer(PY, "-m", "pip", "install", "--upgrade", "pip", "--quiet", env=env)
    if lancer(PY, "-m", "pip", "install", "-e", f".[{extras}]", env=env):
        arret("pip install a échoué (connexion internet ? message ci-dessus)")

    # 4. Contrôle : l'application se charge-t-elle ?
    if lancer(PY, "-c", "import flask, typst, cv2, pymupdf; from thessalia.serve import create_app; "
                        "create_app([], 'data/correction.sqlite', examens='examens')"):
        arret("l'application ne se charge pas (message ci-dessus)")
    if not WINDOWS:
        (ICI / "Thessalia.command").chmod(0o755)

    print("\nInstallation terminée. Pour lancer Thessalia : double-cliquer sur "
          + ("Thessalia.bat" if WINDOWS else "Thessalia.command (ou ./Thessalia.command)"))
    print("Facultatif, pour la préparation de nuit (code manuscrit) : Ollama, voir docs/MODE_EMPLOI.md")


if __name__ == "__main__":
    main()
