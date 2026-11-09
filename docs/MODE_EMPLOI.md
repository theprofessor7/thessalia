# Thessalia — mode d'emploi

Thessalia prépare un examen papier (sujet et corrigé en PDF, en français et en anglais), lit les copies scannées
et aide à les corriger : QCM et vrai/faux lus automatiquement, réponses courtes et code proposés à la relecture,
notes sur 20 dans un classeur Excel.

Tout se passe **sur votre ordinateur**, dans votre navigateur. Rien n'est envoyé sur internet : ni les copies,
ni les noms, ni les notes. Aucun abonnement, aucune clé.

---

## 1. Installer (une fois, ~10 minutes)

Il faut **Python 3.10 ou plus récent** et **git**.

- Python : https://www.python.org/downloads/ (sous Windows, cocher **« Add python.exe to PATH »**).
- git : https://git-scm.com/downloads (options par défaut).

Récupérer Thessalia, dans un dossier dont le chemin ne contient pas « $ » (par exemple `C:\Thessalia`) :

```
git clone <adresse du dépôt> C:\Thessalia
```

Puis :

- **Windows** : double-cliquer sur `installer.bat`.
- **macOS / Linux** : dans un terminal, `./installer.sh`.

L'installeur demande s'il faut ajouter le **lecteur d'écriture** (~2 Go). Il lit automatiquement les réponses
courtes. Sans lui, tout fonctionne : les réponses courtes se corrigent à la main dans l'outil. On peut relancer
l'installeur plus tard pour l'ajouter.

### Facultatif : la préparation de nuit (code manuscrit)

Pour que le code écrit à la main soit transcrit et pré-noté pendant la nuit, installer **Ollama**
(https://ollama.com), puis, une fois, dans un terminal :

```
ollama pull qwen3-vl:8b-instruct
ollama pull qwen3:14b
ollama pull qwen3-vl:4b-instruct
```

Il faut environ 20 Go de disque et 16 Go de mémoire. Sans réseau, le dossier des modèles d'Ollama peut être
copié depuis le PC d'un collègue.

## 2. Lancer

- **Windows** : double-cliquer sur `Thessalia.bat`.
- **macOS** : double-cliquer sur `Thessalia.command` (Linux : `./Thessalia.command`).

Le navigateur s'ouvre sur http://127.0.0.1:8765/examens. **Laisser la fenêtre noire ouverte** : la fermer
arrête Thessalia.

## 3. Mettre à jour

Thessalia lancé fermé, dans le dossier de Thessalia :

```
git pull
```

puis relancer l'installeur (il ne refait que ce qui manque). Vos examens ne sont pas touchés.

---

## 4. Un examen, du sujet aux notes

La page d'un examen présente les étapes dans l'ordre. Une étape faite est cochée en vert.

### Étape 1 — Source du sujet

Le sujet s'écrit **une seule fois** dans un fichier texte `examen.yaml` : énoncés en français et en anglais,
bonnes réponses, barème. Le format est décrit dans [`FORMAT_SUJET.md`](FORMAT_SUJET.md). Le plus simple est de
partir du fichier d'un collègue.

« Nouvel examen » : choisir le fichier (et les images, comme le logo). Thessalia **contrôle** tout de suite le
fichier. En cas d'erreur, il affiche la ligne et la raison (« ligne 42 : bonne réponse « e » absente des
choix »). Corriger dans un éditeur de texte, puis « Remplacer la source ». L'ancienne version est gardée.

### Étape 2 — Sujets et corrigés

« Produire les PDF » fabrique le sujet et le corrigé de chaque langue. Thessalia relit ensuite le PDF produit
et **refuse** de continuer si une zone de réponse n'est pas exactement là où elle est dessinée.

Imprimer les `sujet_….pdf`. **Ne pas modifier le PDF** (ni le redimensionner à l'impression : choisir « taille
réelle »). Les carrés noirs dans les coins servent à repérer la feuille.

Si la source change, il faut produire à nouveau. La page le signale.

### Étape 3 — Copies scannées

Scanner les copies d'une classe en un seul PDF : A4 ou A3, recto, 100 dpi ou plus. Les pages tournées ou
blanches sont gérées.

Indiquer le nom de la classe (ex. `supA_1`) et **la langue du sujet distribué**, puis « Déposer et lire ». La
lecture prend une à quelques minutes. Si la langue est fausse, le journal affiche **« GABARIT DOUTEUX »** :
redéposer avec la bonne langue.

