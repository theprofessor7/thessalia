# Format d'un sujet Thessalia (source unique)

> Spécification validée par l'enseignant le 8 novembre 2026 (YAML avec contrôle strict, propositions du § 8).
> Elle remplace, à terme, le générateur séparé (`esme_python_exam_generator`, scripts Python → HTML → WeasyPrint)
> et les fichiers de corrigé écrits à la main (`keys/*.key.json`, `*.vocab.json`, `*.bareme.json`, `*.tests.py`).

## 1. Le principe

Un examen est décrit **une seule fois**, dans un fichier `examen.yaml`. Pour chaque question, on y trouve au même
endroit l'énoncé (dans chaque langue), la réponse attendue, le barème, les erreurs plausibles et, pour le code,
le corrigé et ses essais.

Thessalia en tire tout le reste :

```
examen.yaml ──► contrôle strict ──► sujet_fr.pdf, sujet_en.pdf          (à imprimer, mise en page Typst)
                                    corrige_fr.pdf, corrige_en.pdf      (barème écrit en clair)
                                    gabarit_fr.json, gabarit_en.json    (zones, vérifiées contre le PDF)
                                    corrige.json                        (ce que la correction consomme)
```

Ce qu'on y gagne :
- une question n'est plus écrite cinq fois (sujet FR, sujet EN, corrigé FR, corrigé EN, `key.json`) ;
- le barème partiel (« 0,25 pt pour `{prix}` seul ») n'existe plus seulement en phrase dans un PDF : il est dans
  la source, et sert à la fois au corrigé imprimé et à la notation ;
- un écart entre sujet et corrigé devient impossible, puisqu'ils viennent du même endroit.

## 2. Lecture du YAML : le contrôle strict

Le YAML est lu **sans conversion automatique** : toute valeur écrite est un texte, exactement comme elle est écrite.

| Écrit dans le fichier | YAML ordinaire comprendrait | Thessalia lit |
|---|---|---|
| `attendu: 12.50` | le nombre 12.5 (zéro perdu) | le texte `12.50` |
| `attendu: True` | un booléen | le texte `True` |
| `attendu: 0169` | le nombre 169 | le texte `0169` |
| `attendu: [23, 16, 15, 8]` | une liste | **refusé** : mettre entre guillemets |
| `attendu: {prix}` | une structure | **refusé** : mettre entre guillemets |

Thessalia refuse le fichier entier, avec le numéro de ligne et la correction à faire, si :
- une réponse attendue (ou acceptée, plausible…) n'est pas un texte : `ligne 14 : la réponse attendue de q2 est
  lue comme une liste ; écrivez-la entre guillemets : '[23, 16, 15, 8]'` ;
- une clé est inconnue (faute de frappe : `atendu`) ou écrite deux fois ;
- un texte visible manque dans une des langues déclarées ;
- un blanc `[[…]]` est utilisé sans être défini, ou défini sans être utilisé ;
- les points ne tombent pas juste (blancs → question → exercice → examen) ;
- un QCM à choix unique a zéro ou plusieurs bonnes réponses ;
- le corrigé d'un exercice de code ne passe pas ses propres essais ;
- une réponse attendue contient un vrai retour à la ligne (voir 6.3) ;
- le fichier contient des tabulations.

Pièges de YAML rencontrés en convertissant le Midterm, tous refusés avec un message qui dit quoi faire :
- un texte sans guillemets contenant « : » suivi d'une espace (« Complétez : ») : très fréquent en français ;
- entre accolades `{fr: …, en: …}`, une virgule, un « ? » ou un « : » coupent le texte ;
- un « # » dans un texte sans guillemets : YAML coupe le texte et prend la suite pour un commentaire.
Dans le doute : **tout texte entre guillemets**.

Les guillemets : `'…'` (simples) gardent le texte tel quel, y compris `\n`. **Préférer les guillemets simples** pour
les réponses. Les guillemets doubles `"…"` transforment `\n` en retour à la ligne, ce qui est refusé.

## 3. Textes

### 3.1 Langues

Un texte visible s'écrit soit une fois (identique dans toutes les langues), soit par langue :

```yaml
titre: Examen Midterm                       # même texte en FR et en EN
sous_titre: {fr: Partie écrite, en: Written part}
```

Les langues de l'examen sont déclarées dans `examen.langues`. Chaque texte par langue doit les avoir toutes.
Cela vaut aussi pour les réponses attendues quand elles changent avec la langue (noms de variables traduits) :

```yaml
attendu: {fr: '{nom}', en: '{product}'}
```

### 3.2 Mise en forme (Markdown réduit)

Dans les textes : `**gras**`, `*italique*`, `` `code` ``, listes à puces ou numérotées, exposant `1^re^`, et blocs
de code :

````yaml
enonce:
  fr: |
    On exécute :
    ```python
    i = len(lst) - 2
    print(lst[i])
    ```
````

Pas de HTML. Les rares mises en page particulières passent par le type `brut` (§ 5.7).

## 4. Structure du fichier

```yaml
format: thessalia-sujet/1

