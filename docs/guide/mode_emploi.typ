// Guide de prise en main de Thessalia (PDF : docs/Thessalia_mode_emploi.pdf)
// Construire : python docs/guide/construire.py
// Captures d'écran : examen de démonstration, copies simulées, noms inventés (aucune donnée d'élève).

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

Le parcours d'un examen, dans l'ordre de ce guide :

#let case-etape(n, titre, texte) = block(width: 100%, fill: white, stroke: 0.6pt + rgb("#d5d3cc"), radius: 4pt,
  inset: 9pt, breakable: false)[
  #pastille(n) #h(4pt) #text(weight: "bold", titre) \
  #v(2pt) #text(size: 9.5pt, texte)
]
#grid(columns: (1fr, 1fr, 1fr), column-gutter: 8pt, row-gutter: 8pt,
  case-etape(1, "Ouvrir", [Lancer Thessalia, retrouver ses examens sur l'accueil.]),
  case-etape(2, "Charger les copies", [Un PDF du scanner par classe : cases lues, réponses découpées.]),
  case-etape(3, "Corriger", [Confirmer ou corriger, question par question, en quelques clics.]),
  case-etape(4, "Outils des cartes", [Chaque réponse : juste, forme, faux, vide, corriger la lecture…]),
  case-etape(5, "Outils des blocs", [Les réponses identiques se décident en une fois.]),
  case-etape(6, "Exporter les notes", [Un classeur Excel : notes sur 20, absents, copies à vérifier.]),
)

#info("Thessalia ne décide jamais en silence")[
  Quand la machine n'est pas sûre (case à moitié cochée, écriture difficile, nombre décimal, page illisible…),
  elle le signale *« à décider »*, avec la raison. Une note n'est définitive que lorsque tout est tranché.
]

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
rester ouverte*, c'est Thessalia qui tourne. Au premier lancement, choisissez un identifiant et un mot de passe
(8 caractères au moins) ; ils sont redemandés après 12 heures.

#astuce[Mise à jour : Thessalia fermé, `cd C:\Thessalia` puis `git pull` dans PowerShell, puis relancer
`installer.bat`. Vos examens ne sont jamais touchés. Après une mise à jour, *relancez Thessalia*.]

== L'accueil et les cartes d'examen

#capture("img/accueil_cartes.png", largeur: 72%, legende: [L'accueil : une carte par examen, avec « Ouvrir » et « Supprimer ».])

- #bouton[Ouvrir] mène à la page de l'examen : un assistant en *six étapes* (pastilles en haut, « Précédent /
  Suivant » en bas). Une étape faite est verte ✓ ; une étape grisée dit ce qui lui manque. Ouvrir un examen
  mène directement à l'étape à faire.
- #bouton-clair[Supprimer] demande confirmation, puis range l'examen dans la *corbeille*, en bas de l'accueil,
  avec tout son contenu (copies lues, décisions, notes). #bouton-clair[Restaurer] le remet en place d'un clic.
  Rien n'est effacé du disque : pour vider la corbeille, supprimer le dossier `examens\.corbeille` à la main.

Le *menu de gauche* : *Accueil*, *Correction* (l'examen ouvert en correction), *Apprentissage*, *Réglages*, *Aide*.

Un nouvel examen se crée depuis l'accueil avec son fichier source `examen.yaml` (voir « Pour aller plus loin »).
Les étapes 1 et 2 (sujet, PDF à imprimer) sont alors faites une fois pour toutes.

// ================================================================== charger
= 2 · Charger les copies d'une classe

Scanner *toutes les copies d'une classe en un seul PDF* : A4 ou A3, recto, 100 dpi ou plus. Les pages tournées,
à l'envers ou blanches sont gérées, de même qu'une copie composée sur un sujet imprimé en A3.

#capture("img/charger_classe.png", legende: [Étape 3 : nom de la classe, langue du sujet distribué, PDF, puis « Déposer et lire ».])

#etape(1, "Nommer la classe")[
  Par exemple `supH` ou `supA_1`. Le nom range la classe dans son *groupe* (`supA_1`, `supA_2` → groupe A) :
  c'est ce groupe qui sert pour les noms des élèves et les notes. Une copie scannée à part se charge comme une
  classe de plus (`supA_2`) : elle rejoint les autres copies de A.
]
#v(4pt)
#etape(2, "Choisir la langue du sujet distribué")[
  FR ou EN. Une erreur est signalée « GABARIT DOUTEUX » (voir « Si ça bloque »).
]
#v(4pt)
#etape(3, "Déposer et lire")[
  La lecture prend quelques minutes ; la jauge suit les pages. Vous pouvez travailler ailleurs : Thessalia
  peut vous prévenir à la fin (« Me prévenir à la fin »).
]

