#!/bin/sh
# Lance Thessalia (macOS : double-cliquer ; Linux : ./Thessalia.command). Fermer la fenêtre arrête Thessalia.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Thessalia n'est pas encore installé : lancer d'abord ./installer.sh"
  exit 1
fi
exec .venv/bin/python -m thessalia app
