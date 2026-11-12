# Thessalia — mode d'emploi

Thessalia lit les copies papier scannées d'un examen et aide à les corriger : cases lues automatiquement,
réponses écrites proposées à la relecture, notes sur 20 dans un classeur Excel. Tout se passe **sur votre
ordinateur**, dans votre navigateur : rien n'est envoyé sur internet.

Guide illustré : [`Thessalia_mode_emploi.pdf`](Thessalia_mode_emploi.pdf) (aussi dans le menu **Aide**).

**Thessalia ne décide jamais en silence** : ce qui est douteux (case à moitié cochée, écriture difficile, page
illisible…) est marqué « à décider », avec la raison.

---

## 1. Ouvrir Thessalia

**Installer, une fois.** Installer [Python](https://www.python.org/downloads/) (Windows : cocher **« Add
python.exe to PATH »**) et [git](https://git-scm.com/downloads), puis dans PowerShell :

```
git clone https://github.com/theprofessor7/thessalia.git C:\Thessalia
```

et double-cliquer sur `installer.bat` (Mac / Linux : `./installer.sh`). Le lecteur d'écriture (~2 Go) est
facultatif ; il s'ajoute plus tard depuis **Réglages**.

**Lancer, à chaque fois.** Double-cliquer sur `Thessalia.bat` (Mac : `Thessalia.command`). **Laisser la fenêtre
noire ouverte.** Au premier lancement, choisir un identifiant et un mot de passe.

**Mettre à jour.** Thessalia fermé : `git pull` dans le dossier, relancer l'installeur, puis relancer Thessalia.

**L'accueil** montre une carte par examen :

- **Ouvrir** : la page de l'examen, un assistant en six étapes ; une étape grisée dit ce qui lui manque ;
- **Supprimer** : l'examen part dans la **corbeille** (en bas de l'accueil) avec tout son contenu ;
  **Restaurer** le remet d'un clic. Rien n'est effacé du disque.

## 2. Charger les copies d'une classe (étape 3)

Scanner **toutes les copies d'une classe en un seul PDF** (A4 ou A3, 100 dpi ou plus ; pages tournées, blanches
ou sujet imprimé en A3 : gérés). Puis : nom de la classe, **langue du sujet distribué**, PDF, **Déposer et lire**.

- Le nom range la classe dans son groupe : `supA_1`, `supA_2` → groupe A. Une copie scannée à part se charge
  comme une classe de plus (`supA_2`).
- Une jauge suit la lecture ; une fenêtre résume la fin. **Lue · relire** relit une classe, décisions gardées.

## 3. Corriger (étape 5)

**Corriger les copies lues** ouvre l'outil : tableau de bord par groupe, une carte par question. Corriger **par
question** : chaque réponse montre l'image, la lecture de la machine, l'attendu et le verdict proposé. Chaque clic
est enregistré.

Autres vues : **Copies et notes** (une copie entière), **Identifier les copies** (attribuer chaque copie à un
élève), **Suivi de la machine**.