examen:
  id: LANGPY-MID-2026-A
  langues: [fr, en]
  matiere: {fr: Langage Python, en: Python Language}
  titre: {fr: Examen Midterm, en: Midterm}
  sous_titre: {fr: Partie écrite, en: Written part}
  duree: 1 h 10
  session: {fr: Session de novembre 2026, en: November 2026 session}
  points: 12                    # total ; contrôlé contre la somme des exercices
  identite: [nom, prenom, groupe]   # facultatif : [nom, prenom] par défaut, [] pour aucune zone
  numero_etudiant:              # facultatif : sans cette clé, pas de grille
    chiffres: 7
    exemple: A2024158           # montré à l'élève, avec sa règle de saisie
    ignorer_prefixe: true       # la lettre n'est pas reportée dans la grille
  consignes:
    fr: |
      - Vous disposez de **1 h 10**. Répondez directement dans les cadres et sur les pointillés prévus.
      - **Cochez d'une croix.** Pour annuler une réponse, noircissez entièrement la case.
    en: |
      - …

exercices:
  - titre: {fr: Les listes, en: Lists}
    points: 2                   # facultatif ; contrôlé s'il est donné
    contexte:                   # facultatif : texte commun aux questions de l'exercice
      fr: |
        Pour tout cet exercice, on considère la liste Python suivante :
        ```python
        lst = [4, 8, 15, 16, 23, 42]
        ```
      en: |
        …
    questions:
      - …                       # voir § 5
```

Les questions sont numérotées dans l'ordre (1, 2, 3…) sur tout l'examen ; `num` n'est à écrire que pour vérifier.

## 5. Types de questions

Chaque question a un `type`, des `points` et un `enonce`. Elle peut avoir une `explication` (montrée dans le
corrigé imprimé seulement) et une `note` (petite remarque imprimée sous l'énoncé du sujet).

### 5.1 `qcm` — choix unique ou multiple

```yaml
- type: qcm
  points: 0.25
  enonce: {fr: "Quelle expression renvoie `True` si 15 est dans `lst` ?", en: "…"}
  choix:
    - '`lst.contains(15)`'
    - '`15 in lst`'
    - '`lst.has(15)`'
    - '`in(15, lst)`'
  bonne: b                      # lettre du choix ; plusieurs : [a, c] avec `plusieurs: true`
```

### 5.2 `vrai_faux`

```yaml
- type: vrai_faux
  points: 0.75
  enonce: {fr: "Cochez **V** si l'affirmation est vraie, **F** sinon.", en: "…"}
  affirmations:
    - {texte: {fr: "`len(lst)` est une méthode de la liste `lst`.", en: "…"}, reponse: F}
    - {texte: {fr: "`lst.sort()` trie `lst` sur place et renvoie `None`.", en: "…"}, reponse: V}
```

Points répartis également entre les affirmations, sauf `points` donné sur chacune.

### 5.3 `blancs` — réponses courtes

Un blanc se place n'importe où dans le texte avec `[[nom]]`, ou `[[nom:taille]]` (`court`, `moyen`, `long` ;
`moyen` par défaut). Trois façons de les disposer :

```yaml
# a) dans l'énoncé
- type: blancs
  points: 0.25
  enonce: {fr: "Donnez la valeur de `lst[-2:0:-1]` : [[v:long]]", en: "…"}
  blancs:
    v: {attendu: '[23, 16, 15, 8]', tolerances: [espaces_virgules],
        plausibles: ['[23, 16, 15, 8, 4]', '[42, 23, 16, 15, 8]', '[16, 15, 8]', '[]']}

