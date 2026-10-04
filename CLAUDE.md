# CLAUDE.md — consignes pour travailler sur Thessalia

Projet d'un enseignant de l'ESME : lire automatiquement les copies papier scannées des examens Python
(secours de Moodle). Utilisateurs : enseignants, collègues de l'auteur. **Langue : français** pour tout ce
qui est destiné aux humains (messages, docs, commentaires, CLI).

Lire d'abord `HANDOFF.md` (où on en est, chiffres mesurés, prochaines étapes), puis `ARCHITECTURE.md`.

## Principes non négociables

1. **Zéro erreur silencieuse.** Toute décision automatique porte un statut (`ok`, `blank`, `review`).
   En cas de doute : `review` avec une raison lisible. On préfère 10 % de revue à 1 % d'erreurs non signalées.
   Toute modification de seuil se valide par une mesure (voir « Valider un changement »).
2. **Gratuit et portable par défaut.** Tout doit fonctionner en local, sans abonnement ni clé, sur la machine
   d'un collègue (Windows/macOS/Linux, sans GPU). Les services payants (API Claude, Google Vision) ne sont que
   des **options opt-in** : désactivées tant que la clé n'est pas fournie (`ocr._require_env`).
3. **Données d'étudiants.** Jamais de scan, de vignette ni de résultat dans le dépôt ou un partage
   (cf. `.gitignore`). Les vignettes envoyées à un service externe ne contiennent jamais l'identité.
4. **Le gabarit vient du PDF.** Ne jamais mesurer de coordonnées à la main : `python -m thessalia template`
   lit les positions exactes dans le PDF vectoriel WeasyPrint.

## Commandes

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -e ".[ocr-light,trocr,dev]"                  # + programme tesseract du système si besoin
pytest -q                                                # ~1 min, inclut un test de bout en bout synthétique

python -m thessalia template templates/<sujet>.pdf -o templates/<sujet>.json --merge templates/<sujet>.json
python -m thessalia process scans/<classe>.pdf -t templates/<gabarit>.json -b templates/<sujet>.pdf -k keys/<x>.key.json -o sorties/<classe>
python -m thessalia ocr sorties/<classe> -v keys/<x>.vocab.json --backend trocr [--truth data/truth/<x>.json]
python -m thessalia simulate -t … -b … -o sim/lot -n 10 --hard && python -m thessalia evaluate out/lot sim/lot/truth.json
```

## Valider un changement

- Niveau 1 (QCM) : `simulate --hard` (≥ 12 copies) + `evaluate` → **0 « FAUSSES »** exigé ; puis repasser le
  lot réel EN et vérifier `review.csv` (8 cas attendus, cf. HANDOFF).
- Niveau 2 : `ocr … --truth data/truth/…` → suivre « acceptés auto » et surtout « dont justes ».

## Carte du code (thessalia/)

`template_builder` PDF → gabarit · `loader` scans → pages · `align` fiducials, homographie, identification
de page · `omr` cases à cocher · `extract` vignettes · `ocr_prep` nettoyage des réponses courtes ·
`ocr` moteurs · `vocab` rapprochement · `ocr_run` commande ocr · `pipeline` orchestration · `report` sorties ·
`grade` notation QCM · `simulate`/`evaluate`/`evaluate_ocr` tests et mesures.

## Pièges connus

- Scans réels : A3 avec la feuille dans la moitié haute, 100 dpi, rotations 90/270, pages blanches → gérés.
- Cases : ratures débordantes (halo), cases noircies pour cocher OU annuler (`full_policy: auto`),
  cases redessinées après correcteur (cœur vide). Voir ARCHITECTURE §5.
- Réponses courtes : lignes espacées de 8 mm, l'écriture déborde sur la ligne voisine → `ocr_prep`
  ne garde que les tracés qui reposent sur leur soulignement ; une zone vide contenant de l'écriture écartée
  est `suspect` (jamais déclarée vide).
- Le vocabulaire d'un champ doit contenir les mauvaises réponses plausibles, sinon le rapprochement
  « corrige » l'étudiant.
