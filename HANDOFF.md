# Passation — état du projet au 18 octobre 2026

> Note de reprise rédigée par Claude (session cloud claude.ai) pour la suite du développement en local
> avec Claude Code. À lire avec `CLAUDE.md` (consignes) et `ARCHITECTURE.md` (conception détaillée).

## 0. Point du 18 octobre 2026 (à lire en premier)

**Modèle en service : `data/models/trocr_v2`** (hors dépôt, 1,3 Go), à passer avec
`ocr … --model data/models/trocr_v2`. Affiné le 17 octobre au soir : `trocr-train --from
data/models/trocr_commun --replay 500 --passes 2`, sur supB 1 entier (570 vignettes) + 500 vignettes tirées
de supA 2, EN et supA 1, soit 1 070 vignettes par passe, ~3,9 s par lot de 2 sur secteur (~35 min par
passe). Perte 0,56 puis 0,35. La passe 2 a été tuée une fois faute de mémoire, la reprise a fonctionné.
`trocr_commun` est conservé pour comparaison.

Mesure sur **supB 3** (10 copies, jamais vu par aucun des deux modèles), vérité validée par l'enseignant le
18 octobre (`data/truth/supB_3.short_truth.json`, 370 réponses, aucune incertaine) :

| supB 3 | trocr_commun | trocr_v2 |
|---|---|---|
| lecture brute exacte | 327/361 (90,6 %) | 335/361 (92,8 %) |
| mots acceptés (justes) | 173 (173) | 174 (174) |
| nombres acceptés (justes) | 59 (**58**) | 50 (50) |
| bonne réponse dans le top 3 | 93,5 % | 94,7 % |
| nombres : proposition juste (texte / chiffres) | 138 / 115 sur 157 | 139 / 117 sur 157 |
| à valider | 151 | 160 |