# b) une ligne par blanc (« 1re ligne : … », « 2e ligne : … »)
- type: blancs
  points: 0.25
  enonce: {fr: "On exécute : …\n\nDonnez les deux lignes affichées :", en: "…"}
  lignes:
    - {fr: "1^re^ ligne : [[a:court]]", en: "1^st^ line: [[a:court]]"}
    - {fr: "2^e^ ligne : [[b:court]]", en: "2^nd^ line: [[b:court]]"}
  blancs:
    a: {attendu: '23', nature: nombre}
    b: {attendu: '15', nature: nombre}

# c) dans un code à compléter (police à chasse fixe, encadré comme un bloc de code)
- type: blancs
  points: 1.00
  enonce: {fr: "On veut afficher exactement `café : 12.50 €`. Complétez le f-string :", en: "…"}
  code: 'print(f"[[a:court]] : [[b:court]] €")'
  blancs:
    a: {attendu: {fr: '{nom}', en: '{product}'}, points: 0.25}
    b: {attendu: {fr: '{prix:.2f}', en: '{price:.2f}'}, points: 0.75,
        partiel: {fr: {'{prix}': 0.25}, en: {'{price}': 0.25}},
        explication: {fr: "spécificateur `.2f` indispensable pour les 2 décimales", en: "…"}}
```

Champs d'un blanc :

| Champ | Rôle | Défaut |
|---|---|---|
| `attendu` | la réponse juste (texte, ou par langue) | obligatoire |
| `nature` | `texte` (affichage exact), `nombre` (2,5 ≠ 2.5, cf. CLAUDE.md), `mot` (liste fermée de réponses) | `texte` |
| `points` | points du blanc | partage égal dans la question |
| `accepte` | autres réponses justes | aucune |
| `forme` | réponses à moitié des points (écart de forme) | aucune |
| `partiel` | `{réponse: points}` prévus par le corrigé | aucun |
| `plausibles` | mauvaises réponses plausibles : aident la lecture **sans « corriger » l'élève** (cf. CLAUDE.md) | recommandé |
| `tolerances` | règles générales, ci-dessous | aucune |
| `explication` | texte du corrigé imprimé | aucune |

Tolérances nommées (elles remplacent les listes de variantes écrites à la main ; Thessalia les développe) :

| Tolérance | Effet | Exemple Midterm |
|---|---|---|
| `guillemets` | avec ou sans guillemets `"…"` / `'…'` : juste | q6, q7, q8 (valeur d'une chaîne) |
| `guillemets_forme` | avec guillemets : écart de forme (moitié) | q11, q14, q18 (ce qu'affiche un `print`) |
| `espaces_virgules` | `[23,16,15,8]` = `[23, 16, 15, 8]` | q2, q4, q5, q12 |
| `espace_ponctuation` | `Alice!` = `Alice !` | q15 |
| `liste_incomplete: {manque_max: 2, points: 0.25}` | liste à 1 ou 2 éléments près : points partiels | q5 (30 variantes énumérées à la main le 2 novembre) |

La règle globale reste celle de l'enseignant (`notes.py`) : juste 100 %, forme 50 %, le reste faux.

### 5.4 `code` — programme écrit dans un cadre

```yaml
- type: code
  points: 0.50
  enonce: {fr: "Créez `exo.txt` en écriture, écrivez-y `\"a\"`, puis refermez-le.", en: "…"}
  cadre: {lignes: 3}            # hauteur du cadre ; libellé « Code (3 lignes) » ajouté
  corrige: |
    f = open("exo.txt", "w")
    f.write("a")
    f.close()
  avant: {exo.txt: ancien}      # fichiers créés avant d'exécuter le code de l'élève
  interdit: '\bwith\b'          # consigne de l'énoncé (« n'utilisez pas with »)
  criteres:
    - texte: {fr: trio open / write / close, en: open / write / close}
      points: 0.25
      contient: 'open|write|close'
      verifie: termine          # le programme va au bout sans erreur
    - texte: {fr: 'mode "w" et argument "a"', en: '"w" mode and "a" argument'}
      points: 0.25
      verifie: 'fichier:exo.txt'  # contenu du fichier après exécution, comparé à celui du corrigé
