# Thessalia

Lecture automatique des copies papier scannées des examens Python ESME — **niveau 1 : QCM et vrai/faux**, avec découpe des zones manuscrites (identité, réponses courtes, code) prêtes pour les niveaux 2 et 3.

**Enseignants** : installation (`installer.bat` / `installer.sh`), lancement (`Thessalia.bat` /
`Thessalia.command`) et utilisation de l'application : [`docs/MODE_EMPLOI.md`](docs/MODE_EMPLOI.md).

Architecture, formats JSON, résultats mesurés et feuille de route niveaux 2–4 : [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Installation (projet local, portable)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -e .                       # Niveau 1 : opencv, numpy, pymupdf, pillow
pip install -e ".[trocr]"              # Niveau 2, moteur local recommandé (gratuit)
pip install -e ".[ocr-light,dev]"      # moteurs légers + tests (pytest -q)
```
Pas besoin de poppler : PyMuPDF rend les PDF et lit leur contenu vectoriel. Aucun abonnement requis ;
les moteurs payants (`--backend claude|google`) ne s'activent que si une clé est fournie.

Reprise du développement : lire `HANDOFF.md` et `CLAUDE.md`.

## Utilisation en ligne de commande

Les sujets et corrigés d'examen ne sont pas dans le dépôt (`templates/`, `keys/`, `sujets/` restent sur le PC
de l'enseignant). Un sujet se décrit dans un fichier source (`docs/FORMAT_SUJET.md`) ; l'application produit son
gabarit et ses corrigés.

```bash
# 1. Une fois par sujet : gabarit depuis le PDF vierge (coordonnées exactes, lues dans le PDF)
python -m thessalia template templates/<sujet>.pdf \
       -o templates/<sujet>.json --exam-id <sujet>

# 2. Traiter un lot de scans (PDF multipages, images, TIFF, ou dossier)
#    -k (optionnel) : corrigé pour noter les QCM
python -m thessalia process scans/lot_TD1.pdf \
       -t templates/<sujet>.json \
       -b templates/<sujet>.pdf \
       -k keys/<sujet>.key.json \
       -o sorties/lot_TD1
```

Sortie :

```
sorties/lot_TD1/
  results.csv            une ligne par copie, une colonne par case (q1.a … q9.d), score
  results.json           idem en JSON ({question_id.option: bool})
  review.csv             ce que l'humain doit regarder (case ambiguë, 2 cases en choix unique, page manquante…)
  copy_001/
    result.json          détail complet (taux d'encre, états, statuts, notes)
    pages/p03_overlay.jpg  page redressée annotée : vert = cochée, gris = vide, orange = ambiguë, rouge = noircie
    crops/identity.nom.png, q2.1.png, q12.png …   vignettes pour niveaux 2/3 et la revue
```

Niveau 2 (réponses courtes), après `process` :

```bash
python -m thessalia ocr sorties/lot_TD1 -v keys/<sujet>.vocab.json --backend trocr
# -> short_answers.csv (valeurs lues, « ? » = à valider) et ocr_review.csv (propositions)
```

Si le sujet change : régénérer le gabarit avec `--merge ancien.json` pour garder les réglages faits à la main (`mode`, `vocab`).

## Réglages utiles

Dans le gabarit, clé `"omr"` (ou `--full-policy` en ligne de commande) :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `empty_max` / `checked_min` | 0.06 / 0.14 | seuils de taux d'encre (entre les deux : revue) |
| `faint_min` | 0.12 | trace claire (crayon, encre pâle) dans une case « vide » → revue |
| `full_policy` | `auto` | case noircie : `auto` (seule → cochée, à côté d'une autre → revue), `checked`, `cancelled` ou `review` |
| `halo_rature` | 0.08 | encre autour d'une case très encrée → rature probable → revue |
| `core_min` | 0.02 | case « cochée » sans encre au centre (case redessinée après correcteur) → revue |

## Tester sans vrais scans

```bash
python -m thessalia simulate -t templates/<sujet>.json -b templates/<sujet>.pdf \
       -o sim/lot -n 10 --hard            # copies remplies + scannées synthétiques + truth.json
python -m thessalia process sim/lot/scans.pdf -t … -b … -o out/lot
python -m thessalia evaluate out/lot sim/lot/truth.json
```

Le même `evaluate` servira sur de vrais scans : saisir la vérité d'une dizaine de copies dans un `truth.json` au même format.

## Conseils de numérisation

Format **A4** (pas A3), 200 à 300 dpi, niveaux de gris ou couleur (**pas de noir & blanc 1 bit**), désactiver la suppression automatique des pages blanches, un seul PDF par lot dans l'ordre des copies.