#capture("img/charger_classe_jauge.png", largeur: 92%, legende: [La lecture en cours : page lue, copie en cours.])

À la fin, une fenêtre résume ce qui mérite votre attention, et le tableau donne pour chaque classe le nombre de
copies et de réponses *à revoir*.

#capture("img/charger_classe_fin.png", largeur: 92%, legende: [Fin de lecture : la page illisible est signalée, la classe est lue.])

#astuce[« Lue · relire » relit une classe (après une mise à jour, par exemple) : vos décisions sont gardées.]

// ================================================================== corriger
= 3 · Corriger

#bouton[Corriger les copies lues] (étape 5) ouvre l'outil de correction. Le tableau de bord présente vos classes
par groupe, puis chaque groupe a une carte par question.

#grid(columns: (1fr, 1fr), column-gutter: 10pt,
  capture("img/accueil_c.png", legende: [Ce qu'il reste à décider par groupe.]),
  capture("img/groupe_c.png", legende: [Un groupe : une carte par question.]))

Corrigez *par question* : toutes les copies, une seule question. Pour chaque réponse : l'image de ce que l'élève
a écrit, ce que la machine a lu, l'attendu et le verdict proposé (cadre pointillé). Vos décisions sont
enregistrées *à chaque clic* : on peut fermer et reprendre plus tard.

#capture("img/question_c.png", legende: [Correction par question : les réponses identiques sont regroupées en blocs.])

Les autres vues, en haut de l'écran : *Copies et notes* (une copie entière, page scannée à gauche),
*Identifier les copies* (attribuer chaque copie à un élève de la liste, le nom écrit à côté), *Suivi de la
machine* (lectures justes et corrigées).

#info("Étape 4, facultative : les lectures automatiques")[
  Avant de corriger, la machine peut lire l'écriture des élèves (*Lire les réponses courtes*, lecteur d'écriture)
  et, en arrière-plan pendant quelques heures, le code manuscrit (*Lecture approfondie*, Ollama). Ces
  extensions s'installent depuis *Réglages*. Sans elles, tout se corrige à la main. Une tâche longue se met en
  pause (⏸) et reprend (▶) là où elle s'était arrêtée.
]

// ================================================================== cartes
= 4 · Les outils des cartes

