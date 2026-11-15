// Guide de prise en main de Thessalia (PDF : docs/Thessalia_mode_emploi.pdf)
// Construire : python docs/guide/construire.py
// Captures : correction réelle du Midterm de novembre 2026 (supA), noms et notes floutés, barre latérale retirée ; réponses manuscrites gardées (accord de l'enseignant, 15 nov. 2026).

#let bleu = rgb("#2a5caa")
#let bleu-clair = rgb("#e8eef8")
#let vert = rgb("#2e7d4f")
#let vert-clair = rgb("#e6f3ec")
#let orange = rgb("#b5651d")
#let orange-clair = rgb("#fbf0e4")
#let gris = rgb("#5f6368")
#let fond = rgb("#f4f3ef")

#set document(title: "Thessalia — mode d'emploi", author: "ESME")
#set text(font: ("Segoe UI", "Helvetica Neue", "Arial", "Libertinus Serif"), size: 10.5pt, lang: "fr")
#set par(justify: false, leading: 0.68em, spacing: 1em)
#show raw: set text(font: ("Consolas", "Menlo", "DejaVu Sans Mono"), size: 9.5pt)
#show raw.where(block: false): box.with(fill: fond, inset: (x: 3pt, y: 0pt), outset: (y: 3pt), radius: 2pt)
#show raw.where(block: true): block.with(fill: fond, inset: 9pt, radius: 4pt, width: 100%)
#show link: set text(fill: bleu)

#set heading(numbering: none)
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  block(width: 100%, inset: (bottom: 8pt), stroke: (bottom: 2pt + bleu))[
    #text(size: 20pt, weight: "bold", fill: bleu, it.body)
  ]
  v(4pt)
}
#show heading.where(level: 2): it => block(above: 1.4em, below: 0.7em,
  text(size: 13pt, weight: "bold", fill: bleu, it.body))
#show heading.where(level: 3): it => block(above: 1.1em, below: 0.5em, text(size: 11pt, weight: "bold", it.body))

#set page(paper: "a4", margin: (x: 2cm, top: 2cm, bottom: 2.2cm),
  footer: context {
    if counter(page).get().first() > 1 [
      #set text(size: 8.5pt, fill: gris)
      Thessalia — mode d'emploi #h(1fr) #counter(page).display()
    ]
  })

// --- petits éléments
#let encadre(couleur, fond, titre, corps) = block(width: 100%, fill: fond, stroke: (left: 3pt + couleur),
  inset: (x: 12pt, y: 10pt), radius: (right: 4pt), breakable: false)[
  #if titre != none [#text(weight: "bold", fill: couleur, titre) \ ]
  #corps
]
#let astuce(corps) = encadre(vert, vert-clair, "Bon à savoir", corps)
#let attention(corps) = encadre(orange, orange-clair, "Attention", corps)
#let info(titre, corps) = encadre(bleu, bleu-clair, titre, corps)
#let bouton(t) = box(fill: bleu, inset: (x: 6pt, y: 2pt), outset: (y: 2pt), radius: 3pt, text(fill: white, size: 9.5pt, t))
#let bouton-clair(t) = box(stroke: 0.6pt + gris, inset: (x: 6pt, y: 2pt), outset: (y: 2pt), radius: 3pt, text(size: 9.5pt, t))
#let touche(t) = box(stroke: 0.6pt + gris, inset: (x: 4pt, y: 1pt), outset: (y: 2pt), radius: 2pt, text(font: ("Consolas", "Menlo"), size: 8.5pt, t))
#let capture(chemin, largeur: 100%, legende: none) = figure(
  box(stroke: 0.6pt + rgb("#c9c7c0"), radius: 3pt, clip: true, image(chemin, width: largeur)),
  caption: if legende != none { text(size: 9pt, fill: gris, legende) }, supplement: none, numbering: none)
#let pastille(n, couleur: bleu) = box(baseline: 25%, circle(radius: 9pt, fill: couleur,
  align(center + horizon, text(fill: white, weight: "bold", size: 10pt, str(n)))))
