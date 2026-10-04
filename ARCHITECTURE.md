# thessalia — architecture

Correction assistée des copies papier des examens Python ESME (secours Moodle).
Entrée : copies remplies et scannées. Sortie : réponses détectées + tout ce qu'il faut pour qu'un humain valide vite.

## 1. Vue d'ensemble

```
                 ┌──────────────────────────── une fois par sujet ────────────────────────────┐
  sujet.html ──WeasyPrint──► sujet.pdf ──template_builder──► gabarit.json  (+ corrigé.key.json)
                                 │                               │
                                 └── rendu 200 dpi = pages de référence (vierges)
                 └─────────────────────────────────────────────────────────────────────────────┘

  scans (PDF/JPG/TIFF) ─► loader ─► align ─────────► page redressée (repère du PDF, 200 dpi)
                                    │ fiducials            │
                                    │ homographie          ├─► omr ─────► QCM / V-F  (niveau 1)
                                    │ n° de page + sens    ├─► extract ─► vignettes  ─► ocr_short (niveau 2)
                                    ▼                      │                          └► htr_code  (niveau 3)
                               regroupement en copies      └─► report ──► overlays, JSON, CSV
                                                                              │
                                                               review UI (niveau 4) ◄┘ ─► CSV notes / Moodle
```

Principe directeur : **chaque décision automatique porte un statut** (`ok`, `blank`, `review`). On vise un taux d'erreur *silencieuse* quasi nul, quitte à envoyer plus de cas en revue ; la revue humaine est rapide parce que tout est pré-rempli.

## 2. Modules

