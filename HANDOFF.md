# Passation — état du projet au 26 octobre 2026

> Note de reprise rédigée par Claude (session cloud claude.ai) pour la suite du développement en local
> avec Claude Code. À lire avec `CLAUDE.md` (consignes) et `ARCHITECTURE.md` (conception détaillée).

## 0. Point du 23-26 octobre 2026 (à lire en premier)

**Booster : 3 erreurs d'attribution corrigées** (notes inchangées, élèves inversés) : supD_2 c04 était MESNIL
(attribuée à MERLIN, qui était absent), supB_1 c12 / supB_3 c08 inversées (DUBOIS / DUBOST). Toutes
confirmées à la main par l'enseignant ; trouvées par un second passage des 314 vignettes Nom/Prénom. Erratum
envoyé par l'enseignant. Classeurs regénérés (copies datées gardées).
- **`verif-noms`** (`thessalia/verif_noms.py`) : page locale nom écrit / élève attribué, copies à risque en tête
  (nom proche d'un autre élève du groupe, proche d'un absent par le rang ou le début du nom, autre groupe).
  Rejoué sur les attributions d'avant correction : les 3 erreurs sont en tête (56 copies à risque sur 314).
  À lancer avant chaque export.
- `lire_liste` refuse de choisir entre plusieurs `.xlsx` dans `data/listes/` (l'ordre des noms dépend du système :
  une liste déposée à côté avait été lue à la place de `Liste SUP.xlsx`) ; ignore le verrou Excel `~$…`.
