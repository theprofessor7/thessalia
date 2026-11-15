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
   d'un collègue (Windows/macOS/Linux, sans GPU). Les services payants (transcription du code en ligne) ne sont
   que des **options opt-in** : désactivées tant que la clé n'est pas fournie (`lecteur_code`, plafond de dépense).
   Aucune étape ne dépend de Claude : tout usage d'un service en ligne a sa version locale (Ollama).
3. **Données d'étudiants.** Jamais de scan, de vignette ni de résultat dans le dépôt ou un partage
   (cf. `.gitignore`). Les vignettes envoyées à un service externe ne contiennent jamais l'identité.
   **Dépôt public** : aucun nom d'élève (ni note nominative) dans HANDOFF, les commentaires, les tests ou les messages
   de commit ; exemples avec des noms inventés. Les sujets et corrigés (`templates/`, `keys/`, `sujets/`) restent hors dépôt.
   Seule exception (accord de l'enseignant, 15 nov. 2026) : les captures du guide (`docs/guide/img/ex_*.png`) gardent
   des réponses manuscrites sans identité ; noms, notes et prénom du compte y sont floutés ou retirés.
4. **Le gabarit vient du PDF.** Ne jamais mesurer de coordonnées à la main : `template_builder` lit les
   positions exactes dans le PDF vectoriel (Typst pour les sujets de Thessalia, celui du générateur pour un sujet
   importé).

## Commandes

Les enseignants n'utilisent que l'application : `installer.bat` / `installer.sh` puis `Thessalia.bat` /
`Thessalia.command` (cf. docs/MODE_EMPLOI.md). Tout le reste (sujet, scans, lectures, correction, apprentissage,
notes) se fait dans le navigateur.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -e ".[serveur,trocr,dev]"
pytest -q                                                # ~2 min, inclut un test de bout en bout synthétique

python -m thessalia app [--examens examens] [--no-browser]   # l'application, http://127.0.0.1:8765/
python -m thessalia importer <nom> --langue fr sujet.pdf sujet.key.json sujet.vocab.json [--zones fr zones.json] [--autre x.bareme.json]
                                                         # sujet d'un autre générateur (aussi depuis l'accueil de l'application)
python -m thessalia verif-zones <sujet.pdf> <zones.json> [-o rapport.md]   # zones d'un générateur contre le PDF : rapport à coller dans son prompt
python -m thessalia transcrire examens/<nom>/classes/<classe> --champ q12 [--limite 20]   # option payante, sur clé : code lu en ligne
python -m thessalia simulate -t <gabarit.json> -b <sujet.pdf> -o sim/lot -n 12 --hard    # copies synthétiques + truth.json
python -m thessalia evaluate sim/lot -t <gabarit.json> -b <sujet.pdf>                     # lit sim/lot/scans.pdf, compare à la vérité
```

## Valider un changement

- Niveau 1 (QCM) : `simulate --hard` (≥ 12 copies) + `evaluate` → **0 « FAUSSES »** exigé ; puis relire une
  classe réelle déjà corrigée et vérifier qu'aucune décision de l'enseignant n'est contredite.
- Niveau 2 : page « Apprentissage » de l'application : un lecteur affiné se mesure sur une classe qu'il n'a
  jamais vue (chiffres : validation croisée par copie), jamais sur les copies qui ont servi à l'affiner.
  Suivre « acceptées d'office » et surtout combien sont justes.
- `pytest -q` passe ; `ruff check thessalia tests --select F` sans erreur.

## Carte du code (thessalia/)

Détail : ARCHITECTURE §2.
Sujet : `sujet/` source YAML → Typst, corrigés · `template_builder` PDF → gabarit · `verif_zones` zones d'un
générateur · `projet` examen de l'application (sujet produit ou importé, classes, lectures) · `enonce` énoncé
découpé dans le PDF.
Lecture : `loader` scans → pages · `align` fiducials, homographie, identification de page · `omr` cases à cocher ·
`extract` vignettes · `code_vide` cadres vides · `pipeline` orchestration · `report` sorties · `grade` notation QCM ·
`ocr_prep` nettoyage des réponses courtes · `ocr` TrOCR · `digits` lecteur de chiffres · `vocab` rapprochement ·
`ocr_run` lecture d'une classe · `identite` noms proposés · `preparer` lecture approfondie (Ollama, `ollama_local`) :
`lecteur_code` transcription du code, `code_tests` pré-cochage par exécution, `second_lecteur` relecture des
réponses courtes.
Correction : `correction` décisions, mémoire des verdicts, lectures tapées, étiquettes `appris.json` · `notes`
règle de jugement des réponses courtes · `serve` + `web_examens` + `web/` application Flask · `apprentissage`,
`digits_train`, `trocr_train`, `evaluate_ocr` affinage et mesure des lecteurs · `verif_noms` contrôle des
attributions · `excel` classeur des notes (copie datée de l'ancien) · `compte`, `reglages`, `extensions`,
`avancement` · `simulate`/`evaluate` tests.

Dossiers : `examens/<nom>/` = un examen de l'application (sujet, gabarits, corrigés, classes lues, décisions,
listes ; hors git). Sur le PC de l'auteur, hors git aussi : `sujets/<examen>/` (sujets vierges, zones, rapports
`verif-zones`), `templates/` et `keys/` (anciens sujets et corrigés, utilisés par quelques tests qui sont sautés
ailleurs), `sorties/`, `scans/`, `data/` (modèles affinés, vérités, réglages).

## Pièges connus

- Mauvais gabarit (sujet EN lu avec le gabarit FR ou l'inverse) : même mise en page, donc rien n'échoue.
  La lecture alerte « GABARIT DOUTEUX » si le score de reconnaissance médian est < 0,85 (bon gabarit :
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