| Module | Rôle | Entrée → sortie |
|---|---|---|
| `template_builder` | Lit le PDF vierge **en vectoriel** (PyMuPDF) : fiducials, cases, blancs, cadres, questions, barème, libellés | `sujet.pdf` → `gabarit.json` |
| `loader` | PDF, images, TIFF multipage, dossiers ; niveau de gris « encre » (min RGB : l'encre bleue devient aussi sombre que la noire) ; estimation px/mm | fichiers → `ScanPage` (générateur, mémoire constante) |
| `align` | Fiducials (ouverture morphologique + filtres forme), reconstruction d'un fiducial manquant, homographie, identification page + orientation par corrélation avec les pages vierges | `ScanPage` → `AlignedPage` |
| `omr` | Raffinement local de chaque case (±2 mm), taux d'encre intérieur − vierge, double seuil + détection de traces claires, décision par question | page redressée → `{field_id: résultat}` |
| `extract` | Découpe identité, blancs, cadres texte/code | page redressée → PNG |
| `report` | Overlays colorés, `results.csv`, `review.csv` | résultats → fichiers |
| `grade` | Barème + corrigé (tout-ou-rien ou par option), `pending` si revue | résultats + clé → notes |
| `pipeline` | Orchestration, regroupement en copies, pages manquantes / en double | scans → dossier de sortie |
| `simulate` / `evaluate` | Copies synthétiques avec vérité terrain ; métriques | tests de non-régression |

Niveau 2 : `ocr_prep` (nettoyage), `ocr` (moteurs), `vocab` (rapprochement), `ocr_run` (commande `ocr`), `evaluate_ocr`. À créer : `htr_code`, `review_app` (voir §6).

## 3. Repère de coordonnées

Tout est en **millimètres, origine en haut à gauche de la page du PDF** (A4 = 210 × 297). Les fiducials sont exprimés dans ce même repère (centres : 11,5/17,5 — 198,5/17,5 — 198,5/281,5 — 11,5/281,5 pour le template v3). L'homographie envoie mm → pixels du scan ; la page redressée est rendue à `dpi` choisi (200 par défaut), donc `px = mm × dpi / 25,4`. Aucun module ne manipule de coordonnées pixels du scan brut, sauf `align`.

## 4. Formats d'échange

### 4.1 Gabarit (`thessalia/template@1`)

```jsonc
{
  "schema": "thessalia/template@1",
  "exam_id": "socle-python-2026-FR",
  "source_pdf": "26_27_Examen_Socle_Python_FR.pdf",
  "source_sha256": "…",               // alerte si le PDF de référence change
  "page_count": 17,
  "page_size_mm": [210.0, 297.0],
  "fiducials_mm": {"tl": [11.5, 17.5], "tr": [198.5, 17.5], "br": [198.5, 281.5], "bl": [11.5, 281.5]},
  "fiducial_size_mm": 5.0,
  "omr": { "full_policy": "checked" },  // optionnel : surcharge d'OMRConfig
  "questions": [
    {"num": 1, "id": "q1", "points": 1.0, "page": 2, "exercise": {"num": 1, "title": "…"},
     "prompt": "Parmi les noms…", "field_ids": ["q1"]}
  ],
  "pages": [
    {"page": 2, "fields": [
      {"id": "q1", "type": "mcq", "mode": "multi", "page": 2, "question": 1,
       "options": [{"id": "a", "label": "age_utilisateur",
                    "bbox_mm": [20.88, 63.57, 3.7, 3.7],     // [x, y, w, h] bord extérieur
                    "inner_mm": [21.3, 63.99, 2.86, 2.86]}]}, // intérieur (hors bordure)
      {"id": "q2.1", "type": "short_text", "prompt": "42 → type :", "bbox_mm": […], "line_mm": […],
       "vocab": null},                                        // niveau 2 : ["int","float","str","bool"]
      {"id": "q12", "type": "code_grid", "label": "PROGRAMME", "bbox_mm": […], "grid_mm": 5.0},
      {"id": "q11.a", "type": "text_box", "label": "EXPLICATION", "bbox_mm": […]},
      {"id": "identity.nom", "type": "identity", "label": "Nom", "bbox_mm": […]}
    ]}
  ]
}
```

Types de champ : `mcq` (single/multi), `truefalse` (une ligne du tableau V/F = un champ, options `V`/`F` ou `T`/`F`), `short_text`, `text_box`, `code_grid`, `identity`.
Le JSON est éditable : `mode`, `vocab`, `notes` et les champs marqués `"manual": true` sont conservés quand on régénère avec `--merge`.

### 4.2 Résultat d'une copie (`thessalia/result@1`)

```jsonc
{
  "copy_id": "copy_001",
  "pages": {"2": {"source": "scans.pdf#2", "rotation": 0, "match_score": 0.885, "match_margin": 0.37,
                  "fiducials_inferred": [], "warnings": [], "overlay": "copy_001/pages/p02_overlay.jpg"}},
  "missing_pages": [], "unreadable": [],
  "answers": {
    "q9": {"type": "mcq", "mode": "single", "selected": ["b"], "status": "ok", "flags": [],
           "options": {"b": {"label": "Type str , valeur \"17\"", "fill": 0.66, "faint": 0.71,
                             "state": "checked", "shift_px": [3, 0], "match": 0.61, "loc": "local",
                             "box_px": [173, 421, 190, 438]}}}
  },
  "flat": {"q1.a": false, "q1.c": true, "q9.b": true},     // {question_id.option: bool | null si revue}
  "fields": {"q12": {"type": "code_grid", "crop": "copy_001/crops/q12.png", "box_px": […]}},
  "review": [{"item": "q4.2", "reason": "plusieurs cases cochées (choix unique)", "overlay": "…"}],
  "grade": {"total": 2.1, "max": 2.25, "pending": [], "details": {…}}   // si corrigé fourni
}
```

États d'une case : `empty`, `checked`, `full` (noircie), `ambiguous`. Statut d'un champ : `ok`, `blank` (rien coché, net), `review`.

Les niveaux 2 et 3 **ajoutent** leurs clés dans `fields[id]` (`ocr`: {text, candidates, confidence, status}) sans toucher aux autres : le résultat reste un document unique par copie, enrichi étape par étape.

### 4.3 Sorties batch
`results.json` (toutes les copies, `flat` + notes), `results.csv` (une ligne par copie, une colonne par case, `;`), `review.csv` (une ligne par point à revoir avec lien vers l'overlay).

## 5. Niveau 1 — choix techniques et réglages

**Gabarit exact sans mesure.** Le PDF WeasyPrint est vectoriel : une case est un rectangle à bordure (3,7 mm, bordure 0,42 mm), un blanc est un rectangle à bordure basse seule, un cadre est un grand rectangle à bordure, un fiducial un aplat 5 × 5 mm. Les libellés viennent du texte du PDF. Le builder retrouve les 19 questions, 24 cases, 37 blancs, 9 cadres des deux sujets FR/EN sans réglage.

**Fiducials.** Seuil à 50 % du blanc papier, ouverture morphologique de 3 mm (efface texte, traits, grille, écriture, y compris le texte d'en-tête qui touche les carrés du haut), filtres taille ±40 % / carré / plein / ne touche pas le bord. Parmi les candidats, on choisit les 4 qui forment le rectangle attendu (côtés opposés égaux, diagonales égales, rapport 264/187), où que soit la feuille dans l'image (scan A3, page couchée, marges). 3 fiducials sur 4 suffisent (angle droit + parallélogramme). Une page sans fiducial et sans traits fins est classée « page blanche » et ignorée. Si la résolution déclarée est fausse (photo), ré-estimation en supposant un A4.

**Page et sens.** Les 4 fiducials sont symétriques : on teste les homographies compatibles (0°/180°, ou 90°/270°), puis on identifie la page en deux passes, **zones d'écriture masquées** :
1. *empreinte d'encre* à 50 dpi, tolérance ±1,2 mm : F1 entre « encre de la page vierge retrouvée dans le scan » et « encre du scan expliquée par la page vierge » — sur toutes les pages × orientations ;
2. *tuiles de texte* à 100 dpi (24 × 10 mm), chacune recalée localement (±2,5 mm) — sur les 4 meilleurs candidats. Indispensable pour séparer des pages de même mise en page (p15/p16 : paragraphe + exemple + grand cadre).

Une corrélation globale (première version) échouait sur 3,5 % des pages difficiles : les éléments communs à toutes les pages (fiducials, en-tête, blanc) dominent le score et un décalage de 0,5 mm suffit à inverser le classement. À quasi-égalité, on préfère la page attendue dans la séquence. Pages dans le désordre ou à l'envers : gérées.

**Cases.** L'homographie à 4 points ne corrige pas une feuille gondolée : chaque case est recalée localement (corrélation avec la case vierge dans ±2 mm), les recalages aberrants sont remplacés par la médiane de la question. Taux d'encre mesuré sur l'intérieur rétréci de 0,35 mm, image divisée par le fond estimé (ombrage, papier gris).

**Seuils (OMRConfig)** : `empty_max 0.06`, `checked_min 0.14`, `full_min 0.80`, `faint_min 0.12` (traces claires ≥ 12 % → revue), `halo_rature 0.08` avec `rature_min_fill 0.55` (rature débordante → revue). Une croix au stylo donne 0,35–0,8, une coche 0,3–0,55, un point d'hésitation < 0,04. Sur les vrais scans, recalibrer avec l'histogramme des `fill` (voir §7).

**Case noircie** (`full_policy`) : `auto` (défaut : seule dans sa question → cochée ; à côté d'une case cochée → revue) — `checked` — `cancelled` si la consigne dit « noircir pour annuler » et qu'elle est respectée — `review` pour tout envoyer à l'humain.

### Résultats mesurés (copies synthétiques, `simulate` + `evaluate`)

| Jeu | Copies / pages | Conditions | QCM auto justes | Erreurs silencieuses | Envoyées en revue |
|---|---|---|---|---|---|
| normal FR | 4 / 68 | 200–300 dpi, rotation ±2,5°, légère ondulation | 31/31 | 0 | 1 (2 cases en choix unique — voulu) |
| normal EN | 6 / 102 | idem, sujet anglais | 47/47 | 0 | 1 (idem) |
| difficile FR | 12 / 204 | 150–300 dpi, ±5°, perspective, papier gondolé 1,5 mm, pages à l'envers, JPEG 60 | 84/84 | 0 | 12 (10 croix au crayon clair, 2 doubles) |
| difficile FR | 25 / 425 | idem, autre graine | 185/185 | 0 | 15 (7 crayon clair, 8 doubles) |

Case par case : 1 108/1 108 justes hors revue. Écart entre classes : case vide ≤ 0,021 d'encre (point d'hésitation), case cochée ≥ 0,30 (coche fine) ; les seuils 0,06 / 0,14 sont au milieu. Identification de page : 425/425. Temps : ~1 s par page sur 1 cœur (≈ 17 s par copie de 17 pages, 25 copies ≈ 7 min).

### Premier lot réel — examen blanc EN, 21 copies (1ᵉʳ octobre 2026)

PDF de 378 pages (21 × 18 : 17 pages + 1 verso blanc), environ 100 dpi, scanner à chargeur. Les 22 premières pages sont des scans A3 contenant la feuille A4 couchée dans la moitié haute, les suivantes sont en A4 avec une rotation alternée de 90°/270° (recto/verso).

| | Résultat |
|---|---|
| Pages alignées et identifiées | 357/357, sans erreur (A3 et A4, 0°/90°/270°) |
| Pages blanches | 21/21 reconnues et ignorées |
| Questions QCM | 168, dont 160 décidées automatiquement et 8 en revue (4,8 %) |
| Erreurs silencieuses | **0 sur 160**, validé par l'enseignant sur la page de vérification ; 3 avant les ajustements (ratures lues « cochées ») |
| Cas en revue | 8, dont 7 dont la proposition était déjà juste ; la 8ᵉ (case redessinée) l'est désormais aussi |

Ce que les vraies copies ont appris, et qui est désormais pris en compte :
- **Ratures par gribouillage débordant** (copies 16, 18) : mesure du *halo*, l'encre dans un anneau de 0,4 à 2,5 mm autour de la case. Une croix est à 0,00–0,07, une rature à 0,08–0,27. Une case très encrée (≥ 0,55) avec un halo ≥ 0,08 part en revue.
- **Case noircie** : certains étudiants noircissent *pour cocher* (copies 17, 18 en Q4), d'autres *pour annuler* (copies 4, 7 en Q9). Avec `full_policy: "auto"` (défaut), une case noircie seule dans sa question est lue cochée, et une case noircie à côté d'une case cochée part en revue.
- **Correcteur blanc + case redessinée à la main** (copies 2, 6) : la bordure tremblée met de l'encre dans la case (jusqu'à 0,30), mais *rien au centre*. Mesure du *cœur* (carré central, 50 % du côté) : 0,00 pour les cases redessinées, ≥ 0,05 pour toutes les vraies marques. Une case « cochée » dont le cœur est vide (< 0,02) part en revue avec le motif « case corrigée/redessinée ? ».
- **Marques minimalistes** : barre oblique seule (« \ »), coche débordante. Lues correctement (0,18–0,49).
- **Fiducials cherchés par géométrie** (les 4 carrés formant le rectangle 187 × 264 mm) et non plus près des coins de l'image : indispensable pour les scans A3.

Réglages de numérisation à corriger pour les prochains lots : **format A4** (pas A3), **200 dpi minimum** (100 dpi fonctionne pour les QCM mais sera limite pour l'OCR des niveaux 2 et 3).

Ces chiffres valident la chaîne, pas les seuils sur tes vrais scans : le simulateur ne reproduit ni tous les styles de marques, ni ton scanner. Première chose à faire avec de vrais scans : 10 copies avec vérité saisie → `evaluate` → ajuster.

## 6. Feuille de route niveaux 2 → 4

### Niveau 2 — réponses courtes contraintes (q2, q3, q5–q8, q10, q14)

**Implémenté** (`ocr_prep`, `vocab`, `ocr`, `ocr_run`, `evaluate_ocr`) — voir HANDOFF §3 pour les mesures.
Contrainte : moteurs **locaux et gratuits par défaut** (TrOCR recommandé) ; API Claude / Google Vision en
option payante opt-in (clé dans l'environnement). Le plan d'origine ci-dessous reste la référence.

Pipeline par vignette `short_text` :
1. **Nettoyage** : soustraire la page vierge recalée (enlève soulignement, texte imprimé), ne garder que l'encre ; recadrer sur la boîte englobante de l'encre ; vide ⇒ `blank` directement (fiable, et c'est déjà une info de notation).
2. **Reconnaissance** : plusieurs candidats (beam search / top-k) plutôt qu'une seule chaîne.
3. **Snapping** vers le vocabulaire du champ, avec une distance d'édition *pondérée par les confusions manuscrites* (1/l/I/7, 0/O/o, 5/S, 2/Z, `"`/`''`, `.`/`,`) — `rapidfuzz` pour la vitesse.
4. **Décision** : accepté si distance ≤ seuil **et** écart suffisant avec le 2e candidat, sinon `review` avec les 3 meilleurs candidats proposés en boutons.

Le piège principal : **le vocabulaire doit contenir les mauvaises réponses plausibles**, pas seulement la bonne, sinon le snapping « corrige » les erreurs des étudiants vers la bonne réponse. Pour q2 : `{int, float, str, bool}` ; pour q3 : `{3, 2, 1024, 2.5, 11, 14}` + erreurs classiques (`3.4`, `2.0`, `20`, `4`, `2`) + valeur libre numérique parsée ; pour q8 : `<class 'int'>`, `int`, … (normaliser : minuscules, espaces, guillemets). Le champ `vocab` du gabarit accueille ces listes ; `"vocab": "number"` pour un nombre libre validé par parsing.

Modèles à comparer (sur 200–300 vignettes étiquetées) :

| Option | Pour | Contre |
|---|---|---|
| Tesseract 5 | déjà connu, rapide | médiocre en manuscrit, garder seulement comme témoin |
| TrOCR `microsoft/trocr-base-handwritten` / `-large-` | local, niveau « ligne », bon sur mots courts | entraîné sur de l'anglais (IAM) : accents, symboles de code moins bons ; fine-tuning utile |
| PaddleOCR / docTR | local, rapide, détection + reco | manuscrit moyen sans fine-tuning |
| Google Cloud Vision (`DOCUMENT_TEXT_DETECTION`), Azure Document Intelligence (modèle *Read*, ex-Form Recognizer) | très bons en manuscrit | payant, données hors établissement |
| VLM (Qwen-VL en local ; Claude / Gemini / GPT via API) | lit le contexte (« type : int »), gère symboles et code | coût/latence ; en local il faut un GPU |

Métriques : CER, exactitude par champ, **taux d'acceptation automatique vs erreur dans les acceptés** (courbe en faisant varier le seuil), temps de revue par copie.

### Niveau 3 — code manuscrit (q11.b, q12, q13, q15–q19)

1. **Isolation de l'encre** : soustraire le cadre vierge recalé (la grille est connue au pixel près grâce au gabarit ⇒ elle disparaît), plutôt que d'essayer de détecter la grille.
2. **Segmentation en lignes** : profil horizontal de l'encre, calé sur la grille 5 mm (une ligne de code ≈ 1 ou 2 carreaux) ; fusion des jambages qui débordent.
3. **Indentation** : abscisse du premier trait de chaque ligne, convertie en carreaux (grille 5 mm) puis regroupement (k-means 1D) en niveaux 0/1/2/3. Plus fiable que ce que l'OCR déduit des espaces.
4. **HTR** — deux familles à comparer :
   - *ligne par ligne* : TrOCR (fine-tuné sur tes données), Google/Azure ; on reconstruit le code avec l'indentation de l'étape 3 ;
   - *cadre entier* : VLM (Qwen-VL local, ou API) avec une consigne du type « transcris exactement, n'invente rien, garde les fautes, [?] si illisible ». Souvent le meilleur résultat brut sur du code, mais risque d'« auto-correction » du code de l'étudiant — à mesurer spécifiquement.
5. **Post-traitement Python** : normalisation des guillemets typographiques, `ast.parse` / `compile` ; règles de confusion ciblées (`;`→`:` en fin de `if/for/while/else/def`, `l`/`1`, `O`/`0` dans les nombres, `=`/`==` dans les conditions) appliquées **seulement si elles font passer le parse**, et affichées comme suggestions surlignées, jamais silencieusement.
6. **Sortie** : pour chaque question, vignette + transcription éditable côte à côte, lignes à faible confiance surlignées.

Bonus puissant pour la notation : une fois la transcription validée, l'exécuter dans le sandbox avec les jeux de tests CodeRunner que tu as déjà dans Moodle ⇒ pré-note automatique du code.

Métriques : CER par ligne, % de lignes exactes, % de programmes qui parsent, et surtout **effort de correction** (distance d'édition entre transcription proposée et version validée, rapportée à la longueur) — l'objectif réel est « le correcteur retouche < 30 % des caractères ».

### Niveau 4 — interface de validation

Flask + SQLite (Streamlit est plus rapide à prototyper mais se prête mal à une file de revue au clavier). Écrans :
- **file de revue** : seulement les éléments `review` (+ un échantillon aléatoire de `ok` pour contrôle qualité), vignette à gauche, proposition à droite, raccourcis clavier (Entrée = valider, 1–4 = choisir un candidat) ;
- **vue copie** : overlays de toutes les pages ;
- **export** : CSV de notes, et CSV d'import du carnet de notes Moodle (identifiant = n° étudiant).

Chaque validation est enregistrée (vignette, proposition, correction) : c'est **ton jeu d'entraînement gratuit** pour fine-tuner TrOCR sur l'écriture de tes étudiants et pour recalibrer les seuils.

## 7. Pièges attendus et parades

- **Scanner à défilement** : pages légèrement étirées ou tordues ⇒ le recalage local des cases l'absorbe ; surveiller `shift_px` et `match` dans les résultats.
- **Encre claire / crayon** : détectés comme trace claire ⇒ revue. Consigne « stylo bleu ou noir » déjà présente.
- **Cases noircies pour annuler** : fixer la convention dans la consigne, puis `full_policy`.
- **Réglages scanner** : 200–300 dpi, niveaux de gris ou couleur, **pas de binarisation** (noir & blanc 1 bit détruit les traces claires et le gris de la grille), pas de « suppression des pages blanches » (sinon pages manquantes).
- **Regroupement des copies** : aujourd'hui par ordre de numérisation + n° de page reconnu. Une copie dont on perd la page 1 se fond dans la précédente ⇒ `missing_pages`/pages en double signalés. Le QR code (hors scope pour l'instant) supprimerait ce risque.
- **Calibrage sur vrais scans** : scanner 10 copies remplies par des collègues avec des marques variées, saisir la vérité dans un `truth.json` (même format que `simulate`), lancer `evaluate`, ajuster les seuils.
- **RGPD** : les vignettes de réponses ne contiennent pas l'identité (elle est découpée à part) ⇒ on peut n'envoyer que des vignettes anonymes à une API cloud ; à valider avec le DPO de l'école.

## 8. Remarques sur le template v3 (observées dans les PDF)

1. Le texte de l'en-tête courant touche les fiducials du haut (« Examen — Socle Python » colle au carré gauche, les pointillés « Prénom : … » touchent le carré droit). La détection le gère (ouverture morphologique), mais **2–3 mm de marge** autour des fiducials rendraient la chose robuste aux bavures d'encre et aux photocopies.
2. Version EN : l'en-tête courant est resté « Nom / Prénom ».
3. Les cases V/F en tableau et les cases de 3,7 mm sont bien dimensionnées. Une consigne explicite pour annuler une case aiderait (voir `full_policy`).
4. Le nom manuscrit en en-tête de chaque page n'est pas encore exploité ; on pourra le découper pour confirmer le regroupement des pages par copie.
