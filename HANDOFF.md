# Passation — état du projet au 3 octobre 2026

> Note de reprise rédigée par Claude (session cloud claude.ai) pour la suite du développement en local
> avec Claude Code. À lire avec `CLAUDE.md` (consignes) et `ARCHITECTURE.md` (conception détaillée).

## 1. En bref

| Niveau | État | Résultat mesuré sur le vrai lot (examen blanc EN, 21 copies, 100 dpi) |
|---|---|---|
| 1 — QCM / V-F | **Opérationnel** | 160/168 questions décidées automatiquement, **0 erreur** (validé par l'enseignant), 8 en revue |
| 2 — réponses courtes | **Chaîne en place, moteur à choisir** | nettoyage + rapprochement OK ; moteurs locaux testés trop faibles (cf. §3), **TrOCR base compris** (mesuré le 3 octobre) |
| 3 — code manuscrit | Non commencé | vignettes des cadres déjà découpées par `process` |
| 4 — interface de validation | Non commencé | une page HTML de vérification statique a servi pour le Niveau 1 |

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
  `number` est découpée en chiffres, chacun classé par un petit réseau (inférence numpy, modèle MNIST de
  0,8 Mo fourni dans `thessalia/data/`). `ocr` s'en sert pour la **proposition** des nombres en revue ;
  il ne change jamais un statut (`--no-digits` pour s'en passer). Un mot du vocabulaire (« ERROR ») est
  gardé si le moteur de texte en est proche et que les chiffres sont peu sûrs.
  - Modèle MNIST seul : 135/250 nombres justes (`1` à la française lus `7`).
  - Affiné sur les chiffres du lot (`digits-train`), validation croisée par copie : 190/250
    (195/250 avec `--bridge-line`).
  - De bout en bout, proposition juste sur les 304 champs numériques : 163 avec TrOCR seul, **235** avec
    le lecteur affiné (validation croisée) ; réponses non numériques préservées (46 justes contre 48).
  - Accord des deux lectures : 111 cas dont 102 justes ; avec confiance ≥ 0,95 : 62 dont 60. Pas encore
    assez sûr pour accepter seul.
  - Un modèle affiné sur tout le lot EN est dans `data/models/digits.npz` (hors dépôt, dérivé de copies ;
    étiquettes issues de la vérité **non validée**). Sur ce même lot il donne 269/304 : chiffre optimiste,
    à ne pas citer comme mesure.
- `ocr` enregistre chaque lot lu dans `ocr_lectures_<moteur>.json` : une commande interrompue reprend où
  elle s'était arrêtée (option `--batch` pour réduire la mémoire).
- **Vérité terrain** : `data/truth/python_core_EN_examen_blanc.short_truth.json` (777 réponses, lues par
  Claude, 37 incertaines marquées `?`), **pas encore validée par l'enseignant**. Hors dépôt (.gitignore).

## 4. Prochaines étapes, dans l'ordre

1. **Installer et vérifier** : `pip install -e ".[ocr-light,trocr,dev]"` puis `pytest -q` (12 tests, ~1 min).
2. **Nouveaux lots** reçus dans `scans/Copies Booster Python 2627/` (27 PDF, une classe par PDF). Seul
   `supA 1` a été traité (`sorties/supA_1_v3`, 9 copies, 7 points en revue). **Non résolu** : la page 1 du
   PDF est illisible (fiducials introuvables), et `align.py` / `omr.py` ont été modifiés le 1ᵉʳ octobre au
   soir sans trace écrite (pas de dépôt git) — seuls leurs effets sont mesurés (§6 toujours respecté).
3. **Nombres** : TrOCR large essayé, non retenu (§3). Le lecteur de chiffres fournit la proposition ;
   pour **accepter** des nombres sans erreur il reste à traiter les résidus pris pour un point décimal
   (`22` lu `2.2`), les ratures, puis à remesurer l'accord des deux lectures sur une vérité validée et
   sur un deuxième lot (Booster).
4. **Faire valider la vérité terrain** par l'enseignant (page HTML : vignette + transcription éditable,
   export JSON), surtout les 37 `?`.
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