```

Les critères reprennent le barème actuel (`code_tests.tests_du_bareme`) : `essais` (saisies), `contient`
(« | » pour l'un ou l'autre), `verifie` (`sortie`, `termine`, `saisies`, `lignes`, `texte[:k]`, `nombre:k`) ;
nouveaux pour les fichiers : `avant` et `verifie: fichier:<nom>`. Le corrigé doit passer tous ses critères,
sinon le fichier est refusé. Cas trop particuliers : `tests_python: tests/q28.py` (fonction Python, comme
`keys/*.tests.py` aujourd'hui).

### 5.5 `redaction` — réponse en phrases

```yaml
- type: redaction
  points: 1
  enonce: {fr: "Expliquez la différence entre `sort()` et `sorted()`.", en: "…"}
  lignes: 4
  criteres:
    - {texte: {fr: "sort() modifie la liste", en: "…"}, points: 0.5}
    - {texte: {fr: "sorted() renvoie une nouvelle liste", en: "…"}, points: 0.5}
```

Corrigée à la main dans l'outil (critères cochés), comme q11.a du sujet A aujourd'hui.

### 5.6 `texte` — sans réponse

Un paragraphe, un code à lire, une consigne entre deux questions : `type: texte`, `contenu`. Pas de points.

### 5.7 `brut` — échappatoire de mise en page

Du Typst brut, pour un cas que les types précédents ne couvrent pas. **Mise en page seulement** : aucune zone de
réponse ne peut y être déclarée (sinon elle échapperait aux contrôles). Si le besoin revient, on en fait un type.

## 6. Points délicats

### 6.1 Barème

- Le total des blancs (ou critères, affirmations) fait les points de la question ; celui des questions, les points de
  l'exercice s'ils sont donnés ; celui des exercices, `examen.points`. Tout écart est refusé.
- Les points s'écrivent `0.25` ou `0,25`.

### 6.2 Identifiants

Les identifiants sont fabriqués, jamais écrits à la main, avec la numérotation déjà utilisée par Thessalia :
`q3` (QCM, ou question à un seul blanc), `q9.1` et `q9.2` (blancs de la question 9 dans leur ordre d'apparition,
quel que soit leur nom dans la source), `q10.1` (1re affirmation), `q25` (code). Ils sont les mêmes dans toutes
les langues : les copies FR et EN se corrigent ensemble, question par question. Le nom d'un blanc (`a`, `v`…)
ne sert qu'à le relier à sa définition dans la source.

### 6.3 Retours à la ligne dans une réponse

Une réponse attendue tient sur une ligne (c'est ce qu'on lit dans un blanc). Pour une réponse contenant le texte
`\n`, l'écrire entre guillemets simples : `attendu: '12\n'`.

## 7. Ce que Thessalia produit et vérifie

1. **Contrôle strict** du fichier (§ 2). Rien n'est produit tant qu'il reste une erreur.
2. **Mise en page Typst** de chaque langue : sujet et corrigé. Mêmes repères et mêmes dimensions de cases que le
   template v5 (cases 3,7 mm, trait 0,53 mm ; grille 6,5 × 4,8 mm, trait 0,4 mm ; repères 5 mm à 16 mm des bords).
3. **Gabarit** : les identifiants et types viennent de la source, les positions sont relues dans le PDF
   (principe n° 4) ; `verif-zones` doit trouver 100 % des zones conformes, sinon refus.
4. **`corrige.json`** : bonnes cases, réponses attendues avec tolérances développées, points par champ,
   plausibles, barème et essais du code. Dans un premier temps, Thessalia écrit aussi les fichiers actuels
   (`key.json`, `vocab.json`, `bareme.json`) pour que la correction marche sans autre changement.
5. **Corrigé imprimé** : réponse attendue en vert, barème détaillé, explications, points partiels écrits en clair.

## 8. Décisions pour le MVP (8 novembre 2026)

- Une question existe dans toutes les langues de l'examen.
- Sujets A / B (mêmes questions, valeurs différentes) : un fichier par sujet ; mécanisme de variantes plus tard.
- Mélange de l'ordre des choix d'un QCM par sujet : plus tard.
- La partie numérique (Moodle / CodeRunner) : hors de ce format.

## 9. Premier cas réel

Le Midterm de novembre 2026 sera converti dans ce format. Critères de réussite :
- les fichiers de corrigé produits sont équivalents à ceux écrits à la main le 2 novembre (`keys/midterm_2026_*`) ;
  ils peuvent alors servir à corriger les copies réelles, imprimées avec l'ancien générateur ;
- le sujet mis en page par Typst a les mêmes champs et les mêmes points que le gabarit actuel ; ses positions
  diffèrent forcément (autre moteur de mise en page) mais doivent être 100 % conformes à son propre PDF ;
- ses copies simulées difficiles se lisent sans aucune erreur non signalée.