#let etape(n, titre, corps) = grid(columns: (26pt, 1fr), column-gutter: 8pt, row-gutter: 0pt,
  pastille(n), [#text(weight: "bold", size: 11pt, titre) \ #corps])

// ================================================================== couverture
#page(footer: none, margin: 0pt, fill: bleu)[
  #set text(fill: white)
  #place(top + left, dx: 2.2cm, dy: 7cm)[
    #text(size: 46pt, weight: "bold")[Thessalia]
    #v(0.2cm)
    #text(size: 18pt)[Corriger ses examens papier,\ du sujet aux notes]
    #v(1.6cm)
    #block(width: 14cm, text(size: 12pt)[
      Vous écrivez le sujet une fois. Thessalia fabrique le sujet et le corrigé en PDF, lit les copies
      scannées, vous présente ce qui reste à décider, et calcule les notes.
    ])
  ]
  #place(bottom + left, dx: 2.2cm, dy: -2.2cm)[
    #text(size: 12pt, weight: "bold")[Mode d'emploi pour les enseignants] \
    #text(size: 10pt)[ESME · version de novembre 2026 · gratuit, tout reste sur votre ordinateur]
  ]
]


// ================================================================== en bref
= Thessalia en bref

Thessalia tourne *sur votre ordinateur* et s'utilise *dans votre navigateur*. Pas de compte en ligne, pas
d'abonnement : *rien ne part sur internet*, ni les copies, ni les noms, ni les notes.

La machine fait le travail répétitif : elle lit les cases, déchiffre l'écriture, regroupe les réponses
identiques, exécute le code. Vous gardez le jugement : *chaque clic de votre part lui apprend quelque chose*, et
la classe suivante va plus vite que la précédente.

#info("Un exemple réel : le Midterm de novembre 2026, classe supA")[
  Ce guide suit la correction d'une vraie classe : *29 copies scannées en un PDF*, plus *1 copie composée sur
  un sujet imprimé en A3*, scannée à part. QCM, réponses courtes à la main, code manuscrit. Au départ, *866
  réponses à décider*. À la fin, l'enseignant : _« Je n'ai jamais corrigé une classe papier aussi vite. »_
  Les captures viennent de cette correction ; les noms et les notes y sont floutés.
]

#let case-etape(n, titre, texte) = block(width: 100%, fill: white, stroke: 0.6pt + rgb("#d5d3cc"), radius: 4pt,
  inset: 9pt, breakable: false)[
  #pastille(n) #h(4pt) #text(weight: "bold", titre) \
  #v(2pt) #text(size: 9.5pt, texte)
]
#grid(columns: (1fr, 1fr, 1fr), column-gutter: 8pt, row-gutter: 8pt,
  case-etape(1, "Ouvrir", [Lancer Thessalia, retrouver ses examens sur l'accueil.]),
  case-etape(2, "Charger les copies", [Un PDF du scanner par classe : cases lues, réponses découpées.]),
  case-etape(3, "Laisser lire", [La machine lit l'écriture et le code pendant que vous faites autre chose.]),
  case-etape(4, "Corriger", [Par question, par blocs de réponses identiques, en quelques clics.]),
  case-etape(5, "Ce qu'elle apprend", [Vos verdicts et vos lectures servent aux classes suivantes.]),
  case-etape(6, "Noms et notes", [Identifier les copies, puis un classeur Excel des notes sur 20.]),
)

#astuce[*Thessalia ne décide jamais en silence.* Quand la machine n'est pas sûre (case à moitié cochée, écriture
difficile, page illisible…), la réponse est *« à décider »*, avec la raison. Une note n'est définitive que
lorsque tout est tranché.]

// ================================================================== ouvrir
= 1 · Ouvrir Thessalia

== Installer, une seule fois

#etape(1, "Python et git")[
  Installer #link("https://www.python.org/downloads/")[Python] (Windows : *cocher « Add python.exe to PATH »*)
  et #link("https://git-scm.com/downloads")[git] (options proposées).
]
#v(4pt)
#etape(2, "Récupérer Thessalia")[
  Dans *PowerShell* (Mac : *Terminal*) : `git clone https://github.com/theprofessor7/thessalia.git C:\Thessalia`
]
#v(4pt)
#etape(3, "Installer")[
  Double-cliquer sur `installer.bat` dans `C:\Thessalia` (Mac : `./installer.sh`). Le *lecteur d'écriture*
  (2 Go) est proposé : facultatif, il s'ajoute plus tard depuis *Réglages*.
]

== Lancer, à chaque fois

Double-cliquer sur *`Thessalia.bat`* (Mac : `Thessalia.command`). Le navigateur s'ouvre ; *la fenêtre noire doit
rester ouverte*, c'est Thessalia qui tourne. Au premier lancement, choisissez un identifiant et un mot de passe.

