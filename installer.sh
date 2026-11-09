#!/bin/sh
# Installation de Thessalia sous macOS / Linux (à relancer sans risque, par exemple après une mise à jour).
#   ./installer.sh            pose la question du lecteur d'écriture
#   ./installer.sh oui|non    installer ou non le lecteur d'écriture (TrOCR, ~2 Go)
set -e
cd "$(dirname "$0")"
arret() { echo; echo "ÉCHEC : $1"; exit 1; }

echo "=== Thessalia : installation dans $(pwd)"
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || arret "Python 3.10 ou plus récent est introuvable (https://www.python.org/downloads/), puis relancer."
echo "$($PY --version) trouvé."

[ -x .venv/bin/python ] || { echo "Création de l'environnement .venv…"; "$PY" -m venv .venv || arret "création de .venv impossible"; }
P=.venv/bin/python

LECTEUR="$1"
if [ -z "$LECTEUR" ]; then
  if $P -c 'import importlib.util as u, sys; sys.exit(not (u.find_spec("torch") and u.find_spec("transformers")))' 2>/dev/null; then
    LECTEUR=oui
  else
    echo
    echo "Lecteur d'écriture (réponses courtes lues automatiquement) : ~2 Go à télécharger."
    echo "Sans lui, tout fonctionne, les réponses courtes se corrigent à la main dans l'outil."
    printf "L'installer ? (o/N) "; read r
    case "$r" in [oOyY]*) LECTEUR=oui ;; *) LECTEUR=non ;; esac
  fi
fi
EXTRAS=serveur; [ "$LECTEUR" = oui ] && EXTRAS=serveur,trocr
echo "Installation des bibliothèques ($EXTRAS), quelques minutes…"
$P -m pip install --upgrade pip --quiet
$P -m pip install -e ".[$EXTRAS]" || arret "pip install a échoué (connexion internet ? message ci-dessus)"
$P -c "import flask, typst, cv2, pymupdf; from thessalia.serve import create_app; create_app([], 'data/correction.sqlite', examens='examens')" \
  || arret "l'application ne se charge pas (message ci-dessus)"
chmod +x Thessalia.command 2>/dev/null || true
echo
echo "Installation terminée. Pour lancer Thessalia : double-cliquer sur Thessalia.command (ou ./Thessalia.command)"
echo "Facultatif, pour la préparation de nuit (code manuscrit) : Ollama, voir docs/MODE_EMPLOI.md"
