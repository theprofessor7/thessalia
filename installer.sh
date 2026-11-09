#!/bin/sh
# Installation de Thessalia (macOS / Linux) : ./installer.sh [--lecteur oui|non]. Lance installer.py.
cd "$(dirname "$0")"
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then exec "$c" installer.py "$@"; fi
done
echo "ÉCHEC : Python est introuvable (https://www.python.org/downloads/), puis relancer."
exit 1