### Étape 4 — Lectures longues (facultatif)

- **Lire les réponses courtes** (lecteur d'écriture) : quelques minutes par classe. Pour un sujet nouveau,
  **toutes** les réponses partent en revue, avec la lecture proposée. C'est voulu : un sujet n'est validé
  qu'après une mesure sur des copies corrigées.
- **Sujet validé** : à mesure que vous corrigez les réponses courtes, la page compte les lectures que la machine
  aurait acceptées d'office et combien sont justes d'après vous. Le bouton s'active à partir de 30 lectures
  vérifiées **sans aucun écart**. Ensuite, les réponses sûres de ce sujet sont acceptées d'office ; les autres
  restent en revue. Produire à nouveau le sujet annule la validation.
- **Préparer la nuit** (Ollama) : transcrit le code manuscrit, pré-coche les critères du barème en exécutant le
  code, et fait relire les réponses courtes par un second modèle. Compter environ une nuit pour une centaine de
  copies. Si c'est interrompu, relancer : la préparation reprend où elle s'était arrêtée.

Une seule tâche longue tourne à la fois. Son journal s'affiche en haut de la page.

### Étape 5 — Correction

« Corriger les copies lues » ouvre l'outil de correction :

- **par question** : toutes les réponses d'une même question, regroupées ; une décision s'applique aux
  réponses identiques ;
- **par copie** : une copie entière ;
- **identification** : attribuer chaque copie à un élève de la liste.

Thessalia ne décide jamais en silence. Tout ce qui est douteux est marqué **« à revoir »**, avec la raison. Une
note n'est définitive que lorsqu'il ne reste rien à revoir.

### Étape 6 — Notes

Déposer la **liste des élèves** de l'examen : un classeur `.xlsx` avec les colonnes `NOM`, `Prénom`, `Classe`.
Sans liste, les copies ne peuvent pas être attribuées.

« Exporter les notes » produit `notes_<examen>.xlsx`, avec trois feuilles :

- **Notes** : une ligne par copie, notes sur 20 ;
- **Absents** : élèves de la liste sans copie ;
- **À vérifier** : copies sans élève ou avec des réponses encore en attente (note provisoire).

Chaque export garde l'ancien classeur, daté.

---

## 5. Où sont mes fichiers ? Confidentialité

Tout un examen est rangé dans `examens/<nom de l'examen>/` dans le dossier de Thessalia :

| Dossier ou fichier | Contenu |
|---|---|
| `examen.yaml` | la source du sujet |
| `produit/` | PDF des sujets et corrigés, fichiers de correction |
| `scans/` | copies scannées |
| `classes/` | lectures des copies |
| `decisions.sqlite` | vos décisions de correction |
| `listes/` | liste des élèves, attributions des copies |
| `notes/` | classeurs de notes |

Ce dossier contient des **copies et des noms d'élèves** :

- ne pas le partager ni le déposer sur un espace partagé ;
- il n'est jamais envoyé avec `git` (il est exclu du dépôt).

Pour sauvegarder un examen, copier son dossier sur un support personnel.

Le sujet lui-même (`examen.yaml`) se partage avec les collègues. Il est **confidentiel jusqu'à l'examen**.

## 6. En cas de problème

| Problème | Que faire |
|---|---|
| `installer.bat` : « Python introuvable » | Installer Python en cochant « Add python.exe to PATH », puis relancer. |
| « le chemin du dossier contient $ » | Cloner Thessalia ailleurs, par exemple `C:\Thessalia`. |
| La page ne s'ouvre pas | Vérifier que la fenêtre noire est ouverte, puis aller sur http://127.0.0.1:8765/examens. |
| « Address already in use » | Thessalia tourne déjà : utiliser la fenêtre ouverte. |
| « Source refusée » | Lire la ligne indiquée ; les pièges courants (« : » dans une phrase, `#`) sont expliqués dans le message. |
| GABARIT DOUTEUX | Mauvaise langue choisie au dépôt : redéposer le PDF avec l'autre langue. |
| Boutons de l'étape 4 grisés | Le message à côté indique ce qui manque (lecteur d'écriture, Ollama, modèle). |
| Autre | Copier le journal de la tâche (en haut de la page) et l'envoyer à l'auteur, **sans** copie d'élève. |