#astuce[Mise à jour : Thessalia fermé, `git pull` dans `C:\Thessalia`, relancer `installer.bat`, puis
Thessalia. Vos examens ne sont jamais touchés.]

== L'accueil

#capture("img/accueil_cartes.png", largeur: 72%, legende: [Une carte par examen, avec « Ouvrir » et « Supprimer ».])

#bouton[Ouvrir] mène à la page de l'examen : un assistant en *six étapes*. Une étape faite est verte ✓, une étape
grisée dit ce qui lui manque. #bouton-clair[Supprimer] range l'examen dans la *corbeille* (en bas de l'accueil),
d'où #bouton-clair[Restaurer] le remet d'un clic.

// ================================================================== charger
= 2 · Charger les copies

Scanner *toutes les copies d'une classe en un seul PDF* : A4 ou A3, 100 dpi ou plus. Pages tournées, à l'envers
ou blanches : gérées.

#capture("img/charger_classe.png", largeur: 80%, legende: [Étape 3 : nom de la classe, langue du sujet distribué, PDF, puis « Déposer et lire ».])

#etape(1, "Nommer la classe")[
  Le nom range la classe dans son *groupe* : `supA` et `supA_2` → groupe A. Dans l'exemple, la copie composée
  sur un sujet A3 a été scannée à part et chargée comme `supA_2` : elle a rejoint les 29 autres copies du groupe A.
]
#v(4pt)
#etape(2, "Choisir la langue du sujet distribué")[FR ou EN (une erreur est signalée « GABARIT DOUTEUX »).]
#v(4pt)
#etape(3, "Déposer et lire")[Quelques minutes ; une jauge suit les pages, une fenêtre résume la fin.]

#capture("img/charger_classe_fin.png", largeur: 68%, legende: [Fin de lecture : ce qui mérite votre attention est signalé.])

// ================================================================== lectures
= 3 · Laisser la machine lire

À l'étape 4, #bouton-clair[Lire les réponses courtes] fait lire l'écriture des élèves (et leurs noms) par le
lecteur d'écriture, *sur votre ordinateur*. Pour supA, 766 vignettes : l'enseignant l'a lancée avant sa pause
déjeuner et a retrouvé tout lu en revenant.

#capture("img/ex_lecture_en_cours.png", largeur: 66%, legende: [La lecture tourne en arrière-plan ; « Me prévenir à la fin » envoie une notification Windows.])

#bouton-clair[Lancer la lecture approfondie] va plus loin, en quelques heures (une nuit) : un modèle local
recopie le *code manuscrit*, Thessalia l'*exécute* avec les tests du sujet et pré-coche les critères du barème.
Les deux tâches se mettent en pause (⏸) et reprennent là où elles s'étaient arrêtées.

#capture("img/ex_lecture_terminee.png", largeur: 60%, legende: [Fin de la lecture : il reste à corriger (étape 5).])

#info("Sujet nouveau : tout passe d'abord par vous")[
  Pour un sujet jamais corrigé, toutes les réponses courtes vous sont présentées, avec la lecture proposée. Après
  30 lectures vérifiées sans erreur, #bouton-clair[Sujet validé] laisse la machine accepter seule ses lectures sûres.
]

// ================================================================== corriger
= 4 · Corriger, par l'exemple

== Le tableau de bord et les questions

#bouton[Corriger les copies lues] (étape 5) ouvre l'outil. Une carte par groupe : ce qu'il reste à décider.

#capture("img/ex_tableau_de_bord.png", largeur: 50%, legende: [Au départ : 866 réponses à décider pour le groupe A.])

Dans un groupe, une case par question. Les QCM sûrs sont déjà faits (✓ vert) ; le bandeau rouge signale la copie
dont une page est illisible, à reprendre sur le papier.

#capture("img/ex_groupe.png", largeur: 88%, legende: [Le groupe A : on corrige question par question, « Commencer par q8.2 ».])

== Une question : les réponses identiques en blocs

Chaque page de question montre en haut *l'énoncé tel que l'élève l'a vu* (découpé dans le sujet, la case à
corriger surlignée) et l'attendu. Dessous, les réponses sont *regroupées par lecture identique* : les gros blocs
d'abord.

