# Thessalia

Correction assistée des copies papier scannées des examens Python ESME : QCM et vrai/faux lus automatiquement,
réponses courtes lues et rapprochées du corrigé, code manuscrit transcrit et pré-coché en l'exécutant. L'enseignant
décide de tout ce qui reste douteux, à la souris, dans le navigateur ; la machine apprend de ses décisions.

Tout tourne en local, gratuitement, sans GPU (Windows, macOS, Linux). Aucune donnée d'élève ne quitte le PC.

## Enseignants

1. Installer une fois : double-cliquer sur `installer.bat` (Windows) ou lancer `installer.sh` (macOS, Linux).
   Il faut Python 3.10 ou plus récent ; l'installeur propose le lecteur d'écriture (~2 Go).
2. Lancer : `Thessalia.bat` / `Thessalia.command`. Le navigateur s'ouvre sur l'application.

Mode d'emploi, par l'exemple d'une vraie classe : [`docs/MODE_EMPLOI.md`](docs/MODE_EMPLOI.md)
(et sa version PDF illustrée, `docs/Thessalia_mode_emploi.pdf`).

Un examen part :
- soit d'un **sujet source** (YAML, [`docs/FORMAT_SUJET.md`](docs/FORMAT_SUJET.md)) : Thessalia produit le sujet
  PDF, le corrigé et tout ce qu'il faut pour lire les copies ;
- soit d'un **sujet produit ailleurs** (générateur d'un collègue, au format Thessalia : carrés noirs aux coins,
  zones de réponse) : accueil de l'application, « Importer un sujet produit par un autre générateur », avec le
  PDF, le corrigé (`.key.json`) et le vocabulaire (`.vocab.json`) de chaque langue.

La lecture approfondie (code manuscrit, relecture des réponses courtes) utilise des modèles locaux servis par
[Ollama](https://ollama.com), installables depuis la page « Réglages ». Sans eux l'application marche, en moins aidée.

## Conseils de numérisation

Format **A4** (pas A3), 200 à 300 dpi, niveaux de gris ou couleur (**pas de noir & blanc 1 bit**), désactiver la
suppression automatique des pages blanches, un seul PDF par classe dans l'ordre des copies.

## Développement

Lire `CLAUDE.md` (principes, commandes), `HANDOFF.md` (où on en est, chiffres mesurés) et `ARCHITECTURE.md`.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -e ".[serveur,trocr,dev]"
pytest -q
python -m thessalia app                                # l'application
python -m thessalia --help                             # autres commandes : importer, verif-zones, transcrire, simulate, evaluate
```

Pas besoin de poppler : PyMuPDF rend les PDF et lit leur contenu vectoriel ; Typst (paquet Python) met en page
les sujets. Seule option payante : la transcription du code par un service en ligne (`transcrire`), sur clé de
l'utilisateur et avec plafond de dépense.

### Tester sans vrais scans

```bash
python -m thessalia simulate -t <gabarit.json> -b <sujet.pdf> -o sim/lot -n 12 --hard   # copies remplies et scannées + truth.json
python -m thessalia evaluate sim/lot -t <gabarit.json> -b <sujet.pdf>                    # 0 « FAUSSES » exigé
```

### Réglages de la lecture des cases

Dans le gabarit, clé `"omr"` :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `empty_max` / `checked_min` | 0.06 / 0.14 | seuils de taux d'encre (entre les deux : revue) |
| `faint_min` | 0.12 | trace claire (crayon, encre pâle) dans une case « vide » → revue |
| `full_policy` | `auto` | case noircie : `auto` (seule → cochée, à côté d'une autre → revue), `checked`, `cancelled` ou `review` |
| `halo_rature` | 0.08 | encre autour d'une case très encrée → rature probable → revue |
| `core_min` | 0.02 | case « cochée » sans encre au centre (case redessinée après correcteur) → revue |

Licence : GPL v3.
