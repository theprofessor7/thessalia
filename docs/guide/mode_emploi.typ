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

Thessalia est une application qui tourne *sur votre ordinateur* et s'utilise *dans votre navigateur*
(Edge, Chrome, Firefox, Safari). Il n'y a pas de compte à créer, pas d'abonnement, et *rien ne part sur
internet* : ni les copies, ni les noms, ni les notes.

== Ce qu'elle fait pour vous

#let case-etape(n, titre, texte) = block(width: 100%, fill: white, stroke: 0.6pt + rgb("#d5d3cc"), radius: 4pt,
  inset: 9pt, breakable: false)[
  #pastille(n) #h(4pt) #text(weight: "bold", titre) \
  #v(2pt) #text(size: 9.5pt, texte)
]
#grid(columns: (1fr, 1fr, 1fr), column-gutter: 8pt, row-gutter: 8pt,
  case-etape(1, "Écrire le sujet", [Un fichier texte : questions, bonnes réponses, barème, en français et en anglais.]),
  case-etape(2, "Produire les PDF", [Sujet à imprimer et corrigé, dans chaque langue, en un clic.]),
  case-etape(3, "Lire les copies", [Vous déposez le PDF du scanner : cases cochées lues, réponses découpées.]),
  case-etape(4, "Lectures longues", [_Facultatif._ Réponses écrites et code manuscrit lus par la machine.]),
  case-etape(5, "Corriger", [Vous confirmez ou corrigez, question par question, en quelques clics.]),
  case-etape(6, "Notes", [Un classeur Excel : notes sur 20, absents, copies à vérifier.]),
)

== Ce qu'elle ne fait jamais

#info("Elle ne décide jamais en silence")[
  Quand la machine n'est pas sûre (case à moitié cochée, écriture difficile, nombre décimal…), la réponse
  est marquée *« à décider »* avec la raison. Une note n'est définitive que lorsque vous avez tout tranché.
  Thessalia préfère vous montrer dix réponses de trop plutôt que de se tromper une fois sans le dire.
]

== Le vocabulaire en trente secondes

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [*Examen*], [Un sujet et tout ce qui va avec : les PDF, les copies de toutes les classes, les notes.],
  [*Source*], [Le fichier texte `examen.yaml` où le sujet est écrit. C'est la seule chose que vous écrivez.],
  [*Classe*], [Un paquet de copies scannées ensemble, par exemple `supA_1`.],
  [*À décider*], [Une réponse que la machine vous laisse trancher.],
  [*Réponses courtes*], [Ce que l'élève écrit sur une ligne : un nombre, un mot, une ligne de code.],
)

Le reste du vocabulaire est dans le lexique, en fin de guide.

// ================================================================== installation
= Installer Thessalia

Une seule fois par ordinateur, compter dix minutes. Il faut une connexion internet pendant l'installation,
plus du tout ensuite.

== Ce qu'il faut avant

#etape(1, "Python")[
  Le télécharger sur #link("https://www.python.org/downloads/")[python.org/downloads] et l'installer.
  Sous Windows, *cocher la case « Add python.exe to PATH »* en bas de la première fenêtre.
]
#v(6pt)
#etape(2, "git")[
  Le télécharger sur #link("https://git-scm.com/downloads")[git-scm.com/downloads] et l'installer avec les
  options proposées. C'est l'outil qui récupère Thessalia et ses mises à jour.
]

== Installer

#etape(3, "Récupérer Thessalia")[
  Ouvrir une fenêtre *PowerShell* (menu Démarrer, taper « PowerShell ») ou le *Terminal* sur Mac, puis taper :
  ```
  git clone https://github.com/theprofessor7/thessalia.git C:\Thessalia
  ```
  Sur Mac, remplacer `C:\Thessalia` par `~/Thessalia`.
]
#v(6pt)
#etape(4, "Lancer l'installeur")[
  Ouvrir le dossier `C:\Thessalia` et *double-cliquer sur `installer.bat`* (Mac : `./installer.sh` dans le
  Terminal). Une fenêtre noire s'ouvre et installe ce qu'il faut, quelques minutes.

  Une question est posée : installer le *lecteur d'écriture* (environ 2 Go) ? Il lit tout seul les réponses
  courtes. Répondez `o` si vous avez la place, sinon `n` : tout fonctionne sans lui, et vous pourrez
  l'ajouter plus tard en un clic, depuis la page *Réglages* de l'application.
]

