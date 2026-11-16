# Thessalia — mode d'emploi

Thessalia lit les copies papier scannées d'un examen et aide à les corriger : cases lues automatiquement,
écriture déchiffrée, réponses identiques regroupées, code exécuté, notes sur 20 dans un classeur Excel. Tout se
passe **sur votre ordinateur**, dans votre navigateur : rien n'est envoyé sur internet.

Guide illustré, par l'exemple d'une vraie classe : [`Thessalia_mode_emploi.pdf`](Thessalia_mode_emploi.pdf)
(aussi dans le menu **Aide**).

La machine fait le travail répétitif, vous gardez le jugement : **chaque clic lui apprend quelque chose**, et la
classe suivante va plus vite. Elle **ne décide jamais en silence** : ce qui est douteux est « à décider », avec
la raison.

---

## 1. Ouvrir Thessalia

**Installer, une fois.** [Python](https://www.python.org/downloads/) (Windows : cocher **« Add python.exe to
PATH »**) et [git](https://git-scm.com/downloads), puis dans PowerShell :

```
git clone https://github.com/theprofessor7/thessalia.git C:\Thessalia
```

et double-cliquer sur `installer.bat` (Mac / Linux : `./installer.sh` dans un terminal ; sur Ubuntu, si
l'installeur le demande : `sudo apt install python3-venv`).

**Lancer, à chaque fois.** Double-cliquer sur `Thessalia.bat` (Mac : `Thessalia.command` ; Linux : « Thessalia »
dans le menu des applications, ou `./Thessalia.command`). **Laisser la fenêtre
noire ouverte.**

**Mettre à jour.** Thessalia fermé : `git pull`, relancer l'installeur, puis Thessalia.

**L'accueil** : une carte par examen, et en bas « Nouvel examen » (sujet source) ou « Importer un sujet » (voir
[Pour aller plus loin](#pour-aller-plus-loin)). **Ouvrir** mène à l'assistant en six étapes ; **Supprimer** range l'examen
dans la corbeille (en bas de l'accueil), **Restaurer** le remet.

## 2. Charger les copies (étape 3)

Toutes les copies d'une classe **en un seul PDF** (A4 ou A3, 100 dpi ou plus). Nom de la classe, **langue du
sujet distribué**, PDF, **Déposer et lire**. Le nom range la classe dans son groupe : `supA`, `supA_2` → groupe A
(une copie scannée à part se charge comme une classe de plus).

## 3. Laisser la machine lire (étape 4)

- **Lire les réponses courtes** : l'écriture des élèves et leurs noms, quelques minutes par classe.
- **Lecture approfondie** : le code manuscrit transcrit, exécuté avec les tests du sujet, critères pré-cochés ;
  quelques heures (une nuit). Pause ⏸ et reprise ▶. Case **lecture rapide** : le code seulement, sans le
  réparateur ni la relecture des réponses courtes, nettement plus court.

Sujet nouveau : tout vous est présenté ; après 30 lectures vérifiées sans erreur, **Sujet validé** laisse la
machine accepter seule ses lectures sûres.

## 4. Corriger (étape 5)

**Corriger les copies lues** ouvre l'outil : un tableau de bord par groupe, une case par question. Chaque
question montre l'énoncé tel que l'élève l'a vu, puis les réponses **regroupées en blocs de lectures
identiques** :

| Bloc | Effet |
|---|---|
| Confirmer le bloc | le verdict proposé pour tout le bloc |
| bien lu pour le bloc | lecture exacte partout |
| = attendu pour le bloc | la machine a mal lu la même chose (« 55 » pour 5), tous ont écrit l'attendu |
| vide pour le bloc | rien d'écrit |
| Valider toutes les propositions | tout ce qui reste sur la question |

| Carte | Touche | Effet |
|---|---|---|
| ✓ valider | Entrée | accepter le verdict proposé |
| juste / forme / faux | 1 / 2 / 3 | tous les points / la moitié / zéro |
| vide / illisible | 4 / 5 | rien d'écrit / impossible à lire |
| bien lu | L | lecture exacte |
| = attendu | A | l'élève a écrit l'attendu, la machine a mal lu |
| autre lecture | 6 7 8 | choisir une autre lecture proposée |
| corriger la lecture | T | taper ce qui est écrit ; le verdict se recalcule |
| déjà saisi | — | reprendre d'un clic une lecture déjà tapée sur cette question |
| 🖌 pinceau | P | appliquer une lecture aux vignettes cliquées ou survolées |
| ↺ | Suppr | annuler la décision |

Code : un clic coche un critère du barème ; « ✔ test » / « ✗ test » disent ce que l'exécution a vérifié.

## 5. Ce que Thessalia apprend

- **Mémoire des verdicts** : rangés par question et par lecture de la machine. Dans les *autres* classes, votre
  verdict est **proposé** dès 3 jugements, **appliqué d'office** dès 10 jugements concordants à 95 %.
- **Lectures tapées** : sur 2 copies ou plus, elles deviennent des réponses plausibles à la lecture suivante.
- **Lecteurs affinés** (menu **Apprentissage**) : réentraînés sur vos lectures vérifiées, adoptés seulement
  s'ils lisent mieux sur une classe jamais vue.

**Entre deux classes** : finir la classe → relancer « Lire les réponses courtes » → lecture approfondie de la
suivante → la corriger → affiner le lecteur d'écriture dès deux classes corrigées.

## 6. Identifier les copies et exporter les notes (étape 6)

1. Déposer la **liste des élèves** (`.xlsx`, colonnes `NOM`, `Prénom`, `Classe`).
2. **Identifier les copies** : un nom pré-rempli n'est qu'une **proposition** ; **Entrée** (ou un clic sur un
   candidat) le confirme, la ligne passe en vert.
3. **Vérifier les noms** : copies sans élève et copies à risque en tête.
4. **Exporter les notes** : feuilles **Notes** (sur 20, arrondie au demi-point supérieur, réglable),
   **Absents**, **À vérifier**. L'ancien classeur est gardé, daté.

---

## Si ça bloque

**Page illisible.** Signalée avec sa place dans le PDF (`supH.pdf#73`). Une page du sujet abîmée reste dans sa
copie ; une **feuille d'un autre format** entre deux copies devient une **copie hors format**, notée à la main.

| Ce que vous voyez | Que faire |
|---|---|
| GABARIT DOUTEUX | Redéposer le PDF avec l'autre langue. |
| Une nouveauté n'apparaît pas | Relancer Thessalia, puis « Lue · relire » si elle concerne la lecture. |
| Un nom saisi reste dans les élèves sans copie | Il n'a pas été confirmé : Entrée sur sa ligne. |
| « une tâche tourne encore » | Mettre la tâche en pause (⏸) ou attendre la fin. |
| « n'a pas pu être déplacé » | Fermer les fichiers ouverts de l'examen (PDF, Excel), recommencer. |
| La page ne s'ouvre pas | Fenêtre noire ouverte ? Aller sur http://127.0.0.1:8765/examens. |
| « Address already in use » | Thessalia tourne déjà : utiliser l'onglet ouvert. |
| Boutons de l'étape 4 grisés | Installer ce qui manque depuis **Réglages**. |
| Mot de passe oublié | Supprimer `data/compte.json`, relancer. |
| « Python introuvable » | Réinstaller Python avec « Add python.exe to PATH ». |
| Windows bloque les `.bat` | « Informations complémentaires » → « Exécuter quand même ». PC verrouillé : `py installer.py` puis `.venv\Scripts\python -m thessalia app`. |
| Autre | Envoyer le journal (« Détail ») à l'auteur, **sans** copie ni nom d'élève. |

## Pour aller plus loin

- **Écrire un sujet** : `examen.yaml`, décrit dans [`FORMAT_SUJET.md`](FORMAT_SUJET.md) ; « Produire les PDF » ;
  imprimer en taille réelle.
- **Importer un sujet produit ailleurs** (générateur d'un collègue, au format Thessalia) : sur l'accueil,
  « Importer un sujet produit par un autre générateur ». Pour chaque langue : le PDF du sujet, son corrigé
  (`.key.json`), son vocabulaire (`.vocab.json`) et, recommandé, le fichier de zones, contrôlé contre le PDF.
  Thessalia lit les zones et les points dans le PDF et les affiche : **vérifier les points**.
- **Réglages** : arrondi de la note, extensions (lecteur d'écriture, Ollama et ses modèles). Sur Linux, Ollama
  s'installe dans un terminal : `curl -fsSL https://ollama.com/install.sh | sh` ; les modèles, depuis Réglages.

Le dossier `examens/` contient des **copies et des noms d'élèves** : ne pas le partager (il n'est jamais envoyé
sur GitHub). Le sujet `examen.yaml` se partage entre collègues, confidentiel jusqu'à l'examen.
