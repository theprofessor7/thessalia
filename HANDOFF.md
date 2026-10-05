# Passation — état du projet au 5 octobre 2026

> Note de reprise rédigée par Claude (session cloud claude.ai) pour la suite du développement en local
> avec Claude Code. À lire avec `CLAUDE.md` (consignes) et `ARCHITECTURE.md` (conception détaillée).

## 0. Point d'arrêt du 5 octobre 2026 (à lire en premier)

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
  identiques. Le lot `sorties/booster/supE_2` n'a pas été retraité.
- **Propositions prises pour des « traductions »** (remarque de l'enseignant sur la page de validation de
  supA 1) : une lecture TrOCR illisible était remplacée par le mot du vocabulaire le plus proche (`input`
  lu « im-ment » → proposé « lire », `str` lu « crn. » → « chaîne »). Jamais accepté seul, mais trompeur.
  Mesure (champs `enum` en revue, EN + supA 1, proposition juste / cas) selon la distance : 0,34-0,55 :
  84/108 ; 0,55-0,65 : 30/52 ; 0,65-0,75 : 10/28 ; > 0,75 : 2/20. Depuis le 5 octobre, au-delà de 0,75
  (`vocab.snap`, `far`) la proposition est la lecture brute (« hors vocabulaire : aucun mot proche, lecture
  brute »), les mots proches restent en suggestions. Acceptés inchangés (supA 1 : 82 dont 82 ; EN : 200
  dont 199). **Partiel** : « lire » et « chaîne » sont vers 0,6 et restent proposés ; abaisser `far` à 0,65
  ou 0,55 se décide avec l'enseignant (on perd autant de bonnes propositions qu'on en retire de mauvaises).
- **Virgules sur supA 1** : 6 vraies virgules, 1 seule « détectée » (les deux lectures d'accord), les 5
  autres proposées avec un point et la virgule en second choix (règle du doute) ; toutes en revue. Sur EN
  c'était 4 sur 5 : la détection de la virgule est à remesurer sur les deux lots avant d'y toucher.
- **Vérité supA 1, entrées à relire par l'enseignant** (elles reprennent la lecture brute de la machine) :
  c05_q7.1 `Bongoun - Alice` (écrit « Bonjour - Alice »), c08_q14.2 `Grandletit` (« GrandPetit »),
  c07_q7.3 `X.X` (un mot raturé puis « XY » ?), c07_q7.2 `A-P-C`, c04_q7.3 `" X "Y .`.

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
