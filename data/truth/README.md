# Vérités terrain (NE PAS diffuser hors de l'équipe pédagogique)

`python_core_EN_examen_blanc.short_truth.json` : transcription des 777 réponses courtes de l'examen blanc
« Exam — Python Core » (EN, 21 copies, lot reçu le 01/10/2026, 100 dpi).

- Clés `cNN_qX.Y` : NN = numéro de copie dans l'ordre du PDF scanné (copy_0NN), qX.Y = champ du gabarit.
- Aucune identité, mais ce sont des réponses d'étudiants : gardé hors dépôt (.gitignore).
- Lecture faite par Claude à partir des vignettes, **non encore validée par l'enseignant** :
  `""` = vide ; suffixe `?` = lecture incertaine (37 cas, exclus des taux).
- On note la réponse FINALE de l'étudiant (les mots barrés sont ignorés), telle qu'écrite (fautes comprises).

Usage : `python -m thessalia ocr <dossier_resultats> -v keys/python_core_EN.vocab.json --truth data/truth/python_core_EN_examen_blanc.short_truth.json`