#attention[
  Le chemin du dossier ne doit pas contenir le signe `$`. Si l'installeur le signale, récupérez Thessalia
  dans `C:\Thessalia` comme ci-dessus. Si Windows bloque le double-clic, voir la page « Si ça bloque ».
]

== Lancer Thessalia, à chaque fois

*Double-cliquer sur `Thessalia.bat`* (Mac : `Thessalia.command`). Votre navigateur s'ouvre sur la page des
examens. Une fenêtre noire reste ouverte à côté : *c'est Thessalia qui tourne, ne la fermez pas* tant que vous
travaillez. La fermer arrête Thessalia ; vos données restent.

== Votre compte

#grid(columns: (1fr, 44%), column-gutter: 14pt,
  [
    Au *tout premier lancement*, Thessalia vous demande de choisir un *identifiant* et un *mot de passe*
    (8 caractères au moins). Ils sont ensuite demandés à chaque ouverture ; après 12 heures, il faut se
    reconnecter. Le bouton « Déconnexion », en bas du menu de gauche, ferme la session.

    Le mot de passe n'est jamais enregistré en clair. Il protège l'application ouverte sur un PC laissé sans
    surveillance ; vos fichiers, eux, sont protégés par votre session Windows.

    *Mot de passe oublié* : fermer Thessalia, supprimer le fichier `data\compte.json` dans le dossier de
    Thessalia, relancer : un nouveau compte est demandé. Vos examens ne sont pas touchés.
  ],
  capture("img/connexion.png", legende: [L'écran de connexion.]))

#astuce[
  Pour récupérer une nouvelle version : Thessalia fermé, dans PowerShell, `cd C:\Thessalia` puis
  `git pull`, puis relancer `installer.bat`. Vos examens ne sont jamais touchés.
]

// ================================================================== premier examen
= Votre premier examen, pas à pas

Le *menu de gauche* est toujours là :
- *Accueil* : la liste de vos examens ; « Nouvel examen » en crée un à partir de son fichier source ;
- *Correction* : l'outil de correction de l'examen ouvert (le menu affiche son nom dessous) ;
- *Réglages* : l'arrondi des notes et les extensions à installer (voir « Réglages », plus bas) ;
- *Aide* : ce guide.

#capture("img/examens.png", legende: [La page des examens. Chaque carte est un examen ; « Ouvrir » mène à ses étapes.])

Ouvrir un examen affiche ses *six étapes*, dans l'ordre. Une étape terminée a un trait vert à gauche.

== Étape 1 — Écrire le sujet

Le sujet s'écrit *une seule fois*, dans un fichier texte `examen.yaml` (Bloc-notes, VS Code…) : les énoncés
dans chaque langue, les bonnes réponses, les points. Le plus simple est de *partir du fichier d'un collègue*
et de le modifier. Voici à quoi ressemblent deux questions :

```yaml
      - type: qcm
        points: 0.5
        enonce: {fr: 'Quel est le type de `3.0` ?', en: 'What is the type of `3.0`?'}
        choix: ['`int`', '`float`', '`str`', '`bool`']
        bonne: b
      - type: blancs
        points: 1
        enonce: {fr: 'Que vaut `x` après `x = 7 // 2` ? [[x:court]]',
                 en: 'What is `x` after `x = 7 // 2`? [[x:court]]'}
        blancs:
          x: {attendu: '3', nature: nombre}
