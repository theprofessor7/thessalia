"""Identification des copies : quelle copie est à quel élève.

La liste des élèves (`data/listes/*.xlsx` : NOM, Prénom, Classe) ne dit pas quel numéro de copie leur
revient. `python -m thessalia identite sorties/booster …` lit les vignettes Nom et Prénom de la page 1
(TrOCR d'origine, en local) et range les élèves du groupe du plus au moins ressemblant. Ce n'est qu'une
proposition : l'enseignant confirme chaque copie dans l'outil (`/g/<groupe>/noms`), qui écrit
`data/listes/<classe>.csv` (copie;etudiant). Rien n'est attribué sans lui : une erreur d'identité est pire
qu'une erreur de note.

Données personnelles : la liste, les vignettes d'identité et les lectures restent sur la machine (hors dépôt,
cf. `.gitignore`) ; la commande n'affiche aucun nom dans le terminal.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path

from .correction import LISTS_DIR, group_of

LECTURES = "identite_lectures.json"     # dans le dossier de la classe (lectures brutes, cache)
MODELE = "microsoft/trocr-base-handwritten"
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


# ---------------------------------------------------------------- liste des élèves
def _xlsx_rows(path):
    """Lignes de la première feuille d'un .xlsx, sans dépendance (un .xlsx est une archive de XML)."""
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        ss = ["".join(t.text or "" for t in si.iter(_NS + "t"))
              for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(_NS + "si")]
    rows = []
    for r in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(_NS + "row"):
        row = {}
        for c in r.findall(_NS + "c"):
            v, t = c.find(_NS + "v"), c.get("t")
            col = re.match(r"[A-Z]+", c.get("r")).group()
            if t == "s" and v is not None:
                row[col] = ss[int(v.text)]
            elif t == "inlineStr":
                row[col] = "".join(x.text or "" for x in c.iter(_NS + "t"))
            else:
                row[col] = v.text if v is not None else None
        rows.append(row)
    return rows


def lire_liste(path=None):
    """{groupe: [« NOM Prénom », …]} depuis la liste de l'enseignant (.xlsx ou .csv ; colonnes NOM, Prénom, Classe)."""
    if path is None:
        cands = sorted(LISTS_DIR.glob("*.xlsx"))
        if not cands:
            return {}
        path = cands[0]
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        rows = _xlsx_rows(path)
        head = {k: (v or "").strip().casefold() for k, v in rows[0].items()}
        data = [{head[k]: (v or "").strip() for k, v in r.items() if k in head} for r in rows[1:]]
    else:
        with open(path, encoding="utf-8-sig") as fh:
            data = [{k.strip().casefold(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(fh, delimiter=";")]
    out = {}
    for r in data:
        nom, prenom, classe = r.get("nom", ""), r.get("prénom", r.get("prenom", "")), r.get("classe", "")
        if nom and classe:
            out.setdefault(group_of(classe), []).append(f"{nom} {prenom}".strip())
    return {g: sorted(set(v)) for g, v in out.items()}


# ---------------------------------------------------------------- lecture des vignettes
def lire_vignettes(dirs, modele=MODELE, force=False):
    """Lit identity.nom / identity.prenom de chaque copie ; écrit <classe>/identite_lectures.json."""
    import cv2
    from .ocr import TrOCRBackend

    eng = None
    for d in map(Path, dirs):
        cache = d / LECTURES
        if cache.exists() and not force:
            continue
        res = json.loads((d / "results.json").read_text(encoding="utf-8"))
        cles, imgs = [], []
        for c in res["copies"]:
            for z in ("nom", "prenom"):
                p = d / c["copy_id"] / "crops" / f"identity.{z}.png"
                im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) if p.exists() else None
                if im is not None:
                    cles.append((c["copy_id"], z))
                    imgs.append(im)
        if eng is None:
            eng = TrOCRBackend(modele, beams=5, n_best=3)
        lus = eng.recognize(imgs) if imgs else []
        out = {}
        for (cid, z), cands in zip(cles, lus):
            out.setdefault(cid, {})[z] = [[t, round(s, 3)] for t, s in cands]
        cache.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {d.name} : {len(out)} copies lues")


# ---------------------------------------------------------------- rapprochement
def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).upper()
    s = re.sub(r"\b(NOM|PRENOM|FIRST ?NAME|LAST ?NAME|NAME)\b", " ", s)   # libellé imprimé de la zone
    return re.sub(r"[^A-Z]+", "", s)


def _ressemblance(lu, ref):
    """0..1 : ressemblance d'une lecture à un nom (sous-chaîne tolérée : le libellé, les pointillés…)."""
    a, b = _norm(lu), _norm(ref)
    if not a or not b:
        return 0.0
    m = SequenceMatcher(None, a, b)
    bloc = sum(x.size for x in m.get_matching_blocks())
    return max(m.ratio(), bloc / len(b) * min(1.0, len(a) / max(1, len(b))) ** 0.25 * 0.95)