- `excel` : colonne « Note arrondie » (demi-point supérieur, comme le faisait l'enseignant) ; copie datée
  `<nom>.avant-AAAAMMJJ-HHMM.xlsx` avant tout écrasement.
- Noms manquants signalés par l'enseignant (3 élèves) : absents de la liste de l'école
  (l'un d'eux est en SPE). Rien à faire côté Thessalia.

**Lot BIS (rattrapage, sujet B FR) : 7 copies notées**, `sorties/bis/BIS`, classeur `sorties/notes/notes_BIS.xlsx`
(moyenne 11,03 ; 5 convoqués absents). Scan : feuille d'émargement + verso blanc + 7 × (17 pages + 1 blanche).
- Sujet B : `templates/socle_python_FR_B.json` (mêmes champs que le A, q19 en p. 17) ; `keys/socle_python_FR_B.*`
  tirés du corrigé (`keys/…_CORRIGE.pdf`, hors dépôt) ; barème du code arbitré par l'enseignant (note du fichier).
  `template` gère maintenant un énoncé en bas de page dont les cadres sont sur la page suivante.
- **Session à part** : `data/listes/<classe>.convoques.txt` (hors dépôt, « NOM Prénom » de la liste de l'école) :
  noms proposés, absents de l'Excel (seuls les convoqués), `verif-noms`. Convoqués BIS = exactement les 12 absents
  du Booster corrigé.
- **Biais des modèles sur un nouveau sujet (mesure)** : trocr_v2/v3 affinés sur le sujet A proposent des réponses
  du A (« ERREUR » ou « Petit » pour « Impair », « 2.5 » pour « 30 »). Lecture brute juste : v2 62 %, v3 56 %
  (contre 70 / 78,5 % sur une classe A jamais vue). Acceptations d'office qu'il y aurait eu : v2 seul 12 fausses
  sur 91, v3 seul 12/91, v3 + accord v2 (réglage du Booster) 3/80. → **Règle `lecture_validee`** : sans
  `"lecture_validee": true` dans le corrigé, `ocr` n'accepte rien d'office (posé sur les sujets A FR/EN, pas sur B).
  Prochain affinage : mélanger les sujets, mesurer sur un sujet jamais vu ; sur un sujet nouveau v2 > v3.
- Code : 52 cadres lus en session par 2 sous-agents (questions entières par agent), critères pré-cochés,
  validés tels quels par l'enseignant (52/52) ; 11 « vide ? » confirmés.

**Outil de correction** : **pinceau** (idée de l'enseignant : 🖌 ou P prend une lecture, clic ou glisser bouton
enfoncé l'applique aux autres vignettes, d'un bloc à l'autre, Échap) ; « vide pour le bloc » sur un bloc sans
lecture (90 des 540 « vide » du Booster étaient saisis carte par carte).

**Regroupement par image : deux résultats négatifs** (lecture seule, sur 4 444 réponses vérifiées du Booster) :
blocs par texte lu aujourd'hui 1 301 (pureté 92,7 %, 44 % des réponses dans un bloc pur ≥ 2) pour 1 013 idéaux.
Pixels (encre recadrée, floutée, cosinus, liaison moyenne) : ≥ 2 994 blocs, pire. Fusion des blocs dont les
lectures (proposition + autres) se recoupent : 816 blocs mais pureté 83 %, 16 % en bloc pur. Le pinceau couvre le
besoin. Piste non essayée : vecteurs de l'encodeur TrOCR (plus lourd en mémoire et en temps).

**Suite** : premier vrai lot vers le 1er novembre (sujet A) ; avant l'export, `verif-noms`. Idées en attente :
bouton « ⇄ » séparateur collé à la lecture (la touche 6 le fait déjà : 60/60 corrections de séparateur l'avaient en
1re autre lecture), encodeur TrOCR pour le regroupement, affinage multi-sujets.

**Architecture des lecteurs (décision de l'enseignant, 26 octobre)** : le socle (TrOCR local + revue humaine)
doit donner un résultat acceptable sur tout PC ; un lecteur branché (Claude, ChatGPT, Mistral, Qwen-VL /
DeepSeek-VL / MiniCPM-V via Ollama ou vLLM sur GPU loué…) ne fait que réduire la revue, et ne gagne
l'acceptation automatique qu'après mesure sur les vérités. À faire :
- commande « second lecteur » pour les réponses courtes, branchée sur les adaptateurs de `lecteur_code.py`
  (claude / openai-compatible), qui remplit le fichier générique de lectures secondaires ;
- banc d'essai des lecteurs : les 247 réponses vérifiées du BIS (+ un groupe du Booster), lecture juste et
  surtout réponses fausses qu'il aurait acceptées, sur un sujet jamais vu par le lecteur.
- **Regroupement par empreintes de l'encodeur trocr_v2 (essai du 26 octobre, positif mais modeste)** : moyenne des
  patchs de l'encodeur, cosinus, liaison moyenne, par (groupe, champ) ; 1,6 s/vignette sur CPU, lancé hors de Claude
  Code (`data/models/lancer_essai_empreintes.ps1`, script et empreintes dans `data/models/essai_empreintes/`).
  « Bloc pur » = toutes les réponses du bloc identiques ; « en bloc » = part des réponses dans un bloc pur de 2+.
  BIS (sujet nouveau, 245 rép., 73 blocs idéaux) : texte lu 101 blocs, pureté 95,5 %, en bloc 67 % ; **texte lu +
  fusion des blocs par empreintes (seuil 0,05) : 82 blocs, 95,1 %, 73 %**. Booster A+B (sujet connu, 2 226 rép.,
  337 idéaux) : texte lu 457 blocs, 95,2 %, 57 % ; même fusion 345 blocs, 93,0 %, 48 % (moins bien).
  → utile quand la lecture est mauvaise (sujet nouveau) : **option** à construire (décision de l'enseignant) —
  commande par lot qui calcule les empreintes une fois, sélecteur « regrouper par : lecture | ressemblance » dans la
  vue par question, absent sans le fichier. Seuil choisi après coup sur 245 réponses : à confirmer sur un autre lot.
- Ollama 0.40.11 installé (compte de l'enseignant, 26 octobre) pour essayer un VLM local (`qwen3-vl:4b-instruct`,
  CPU seul : Core Ultra 7 155H, 16 Go, pas de carte graphique dédiée) via l'adaptateur « compatible OpenAI »
  (`http://localhost:11434/v1`). Essai rapide (5 vignettes) : vignette brute meilleure que nettoyée, 3/5 justes,
  ~32 s/vignette. Banc complet sur les 247 réponses du BIS : `data/models/lancer_banc_qwen.ps1` (fenêtre séparée,
  ~2 h, reprend après arrêt ; lectures dans `data/models/banc_qwen/lectures.json`, bilan dans `resultat.txt` :
  justes Qwen / v2 / v3, rattrapages, accords v2 = Qwen et combien sont faux).
- **Piste : un VLM local comme amorce d'un sujet nouveau (idée de l'enseignant, 26 octobre)**. Qwen n'a jamais vu
  nos copies, donc il n'a pas le biais « sujet A » de v2/v3 (les 3 erreurs muettes du BIS). Mais il est trop lent
  pour un lot entier (Booster ≈ 11 000 vignettes ≈ 100 h sur CPU) et ne s'affine pas sans GPU. Schéma proposé,
  calqué sur le Booster, où j'ai fait l'amorce :
  1. Qwen lit ~30 copies du nouveau sujet (une nuit) ;
  2. l'enseignant valide dans l'outil ;
  3. on affine TrOCR sur cette vérité ;
  4. TrOCR lit le reste et Qwen ne relit que les cas douteux.

  À trancher avec le banc :
  - Qwen lit-il mieux que TrOCR sur un sujet inconnu ?
  - « corrige »-t-il l'étudiant (`2,5` → `2.5`, orthographe) ?
  - l'accord TrOCR = Qwen est-il assez sûr pour accepter automatiquement ?

  Règle envisagée :
  - sujet « lecture validée » et TrOCR sûr : accepté ;
  - sinon, TrOCR = Qwen : accepté, si le banc le justifie ;
  - désaccord : revue, avec les deux lectures en boutons ;
  - nombre décimal : toujours en revue.

  Pour gagner du temps, Qwen ne lirait ni les zones vides ni les lectures sûres. Pour un gros lot, l'enseignant
  passerait une classe à la fois (~1 000 vignettes ≈ 9 h sans ces filtres).
- **Résultat du banc Qwen 4B (26 octobre, 247 réponses du BIS, vignette brute, ~32 s/vignette)**.
  - Lectures justes : Qwen 55 %, v2 62 %, v3 55 %. Au moins l'un des deux (v2 ou Qwen) : 81 %.
  - 58 réponses où Qwen lit juste alors que la proposition de l'outil était fausse.
  - **Accord v2 = Qwen : 92 réponses acceptables (37 %), 0 fausse** une fois la vérité corrigée (v3 + v2 : 80, dont 3
    fausses).
  - Pas de biais « corrige l'étudiant » : 2 confusions point/virgule, une dans chaque sens.
  - Défauts : mots très courts de q2 (`int`, `str` → charabia), recopie de la ligne imprimée (q7.3), espaces
    ajoutés et minuscules (`1 + 2 + 3`, `erreur`).

  → bon second lecteur (accord = acceptation, lecture en bouton), mauvais premier lecteur.

  Les 3 « accords faux » étaient des **erreurs de saisie de l'enseignant** (copie 3 q8.3 `3.14` validé « float »,
  copie 7 q10.4 `8` validé « 7 », copie 7 q7.1 `A_B_C` validé « A B C » : clic de bloc ou pinceau). Corrigées ;
  `notes_BIS.xlsx` regénéré : élève 1 11,29 → 11,13 et élève 2 7,46 → 7,29, notes arrondies inchangées.
  **À construire : contrôle de fin de correction** = lister les réponses où deux lecteurs indépendants
  s'accordent sur une lecture différente de la décision enregistrée (ici 3 cas sur 247, tous des erreurs).
- **Banc « code pré-rempli »** : `data/models/lancer_banc_code.ps1 [modèle_vision] [modèle_texte] [-sansEnonce]`
  sur les 52 cadres décidés du BIS. Étape 1 : transcription (consigne de `lecteur_code`). Étape 2 : critères
  cochés d'après le barème et ses arbitrages. Le script compare les critères et les points avec l'enseignant, et la
  transcription avec celle de la session. Prévu : 8B avec et sans énoncé, puis 8B pour lire + 14B texte pour noter.
  - **Avec énoncé : le 8B répond « (vide) » sur des cadres pleins.** L'énoncé de q11 contient le programme imprimé ;
    sans énoncé, il lit le même cadre. Consigne courte sans exigence de fidélité : il corrige l'étudiant (`x` → `*`,
    parenthèses fermées). La consigne « ne corrige rien » est donc indispensable, et l'énoncé est nuisible à la lecture.
  - La consigne de `lecteur_code` dit « transcris le code » : une phrase d'explication (q11.a) est lue « (vide) ».
    À corriger : « le texte ou le code écrit ».
  - **Résultat, 8B sans énoncé (27 octobre, 52 cadres)** : transcription à 75 % de ressemblance avec la session ;
    7 lues « (vide) » à tort ou par hasard. Notes identiques à l'enseignant : 27/52 (session Claude : 52/52 gardées).
    - q11-q13 : ~5/7 justes ; q15 : 1/7 (+3,25 pt cumulés) ; q16 : 1/6.
    - Le malus est proposé 14 fois (enseignant : 1 fois).
    - 15 cadres trop notés, 10 pas assez : +5 pt sur 7 copies au total.
    - 65 s par transcription, 11 s par cadre pour les critères.

    → 8B **inutilisable pour cocher le barème**. Sa transcription est peut-être exploitable.
  - Suite : garder ses transcriptions, critères par `qwen3:14b` (texte). Malus seulement si l'erreur est flagrante ;
    critère coché seulement en citant la ligne qui le prouve.
  - **Résultat, critères par `qwen3:14b` sans réflexion sur les transcriptions du 8B** (`banc_criteres.py`,
    41 s/cadre) :
    - notes identiques 27/52 (= 8B), critères identiques 25/52 ;
    - malus 3 fois (réglé) ;
    - **trop notés 18, pas assez 7, +8 pt cumulés** : encore plus généreux ;
    - voit l'erreur sans en tenir compte (doute « 'x' n'est pas la multiplication », critère coché quand même).

    → en local sur ce PC, critères pré-cochés pas atteignables pour l'instant. Pistes : transcription locale affichée
    sous l'image, critères pré-cochés par API (option). Dernier test : 14B sur les transcriptions validées de la
    session (`--session`), pour séparer l'erreur de lecture de l'erreur de jugement.
  - **14B sur les transcriptions validées (27 octobre)** :
    - notes identiques 27/52 (comme sur celles du 8B), critères 21/52 ;
    - trop notés 17, pas assez 8, +4,3 pt, malus 4 ;
    - écarts dans les deux sens (c07 q16 : 1,5 contre 0 ; c01 q15 : 0,5 contre 1,25), q11.a ratée 3 fois sur 7.

    → le goulot est le **jugement**, pas la lecture. L'enseignant relativise : on compare un modèle local à un humain
    et à un grand modèle en ligne.
  - Pistes d'amélioration du pré-coché local :
    1. exemples déjà corrigés par l'enseignant (même question, autres copies), qui grossissent avec chaque lot ;
    2. une question fermée par critère (oui / non + ligne citée) ;
    3. exécuter le code transcrit sur des valeurs de test (critères objectifs ; limité par les fautes de syntaxe
       tolérées) ;
    4. mode réflexion ;
    5. plus gros modèle sur GPU loué (option).

    Test 1+2 écrit : `data/models/lancer_banc_exemples.ps1 [modèle] [nb_exemples]` (201 questions, 3 exemples max
    pris sur les autres copies, malus jamais proposé, transcriptions de session). Le BIS n'a que 7 copies, donc peu
    d'exemples : à refaire sur un lot comme le Booster.
  - **Piste 3, pré-cochage par exécution (idée de l'enseignant, 27 octobre)** : `data/models/banc_code/banc_tests.py`,
    sans modèle.
    - Le code transcrit tourne isolé (`python -I`, 5 s max), avec des `input()` simulés.
    - Les tests sont écrits par critère, de q11.b à q19. Une tranche de q15 doit donner son prix à ses deux bornes et
      pas aux âges voisins.
    - Un critère est pré-coché seulement si ses tests passent ; un échec ne décide rien.
    - Réparation par règles des fautes tolérées par le barème : `=<`, `≠`, `=` pour `==`, `:` ou `)` oubliés,
      `Print`, `²`, virgules oubliées dans `print`, `12€`, nom de variable écrit de deux façons. `x` n'est
      jamais réparé.

    Résultat sur 45 cadres testables :
    - transcriptions du 8B : 27 critères pré-cochés, **0 à tort** ;
    - transcriptions de session : 35 pré-cochés, **0 à tort** ;
    - sur 113 critères cochés par l'enseignant, la couverture reste faible : 27 à 35 retrouvés ;
    - 27 à 29 programmes ne tournent toujours pas (fautes plus lourdes), et q16, q18, q19 ne sont jamais
      pré-cochés.

    → **sûr mais partiel**, à l'opposé du 14B juge (couverture large, erreurs dans les deux sens). Suite : le 14B
    en **réparateur de syntaxe** seulement (consigne « ne change pas la logique »), puis les tests tranchent
    (`lancer_banc_tests.ps1`). À mesurer surtout : les critères cochés à tort après réparation.
  - **Décisions de l'enseignant (27 octobre)**.
    - **`x` pour `*` désormais accepté** : c'était un arbitrage ponctuel. La réparation le change en `*`. Avec ce
      réglage, réparation par règles : 8B 28 pré-cochés, session 36, toujours 0 à tort.
    - **Le BIS reste figé** : c'est une photo du logiciel au moment de son usage réel. Pas de nouveau calcul des
      notes ; son barème garde l'arbitrage `x` refusé.
    - **« Ne s'exécute pas, même après réparation des fautes tolérées » = signal d'infraction lourde au langage.**
      L'outil le signale (« infraction lourde ? ») et l'enseignant décide le malus. Sur le BIS, le malus n'a été
      mis qu'une fois pour 26 à 28 programmes qui ne tournent pas : la frontière est à mesurer après le réparateur 14B.
    - **« Le modèle s'adapte à nous, nous nous adaptons au modèle »** : pour les prochains sujets, écrire le
      barème du code en **critères observables** (« pour 13 ans, affiche 8 € ») et les tests avec le corrigé, une
      fois par sujet. q15 (tranches) marche bien ; q16, q18 et q19 (forme du code : « boucle while », « initialisations »)
      ne donnent rien.
  - **Le Booster comme échantillon d'entraînement et de mesure du code** : 314 copies, cadres de code transcrits
    en session, critères validés par l'enseignant = vérité. Usages :
    - écrire les tests du sujet A et mesurer le pré-cochage par exécution à grande échelle ;
    - réserve d'exemples corrigés (piste 1) ;
    - mesurer les transcriptions locales (8B) contre celles de la session ;
    - entraîner un lecteur.

    Toujours séparer les copies qui servent à affiner de celles qui servent à mesurer (validation croisée par copie).
- **Partage du modèle affiné entre profs de la même institution (26 octobre)**. Promotion unique, plusieurs profs :
  mêmes élèves, mêmes sujets, même usage. Partager le modèle est donc acceptable, avec un mot au DPO par prudence.
  - Par le dépôt : code, gabarits, corrigés, vocabulaires, barèmes et le marqueur `lecture_validee`.
  - Par un partage interne, hors dépôt : le dossier du modèle (`data/models/trocr_vN`).
  - Jamais : scans, vignettes, `data/truth/`, `appris.json` hors de l'institution.

  Boucle visée :
  1. chaque prof corrige ses classes ;
  2. il envoie ses vérités validées par un partage interne ;
  3. un responsable réaffine le modèle (v4, v5…) ;
  4. le modèle est redistribué à tous.

  Chaque version est numérotée et notée ici, avec les lots sur lesquels elle a été mesurée (jamais ceux qui ont
  servi à l'affiner). Qwen n'a rien appris des copies : chacun l'installe via Ollama, sans rien à transmettre.

## 0. Point du 23 octobre 2026

**Examen blanc Booster terminé : 314 copies notées sur 20** (QCM + réponses courtes + code), classeur
`sorties/notes/notes.xlsx` (hors dépôt, contient les noms). Moyenne 12,02 (code 5,15 / 11), 86 copies sous 10.
Reste : 2 copies dont 3 cadres de code sont sur une page absente du scan (feuille « À vérifier », note
provisoire), à noter sur le papier dans l'outil puis relancer `excel`.

**Identification** (commit 1fe6538) : 314 copies sur 314 attribuées (`data/listes/<classe>.csv`), 12 absents.
Un élève de la liste E a composé avec F : accepté après confirmation, il sort dans son groupe de la liste.

**Code (11 pts) : lu en session Claude Code, pas par l'API.** 2 560 cadres transcrits et notés au barème
(`keys/socle_python_FR.bareme.json`) par des sous-agents, en paquets de 75 cadres (planches de 3 cadres sans
identité), rangés dans `<classe>/code_lectures.json` (`fournisseur: session`, `criteres_proposes`).
Coût mesuré : ~5 % du quota hebdomadaire de l'abonnement (≈ 15-25 $ par l'API, estimation). L'option API
(`transcrire`) reste dans le code, opt-in et plafonnée.
- Lecture **stricte** voulue par l'enseignant (« l'humain a des biais positifs »), avec ses arbitrages :
  q17 `*` au lieu de `x` accepté ; q13 `int(input())` sur un prénom refusé (contresens) ; q13 prénom et nom
  collés acceptés ; q18 boucle qui s'arrête à 0 sans rien compter : critère 1 refusé ; q19 affichages
  présents mais valeurs fausses : laissé accordé (non tranché).
- **Toutes les propositions validées automatiquement à la demande de l'enseignant** (2 441 propositions,
  233 cadres « vide ? » sous 2 ‰ d'encre) ; ses 149 décisions manuelles conservées. Les validations auto
  portent `texte = "auto: lecture session"` / `"auto: vide (encre)"` dans `data/correction.sqlite` : on
  peut les retrouver et les annuler.
- Constat : beaucoup d'élèves écrivent **sous le cadre imprimé** (q15 surtout) → bouton **« voir la page »**
  sur chaque carte de code (page entière `pages/pNN_overlay.jpg`, au clic). Une copie de q19 renvoie à la
  page 17 : non couvert.
- Pièges de la lecture par sous-agents : donner à chacun **son propre dossier de brouillon** (trois agents
  q13 ont partagé un fichier ; vérifié sans mélange) ; règles de barème non écrites tranchées différemment
  d'un paquet à l'autre → lister les cas récurrents et les faire trancher par l'enseignant.
- **Identité** : chaque page porte Nom/Prénom en en-tête ; seuls les cadres découpés (`crops/`) sont sans
  nom. Ne jamais envoyer une page entière à un service externe.

**Ajouts** : `excel` (`thessalia/excel.py`, xlsx sans dépendance : feuilles Notes, Absents, À vérifier ;
mémoire des verdicts reconstruite comme dans l'outil, sinon ~1 300 réponses courtes paraissent en attente).

## 0. Point du 22 octobre 2026

**Tous les groupes sont corrigés : A à NB, 314 copies complètes** (QCM + réponses courtes). Reste : noms des
étudiants (`data/listes/<classe>.csv`, noms provisoires jusqu'ici ; liste fournie le 22), export Moodle, puis
le code Python (11 pts, « prochaine phase »).

**Ajouts** (commit d3d2f4b) :
- **Copies à reprendre sur le papier** (`/a-la-main`, bouton rouge en en-tête, bandeaux groupe et copie ;
  même liste à la fin de `process`, `report.copies_a_la_main`) : pages absentes du scan ou illisibles, réponses
  touchées, points en jeu. Cas : supNA_2 c12 (p. 4-5), supB_2 c7 (p. 6-7), supB_3 c1 (p. 12-13, pages de code),
  supA_1 c1 (page illisible en trop).
- **Erreur silencieuse corrigée** : un QCM d'une page absente n'avait pas de réponse lue, `grade_copy` le
  comptait 0 (« missing ») et la note passait « complète » (supNA_2 c12, q9). Il est maintenant à décider.
- **QCM « illisible »** (touche 5, second clic annule) : 0 point, même avec la règle par option (sinon
  « aucune case » rapporterait les cases laissées vides à raison).
- **Commande `bilan <groupes>`** (`thessalia/bilan.py`) : mesures ci-dessous, lecture seule.

**Mémoire et `3.14` en q10.3** : avec NA/NB, la lecture `3.14` est tombée à 150 « juste » sur 159 (< 95 %) ;
37 réponses E-H décidées par la mémoire sont revenues à l'enseignant : **4 étaient des `3,14`** notés justes à
tort. Le seuil a joué son rôle, mais une décision de la mémoire n'est pas définitive : les notes d'un groupe
peuvent repasser « incomplètes » quand d'autres classes s'ajoutent (vérifier avant tout export).

**Bilan** (`bilan G H NA NB`, lectures vérifiées par l'enseignant = cas difficiles ; G/H recalculés avec la
mémoire du 22) :

| | G | H | NA | NB |
|---|---|---|---|---|
| lectures vérifiées | 261 | 295 | 314 | 310 |
| proposition juste | 142 (54 %) | 183 (62 %) | 222 (71 %) | 231 (75 %) |
| bonne lecture dans les boutons, si proposition fausse | 71/119 | 77/112 | 59/92 | 66/79 |
| lecture brute juste v3 / v2 | 152 / 147 | 174 / 175 | 213 / 202 | 222 / 199 |
| décidées par la mémoire | 225 | 230 | 201 | 275 |

- Sujet EN mieux lu : q7.4 n'y coûte presque rien (27 et 25 propositions fausses en G et H) ; sans q7.4,
  G/H ≈ 61-68 %. **v3 dépasse v2 sur les cas difficiles EN** (+11, +23), pas sur le FR.
- **Séparateur sur l'EN : sans gain.** NA 50/61 comme la lecture brute ; NB 58/67 contre 61 (3 changements,
  0 à raison). Sur H : 6 sur 6. Petits nombres : à surveiller avant de s'y fier.
- Espace q7.3 (lecture) : `X Y` proposé juste 23/24 sur NA+NB.
- q14 EN : aucune réponse en français tapée hors supNA_2 c12 ; le biais `Zéro` de TrOCR est resté sans effet.
- Propositions fausses les plus fréquentes : q6.1, q6.2, q3.4, q7.1 (cibles d'un futur v4).

## 0 (suite). Point du 21 octobre 2026

**Groupes corrigés et notés** : A à H (G et H les 20-21 octobre). **Reste : NA (prévu le 22), NB** (sujet EN :
la mémoire des verdicts y sera presque vide, autre `exam_id`). Puis notes, export Moodle, le code (11 pts).

**Ajouts à l'outil** (commits cffbaa2, f9b3fd9) :
- **Détecteur point/virgule branché** (cf. §0 du 19 plus bas) : `separateur sorties/booster sorties/supA_1_v3
  --save image+lecteur` puis `separateur <classes> --indices` → `<classe>/separateur.json`. Indices écrits pour
  G, H, NA, NB. **À lancer à la main après `ocr` pour une nouvelle classe** (pas encore automatique).
- **Autres lectures en un clic** : jusqu'à 3 lectures de la machine sous la proposition (boutons « ou : »,
  touches 6, 7, 8), jamais pré-sélectionnées. Jugé par l'enseignant « gain de temps phénoménal ».
- **QCM** : un clic sur une case enregistre (plus de « valider » ; q1 à plusieurs cases : le dernier état fait foi).
- **Espace de q7.3** (`Classe._espace`) : lecture qui ne diffère du corrigé que par des espaces (`X Y` / `XY`) :
  blanc entre lettres mesuré, corrigé proposé si < 0,5 hauteur (seuil `ESPACE_SERRE`). Indice, jamais mémoire.

**Mesures sur G et H** (lectures confirmées ou tapées par l'enseignant = cas difficiles) :

| | G | H |
|---|---|---|
| lectures vérifiées | 254-258 | 272 |
| proposition juste | 133 (52 %) | 160 (59 %) |
| bonne lecture dans les boutons, si proposition fausse | 77/125 | 84/112 |
| v3 / v2 lecture brute juste | 149 / 144 | 171 / 172 |
| décidées par la mémoire | 225 | 232 |

- **v3 n'apporte presque rien sur les cas difficiles** (désaccords v2/v3 : G 28 contre 23, H 31 contre 32). Son
  gain sur supF 2 portait sur les réponses faciles, acceptées de toute façon. Avant un v4 : viser les réponses
  difficiles et fausses (étiquettes tapées), pas le volume.
- **Séparateur sur H** : 53/55 justes (lecture brute seule : 47) ; 6 propositions changées, 6 à raison.
- **Espace q7.3 sur H** : `X Y` proposé → faux 17/17 ; `XY` proposé → 1 juste, 2 faux.
- **Limite des boutons** : TrOCR ne garde que 3 candidats ; sur 390 lectures corrigées (A-G), la bonne est
  absente 131 fois, au rang 4-5 seulement 6 fois. Garder 5 à 8 candidats demande une relecture (heures) : pour
  les prochaines copies.
- Réponses fantaisistes (`"42","7"`) : illisibles pour le modèle, l'enseignant les tape (étiquettes de
  réponses fausses, les plus utiles à l'apprentissage).

**Sujet EN (NA, NB)** : traduction exacte du FR (enseignant, 21 octobre). `traduction_de` dans
`keys/python_core_EN.key.json` : la mémoire des verdicts est commune FR/EN pour les 29 champs de même corrigé
(`Classe.memory_id`) → 442 réponses EN décidées par la mémoire au lieu de 0. q14 EN : l'énoncé demande ce que
le programme affiche (`print("Large")`…) → les mots français sont faux, `Zéro` compris (`notes.EQUIV_ONE_WAY` :
`Zero` reste juste pour `Zéro` sur copie FR). **Piège** : TrOCR lit `Zéro` (accent ajouté) sur presque toutes
les copies EN en q14.3 — biais du modèle appris sur le FR, pas une preuve que l'étudiant a écrit en français.
Ne PAS ajouter les mots français au vocabulaire EN (tout `Zero` deviendrait faux) ; les `Zero` acceptés gardent
le bénéfice du doute. Seul cas net vu : supNA_2 c12 q14.4, lu `Négatif`, accepté `Negative` (à revoir).

**Gardé pour plus tard** : VLM local comme second lecteur via `lectures_secondaires.json` (essai sur ~50
vignettes de supF 2 ; risque : il « corrige » l'étudiant).

## 0 bis. Point du 19 octobre 2026

**La correction se fait désormais dans l'outil local** (remplace les pages `validation.html` du 18) :
`pip install -e ".[serveur]"` puis
`python -m thessalia serve sorties/booster sorties/supA_1_v3 --no-browser` → http://127.0.0.1:8765/.
Motif (enseignant) : 30 minutes de validation par classe, « la correction manuelle serait plus rapide ».
L'enseignant **juge** (verdict) au lieu de recopier la vérité ; il retouche la lecture seulement quand elle
est fausse.

- **Vues** : par question (réponses groupées par proposition identique, boutons de bloc « Confirmer le
  bloc », « bien lu pour le bloc », « = attendu pour le bloc », sans confirmation) et par copie (pages avec
  cadres colorés, note recalculée). Verdicts `juste` / `forme` / `faux` / `vide` / `illisible` (touches
  1 à 5, Entrée valide la proposition) ; « ✓ bien lu » (L), « = attendu » (A, faux négatif de lecture),
  « ✎ corriger la lecture » (T : le verdict est alors recalculé). Pages `/suivi` (erreurs de la machine
  relevées par l'enseignant : 0 acceptée puis corrigée sur ~5 760) et `/revoir?cles=classe/cle,…` (cas
  isolés à trancher). Notes : `/g/<groupe>/notes.csv`.
- **Moteur** (`thessalia/correction.py`) : décisions dans `data/correction.sqlite` (hors dépôt).
  Origine de chaque réponse, par priorité : enseignant > vérité validée > page absente > acceptée par la
  machine > vide douteux > deux lecteurs d'accord > **mémoire** > proposition.
- **Mémoire des verdicts** (par sujet, clé `exam_id` + champ + lecture nettoyée, jugements des **autres**
  classes seulement) : décide seule à partir de 10 jugements et 95 % du même verdict (l'enseignant accepte
  ~1 % d'erreur) ; sinon son verdict le plus fréquent est pré-sélectionné dès 3 jugements. `illisible`
  n'entre pas dans la mémoire.
- **Étiquettes d'apprentissage** écrites à chaque décision : `data/truth/<classe>.appris.json` (vérité
  validée, textes tapés prioritaires, et « juste » quand lecture brute = valeur = corrigé). Ce sont elles
  que lira le prochain réaffinage.
- **Règles de notation ajoutées le 19** : décimal à virgule laissé **faux** (« laisse à faux
  finalement ») ; une réponse numérique « calcul = bonne valeur » (`2^10 = 1024`, `7x2 = 14`) est juste
  (« mathématiquement c'est juste »).
- **Second lecteur** : fichier générique optionnel `<classe>/lectures_secondaires.json`
  (`{cle: {lecture, sur}}`), jamais Claude en dur (projet distribuable). Mesuré TrOCR + Claude d'accord et
  sûrs : 498 décidées sur 1 064, 1 erreur. Appliqué à aucun groupe à ce jour. Le 20, l'enseignant a écarté
  l'idée de faire lire par Claude les désaccords v2/v3 (gain estimé modeste).
- **Nombres** : la proposition vient maintenant de TrOCR, la lecture du lecteur de chiffres en second
  choix (proposition juste : supA 3 155/173 contre 147, supB 3 139/157 contre 117). Réaffiner le lecteur
  de chiffres n'a rien apporté en pratique.
- **Résultats négatifs** : la probabilité TrOCR du texte attendu ne sépare pas juste/faux (TrOCR « voit »
  le corrigé, `42` pour `41`). Détecteur point/virgule (`thessalia/separateur.py`) :
  ne décide pas seul ; constat : `ocr_prep` efface la queue de la virgule près du soulignement.
  **Fusionné et branché le 20 octobre** comme indice : modèle `image+lecteur` (`separateur … --save
  image+lecteur`, `data/models/separateur.npz`), puis `separateur <classes> --indices` écrit
  `<classe>/separateur.json` ; l'outil y prend le séparateur de la proposition des décimaux en revue
  (virgule si P >= 0,5), jamais décidés par la mémoire. Mesure croisée sur 239 décimaux corrigés : 27
  séparateurs faux contre 46 (pénalisants 11 = 11, favorables 16 contre 35). Indices écrits pour G, H, NA,
  NB : 241 décimaux, 15 propositions changées. Pas encore automatique après `ocr`.

**Groupes corrigés et notés** : A (complet), B 31/33 (restent supB 1 c05 q3.1, supB 2 c07 pages 6-7
absentes), C 31/31, D 31/31, E 27/27, F 33/33. 9 décimaux litigieux tranchés à `/revoir` : 5 corrigés,
2 notes changées.

**`trocr_v3`** (`data/models/trocr_v3`, hors dépôt) : 1 passe depuis `trocr_v2` sur les étiquettes A à F
(supF 2 tenu à l'écart), 2 536 vignettes. Lancé par l'enseignant dans une fenêtre PowerShell à part
(`data/models/lancer_trocr_v3.ps1`) : la surveillance mémoire de Claude Code tuait l'entraînement ;
`trocr-train` sauvegarde maintenant tous les 300 lots et reprend en cours de passe. Mesure sur supF 2
(vérifié, jamais vu) : lecture juste 78,5 % contre 70 % pour v2, **mais 3 réponses fausses acceptées**
(`Booléen` lu `bool`, `return` lu `str`). Correctif : `ocr --confirm-model data/models/trocr_v2` (une
réponse n'est acceptée que si v2, déjà en cache, donne la même lecture brute) → 0 erreur, même volume
accepté ; vocabulaire des types complété (`string`, `chaîne`, `entier`, `réel`, `booléen`, `return`…).

**G, H, NA, NB relus le 19 au soir** avec
`ocr … --model data/models/trocr_v3 --confirm-model data/models/trocr_v2` (en service). À décider
(v2 → v3) : supG 1 273 → 270, supG 2 219 → 217, H 555 → 550, NA 571 → 567, NB 613 → 622. Le volume ne
bouge pas (l'accord de v2 le borne) ; v3 change la proposition d'environ 15 % des vignettes (36 à 102 par
classe). **À mesurer** après la correction d'une de ces classes : combien de propositions v3 l'enseignant
a gardées.

**Suite** : corriger G, H, NA, NB dans l'outil ; notes de ces groupes ; mesurer v3 sur une classe
corrigée ; puis commande `apprendre` (réaffinage automatique à partir des `appris.json`), export Moodle
(liste réelle), et le code (11 pts) par l'API Claude à la demande de l'enseignant.

## 0 quater. Point du 18 octobre 2026

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

**Groupe A noté** (`sorties/notes/A.csv`, 28 notes complètes sur 29). `trocr_v2` sur supA 3 (jamais vu) :
175 mots acceptés dont 174 justes (c04_q8.6 : mot raturé au gribouillis puis `1`, accepté `str` ; la règle
du mot barré ne voit que les traits) ; 60 nombres acceptés, justes. Vérité supA 2 : c06_q10.4 `tERREUR`
(faute de frappe) → `ERREUR`.

**« Le modèle manque de confiance » (remarque de l'enseignant)** : sur 4 classes lues avec `trocr_v2` et
validées, 356 des 478 réponses en revue (74 %) étaient déjà justes : chiffres seuls aux deux lectures
d'accord 154/157 (en revue volontairement : accepter aurait fait 3 erreurs), q7 106/115 (toujours en revue),
décimaux 25/56. Décisions du 18 octobre au soir, dans la page de validation :
- bouton « Valider ce bloc » par série de propositions identiques ;
- **les réponses acceptées par la machine arrivent validées d'office** (filtre « acceptées par la machine
  (contrôle rapide) ») : environ moitié moins de réponses à traiter (supC 1 : 338 au lieu de 666). Tant que
  l'enseignant n'y touche pas, elles ne sont **pas exportées dans la vérité** : `notes` les reprend de la
  lecture, l'affinage et les mesures les ignorent. Conséquence : sur une classe validée ainsi, la précision
  des acceptations ne se mesure plus (les acceptées non relues sont hors vérité) ; faire relire en entier
  une classe de temps en temps pour la suivre.
- À mesurer sur C et D : chiffres seuls « très sûrs » (47/47 jusqu'ici) avant de les accepter d'office.

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