Étape 4, facultative : lecture des réponses courtes (lecteur d'écriture) et **lecture approfondie** du code
manuscrit (Ollama, en arrière-plan, quelques heures ; pause ⏸ et reprise ▶). À installer depuis **Réglages**.

## 4. Les outils des cartes

| Bouton | Touche | Effet |
|---|---|---|
| ✓ valider | Entrée | accepter le verdict proposé |
| juste / forme / faux | 1 / 2 / 3 | tous les points / la moitié / zéro |
| vide / illisible | 4 / 5 | rien d'écrit / impossible à lire |
| bien lu | L | lecture exacte : exemple pour l'apprentissage |
| = attendu | A | l'élève a écrit l'attendu, la machine a mal lu |
| autre lecture | 6 7 8 | choisir une autre lecture proposée |
| corriger la lecture | T | taper ce qui est écrit ; le verdict se recalcule |
| annuler | Suppr | effacer la décision |

Code : 1…5 cochent les critères, J tout juste, 0 rien de juste, V vide, M entorse grave.

L'étiquette de la carte dit d'où vient la proposition (vous, lecteur sûr, deux lecteurs d'accord, tests
exécutés, mémoire, lecture proposée). Dès 3 jugements identiques, votre verdict est proposé dans les autres
classes ; dès 10 à 95 %, il est appliqué d'office.

## 5. Les outils des blocs

Les réponses identiques d'une question forment un bloc :

- **Confirmer le bloc** : le verdict proposé pour tout le bloc ;
- **bien lu pour le bloc** : lecture exacte partout ;
- **= attendu pour le bloc** : la machine a mal lu la même chose, tous ont écrit l'attendu ;
- **vide pour le bloc** : zones sans lecture où rien n'est écrit.

**Valider toutes les propositions** (en haut) accepte tout ce qui reste sur la question.

## 6. Exporter les notes (étape 6)

1. Déposer la **liste des élèves** (`.xlsx`, colonnes `NOM`, `Prénom`, `Classe`).
2. Attribuer les copies (**Identifier les copies**).
3. **Vérifier les noms** : copies sans élève et copies à risque en tête.
4. **Exporter les notes** : feuilles **Notes** (note sur 20, arrondie au demi-point supérieur, réglable),
   **Absents**, **À vérifier**. L'ancien classeur est gardé, daté.

---

## Si ça bloque

**Page illisible.** Une page sans les carrés noirs des coins est signalée avec sa place dans le PDF
(`supH.pdf#73` = page 73). Une page du sujet abîmée reste dans sa copie (réponses à décider). Une **feuille d'un
autre format** (réponses tapées, feuille libre) entre deux copies complètes devient une **copie hors format**,
numérotée après les autres : la lire dans l'outil, saisir sa note (même échelle que les autres copies),
l'attribuer à l'élève. L'export la reprend ; en attendant, elle compte 0 et figure dans « À vérifier ».

| Ce que vous voyez | Que faire |
|---|---|
| GABARIT DOUTEUX | Mauvaise langue au dépôt : redéposer le PDF avec l'autre langue. |
| Une nouveauté n'apparaît pas | Relancer Thessalia, puis « Lue · relire » si elle concerne la lecture. |
| « une tâche tourne encore » | Mettre la tâche en pause (⏸) ou attendre la fin. |
| « n'a pas pu être déplacé » | Fermer les fichiers ouverts de l'examen (PDF, Excel), recommencer. |
| La page ne s'ouvre pas | Fenêtre noire ouverte ? Aller sur http://127.0.0.1:8765/examens. |
| « Address already in use » | Thessalia tourne déjà : utiliser l'onglet ouvert. |
| Boutons de l'étape 4 grisés | Installer ce qui manque depuis **Réglages**. |
| « Source refusée » | Lire la ligne indiquée, corriger le fichier, « Remplacer la source ». |
| Mot de passe oublié | Supprimer `data/compte.json`, relancer. |
| « Python introuvable » | Réinstaller Python avec « Add python.exe to PATH ». |
| Windows bloque les `.bat` | SmartScreen : « Informations complémentaires » → « Exécuter quand même ». PC verrouillé : `py installer.py` puis `.venv\Scripts\python -m thessalia app` dans PowerShell. |
| Autre | Envoyer le journal (« Détail ») à l'auteur, **sans** copie ni nom d'élève. |

## Pour aller plus loin

- **Écrire un sujet** : fichier `examen.yaml`, décrit dans [`FORMAT_SUJET.md`](FORMAT_SUJET.md) ; « Produire
  les PDF » fabrique sujet et corrigé ; imprimer en taille réelle, sans modifier le PDF.
- **Sujet validé** : après 30 lectures vérifiées sans erreur, la machine accepte seule ses lectures sûres.
- **Apprentissage** : mémoire des verdicts, affinage des lecteurs (adopté seulement s'il fait mieux).
- **Réglages** : arrondi de la note, extensions (lecteur d'écriture, Ollama et ses modèles).

Le dossier `examens/` contient des **copies et des noms d'élèves** : ne pas le partager (il n'est jamais envoyé
sur GitHub). Le sujet `examen.yaml` se partage entre collègues, confidentiel jusqu'à l'examen.