def classer(lectures, etudiants):
    """Élèves du groupe triés par ressemblance avec les lectures Nom + Prénom d'une copie : [(élève, score)]."""
    out = []
    for e in etudiants:
        parts = e.split(" ")
        # NOM = mots en majuscules en tête, Prénom = le reste
        k = next((i for i, w in enumerate(parts) if not w.isupper()), len(parts))
        nom, prenom = " ".join(parts[:k]) or e, " ".join(parts[k:])
        sn = max((_ressemblance(t, nom) for t, _ in lectures.get("nom", [])), default=0.0)
        sp = max((_ressemblance(t, prenom) for t, _ in lectures.get("prenom", [])), default=0.0) if prenom else sn
        out.append((e, round(0.6 * sn + 0.4 * sp, 3)))
    return sorted(out, key=lambda x: -x[1])


def repartir(scores, eleves):
    """Répartition d'ensemble : un élève n'a qu'une copie. `scores` : {copie: {élève: score}} (copies pas encore
    confirmées, élèves encore libres). Score relatif (on retire la moitié de la moyenne de la copie et de celle
    de l'élève : un nom « qui ressemble à tout » ne gagne plus partout), puis on fixe d'abord les copies les moins
    ambiguës. Mesuré le 22 octobre sur NB (37 copies confirmées) : 27 justes en tête, contre 18 copie par copie."""
    cop = list(scores)
    if not cop or not eleves:
        return {}
    M = [[scores[c].get(e, 0.0) for e in eleves] for c in cop]
    lig = [sum(r) / len(r) for r in M]
    col = [sum(M[i][j] for i in range(len(cop))) / len(cop) for j in range(len(eleves))]
    S = [[M[i][j] - 0.5 * lig[i] - 0.5 * col[j] for j in range(len(eleves))] for i in range(len(cop))]
    libres_c, libres_e, out = set(range(len(cop))), set(range(len(eleves))), {}
    while libres_c and libres_e:
        best = None
        for i in libres_c:
            vals = sorted(((S[i][j], j) for j in libres_e), reverse=True)
            cle = 2 * vals[0][0] - (vals[1][0] if len(vals) > 1 else vals[0][0])   # meilleur + marge sur le 2e
            if best is None or cle > best[0]:
                best = (cle, i, vals[0][1])
        _, i, j = best
        out[cop[i]] = eleves[j]
        libres_c.discard(i)
        libres_e.discard(j)
    return out


# ---------------------------------------------------------------- fichier copie;etudiant
def provisoire(classe, cid):
    return f"{classe}_copie{int(cid.split('_')[-1]):03d}"


def lire_attributions(classe, lists_dir=LISTS_DIR):
    p = Path(lists_dir) / f"{classe}.csv"
    if not p.exists():
        return {}
    with open(p, encoding="utf-8-sig") as fh:
        return {r["copie"]: r["etudiant"] for r in csv.DictReader(fh, delimiter=";")
                if r.get("etudiant") and r["etudiant"] != provisoire(classe, r["copie"])}


def ecrire_attribution(classe, copy_ids, cid, etudiant, lists_dir=LISTS_DIR):
    """Attribue (ou retire, etudiant vide) une copie ; les autres lignes sont gardées."""
    att = lire_attributions(classe, lists_dir)
    if etudiant:
        att[cid] = etudiant
    else:
        att.pop(cid, None)
    p = Path(lists_dir) / f"{classe}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["copie", "etudiant"])
        for c in copy_ids:
            w.writerow([c, att.get(c, provisoire(classe, c))])


def run(dirs, liste=None, force=False):
    from .serve import _classes

    classes = _classes(dirs)
    groupes = lire_liste(liste)
    if not groupes:
        raise SystemExit("Liste des élèves introuvable (data/listes/*.xlsx, colonnes NOM, Prénom, Classe).")
    lire_vignettes(classes, force=force)
    # résumé SANS nom : nombre de copies par groupe, élèves sur la liste, propositions nettes
    bilan = {}
    for d in classes:
        g = group_of(d.name)
        lus = json.loads((d / LECTURES).read_text(encoding="utf-8"))
        b = bilan.setdefault(g, {"copies": 0, "nettes": 0})
        for cid, lec in lus.items():
            b["copies"] += 1
            r = classer(lec, groupes.get(g, []))
            b["nettes"] += len(r) > 1 and r[0][1] >= 0.6 and r[0][1] - r[1][1] >= 0.15
    for g, b in sorted(bilan.items()):
        print(f"  groupe {g} : {b['copies']} copies, {len(groupes.get(g, []))} élèves sur la liste, "
              f"{b['nettes']} propositions nettes")
    print("Confirmer dans l'outil : /g/<groupe>/noms")
