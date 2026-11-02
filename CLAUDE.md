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
python -m thessalia truth-page sorties/<classe> -t templates/<gabarit>.json [--truth data/truth/<x>.json]   # validation.html, local
python -m thessalia notes sorties/<classe> [sorties/<classe2> …] -t templates/<gabarit>.json -k keys/<x>.key.json -v keys/<x>.vocab.json [-o sorties/notes/<groupe>.csv]   # QCM + réponses courtes, sur 9
python -m thessalia serve sorties/booster [sorties/<autre> …] --no-browser   # outil de correction local (extra [serveur]), http://127.0.0.1:8765/
python -m thessalia transcrire sorties/<classe> --local [qwen3-vl:8b-instruct]   # code : transcription locale (Ollama, gratuit), ~1 min par cadre
python -m thessalia precocher sorties/<classe> [--reparateur qwen3:14b]   # code : critères pré-cochés en exécutant le code transcrit (tests keys/<sujet>.tests.py)
python -m thessalia serve sorties/essai_code --essai   # essai : décisions dans data/correction_essai.sqlite, rien appris
python -m thessalia serve sorties/essai_supD_2 --banc   # banc : correction à l'aveugle (H), boutons H / Claude / local
python -m thessalia preparer sorties/<classe>   # la veille, une nuit, sans Claude : code transcrit + pré-coché (tests tirés du "corrige" du barème), réponses courtes relues
python -m thessalia second-lecteur sorties/<classe>   # réponses courtes : Qwen3-VL 4B local relit les réponses en revue (~32 s/réponse)
python -m thessalia code-bilan sorties/<classe> [--essai]   # code : chaîne locale contre l'enseignant, quoi améliorer avant la classe suivante
python -m thessalia bilan NA NB [--dossiers sorties/booster sorties/supA_1_v3]   # après correction : propositions, boutons, v2/v3, mémoire, indices
python -m thessalia verif-noms sorties/booster sorties/supA_1_v3   # AVANT l'export : nom écrit / élève attribué, copies à risque en tête
python -m thessalia verif-zones sujets/<examen>/<sujet>.pdf sujets/<examen>/<zones>.json [-o rapport.md]   # fichier de zones d'un générateur contre le PDF : rapport Markdown à coller dans le prompt du générateur
python -m thessalia excel sorties/booster sorties/supA_1_v3 [-o sorties/notes/notes.xlsx]   # notes finales sur 20, absents, copies à vérifier
python -m thessalia digits-train sorties/<classe> -v keys/<x>.vocab.json --truth data/truth/<x>.json   # vérité validée
python -m thessalia trocr-train sorties/<classe> -v keys/<x>.vocab.json --truth data/truth/<x>.json [--also …] [--limit 160]   # long, ~6 Go ; mesurer ensuite avec ocr --model data/models/trocr sur un lot jamais vu
python -m thessalia simulate -t … -b … -o sim/lot -n 10 --hard && python -m thessalia evaluate out/lot sim/lot/truth.json
```

## Valider un changement

- Niveau 1 (QCM) : `simulate --hard` (≥ 12 copies) + `evaluate` → **0 « FAUSSES »** exigé ; puis repasser le
  lot réel EN et vérifier `review.csv` (8 cas attendus, cf. HANDOFF).
- Niveau 2 : `ocr … --truth data/truth/…` → suivre « acceptés auto » et surtout « dont justes » ; pour les
  nombres, « proposition juste ». Le lecteur de chiffres se mesure en validation croisée par copie
  (`digits-train`), jamais sur les copies qui ont servi à l'affiner.

## Carte du code (thessalia/)

`template_builder` PDF → gabarit · `loader` scans → pages · `align` fiducials, homographie, identification
de page · `omr` cases à cocher · `extract` vignettes · `ocr_prep` nettoyage des réponses courtes ·
`ocr` moteurs · `digits` lecteur de chiffres (nombres) · `vocab` rapprochement · `ocr_run` commande ocr · `truth_page` page de validation de la vérité · `pipeline` orchestration · `report` sorties ·
`grade` notation QCM · `notes` notes QCM + réponses courtes (règle globale de l'enseignant) · `correction` décisions, mémoire des
verdicts, étiquettes `appris.json` · `serve` + `web/` outil de correction Flask · `code_tests` pré-cochage du code par exécution (réparation tolérée, contrôle du réparateur) · `preparer` routine de la veille · `second_lecteur` second lecteur local des réponses courtes · `code_bilan` bilan de la chaîne locale du code · `bilan` mesures après correction · `excel` classeur des notes finales (copie datée de l'ancien) · `verif_noms` contrôle des attributions · `verif_zones` fichier de zones d'un générateur contre le PDF · `simulate`/`evaluate`/`evaluate_ocr` tests et mesures.

Dossiers : `scans/` = copies scannées des élèves seulement ; `sujets/<examen>/` = sujets vierges, fichiers de zones,
PDF corrigés et rapports `verif-zones` (hors git : confidentiels jusqu'à l'examen) ; `templates/` = gabarits Thessalia
(et PDF des anciens sujets, laissés là).

## Pièges connus

- Mauvais gabarit (sujet EN lu avec le gabarit FR ou l'inverse) : même mise en page, donc rien n'échoue.
  `process` alerte « GABARIT DOUTEUX » si le score de reconnaissance médian est < 0,85 (bon gabarit :
  0,96 ; mauvais : 0,75). Booster 2627 : classes « sup nb » et « supNA » = sujet EN, les autres = FR.
- Scans réels : A3 avec la feuille dans la moitié haute, 100 dpi, rotations 90/270, pages blanches → gérés.
- Cases : ratures débordantes (halo), cases noircies pour cocher OU annuler (`full_policy: auto`),
  cases redessinées après correcteur (cœur vide). Voir ARCHITECTURE §5.
- Réponses courtes : lignes espacées de 8 mm, l'écriture déborde sur la ligne voisine → `ocr_prep`
  ne garde que les tracés qui reposent sur leur soulignement ; une zone vide contenant de l'écriture écartée
  est `suspect` (jamais déclarée vide).
- Nombres : `2,5` n'est pas `2.5` (faute courante en Python). Un nombre décimal part toujours en revue.
  Virgule détectée (texte ET forme d'accord) : on la garde ; séparateur incertain : le doute profite à
  l'étudiant, point proposé et virgule en second choix.
- Le vocabulaire d'un champ doit contenir les mauvaises réponses plausibles, sinon le rapprochement
  « corrige » l'étudiant.