#capture("img/ex_bloc_bien_lu.png", largeur: 90%, legende: [q2 : deux élèves ont écrit « 23 » ; la machine l'a bien lu. « bien lu pour le bloc » le confirme en un clic.])

Le cas le plus spectaculaire : à la q5.2 (attendu `5`), la machine a lu « 55 » sur *9 copies* (le soulignement
pris pour un second 5). Un clic sur #bouton-clair[\= attendu pour le bloc] : les 9 réponses sont justes, et les 9
images deviennent des exemples pour que la machine ne refasse pas l'erreur.

#capture("img/ex_bloc_attendu.png", largeur: 90%, legende: [q5.2 : 9 réponses lues « 55 » alors que l'élève a écrit 5 : réglées d'un clic.])

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [#bouton-clair[Confirmer le bloc]], [accepter le verdict proposé pour tout le bloc ;],
  [#bouton-clair[bien lu pour le bloc]], [la lecture est exacte partout ;],
  [#bouton-clair[\= attendu pour le bloc]], [la machine a mal lu la même chose, tous ont écrit l'attendu ;],
  [#bouton-clair[vide pour le bloc]], [rien n'est écrit dans ces zones ;],
  [#bouton[Valider toutes les propositions]], [en haut : tout ce qui reste sur la question, une fois tout regardé.],
)

== Une réponse : la carte

#grid(columns: (32%, 1fr), column-gutter: 14pt,
  capture("img/ex_corriger_lecture.png", legende: [« corriger la lecture » : taper ce qui est écrit.]),
  [
    Chaque carte : l'image, ce que la machine a lu (*lu*), d'autres lectures possibles (*ou*), l'attendu et le
    verdict proposé (cadre pointillé). Un clic enregistre.

    Ici, la machine a lu « 64.8 » ; l'élève a écrit `4,8`. #bouton-clair[corriger la lecture] : on tape ce qui est
    écrit, le verdict se recalcule, et l'image rejoint les exemples d'apprentissage.

    #table(columns: (auto, 1fr), stroke: none, inset: (x: 4pt, y: 3pt),
      [#bouton-clair[✓ juste]], [tous les points],
      [#bouton-clair[½ forme]], [la moitié : bonne réponse mal écrite],
      [#bouton-clair[✗ faux]], [zéro],
      [#bouton-clair[ø vide] #bouton-clair[? illisible]], [rien d'écrit / impossible à lire],
      [#bouton-clair[bien lu]], [la machine a lu exactement],
      [#bouton-clair[\= attendu]], [l'élève a écrit l'attendu, mal lu],
      [#bouton-clair[↺]], [annuler la décision],
    )
  ])

*Une erreur fréquente ne se tape qu'une fois.* À la q9.2, beaucoup d'élèves ont écrit `{prix}` au lieu de
`{prix:.2f}`, et la machine lisait n'importe quoi (« Spring ? », « 5 points 3 . »). Une fois `{prix}` tapé, il
apparaît sur les autres cartes de la question : *« déjà saisi : {prix} ×18 »*, à prendre d'un clic.

#capture("img/ex_pinceau.png", largeur: 85%, legende: [« déjà saisi » sous la lecture, et le pinceau 🖌 : prendre une lecture, puis cliquer ou glisser sur les autres vignettes.])

== Le code manuscrit

Les cadres de code se notent *au barème* : un clic coche un critère. Après la lecture approfondie, la carte montre
la transcription du code, le résultat de son exécution et les critères pré-cochés (« ✔ test ») ; un critère non
vérifié (« ✗ test ») reste à juger. Les codes qui passent tous les tests forment un bloc « note pleine ? ».

#capture("img/ex_code.png", largeur: 82%, legende: [q25 : le code de l'élève, les critères du barème, « tout juste » / « rien de juste ».])

== Une copie entière

#bouton-clair[Copies et notes] montre une copie avec sa page scannée : chaque zone est cliquable, la note se met
à jour à chaque décision.

#capture("img/ex_copie.png", largeur: 68%, legende: [Une copie : la page à gauche, les réponses à droite (note floutée).])

// ================================================================== apprendre
= 5 · Ce que Thessalia apprend

== La mémoire de vos verdicts

Après chaque décision, un message en bas à droite dit ce que Thessalia en retient. La mémoire range vos verdicts
*par question et par lecture de la machine*, classe par classe. Une classe ne se juge jamais avec ses propres
décisions : ce sont *les classes suivantes* qui en profitent.

#capture("img/ex_memoire_message.png", largeur: 74%, legende: [q5.2 : « 5 » jugé juste 7 fois sur 7 ; 13 réponses identiques d'autres classes recevront ce verdict.])

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [*3 jugements*], [votre verdict le plus fréquent est *proposé* ailleurs (étiquette « ↺ vos verdicts ailleurs ») ;],
  [*10 jugements, 95 % d'accord*], [il est *appliqué d'office* (étiquette « ↺ mémoire »), toujours visible et annulable.],
)

== Les lectures que vous tapez

Une lecture tapée sur au moins 2 copies (comme `{prix}`) entre dans les *réponses plausibles* de la question à la
lecture suivante : la machine la propose alors directement au lieu d'une lecture fantaisiste. Les erreurs
classiques de vos élèves deviennent connues de la machine.

== Les lecteurs affinés

Toutes les lectures vérifiées (tapées, « bien lu », « = attendu ») sont des exemples. Le menu *Apprentissage*
les compte et réentraîne les lecteurs sur l'écriture de *vos* élèves. Après supA : 612 lectures jugées, 691
exemples pour le lecteur d'écriture, 187 pour le lecteur de chiffres.

#capture("img/ex_apprentissage.png", largeur: 58%, legende: [Apprentissage : la mémoire, et les lecteurs prêts à être affinés.])

Un lecteur affiné est mesuré sur une classe qu'il n'a jamais vue ; #bouton[Adopter] n'apparaît que s'il lit
mieux que l'actuel, et l'ancien est gardé.

#info("La routine entre deux classes")[
  #etape(1, "Finir la classe", [Toutes les questions décidées.])
  #etape(2, "Relancer « Lire les réponses courtes »", [Vos lectures tapées deviennent des réponses plausibles ; vos décisions sont gardées.])
  #etape(3, "Lecture approfondie de la classe suivante", [Le code transcrit et pré-coché, pendant une nuit.])
  #etape(4, "Corriger la classe suivante", [La mémoire propose ou décide ce que vous avez déjà jugé.])
  #etape(5, "Affiner le lecteur d'écriture", [Dès deux classes corrigées, une nuit ; l'adopter s'il fait mieux.])
]

// ================================================================== notes
= 6 · Identifier les copies et exporter les notes

== Identifier les copies

Déposez d'abord la *liste des élèves* à l'étape 6 (Excel, colonnes `NOM`, `Prénom`, `Classe`). Dans l'outil,
#bouton-clair[Identifier les copies] montre pour chaque copie le nom et le prénom écrits par l'élève, et
l'élève de la liste que la machine propose, avec ses autres candidats.

#capture("img/ex_noms.png", largeur: 80%, legende: [Identifier les copies (noms floutés) : à gauche ce qu'a écrit l'élève, à droite l'élève proposé.])

#attention[Un nom pré-rempli (gris italique, « proposé ») n'est *qu'une proposition* : il n'est enregistré
qu'avec #touche[Entrée], un clic sur un candidat, ou #bouton[Confirmer toute la page]. Une copie confirmée passe
en vert. Après chaque confirmation, les propositions restantes se recalculent.]

Quand toutes les copies du groupe sont identifiées, un bandeau mène à l'étape suivante. En bas de la page, les
*élèves sans copie* : à la fin, il ne doit rester que les absents.

== Vérifier les noms, puis exporter

#bouton-clair[Vérifier les noms] (étape 6) met en tête les copies *à risque* : nom proche d'un autre élève, voisin
d'un absent, élève d'un autre groupe.

#capture("img/ex_controle_noms.png", largeur: 85%, legende: [Le contrôle avant l'export : copies attribuées, à risque, sans élève.])

#bouton[Exporter les notes] produit un classeur `.xlsx` :

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [*Notes*], [une ligne par copie : élève, détail par partie, note sur 20 arrondie au demi-point supérieur (réglable) ;],
  [*Absents*], [les élèves de la liste sans copie ;],
  [*À vérifier*], [copies sans élève, réponses encore à décider (note provisoire), copies hors format.],
)

#capture("img/ex_notes.png", largeur: 52%, legende: [Copies et notes : QCM, réponses courtes, code, total (notes floutées).])

#astuce[Chaque export garde l'ancien classeur à côté, daté.]

// ================================================================== dépannage
= Si ça bloque

== Une page illisible ou une copie hors format

#capture("img/page_illisible.png", largeur: 66%, legende: [Une page sans les repères du sujet : signalée, jamais ignorée.])

Thessalia retrouve chaque page grâce aux *carrés noirs des coins*. Une page sans ces repères est signalée avec sa
place dans le PDF (`supH.pdf#73` : page 73) :

- *une page du sujet abîmée* : elle reste dans sa copie, ses réponses sont à reprendre sur le papier ;
- *une feuille d'un autre format* (réponses tapées, feuille libre) entre deux copies : elle devient une *copie
  hors format*, numérotée après les autres, notée à la main (même échelle), puis attribuée à l'élève.

#capture("img/hors_format.png", largeur: 66%, legende: [Copie hors format : la feuille en grand, la note saisie à la main.])

== Les messages courants

#table(columns: (38%, 1fr), stroke: (x, y) => (bottom: 0.4pt + rgb("#dddbd4")), inset: (x: 6pt, y: 6pt),
  table.header([*Ce que vous voyez*], [*Que faire*]),
  [« GABARIT DOUTEUX »], [Mauvaise langue au dépôt : redéposer le même PDF avec l'autre langue.],
  [Une nouveauté n'apparaît pas], [Relancer Thessalia (fermer la fenêtre noire, puis `Thessalia.bat`), puis « Lue · relire » si elle concerne la lecture.],
  [Un nom « saisi » reste dans les élèves sans copie], [Il n'a pas été confirmé : #touche[Entrée] sur sa ligne.],
  [« une tâche tourne encore »], [Une seule tâche longue à la fois : la mettre en pause (⏸) ou attendre la fin.],
  [« n'a pas pu être déplacé »], [Un fichier de l'examen est ouvert (PDF, Excel) : le fermer, puis recommencer.],
  [La page ne s'ouvre pas], [Vérifier que la fenêtre noire est ouverte, puis aller sur #link("http://127.0.0.1:8765/examens")[127.0.0.1:8765/examens].],
  [« Address already in use »], [Thessalia tourne déjà : utiliser l'onglet déjà ouvert.],
  [Boutons de l'étape 4 grisés], [Le message à côté dit ce qui manque : l'installer depuis *Réglages*.],
  [Une note semble fausse], [Ouvrir la copie (*Copies et notes*) : chaque point est détaillé, chaque décision modifiable.],
  [Mot de passe oublié], [Fermer Thessalia, supprimer `data\compte.json`, relancer.],
  [« Python introuvable »], [Réinstaller Python en cochant « Add python.exe to PATH ».],
  [Autre chose], [Copier le journal (« Détail ») et l'envoyer à l'auteur, *sans* copie ni nom d'élève.],
)

*Windows refuse les `.bat`* : « Informations complémentaires » puis « Exécuter quand même ». PC verrouillé :
dans le dossier de Thessalia, `py installer.py` (une fois) puis `.venv\Scripts\python -m thessalia app`.

// ================================================================== plus loin
= Pour aller plus loin

*Écrire un sujet.* Un fichier texte `examen.yaml` (énoncés FR et EN, bonnes réponses, mauvaises réponses
plausibles, barème du code), décrit dans `docs/FORMAT_SUJET.md`. #bouton-clair[Produire les PDF] fabrique sujet
et corrigé ; imprimer en *taille réelle*. Un sujet d'un autre générateur peut être importé.

*Réglages.* L'arrondi de la note finale, et les extensions installées en un clic : lecteur d'écriture (2 Go),
Ollama et ses modèles pour la lecture approfondie. Sans extension, tout fonctionne : vous corrigez plus à la main.

#attention[
  Le dossier `examens\` contient des *copies et des noms d'élèves* : ne le partagez pas, il n'est jamais envoyé
  sur GitHub. Pour sauvegarder un examen, copiez son dossier sur un support personnel. Le sujet `examen.yaml` se
  partage entre collègues, confidentiel jusqu'à l'examen.
]

#v(1fr)
#align(center, text(size: 9pt, fill: gris)[
  Thessalia est gratuit et libre (licence GPL v3) :
  #link("https://github.com/theprofessor7/thessalia")[github.com/theprofessor7/thessalia]. \
  Version texte de ce guide : `docs/MODE_EMPLOI.md`. Écrire un sujet : `docs/FORMAT_SUJET.md`.
])