Chaque réponse est une *carte*. Tout se fait au clavier : #touche[↑] #touche[↓] passent d'une carte à l'autre.

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [#bouton[✓ valider] #touche[Entrée]], [accepter le verdict proposé ;],
  [#bouton-clair[✓ juste] #touche[1]], [tous les points ;],
  [#bouton-clair[½ forme] #touche[2]], [la moitié : bonne réponse mal écrite (guillemets en trop, `2,5` au lieu de `2.5`) ;],
  [#bouton-clair[✗ faux] #touche[3]], [zéro ;],
  [#bouton-clair[ø vide] #touche[4] #bouton-clair[? illisible] #touche[5]], [rien d'écrit, ou impossible à lire ;],
  [#bouton-clair[bien lu] #touche[L]], [la machine a lu exactement ce qui est écrit : la lecture devient un exemple pour l'apprentissage ;],
  [#bouton-clair[\= attendu] #touche[A]], [l'élève a écrit la réponse attendue, la machine l'a mal lue ;],
  [#touche[6] #touche[7] #touche[8]], [choisir une autre lecture proposée ;],
  [#bouton-clair[corriger la lecture] #touche[T]], [taper ce que l'élève a vraiment écrit : le verdict se recalcule ;],
  [#touche[Suppr]], [annuler la décision.],
)

*Cartes de code.* #touche[1]…#touche[5] cochent les critères du barème, #touche[J] tout juste, #touche[0] rien de
juste, #touche[V] vide, #touche[M] entorse grave. La transcription du code se corrige sur la carte ; les tests
sont alors relancés.

*D'où vient la proposition ?* L'étiquette de la carte le dit (survolez-la) : *✓ vous*, *⚙ lecteur sûr*,
*⚙ deux lecteurs d'accord*, *⚙ tests exécutés* (code), *↺ mémoire* (votre verdict habituel dans les autres
classes), *? lecture proposée* (la machine hésite).

*Ce que Thessalia retient.* Après une décision, un message en bas à droite dit ce qu'elle en garde. Dès 3
jugements identiques, votre verdict est *proposé* dans les autres classes ; dès 10 jugements concordants à 95 %,
il est *appliqué d'office*.

// ================================================================== blocs
= 5 · Les outils des blocs

Les réponses identiques d'une question forment un *bloc* (« lu « 3 » → juste · 14 »). Les boutons du bloc
agissent sur toutes ses cartes d'un coup :

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [#bouton-clair[Confirmer le bloc]], [accepter le verdict proposé pour tout le bloc ;],
  [#bouton-clair[bien lu pour le bloc]], [la lecture est exacte partout : autant d'exemples d'apprentissage en un clic ;],
  [#bouton-clair[\= attendu pour le bloc]], [la machine a mal lu la même chose partout, tous ont écrit l'attendu ;],
  [#bouton-clair[vide pour le bloc]], [zones sans lecture où rien n'est écrit : 0 point, « vide ».],
)

En haut de la page, #bouton[Valider toutes les propositions] accepte d'un coup tout ce qui reste sur la question,
une fois que vous avez tout regardé.

#astuce[Parcourez d'abord les gros blocs : ils sont en tête. Une carte du bloc qui ne lui ressemble pas se décide
seule avant de confirmer le reste.]

// ================================================================== notes
= 6 · Exporter les notes

#etape(1, "Déposer la liste des élèves")[
  À l'étape 6 : un fichier Excel avec les colonnes `NOM`, `Prénom`, `Classe`.
]
#v(4pt)
#etape(2, "Attribuer les copies")[
  Dans l'outil, *Identifier les copies* : chaque copie avec le nom écrit par l'élève et l'élève proposé.
]
#v(4pt)
#etape(3, "Vérifier les noms")[
  L'étape 6 compte les copies sans élève et les copies *à risque* (nom proche d'un autre, voisin d'un absent,
  autre groupe). #bouton-clair[Vérifier les noms] les montre en tête ; #bouton[J'ai vérifié les copies à risque]
  évite que l'export le redemande.
]
#v(4pt)
#etape(4, "Exporter")[
  #bouton[Exporter les notes] produit un classeur `.xlsx` à télécharger :
]

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [*Notes*], [une ligne par copie : élève, détail par partie, total, note sur 20 arrondie au demi-point supérieur (13,1 → 13,5 ; réglable dans *Réglages*), plafonnée à 20 ;],
  [*Absents*], [les élèves de la liste sans copie ;],
  [*À vérifier*], [copies sans élève, copies avec des réponses encore à décider (note provisoire), copies hors format.],
)

#astuce[Chaque export garde l'ancien classeur à côté, daté : aucune version n'est perdue.]

// ================================================================== dépannage
= Si ça bloque

== Une page illisible ou une copie hors format

#capture("img/page_illisible.png", largeur: 92%, legende: [Une page sans les repères du sujet : signalée, jamais ignorée.])

Thessalia retrouve chaque page grâce aux *carrés noirs des coins*. Une page sans ces repères est signalée
« page illisible » avec sa place dans le PDF (`supH.pdf#73` : page 73). Ouvrez le PDF à cette page :

- *une page du sujet abîmée* (coin plié, scan de travers) : elle reste dans sa copie ; ses réponses sont « à
  décider », à reprendre sur le papier ;
- *une feuille d'un autre format* (réponses tapées d'un élève avec aménagement, feuille libre) placée entre deux
  copies complètes : elle devient une *copie hors format*, numérotée après les autres.

#capture("img/hors_format.png", largeur: 92%, legende: [Copie hors format : la feuille en grand, la note saisie à la main, l'élève attribué.])

Une copie hors format se note *à la main* : lisez la feuille, saisissez les points obtenus (même échelle que les
autres copies), puis attribuez-la à l'élève dans *Identifier les copies*. L'export reprend la note ; en attendant,
elle compte 0 et figure dans « À vérifier ».

== Les messages courants

#table(columns: (38%, 1fr), stroke: (x, y) => (bottom: 0.4pt + rgb("#dddbd4")), inset: (x: 6pt, y: 6pt),
  table.header([*Ce que vous voyez*], [*Que faire*]),
  [« GABARIT DOUTEUX »], [Mauvaise langue au dépôt : redéposer le même PDF avec l'autre langue.],
  [Une nouveauté n'apparaît pas], [Relancer Thessalia (fermer la fenêtre noire, puis `Thessalia.bat`), puis « Lue · relire » si elle concerne la lecture.],
  [« une tâche tourne encore »], [Une seule tâche longue à la fois : la mettre en pause (⏸) ou attendre la fin.],
  [« n'a pas pu être déplacé »], [Un fichier de l'examen est ouvert (PDF, Excel) : le fermer, puis recommencer.],
  [La page ne s'ouvre pas], [Vérifier que la fenêtre noire est ouverte, puis aller sur #link("http://127.0.0.1:8765/examens")[127.0.0.1:8765/examens].],
  [« Address already in use »], [Thessalia tourne déjà : utiliser l'onglet déjà ouvert.],
  [Boutons de l'étape 4 grisés], [Le message à côté dit ce qui manque : l'installer depuis *Réglages*.],
  [« Source refusée »], [Lire la ligne indiquée et la correction proposée, modifier le fichier, « Remplacer la source ».],
  [Une note semble fausse], [Ouvrir la copie (*Copies et notes*) : chaque point est détaillé, chaque décision modifiable.],
  [Mot de passe oublié], [Fermer Thessalia, supprimer `data\compte.json`, relancer : un nouveau compte est demandé.],
  [« Python introuvable »], [Réinstaller Python en cochant « Add python.exe to PATH », puis relancer l'installeur.],
  [Autre chose], [Copier le journal (« Détail » en haut de la page) et l'envoyer à l'auteur, *sans* copie ni nom d'élève.],
)

== Windows refuse d'ouvrir les fichiers .bat

*Écran bleu « Windows a protégé votre ordinateur »* (Thessalia téléchargé en ZIP) : « Informations
complémentaires » puis « Exécuter quand même ». *Rien ne se passe* (PC verrouillé) : dans le dossier de
Thessalia, taper `powershell` dans la barre d'adresse de l'Explorateur, puis `py installer.py` (une fois) et
`.venv\Scripts\python -m thessalia app` (à chaque fois). Si `py` n'est pas reconnu, écrire `python`.

// ================================================================== plus loin
= Pour aller plus loin

*Écrire un sujet.* Le sujet s'écrit une fois dans un fichier texte `examen.yaml` (énoncés FR et EN, bonnes
réponses, points), décrit dans `docs/FORMAT_SUJET.md` ; le plus simple est de partir de celui d'un collègue.
Thessalia le contrôle (une faute est signalée avec sa ligne), puis #bouton-clair[Produire les PDF] fabrique sujet
et corrigé. À l'impression : *taille réelle*, PDF non modifié. Un sujet produit par un autre générateur peut aussi
être importé (demander à l'auteur).

*Sujet validé.* Pour un sujet nouveau, toutes les réponses courtes vous sont présentées. Après 30 lectures
vérifiées sans erreur, #bouton-clair[Sujet validé] (étape 4) laisse la machine accepter seule ses lectures sûres.

*Apprentissage* (menu de gauche). La mémoire de vos verdicts, et l'affinage des lecteurs de chiffres et
d'écriture sur vos corrections. Un nouveau lecteur est mesuré sur des copies qu'il n'a jamais vues ;
#bouton[Adopter] n'apparaît que s'il fait mieux, et l'ancien est gardé.

*Réglages* (menu de gauche). L'arrondi de la note finale, et les extensions installées en un clic : lecteur
d'écriture (2 Go), Ollama et ses modèles (environ 20 Go en tout). Sans extension, tout fonctionne : vous
corrigez simplement plus à la main.

#attention[
  Le dossier `examens\` contient des *copies et des noms d'élèves* : ne le partagez pas. Il n'est jamais envoyé
  sur GitHub. Pour sauvegarder un examen, copiez son dossier sur un support personnel. Le fichier `examen.yaml`,
  lui, se partage entre collègues, mais reste confidentiel jusqu'à l'examen.
]

#v(1fr)
#align(center, text(size: 9pt, fill: gris)[
  Thessalia est gratuit et libre (licence GPL v3) :
  #link("https://github.com/theprofessor7/thessalia")[github.com/theprofessor7/thessalia]. \
  Version texte de ce guide : `docs/MODE_EMPLOI.md`. Écrire un sujet : `docs/FORMAT_SUJET.md`.
])