- **Erreur acceptée avec `trocr_commun`** : c04_q10.1 accepté `49`, vérité `42` (TrOCR et lecteur de
  chiffres d'accord). Première faute de la règle « entiers acceptés » (89/89 sur supA 2 et supB 1).
  `trocr_v2` accepte moins de nombres (d'où 9 réponses de plus à valider) et aucun faux. La règle tient avec
  `trocr_v2` sur ce lot, mais elle n'est mesurée que sur 50 cas de ce modèle : **à remesurer au prochain
  lot validé**, et resserrer (revue) si une erreur réapparaît.
- Gain surtout sur q7 (texte libre, 34/39 contre 30/39) et q10.
- Durée de lecture de supB 3 : 2,2 s par vignette sur secteur (361 vignettes, ~13 min).
- Vérités validées le 18 octobre : supB 3, puis supB 2 (`data/truth/supB_2.short_truth.json`, 253
  réponses) ; QCM en revue de supB 1, 2 et 3 (`*.qcm_truth.json`).
- Vérité supA 2 corrigée le 18 octobre : c07_q6.1 `int` → `print` (ancienne version :
  `supA_2.short_truth.avant_corrections_2026-10-18.json`). `trocr_v2` a appris l'ancienne étiquette (1 sur 1 070).
### 18 octobre, après-midi : notes des questions de cours (QCM + réponses courtes)

Objectif de l'enseignant : **exploiter des notes Booster avant la fin de la semaine du 19 octobre**.
Barème du sujet FR : QCM 2,25 + réponses courtes 6,75 = **9 points** ; le code (q11-q13, q15-q19) vaut
11 points, non lu : il passera par l'API Claude **plus tard**, à la demande de l'enseignant (il fournira le
corrigé du code ; essai sur quelques copies et coût annoncé avant tout envoi en masse).

**Organisation du travail (demandée par l'enseignant)** : lecture par groupe de classes, en journée, pendant
qu'il valide le groupe précédent (pas « une nuit d'un coup ») ; une page `validation.html` par classe
(~100 à 300 réponses : « paquet de 100 » était un ordre de grandeur, pas un découpage). Ordre des groupes :
B, A, C, D, E, F, G, H, NA, NB (NA et NB : sujet EN). File de lecture lancée le 18 octobre à 17 h 28
(script de session, non conservé) ; journal `sorties/booster/file_lecture.log` (une ligne PRÊT par classe).
Les classes déjà validées (supA 1, supA 2, supB 1, supB 3) ne sont pas relues.

**Règle globale de notation des réponses courtes, décidée par l'enseignant le 18 octobre** :
identique au corrigé ou équivalence (`Error` = `ERREUR` toute casse, `Zero` = `Zéro`) = 100 % ;
**écart de forme seulement** (casse, parenthèses `print()` / `print("...")`, guillemets `"427"`,
espaces) = **50 %** ; tout le reste = faux, virgule décimale comprise. En **q7** (affichage exact demandé)
tout écart, espace compris, est faux. Il a refusé l'arbitrage réponse par réponse et les points partiels au
cas par cas : « il faut une politique globale ». Le corrigé peut porter des exceptions par champ
(`short_accept` / `short_reject`), inutilisées à ce jour.

**Commande `notes`** (`thessalia/notes.py`) :
`python -m thessalia notes sorties/booster/supB_1 sorties/booster/supB_2 … -t templates/socle_python_FR.json
-k keys/socle_python_FR.key.json -v keys/socle_python_FR.vocab.json -o sorties/notes/B.csv`.
Source de chaque réponse : vérité validée `data/truth/<classe>.short_truth.json` si elle existe, sinon la
lecture `ocr` (acceptée = notée, en revue = **en attente**, jamais notée en silence). QCM : note de
`results.json`, recalculée avec `data/truth/<classe>.qcm_truth.json`. Sorties par classe : `notes.csv`
(note sur 9, en attente, écarts de forme, état complète/incomplète), `notes_detail.csv` (chaque blanc).
Identité : `data/listes/<classe>.csv` (`copie;etudiant`, hors dépôt) ; pour l'instant des noms fictifs
(`supB_2_copie001`…), la vraie liste Moodle sera fournie quand le procédé sera rodé.

**Page de validation** : les QCM en revue y sont (extrait de la page, une case par option pré-réglée sur
la lecture de la machine) ; l'export télécharge deux fichiers, `<classe>.short_truth.json` et
`<classe>.qcm_truth.json`, que l'enseignant enregistre dans `data/truth/`. Une page construite sur une
vérité déjà validée ne montre plus que ce qui reste à faire.

**Groupe B noté** (`sorties/notes/B.csv`) : supB 2 validé le 18 octobre (253 réponses + 3 QCM), QCM de
supB 1 et supB 3 validés. **31 notes complètes sur 33.** Restent : supB 1 copie 5 q3.1 (incertaine dans
la vérité) ; supB 2 copie 7, pages 6 et 7 absentes du scan (q10 en attente, voir la copie papier).

**Mesure de `trocr_v2` sur supB 2** (7 copies, jamais vu) : lecture brute 91,4 % ; 119 mots acceptés dont
117 justes ; 31 nombres acceptés, tous justes. Les 2 fautes :
- c03_q6.1 `print("...")` accepté `print` : sans conséquence avant la règle de notation, mais `print` vaut
  100 % et `print()` 50 %. **Correctif** (`ocr_run.form_marks`) : une lecture brute portant parenthèses ou
  guillemets absents de la valeur retenue part en revue (« forme à vérifier »). Mesure sur les 6 lots
  validés (lectures en cache) : plus aucune acceptation fausse ; 22 réponses de plus en revue. Avec
  `trocr_v2` (supB 2, supB 3) les 9 nouveaux cas sont tous de vrais `print()` / `input()`, qui étaient
  acceptés à 100 % au lieu de 50 % ; avec TrOCR de base (supA 1, EN), 10 fausses alertes sur 13 (ce modèle
  invente des guillemets). Pages de supA 3, supA PRENOM NOM, supC 1 et supC 2 recalculées après le correctif.
- c05_q8.4 : `int` barré puis `float`, accepté `int`. La règle du mot barré ne l'a pas vu ; seul cas sur
  6 lots, seuil inchangé, à surveiller.

**Suite** : valider les groupes au fil de la lecture, `notes` après chaque groupe ; remesurer `trocr_v2` sur
chaque classe validée (`ocr … --truth`) ; après 2 ou 3 groupes validés, proposer un réaffinage ; puis export
Moodle (liste réelle), puis le code par l'API.

## 0 ter. Point du 17 octobre 2026

Entre le 5 et le 17 octobre (commits du 11 et du 15) : marge d'acceptation 0,30 et refus d'un mot reconnu
par une seule lecture secondaire ; étiquettes de `trocr-train` sans `<s>` ; règle « second mot séparé »
(`ocr_prep.extra_word`). Modèle **`data/models/trocr_commun`** (hors dépôt) : TrOCR base affiné sur EN +
supA 1 (1 079 vignettes, 3 passes) ; modèle en service jusqu'au 18 octobre (remplacé par `trocr_v2`, cf. §0). Vérités validées : EN, supA 1, supA 2,
**supB 1** (`data/truth/supB_1.short_truth.json`, 592 réponses, 1 incertaine, validée le 17 octobre).

Mesures du 17 octobre avec `trocr_commun`, sur deux lots jamais vus par le modèle :

| | supB 1 | supA 2 |
|---|---|---|
| lecture brute exacte | 80 % | 87 % |
| mots acceptés (justes) | 249 (249) | 136 (135, cf. ci-dessous) |
| nombres acceptés (justes) | 83 (83) | 49 (49) |
| à valider | 278 (351 avant les règles du jour) | 126 |

- **Mot barré** (`ocr_prep.struck_word`) : 3 acceptées fausses sur supB 1, le moteur lisait le mot barré
  (`input` barré puis `for`, `ERREU` barré puis `"42" + "7"`, rature puis `InPU`). En revue quand un trait
  horizontal ≥ 1,6 × la hauteur d'écriture traverse la bande centrale ET qu'une autre écriture est séparée
  du trait. Sur les 643 acceptées des 4 lots : ces 3 cas, aucune juste. Marge courte (1,69 / 1,55),
  réglée sur 3 cas ; un mot barré seul n'est pas repéré.
- **`snap`** : lectures secondaires < 0,05 ignorées (`float` 1,00 / `bool` 0,014 n'est plus une
  hésitation) ; lecture principale exactement égale à un mot (`enum` seulement) acceptée si le suivant
  est à ≥ 0,15 (`print` / `printf` : 14 copies sur 16 en revue sur supB 1). Risque connu, choix de
  l'enseignant : `printf` lu sans son « f » serait accepté `print`. Aucune erreur nouvelle sur 4 lots.
- **Nombres acceptés** (`vocab.propose_digits`, `accept_numbers`) : entier d'au moins 2 chiffres, TrOCR et
  lecteur de chiffres d'accord, confiance TrOCR ≥ 0,99, **seulement avec un TrOCR affiné localement**
  (`ocr_run` : modèle hors `microsoft/`). 89/89 sur les deux lots ; un chiffre seul reste en revue
  (2 fautes sur 85 : `3` lu `5`, `2` bouclé lu `9`, deux lectures d'accord à 1,00). Avec TrOCR base,
  la règle « très sûr » du 5 octobre se trompait sur supA 2 (`3` lu `43`). **À remesurer à chaque lot
  validé et à chaque nouveau modèle.**
- **Mesure `--truth`** : applique désormais les règles d'image (deux mots, mot barré), compte
  `Error` = `ERREUR` et `Zero` = `Zéro` comme justes (décision de l'enseignant) et affiche les nombres
  acceptés. Les « acceptés auto » mesurés avant le 17 octobre ignoraient les règles d'image.
- Le lecteur de chiffres fait moins bien que TrOCR affiné sur les nombres (supB 1 : 171 contre 185/242
  propositions justes ; supA 2 : 96 contre 106/128) : à revoir (qui fait la proposition).
- **Vérité supA 2 à revoir** : c07_q6.1 vaut `int` dans la vérité, la vignette montre `print`.
- `trocr-train --from MODELE --replay N` : affinage classe par classe en repartant d'un modèle affiné, avec
  la nouvelle classe entière et N vignettes tirées des lots déjà appris. Pas encore essayé.
- Suite proposée : affinage `--from trocr_commun` sur supA 2 + supB 1 (durée à estimer avant), test sur un
  lot validé jamais vu ; puis lecture des 25 classes (une nuit).

## 0 bis. Point d'arrêt du 5 octobre 2026

Session locale Claude Code des 4 et 5 octobre. L'enseignant s'est déconnecté ici.

- **Non commité à l'arrêt** : `thessalia/pipeline.py` (feuille de présence ignorée, pages rendues à la
  première copie) et ce fichier. Tests : 14 passés. À commiter si l'enseignant confirme.
- **Questions restées sans réponse** : (1) commiter ce qui précède ; (2) lancer `ocr` sur les 25 lots
  Booster (plusieurs heures à ~2,5 s par vignette : plutôt la nuit, machine sur secteur).
- **À faire ensuite, dans l'ordre proposé** :
  1. `ocr` sur les lots Booster (`sorties/booster/<classe>`, vocabulaire FR ou EN selon la classe), puis
     `truth-page` pour la revue des réponses courtes.
  2. Faire valider par l'enseignant un lot Booster (supA 1 : `sorties/supA_1_v3/validation.html`), puis
     réaffiner le lecteur de chiffres sur EN + Booster (`digits-train`) : priorité aux `1` à la française.
  3. Regarder supNA 2 (14 QCM en revue pour 18 copies) et supE 2 copie 1 (pages 1-2 illisibles).
  4. Statistiques d'erreurs par question pour l'enseignant (souhaitées, reportées).
- **Les QCM des lots Booster ne sont validés par personne** : seuls ceux du lot EN l'ont été.
- Les scripts d'essai de la session (traitement par lots, bilans, prototypes) étaient dans un dossier
  temporaire et ne sont pas conservés ; les commandes utiles sont dans `CLAUDE.md`.
- Sur batterie, TrOCR est 3 à 6 fois plus lent : brancher la machine avant une lecture longue.

### Reprise du 5 octobre (suite)

- Point d'arrêt ci-dessus commité (`3709b7b`). `ocr` sur les 25 lots Booster : **pas maintenant** (réponse
  de l'enseignant) ; à reproposer, un lot d'essai d'abord.
- **Vérité de supA 1 validée par l'enseignant** : `data/truth/supA_1_v3.short_truth.json` (333 réponses,
  aucune incertaine, 6 virgules décimales). La lecture de Claude des nombres différait sur 19 des 140.
  Mesure `ocr --truth` (TrOCR base, lectures en cache, modèle de chiffres affiné sur EN seul, donc lot
  jamais vu) : 82 acceptées sur 289 champs à vocabulaire, **82 justes** ; proposition juste des nombres
  74/140 avec TrOCR seul, 107/140 avec le lecteur de chiffres.
- **`digits-train --also DOSSIER VOCAB VERITE`** (répétable) : affinage et validation croisée sur plusieurs
  lots. EN + supA 1 (396 nombres, 30 copies, ~4 min) : 305/396 en validation croisée, soit EN 211/275
  (200 avec EN seul) et supA 1 94/121 (93 avec le modèle fourni, affiné sur EN seul). Gain faible sur
  supA 1 : les fautes restantes sont les `1` à la française d'une seule copie (c05 : `1024` → `7024`,
  `11` → `17`…) et des découpages faux (`1024` → `1.24`, `427` → `49.7`). Le modèle fourni n'a **pas** été
  remplacé.
- **supNA 2** (14 QCM en revue) : revues légitimes. Coches fines au crayon (encre 0,12-0,14, copie 14),
  coches débordantes et libellés barrés (copie 18), une feuille absente (copie 12), et 3 « case non
  retrouvée » : la case imprimée a disparu du scan, recouverte de correcteur, alors que les voisines sont
  recalées à 0,95. Le motif dit maintenant « effacée au correcteur ? » dans ce cas (`omr`, champ `erased`) ;
  « page mal alignée ? » reste quand aucune case de la page n'est recalée. Aucun seuil modifié.
- **supE 2, copie 1** : la première feuille est passée de travers dans le chargeur (~12°), deux coins sont
  hors du scan, il ne reste que 2 repères sur 4 par face.
- **Alignement de secours sur 2 repères** (`align._align_on_two`, demandé par l'enseignant) : quand aucun
  rectangle de 3 ou 4 repères n'est trouvé, chaque paire de candidats dont la distance vaut un côté ou la
  diagonale (± 8 %) donne des rectangles possibles ; on garde celui dont la page redressée ressemble le plus
  au sujet (score ≥ 0,75 exigé, sinon « page illisible » comme avant), puis recalage sur le texte imprimé.
  La page part **toujours en revue** (« alignement de secours sur 2 repères … , N % de la page hors du
  scan ») : ce qui est hors du scan serait sinon lu vide. Essai sur supE 2 copie 1 : pages 1 et 2
  identifiées (score 0,96), cases et lignes bien calées à l'œil, 4 % hors du scan. Simulé difficile
  graine 7, 12 copies : 0 FAUSSES, 17,7 % en revue (inchangé). Lot réel EN : `results.csv` et `review.csv`
  identiques. Lot `sorties/booster/supE_2` retraité le 5 octobre : copie 1 complète (17 pages, QCM de la
  page 2 lus), 6 points en revue au lieu de 8, les 15 autres copies inchangées dans `results.csv`.
- **Propositions prises pour des « traductions »** (remarque de l'enseignant sur la page de validation de
  supA 1) : une lecture TrOCR illisible était remplacée par le mot du vocabulaire le plus proche (`input`
  lu « im-ment » → proposé « lire », `str` lu « crn. » → « chaîne »). Jamais accepté seul, mais trompeur.
  Mesure (champs `enum` en revue, EN + supA 1, proposition juste / cas) selon la distance : 0,34-0,55 :
  84/108 ; 0,55-0,65 : 30/52 ; 0,65-0,75 : 10/28 ; > 0,75 : 2/20. Depuis le 5 octobre, au-delà de 0,75
  (`vocab.snap`, `far`) la proposition est la lecture brute (« hors vocabulaire : aucun mot proche, lecture
  brute »), les mots proches restent en suggestions. Acceptés inchangés (supA 1 : 82 dont 82 ; EN : 200
  dont 199). **Seuil abaissé à 0,65 le 5 octobre, choix de l'enseignant** (36 mauvaises propositions
  retirées, 12 bonnes perdues ; à 0,55 : 58 et 42). Entre 0,55 et 0,65 le mot reste proposé (`print` lu
  « animal » → « ecrire ») : juste 30 fois sur 52, bonne réponse dans les suggestions 45 fois. À remesurer
  quand d'autres lots seront validés (30 copies seulement).
- **Virgules sur supA 1** : 6 vraies virgules, 1 seule « détectée » (les deux lectures d'accord), les 5
  autres proposées avec un point et la virgule en second choix (règle du doute) ; toutes en revue. Sur EN
  c'était 4 sur 5 : la détection de la virgule est à remesurer sur les deux lots avant d'y toucher.
- **Vérité supA 1 relue par l'enseignant le 5 octobre** (fichier de 13 h 28, puis deux corrections) :
  c05_q7.1 → `Bonjour - Alice`, c08_q14.2 → `GrandPetit`, c04_q7.3 → `" X "Y`, q14.3 des copies 1, 3, 5 →
  `Zéro`, q7.4 des copies 1 et 5. **Gardées volontairement** : c07_q7.2 `A-P-C` et c07_q7.3 `X.X` — règle
  de l'enseignant : la vérité transcrit ce qui se lit ; une lettre mal formée joue au détriment de
  l'étudiant (le doute favorable ne vaut que pour le doute de la machine). Mesure refaite : 82 acceptées
  dont 82 justes, bonne réponse dans le top 3 76,8 %, nombres 107/140 (74 avec TrOCR seul).
- **Page de validation** (`truth-page`) : la confirmation de « Valider les N affichées » est supprimée
  (demande de l'enseignant) ; celle de l'export reste (réponses non validées exportées avec « ? »). Pas
  de filtre par copie : chercher la clé `cNN_qX.Y` avec Ctrl+F, filtre d'état sur « toutes ».

### 5 octobre, après-midi : série Booster suspendue, essai d'affinage de TrOCR

- Décision de l'enseignant : **optimiser le Niveau 2 avant de lire les 25 classes** (7 h 30) — les lectures
  TrOCR sont à refaire si le modèle change, le reste (chiffres, rapprochement) se réapplique en 1 min.
  Lus avec le modèle d'origine : `supA_PRENOM_NOM` (36 vignettes) et `supA_2` (294 : 62 acceptées, 232 en
  revue dont 114 nombres). Vitesse : 2,9 à 4,2 s/vignette selon batterie et charge.
- **Essai court d'affinage de TrOCR base** (script temporaire, non conservé : AdamW 2e-5, lots de 4,
  2 passes, étiquettes = vérité validée) : entraîné sur 160 vignettes EN tirées au hasard, testé sur les
  copies 1 à 3 de supA 1 (110 vignettes, lot et sujet jamais vus). Lecture brute exacte **35 → 67/110** ;
  par type : enum 13 → 35/51, nombres 21 → 29/47, texte libre 1 → 3/12. Acceptées 36 → 40 ; bonne
  réponse dans le top 3 : 81 → 90/98. Une acceptée « à tort » (c01_q8.6, vérité `list`, lu `bool`) : la
  vignette montre plutôt `bool`, **vérité à revoir par l'enseignant**.
  Limites vues : « Bonjour » reste mal lu (aucun dans l'entraînement EN) ; le modèle affiné invente
  parfois un mot fréquent avec aplomb (`Total: _8` lu `str`, confiance 0,98) ; sa confiance ne sépare pas
  le juste du faux (≥ 0,95 : 56 justes, 13 fausses). Coût : 14 min pour 80 pas (6 s/pas, 10 s quand la
  mémoire sature : 6 Go pour l'entraînement sur 15,5) ; lecture inchangée (2,9 s/vignette).
- **Nombres, accord des deux lectures** (entiers en revue ; EN optimiste, supA 1 jamais vu) : accord seul
  103/106 et 44/50 ; confiance chiffres ≥ 0,95 : 78/78 et 26/27 (`3.14` lu `314` à 0,957) ; ≥ 0,96 :
  72/72 et 21/21 ; ≥ 0,99 : 18/18 et 7/7. Les `1` à la française lus `7` sortent à 0,93-0,94 avec les deux
  lectures d'accord. **Décision de l'enseignant : marquer sans accepter.** `vocab.propose_digits` pose
  `sure` (entier, accord, confiance chiffres ≥ 0,99) et le motif « … très sûr, à confirmer » ; la page
  `truth-page` a un filtre « nombres très sûrs à valider » pour la validation groupée. Statuts inchangés
  (supA 1 : 82 acceptées dont 82 justes ; 6 marquées, 6 aussi sur supA 2). À remesurer sur un 3ᵉ lot
  validé avant toute acceptation automatique.
- **Affinage complet (étape 1) tenté le 5 octobre après-midi, sans résultat** : tout le lot EN, 3 passes,
  test prévu sur les 9 copies de supA 1. Arrêté par le système à 260 pas sur 567 (mémoire critique :
  ~6 Go pour l'entraînement, l'enseignant travaillait en parallèle) ; rien d'enregistré, le script ne
  sauvegardait qu'à la fin. **À refaire sur demande de l'enseignant** (soir / nuit, applications fermées,
  ~1 h 30), avec une sauvegarde à chaque passe et des lots de 2 avec cumul des gradients ; destination
  prévue `data/models/trocr_en` (hors dépôt, ~1,3 Go). Le script d'essai était dans le dossier temporaire :
  à réécrire (TrOCR base, AdamW 2e-5, étiquettes = vérité validée, vignettes `.clean.png` avec `_pad(12)`,
  `config.pad_token_id = 1`, `config.decoder_start_token_id = 2`).
  Page de validation de supA 2 prête : `sorties/booster/supA_2/validation.html`.
- **Affinage complet réussi le 5 octobre au soir** (3ᵉ tentative, reprise après la 2ᵉ passe) : TrOCR base,
  754 vignettes EN, 3 passes, lots de 2 avec cumul sur 2, ~21 min par passe ; modèle dans
  `data/models/trocr_en` (hors dépôt, 1,3 Go ; `etat.json` = passes faites). Utilisable avec
  `ocr … --model data/models/trocr_en` (fichier de lectures distinct, lié au chemin : le supprimer si on
  réentraîne au même endroit). Mémoire : ~6 Go quel que soit le lot (modèle + optimiseur).
  **Test sur les 9 copies de supA 1** (325 vignettes, jamais vues, sujet FR), origine → affiné :
  lecture brute exacte 91 → 211 (enum 28 → 101/149, nombres 59 → 102/140, texte libre 4 → 8/36) ;
  bonne réponse dans le top 3 : 222 → 269/289 ; acceptées 82 → 125, dont « justes » 82 → 120.
  Les 5 « fausses » : 3 sont des **erreurs de la vérité** (vignettes relues par Claude : c01_q8.4 = `float`,
  c01_q8.6 = `bool`, c07_q8.6 = `bool`) et 2 de vraies erreurs sur des mots français (`Grand`, `Petit`
  lus `bool` / `print` puis rapprochés de `ERREUR` par la 2ᵉ lecture « Error »).
  **Le modèle a appris le vocabulaire du sujet EN** : `Zéro` → « Zero », `Négatif` → « Negative »,
  « Bonjour Alice » → « Error » (9 fois sur 9), `Total : 8` → « Total: 8 » ; et il se trompe parfois avec
  une confiance de 1,00 sur un mot connu (c08_q8.4 `float` lu `bool`, c07_q8.5 `str` lu `14`). Donc :
  bon pour les types et les nombres, **inutilisable tel quel sur les classes du sujet FR** ; sa confiance
  ne vaut rien. Exiger que la 1ʳᵉ lecture soit celle rapprochée : 117 acceptées dont 114 « justes ».
  Suite prévue (étape 2) : entraîner sur EN + supA 1, tester sur supA 2 validée.
- **Commande `trocr-train`** (`thessalia/trocr_train.py`, ajoutée le 5 octobre au soir) : le script d'essai
  intégré au projet — plusieurs lots (`--also`), sauvegarde à chaque passe, reprise, `--limit` pour un essai
  court, pas de mise en veille sous Windows pendant le calcul. Vérifiée sur 8 vignettes (entraînement,
  reprise, refus d'écraser un modèle fait sur d'autres données) ; pas de test automatique. Le modèle
  `data/models/trocr_en` vient du script d'essai : son `etat.json` n'a pas le champ `lots`, ne pas le
  reprendre avec la commande.
- **Plan convenu avec l'enseignant (5 octobre au soir), l'affinage est borné à un entraînement de plus** :
  (1) l'enseignant revalide supA 1 (questions 2, 6, 8, 14) et valide supA 2 ; (2) corriger la règle
  d'acceptation qui a laissé passer `Grand` / `Petit` → `ERREUR` (acceptation fondée sur une lecture
  secondaire peu sûre), mesurée sur les deux lots ; (3) un seul entraînement commun EN + supA 1 (~1 h 30,
  un soir, machine libre), test sur supA 2 ; (4) choisir le modèle sur ce test (affiné seulement s'il lit
  nettement mieux sans acceptation fausse), puis lire les 25 classes (~7 h 30, une nuit) ; (5) page de
  revue et de notation (Niveau 4). Un modèle commun à tous les sujets, pas un par sujet.
- **Vérité supA 1 à revalider par l'enseignant avant l'étape 2** (elle sert d'étiquettes) : au moins
  c01_q8.4, c01_q8.6, c07_q8.6, c03_q6.2 (`print`, vignette « input »), c07_q14.2 (`rien`, vignette
  « Petit ») ; relire les questions 2, 6, 8 et 14 en entier.

## 1. En bref

| Niveau | État | Résultat mesuré sur le vrai lot (examen blanc EN, 21 copies, 100 dpi) |
|---|---|---|
| 1 — QCM / V-F | **Opérationnel** | 160/168 questions décidées automatiquement, **0 erreur** (validé par l'enseignant), 8 en revue ; 26 lots Booster traités (306 copies avec supA 1), non validés |
| 2 — réponses courtes | **Chaîne en place, moteur à choisir** | nettoyage + rapprochement OK ; moteurs locaux testés trop faibles (cf. §3), **TrOCR base compris** (mesuré le 3 octobre) |
| 3 — code manuscrit | Non commencé | vignettes des cadres déjà découpées par `process` |
| 4 — interface de validation | Amorcé | page locale de validation de la vérité des réponses courtes (`truth-page`) ; pas encore de file de revue ni d'export de notes |

## 2. Décisions de l'enseignant (à respecter)

- **Gratuit, local et portable d'un collègue à l'autre par défaut.** Les services payants (API Claude,
  Google Vision) restent des **options opt-in** activées seulement par une clé dans l'environnement.
  Modèle à suivre : les outils d'IA locaux qui acceptent une clé d'API externe facultative.
- Moteur Niveau 2 : **local d'abord** (TrOCR). La « revue par question » (toutes les réponses à q2.1
  côte à côte, validation par colonne) est **reportée** jusqu'au choix du moteur.
- Il ne contrôle **pas** la numérisation : la chaîne doit encaisser des scans médiocres
  (A3, 100 dpi, pages tournées, pages blanches). On demande A4 / 200 dpi mais sans garantie.
- Template du sujet : passage v3 → v4 en cours **dans une autre conversation** (marge de 3 mm autour des
  fiducials, en-tête EN traduit, consigne « noircir pour annuler »). Les gabarits se régénèrent avec
  `template --merge` ; garder les gabarits v3 pour les lots déjà imprimés.

## 3. Niveau 2 — où on en est

Chaîne : `process` produit pour chaque blanc une vignette **nettoyée** (`crops/qX.Y.clean.png` : page
vierge recalée soustraite, seuls les tracés qui reposent sur leur ligne) ; `ocr` lit, rapproche du
vocabulaire (`keys/*.vocab.json`) et écrit `short_answers.csv` + `ocr_review.csv`.

- Détection des blancs vides : 23/23 conformes à la vérité ; 7 « suspects » (écriture trop haute ou
  débordante) envoyés en revue, jamais déclarés vides.
- Moteurs testés (Tesseract et RapidOCR dans la session cloud, TrOCR en local le 3 octobre) :

| Moteur | Lecture brute exacte | Acceptés auto | dont justes | Bonne réponse dans le top 3 |
|---|---|---|---|---|
| Tesseract 5 | 13 % | 16 % | 88,5 % | 53 % |
| RapidOCR (PP-OCR) | 24 % | 26 % | 94,6 % | 71 % |
| TrOCR base (`microsoft/trocr-base-handwritten`) | 24,7 % | 33,8 % | 95,4 % | 74,5 % |
| TrOCR base, nombres libres en revue | 24,7 % | 26,9 % | 99,4 % | 74,5 % |
| TrOCR base, + point final retiré (réglage actuel, 4 octobre) | 32,8 % | 31,2 % | 99,5 % | 77,9 % |

  → insuffisant : ces moteurs sont faits pour l'imprimé. Les erreurs restantes sont des chiffres mal lus
  avec une confiance élevée (15 → 45, 22 → 27) : les seuils de confiance de ces moteurs ne sont pas fiables.
- **TrOCR base** (754 vignettes, ~2,4 s/vignette sur CPU, lots de 4, soit ~30 min pour 21 copies) : à peine
  mieux que RapidOCR. 10 réponses acceptées à tort, dont 9 sont des **nombres** lus avec un point ou un
  chiffre en trop (2.5 → 2.25 trois fois, 22 → 1.2 / 2.2, 11 → 1.1, 1024 → 1924, 15 → 95, 42 → 49) : la
  lecture fausse tombe sur une valeur du vocabulaire (distance 0), le rapprochement l'accepte donc.
  q3 est la plus touchée (20 acceptées, 14 justes). Détail : `sorties/EN_blanc/ocr_eval_trocr_*.txt`.
- **Nombres libres : toujours en revue depuis le 3 octobre** (`vocab.snap`). Mesure : les nombres mal lus
  ont la même confiance que les bons (à `min_conf` 0,99 il reste 1 faux sur 7 acceptés ; à 0,995, 2
  acceptés). La lecture reste proposée ; `min_conf` dans le vocabulaire d'un champ rétablit l'acceptation
  (opt-in). Reste 1 erreur acceptée : c07_q2.1, `int` lu `list`. Deux causes vues sur les vignettes
  nettoyées, côté `ocr_prep` : résidus du soulignement lus comme un point décimal (22 → 2.2, 11 → 1.1)
  et bas d'un chiffre effacé avec la ligne (42 → 49).
- **Point final parasite retiré depuis le 4 octobre** (`vocab.normalize`, champs `enum` et `number`) : TrOCR
  termine presque toutes ses lectures par « . ». Mesure sur les 754 lectures base : 173 → 200 acceptées,
  172 → 199 justes, même unique erreur (c07_q2.1).
- **TrOCR large** essayé le 4 octobre, arrêté après 40 vignettes (~11 s/vignette, soit ~2 h 30 pour le lot) :
  sur ces 39 réponses, 15 acceptées contre 12 pour base, mêmes fautes sur les nombres. Pas retenu.
- **Petit modèle de vision local** (Ollama, `qwen3-vl:4b-instruct`, CPU sans GPU) essayé le 4 octobre sur
  12 vignettes de la copie 1 : ~46 s/vignette (~10 h pour le lot), donc inutilisable sur cette machine.
  Qualité : nombres lus justes là où TrOCR se trompe (1024, 2.5, 14), mots mal lus (`float` → `22at`).
  La version avec réflexion (`qwen3-vl:4b`) ne rend rien d'exploitable. À réessayer seulement avec un GPU.
- **Tracés coupés par le soulignement** (4 octobre) : `ocr_prep` sait les recoller, option
  `process --bridge-line`, **désactivée par défaut**. Mesure sur le lot EN (TrOCR base, lot retraité dans
  `sorties/EN_blanc_prep2`) : 200 → 227 acceptées, 199 → 224 justes, mais 1 → 3 erreurs acceptées
  (c18_q2.2 `float` → `bool`, c16_q14.3 `Zero` → `ERROR` : lectures TrOCR fausses que le rapprochement
  accepte). Gardée pour voir si le lecteur de chiffres en profite.
- **Nombres : le plafond est TrOCR**, pas le nettoyage. Sur 250 réponses numériques, la 1ʳᵉ lecture de
  TrOCR base est le bon nombre 114 fois, un autre nombre valide 104 fois (chiffre isolé lu en double :
  `3` → `3 3`). Élargir la vignette en format « ligne » empire (25 exactes contre 34 sur 107).
- **Lecteur de chiffres** (`digits`, `digits_train`, intégré le 4 octobre) : la vignette d'un champ
  `number` est découpée en chiffres, chacun classé par un petit réseau (inférence numpy, modèles de
  0,85 Mo fournis dans `thessalia/data/`). `ocr` s'en sert pour la **proposition** des nombres en revue ;
  il ne change jamais un statut (`--no-digits` pour s'en passer). Un mot du vocabulaire (« ERROR ») est
  gardé si le moteur de texte en est proche et que les chiffres sont peu sûrs.
  - Modèle MNIST seul : 135/250 nombres justes (`1` à la française lus `7`).
  - Affiné sur les chiffres du lot (`digits-train`), validation croisée par copie : 190/250
    (195/250 avec `--bridge-line`).
  - De bout en bout, proposition juste sur les 304 champs numériques : 163 avec TrOCR seul, **235** avec
    le lecteur affiné (validation croisée) ; réponses non numériques préservées (46 justes contre 48).
  - Accord des deux lectures : 111 cas dont 102 justes ; avec confiance ≥ 0,95 : 62 dont 60. Pas encore
    assez sûr pour accepter seul.
  - Le modèle affiné sur tout le lot EN est fourni avec le paquet (`thessalia/data/digits_affine.npz`,
    0,85 Mo, utilisé par défaut) : il ne contient que des poids, l'enseignant a autorisé son partage entre
    collègues. Ses étiquettes viennent de la vérité **non validée**. Sur le lot EN lui-même il donne
    269/304 : chiffre optimiste (copies vues à l'affinage), à ne pas citer comme mesure.
  - **Contrôle sur un autre lot** (Booster supA 1, 9 copies, sujet FR, `sorties/supA_1_v3`, 4 octobre) ;
    référence = lecture de Claude, non validée (`data/truth/booster_supA1.numbers_truth.json`, hors dépôt) :
    108 nombres lisibles, proposition juste 51 avec TrOCR seul, **90** avec le lecteur ; les 19 `ERREUR`
    sont tous conservés (14 acceptés, 5 en revue) ; aucune acceptation fausse sur ces champs.
    Accord des deux lectures : 54 dont 48 justes ; avec confiance ≥ 0,95 : 28 dont 27. Les deux moteurs
    se trompent ensemble sur les `1` à la française lus `7` (copie 5 : `1024` → `7024`) : l'accord
    n'est pas une preuve indépendante.
- `ocr` enregistre chaque lot lu dans `ocr_lectures_<moteur>.json` : une commande interrompue reprend où
  elle s'était arrêtée (option `--batch` pour réduire la mémoire).
- **Vérité terrain validée par l'enseignant le 4 octobre** : `data/truth/EN_blanc.short_truth.json`
  (777 réponses, aucune incertaine ; hors dépôt). Par rapport à la lecture de Claude : 28 incertaines
  confirmées, 14 confusions point / virgule, 13 autres erreurs. L'ancien fichier
  `python_core_EN_examen_blanc.short_truth.json` est conservé mais ne doit plus servir de référence.
  Mesures refaites sur la vérité validée (TrOCR base, 754 réponses non vides) : 200 acceptées dont
  199 justes (même erreur c07_q2.1) ; lecteur de chiffres en validation croisée par copie : 200/275
  (MNIST seul : 143/275). Le modèle fourni `digits_affine.npz` est réaffiné sur cette vérité.
- **Point et virgule distingués** (décision de l'enseignant, 4 octobre : `2,5` est une faute courante en
  Python). `parse_number` conserve le séparateur écrit ; un nombre décimal n'est **jamais accepté seul**
  et les deux écritures sont proposées. Règle de l'enseignant : **une virgule détectée est gardée ; quand
  la machine n'est pas sûre, le doute profite à l'étudiant** (point proposé, virgule en second choix).
  « Détectée » = le moteur de texte ET la forme du séparateur (plus haut que large) voient une virgule :
  sur le lot EN, 4 vraies virgules sur 5 ; une seule lecture est trop peu fiable (texte 6/8, forme 10/14).
  Sans lecteur de chiffres (`--no-digits`), la virgule lue par le moteur de texte est conservée.
  Statistiques d'erreurs par question pour l'enseignant : souhaitées, reportées à plus tard.

## 4. Prochaines étapes, dans l'ordre

1. **Installer et vérifier** : `pip install -e ".[ocr-light,trocr,dev]"` puis `pytest -q` (13 tests, ~1 min).
2. **Lots Booster** (`scans/Copies Booster Python 2627/`, 26 PDF, une classe par PDF). Les classes
   « sup nb » et « supNA » ont passé le **sujet EN**, les autres le sujet FR (indication de l'enseignant).
   `supA 1` est dans `sorties/supA_1_v3` ; les 25 autres sont traités dans `sorties/booster/<classe>/`
   (Niveau 1 + vignettes, relancé le 5 octobre après la correction ci-dessous).
   **Page 1 « illisible » expliquée** : la première page de chaque PDF de classe est la feuille de
   présence (liste d'émargement, avec des noms), pas une copie. Depuis le 5 octobre, une page non
   reconnue avant la première copie est ignorée et consignée (`other_pages` de `results.json`), sans
   ligne de revue. Si la première copie ne commence pas à la page 1, les pages non reconnues juste avant
   lui sont rendues comme « page illisible » (cas réel : supE 2, copie 1).
   **Bilan des 25 lots (5 octobre)** : 305 copies, 5 177 pages reconnues, 20 feuilles de présence
   ignorées, aucun « gabarit douteux » (score médian 0,96-0,97 partout). 2 pages illisibles (supE 2,
   copie 1, pages 1 et 2). 153 points en revue dont 112 questions de QCM (4,6 % des 2 440 questions)
   et 33 « fiducial reconstruit ». 6 pages manquantes dans 3 copies (supB 2, supB 3, supNA 2 : une
   feuille recto-verso absente du scan).
   Les réponses courtes (`ocr`) ne sont pas encore lues sur ces lots ; QCM non validés par l'enseignant.
   **Seuil des repères relevé de 0,50 à 0,62 le 5 octobre** (`align.detect_fiducials`) : sur ces scans un
   repère est parfois rendu en gris uniforme à 128 sur papier à 255, soit exactement 50 %, et était manqué
   d'un niveau de gris (page 17 surtout : 30 manquantes sur 144 copies FR, ~235 « fiducial reconstruit »).
   Validation : supB 2 passe de 13 points en revue (5 pages illisibles) à 6 (seule la feuille de
   présence illisible) ; simulé difficile graine 7 : 0 FAUSSES, 17,7 % en revue ; lot réel EN :
   `results.csv` et `review.csv` identiques.
   `align.py` / `omr.py` ont aussi été modifiés le 1ᵉʳ octobre au soir sans trace écrite (avant le dépôt
   git) — seuls leurs effets sont mesurés (§6 toujours respecté).
   **Garde-fou ajouté le 4 octobre** : un lot EN lu avec le gabarit FR passait sans aucune alerte (pages
   alignées, 3 à 11 points en revue) ; `process` signale maintenant « GABARIT DOUTEUX » en tête de
   `review.csv` quand le score de reconnaissance médian est < 0,85.
3. **Nombres** : TrOCR large essayé, non retenu (§3). Le lecteur de chiffres fournit la proposition ;
   pour **accepter** des nombres sans erreur il reste à traiter les résidus pris pour un point décimal
   (`22` lu `2.2`), les ratures, puis à remesurer l'accord des deux lectures sur une vérité validée et
   sur un deuxième lot (Booster).
4. **Vérité terrain** : lot EN validé (§3). Reste à valider le lot Booster supA 1
   (`sorties/supA_1_v3/validation.html`, commande `truth-page`).
5. Si TrOCR reste insuffisant : **affiner TrOCR** sur ces vignettes validées (quelques centaines suffisent
   pour un vocabulaire aussi restreint), ou tester un modèle de vision local (option GPU).
6. Puis, selon l'enseignant : revue par question (Niveau 4), diagnostic automatique de lot, Niveau 3.

## 5. Données (chez l'enseignant, jamais dans le dépôt)

- `python.pdf` : examen blanc EN, 378 pages = 21 copies × (17 pages + 1 verso blanc). Pages 1–22 en A3
  (feuille A4 dans la moitié haute, couchée), puis A4 avec rotations 90°/270° alternées ; ~100 dpi.
- `BOOSTER S1 2627 supA 1 python.pdf` : nouveau lot, non traité.

## 6. Repères chiffrés pour ne pas régresser

- Simulé difficile (`simulate --hard`, graine 7, 12 copies) : 0 erreur, ~20 % en revue.
- Lot réel EN : 357 pages identifiées, 21 pages blanches ignorées, `review.csv` = 8 QCM + 1 alerte
  « fiducial reconstruit » (copie 5, page 16).
- Temps : ~1 s/page au Niveau 1 sur 1 cœur ; la préparation des vignettes du Niveau 2 ajoute ~50 %.
