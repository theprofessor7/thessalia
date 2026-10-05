# Vérités terrain (NE PAS diffuser hors de l'équipe pédagogique)

`python_core_EN_examen_blanc.short_truth.json` : transcription des 777 réponses courtes de l'examen blanc
« Exam — Python Core » (EN, 21 copies, lot reçu le 01/10/2026, 100 dpi).

- Clés `cNN_qX.Y` : NN = numéro de copie dans l'ordre du PDF scanné (copy_0NN), qX.Y = champ du gabarit.
- Aucune identité, mais ce sont des réponses d'étudiants : gardé hors dépôt (.gitignore).
- Lecture faite par Claude à partir des vignettes, **non encore validée par l'enseignant** :
  `""` = vide ; suffixe `?` = lecture incertaine (37 cas, exclus des taux).
- On note la réponse FINALE de l'étudiant (les mots barrés sont ignorés), telle qu'écrite (fautes comprises).

Usage : `python -m thessalia ocr <dossier_resultats> -v keys/python_core_EN.vocab.json --truth data/truth/python_core_EN_examen_blanc.short_truth.json`

## Mise à jour du 4 octobre 2026

- `EN_blanc.short_truth.json` : **vérité validée par l'enseignant** (page `truth-page`), 777 réponses, aucune
  incertaine. C'est la référence pour le lot EN ; `python_core_EN_examen_blanc.short_truth.json` (lecture de
  Claude) n'est gardé que pour mémoire.
- `booster_supA1.numbers_truth.json` : champs numériques du lot Booster supA 1, lecture de Claude, non validée.

## Mise à jour du 5 octobre 2026

- `supA_1_v3.short_truth.json` : **vérité validée par l'enseignant** du lot Booster supA 1 (sujet FR,
  9 copies, 333 réponses, aucune incertaine). C'est la référence pour ce lot ; `booster_supA1.numbers_truth.json`
  (19 écarts sur 140) n'est gardé que pour mémoire.