```

Types de questions disponibles : *QCM*, *vrai/faux*, *blancs* (réponses courtes dans une phrase, une ligne
ou un code à compléter), *code* (programme écrit dans un cadre) et *rédaction*. Tout est décrit dans
`docs/FORMAT_SUJET.md`.

Dans Thessalia : « Nouvel examen », donner un nom de dossier (par exemple `midterm_2026`), choisir le fichier
et, s'il y en a, les images (logo), puis #bouton[Créer l'examen].

#info("Le fichier est vérifié tout de suite")[
  Une faute (bonne réponse qui n'existe pas, points qui ne tombent pas juste, guillemet oublié…) est signalée
  avec *sa ligne et la façon de la corriger*. Corrigez le fichier, puis « Remplacer la source ».
  L'ancienne version est gardée à côté.
]

#capture("img/examen_haut.png", largeur: 92%, legende: [Les trois premières étapes d'un examen : source contrôlée, PDF produits, une classe lue.])

== Étape 2 — Produire les PDF

#bouton-clair[Produire les PDF] fabrique, pour chaque langue, le *sujet à imprimer* et le *corrigé*. Thessalia
relit ensuite chaque PDF et refuse de continuer si une zone de réponse n'est pas exactement là où elle est
dessinée : vous ne pouvez pas imprimer un sujet que la machine lirait mal.

#grid(columns: (46%, 1fr), column-gutter: 14pt,
  capture("img/sujet_p2.png", legende: [Une page de sujet produite.]),
  [
    #v(10pt)
    *À l'impression*
    - imprimer le fichier `sujet_….pdf` *tel quel* ;
    - choisir *« taille réelle »* (pas « ajuster à la page ») ;
    - *ne pas modifier* le PDF.

    Les carrés noirs dans les coins permettent à Thessalia de retrouver la feuille sur le scan, même
    tournée ou de travers.

    #v(6pt)
    *Pour les élèves*
    - cocher franchement, au stylo ;
    - pour annuler une case : la *noircir entièrement* ;
    - écrire les réponses courtes *sur la ligne*.

    #v(6pt)
    Si vous modifiez la source après coup, la page l'indique : produisez à nouveau avant d'imprimer.
  ])

== Étape 3 — Scanner et déposer les copies

Après l'examen, scanner *toutes les copies d'une classe en un seul PDF* : A4 ou A3, recto, 100 dpi ou plus.
Les pages tournées, à l'envers ou blanches ne posent pas de problème.

Dans l'étape 3 : nom de la classe (`supA_1`…), *langue du sujet distribué*, le PDF, puis
#bouton[Déposer et lire]. La lecture prend une à quelques minutes ; son journal s'affiche en haut de la page.
Le tableau indique ensuite le nombre de copies et le nombre de réponses à revoir.

#attention[
  Choisissez bien la langue. Si les copies sont en anglais et que vous indiquez FR, le journal affiche
  *« GABARIT DOUTEUX »* : redéposez simplement le même PDF avec la bonne langue.
]

== Étape 4 — Lectures longues (facultatif)

#capture("img/examen_bas.png", largeur: 92%, legende: [Étapes 4 à 6. Les boutons grisés disent ce qui manque.])

- #bouton-clair[Lire les réponses courtes et les noms] : la machine lit l'écriture des élèves (quelques
  minutes par classe) et vous propose sa lecture ; elle lit aussi les noms, pour l'identification. Il faut le lecteur d'écriture (installation).
- #bouton-clair[Sujet validé] : pour un sujet nouveau, *toutes* les réponses courtes vous sont présentées,
  même quand la machine est sûre d'elle. Au fil de votre correction, Thessalia compte ses lectures justes.
  Après 30 lectures vérifiées *sans une seule erreur*, ce bouton s'active : ensuite, les réponses sûres sont
  acceptées d'office et vous n'avez plus que les autres.
- #bouton-clair[Préparer la nuit] : transcrit le code écrit à la main et pré-coche le barème en l'exécutant.
  À lancer le soir : une centaine de copies tient en une nuit.

#info("Ce qu'il faut installer pour ces lectures")[
  Le lecteur d'écriture, Ollama et ses modèles s'installent en un clic depuis la page *Réglages* (menu de
  gauche), une fois par PC. La ligne « Modèles locaux » de l'étape 4 dit ce qui est déjà là.
]

Sans ces lectures, tout se corrige quand même à la main dans l'étape 5.

== Étape 5 — Corriger

#bouton[Corriger les copies lues] ouvre l'outil de correction. Il présente vos classes par groupe :

#capture("img/accueil_c.png", largeur: 70%, legende: [Le tableau de bord : ce qu'il reste à décider dans chaque groupe.])

#capture("img/groupe_c.png", legende: [Un groupe : une carte par question, avec le nombre de réponses à décider.])

La façon la plus rapide de corriger est *par question* : toutes les copies, une seule question. Les réponses
identiques sont regroupées en *blocs* : vous décidez une fois pour tout le bloc.

#capture("img/question_c.png", legende: [Correction par question : l'image de la réponse, la lecture de la machine, l'attendu et le verdict proposé (pointillés).])

Pour chaque réponse, vous voyez l'image de ce que l'élève a écrit, ce que la machine a lu, la réponse attendue,
et le verdict proposé (cadre pointillé). Vous pouvez :

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [#bouton[✓ valider]], [accepter le verdict proposé (#touche[Entrée]) ;],
  [#bouton-clair[✓ juste] #bouton-clair[½ forme] #bouton-clair[✗ faux]], [trancher vous-même (#touche[1] #touche[2] #touche[3]). « Forme » donne la moitié des points : bonne réponse mal écrite, par exemple avec des guillemets en trop ;],
  [#bouton-clair[ø vide] #bouton-clair[? illisible]], [rien d'écrit, ou impossible à lire (#touche[4] #touche[5]) ;],
  [#bouton-clair[corriger la lecture]], [taper ce que l'élève a vraiment écrit (#touche[T]) : le verdict se recalcule ;],
  [#bouton[Valider toutes les propositions]], [accepter d'un coup tout ce qui reste sur la question, quand vous avez tout regardé.],
)

#astuce[
  Les flèches #touche[↑] #touche[↓] passent d'une réponse à l'autre ; tout se fait au clavier. Vos décisions
  sont enregistrées *à chaque clic* : vous pouvez fermer et reprendre plus tard.
  Thessalia retient aussi vos décisions : une réponse que vous avez déjà jugée plusieurs fois de la même façon
  vous sera proposée avec ce verdict.
]

Les autres vues, en haut de l'écran :
- *Copies et notes* : une copie entière, page scannée à gauche, réponses à droite ;
- *Identifier les copies* : associer chaque copie à un élève de la liste (le nom écrit par l'élève est affiché
  à côté) ;
- *Suivi de la machine* : le bilan de la machine d'après vos corrections (lectures justes, lectures corrigées, erreurs).

== Étape 6 — Les notes

Déposer la *liste des élèves* de l'examen : un fichier Excel avec trois colonnes `NOM`, `Prénom`, `Classe`.
Puis #bouton[Exporter les notes] : un classeur `notes_<examen>.xlsx` à télécharger, avec trois feuilles :

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [*Notes*], [une ligne par copie : élève, détail par partie, total, note sur 20 arrondie au demi-point supérieur (13,1 donne 13,5 ; réglable dans Réglages) ;],
  [*Absents*], [les élèves de la liste qui n'ont pas de copie ;],
  [*À vérifier*], [les copies sans élève et celles où il reste des réponses à décider (note provisoire).],
)

#astuce[Chaque export garde l'ancien classeur à côté, daté. Vous ne perdez jamais une version.]

// ================================================================== réglages
= Réglages

La page *Réglages* (menu de gauche) vaut pour tous les examens de ce PC.

#capture("img/reglages.png", legende: [La page Réglages : l'arrondi, puis les extensions, chacune avec son bouton.])

== Paramètres

- *Arrondir la note finale au demi-point supérieur* : activé, 13,1 donne 13,5 ; désactivé, la note reste exacte
  (13,1). Dans tous les cas la note est plafonnée à 20. Le changement vaut pour les prochains exports.

== Extensions

Comme des modules qu'on ajoute : chaque carte dit ce que fait l'extension, sa taille, et si elle est installée.
Un clic l'installe ; la progression s'affiche dans le journal en haut de la page. Internet n'est nécessaire
que pendant le téléchargement. Sans extension, tout fonctionne : vous corrigez simplement plus à la main.

#table(columns: (auto, auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [*Lecteur d'écriture*], [2 Go], [lit les réponses courtes et les noms (étape 4, « Lire les réponses courtes ») ;],
  [*Ollama*], [1 Go], [logiciel gratuit qui fait tourner les modèles ci-dessous sur votre PC (Windows : installé sans question ; Mac : la page de téléchargement s'ouvre) ;],
  [*qwen3-vl:8b*], [6 Go], [lit le code écrit à la main (préparation de nuit) ;],
  [*qwen3-vl:4b*], [3 Go], [relit les réponses courtes laissées en revue ;],
  [*qwen3:14b*], [9 Go], [facultatif : répare les petites fautes du code avant les tests.],
)

Les modèles demandent Ollama démarré ; s'il est arrêté, sa carte propose #bouton-clair[Démarrer].
#bouton-clair[Supprimer] libère la place d'un modèle ; il se retélécharge d'un clic. Pour tout : environ 20 Go
de disque et 16 Go de mémoire.

// ================================================================== règles
= Comment Thessalia note

Les règles sont celles de l'enseignant, appliquées partout de la même façon :

- *Juste* : tous les points. *Forme* : la moitié (bonne réponse, mais écrite d'une façon qu'un programme
  refuserait : guillemets en trop, `2,5` au lieu de `2.5`…). *Faux* : zéro.
- Les petites variantes acceptées sont prévues dans la source, question par question (espaces, majuscules,
  guillemets…) : c'est vous qui les choisissez en écrivant le sujet.
- *QCM et vrai/faux* : les points de la question sont partagés entre les cases. Une case à moitié cochée,
  raturée ou noircie part en *« à décider »*.
- *Nombres* : un nombre décimal est toujours présenté à l'enseignant. Quand la machine hésite entre point et
  virgule, le doute profite à l'élève.
- *Note finale* : arrondie au *demi-point supérieur* (13,1 donne 13,5 ; 13,5 reste 13,5) et plafonnée à 20.
  L'arrondi se désactive dans *Réglages* (interrupteur) : la note reste alors exacte.

// ================================================================== confidentialité
= Vos fichiers et la confidentialité

Tout un examen est rangé dans *un dossier* : `C:\Thessalia\examens\<nom de l'examen>\`.

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 5pt), fill: (_, y) => if calc.odd(y) { fond },
  [`examen.yaml`], [la source du sujet (et son logo) ;],
  [`produit\`], [les PDF des sujets et des corrigés ;],
  [`scans\`], [les copies scannées ;],
  [`classes\`], [ce que la machine a lu sur chaque copie ;],
  [`decisions.sqlite`], [toutes vos décisions de correction ;],
  [`listes\`], [la liste des élèves et l'attribution des copies ;],
  [`notes\`], [les classeurs de notes.],
)

#attention[
  Ce dossier contient des *copies et des noms d'élèves*. Ne le partagez pas et ne le déposez pas sur un
  espace partagé. Pour le sauvegarder, copiez-le sur un support personnel. Il n'est jamais envoyé sur
  GitHub, même par erreur : Thessalia l'exclut.
]

Le fichier `examen.yaml`, lui, *se partage* entre collègues : c'est le sujet. Il reste *confidentiel jusqu'à
l'examen*.

// ================================================================== dépannage
= Si ça bloque

== Windows refuse d'ouvrir les fichiers .bat

*Un écran bleu « Windows a protégé votre ordinateur ».* Cela arrive si Thessalia a été téléchargé en
fichier ZIP plutôt qu'avec `git clone`. Cliquer *« Informations complémentaires »* puis *« Exécuter quand
même »*. Ou, avant de décompresser le ZIP : clic droit → *Propriétés* → cocher *« Débloquer »* → OK.

*Rien ne se passe, ou un message de l'antivirus.* Sur un PC verrouillé par la DSI, taper les commandes
à la main. Dans l'Explorateur, ouvrir le dossier de Thessalia, taper `powershell` dans la barre d'adresse et
appuyer sur Entrée. Puis, une seule fois :
```
py installer.py
```
et pour lancer Thessalia, à chaque fois :
```
.venv\Scripts\python -m thessalia app
```
Si `py` n'est pas reconnu, écrire `python` à la place. Si Python lui-même est interdit, demander à la DSI
de l'autoriser : Thessalia n'a besoin de rien d'autre.

== Les problèmes courants

#table(columns: (38%, 1fr), stroke: (x, y) => (bottom: 0.4pt + rgb("#dddbd4")), inset: (x: 6pt, y: 6pt),
  table.header([*Ce que vous voyez*], [*Que faire*]),
  [« Python introuvable », « py n'est pas reconnu »], [Réinstaller Python en cochant « Add python.exe to PATH », puis relancer l'installeur.],
  [« le chemin du dossier contient \$ »], [Récupérer Thessalia dans `C:\Thessalia`.],
  [La page ne s'ouvre pas], [Vérifier que la fenêtre noire est ouverte, puis aller à l'adresse #link("http://127.0.0.1:8765/examens")[127.0.0.1:8765/examens].],
  [« Address already in use »], [Thessalia tourne déjà : utilisez l'onglet ou la fenêtre déjà ouverts.],
  [« Source refusée »], [Lire la ligne indiquée et la correction proposée, modifier le fichier, « Remplacer la source ».],
  [« GABARIT DOUTEUX »], [Mauvaise langue au dépôt : redéposer le PDF avec l'autre langue.],
  [Boutons de l'étape 4 grisés], [Le message à côté dit ce qui manque : lecteur d'écriture, Ollama ou un modèle ; les installer depuis la page Réglages.],
  [Mot de passe oublié], [Supprimer `data\compte.json` dans le dossier de Thessalia, puis relancer.],
  [Une note semble fausse], [Ouvrir la copie (« Copies et notes ») : chaque point est détaillé, chaque décision modifiable.],
  [Autre chose], [Copier le journal affiché en haut de la page de l'examen et l'envoyer à l'auteur, *sans* copie ni nom d'élève.],
)

// ================================================================== lexique
= Lexique

#table(columns: (auto, 1fr), stroke: none, inset: (x: 6pt, y: 6pt), fill: (_, y) => if calc.odd(y) { fond },
  [*À décider*], [Réponse dont la machine n'est pas sûre : c'est vous qui tranchez. On dit aussi « en revue ».],
  [*Bloc*], [Réponses identiques sur une même question, décidées en une fois.],
  [*Classe*], [Un PDF de copies scannées ensemble (`supA_1`). Plusieurs classes forment un *groupe* (A, B…).],
  [*Corrigé*], [PDF avec les réponses, produit en même temps que le sujet ; sert aussi à la machine pour noter.],
  [*Forme*], [Bonne réponse mal écrite : la moitié des points.],
  [*Gabarit*], [La carte des zones de réponse d'un sujet, lue dans le PDF produit. Vous n'avez jamais à y toucher.],
  [*Lecteur d'écriture*], [Le programme qui lit les réponses courtes (TrOCR). Facultatif, environ 2 Go.],
  [*Ollama*], [Logiciel gratuit qui fait tourner sur votre PC les modèles utilisés pour le code manuscrit. Facultatif.],
  [*Source*], [Le fichier `examen.yaml` qui décrit le sujet. Tout le reste en est fabriqué.],
  [*Sujet validé*], [Sujet dont les lectures ont été vérifiées sans erreur sur au moins 30 réponses : la machine peut accepter seule ses lectures sûres.],
)

#v(1fr)
#align(center, text(size: 9pt, fill: gris)[
  Thessalia est gratuit et libre (licence GPL v3) :
  #link("https://github.com/theprofessor7/thessalia")[github.com/theprofessor7/thessalia]. \
  Mode d'emploi détaillé : `docs/MODE_EMPLOI.md`. Écrire un sujet : `docs/FORMAT_SUJET.md`.
])
