"""Fichiers de corrigé tirés de la source (docs/FORMAT_SUJET.md, § 7.4).

Pour l'instant, on écrit les fichiers que la correction lit déjà (`key.json`, `vocab.json`, `bareme.json`), pour
qu'elle marche sans autre changement. Les tolérances nommées sont développées ici en listes de réponses.
Avec `gabarit`, chaque champ produit est confronté au gabarit (même identifiant, même nature, mêmes points par
question) : un corrigé qui ne colle pas au sujet imprimé est refusé.
"""
from __future__ import annotations

import itertools
import re

from .modele import NATURES, VF, Examen, _f, _pts
from .source import ErreurSujet

NOTE = "Produit par « thessalia sujet » depuis {src} : ne pas modifier à la main, modifier la source."


def variantes(b, langue):
    """(accepte, forme, partiel) d'un blanc dans une langue : listes écrites + tolérances développées."""
    att = b.attendu[langue]
    base = {att}
    if "espace_ponctuation" in b.tolerances:
        base |= {re.sub(r" ([!?])", r"\1", s) for s in base} | {re.sub(r"(?<! )([!?])", r" \1", s) for s in base}
    if "espaces_virgules" in b.tolerances:
        base |= {s.replace(", ", ",") for s in base}
    accepte = set(base - {att}) | set(b.accepte.get(langue, []))
    forme = set(b.forme.get(langue, []))
    cites = {f'"{s}"' for s in base} | {f"'{s}'" for s in base}
    if "guillemets" in b.tolerances:
        accepte |= cites
    if "guillemets_forme" in b.tolerances:
        forme |= cites
    partiel = dict(b.partiel.get(langue, {}))
    for t in b.tolerances:
        if isinstance(t, tuple) and t[0] == "liste_incomplete":
            elems = _elements(att)
            if elems is None:
                raise ErreurSujet([f"{b.id} : liste_incomplete demande une réponse en liste [a, b, …] ({att})"])
            for k in range(1, t[1]["manque_max"] + 1):
                for garde in itertools.combinations(range(len(elems)), len(elems) - k):
                    s = "[" + ", ".join(elems[i] for i in garde) + "]"
                    partiel[s] = t[1]["points"]
                    if "espaces_virgules" in b.tolerances:
                        partiel[s.replace(", ", ",")] = t[1]["points"]
    return sorted(accepte), sorted(forme), partiel


def _elements(s):
    s = s.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return None
    return [x.strip() for x in s[1:-1].split(",")] if s[1:-1].strip() else []


def fichiers(ex: Examen, langue: str, exam_id: str, source: str, traduction_de: str | None = None):
    """(key, vocab, bareme) au format actuel de Thessalia ; bareme = None s'il n'y a pas de code, ou pour une
    traduction (le barème du sujet d'origine sert, cf. correction.py)."""
    note = NOTE.format(src=source)
    key = {"exam_id": exam_id, **({"traduction_de": traduction_de} if traduction_de else {}), "_note": note,
           "scoring": {"default": "exact"}, "answers": {}, "short_answers": {}, "short_accept": {},
           "short_forme": {}, "short_partiel": {}, "points_champs": {}}
    vocab = {"exam_id": exam_id, "_note": note, "fields": {}}
    bareme = {"exam_id": exam_id, "_note": note, "champs": {}}
    for q in ex.questions():
        d = q.donnees
        if q.type == "qcm":
            key["answers"][d["id"]] = list(d["bonnes"])
        elif q.type == "vrai_faux":
            v, f = VF.get(langue, ("V", "F"))
            for a in d["affirmations"]:
                key["answers"][a["id"]] = [v if a["vrai"] else f]
        elif q.type == "blancs":
            for b in d["blancs"]:
                acc, forme, part = variantes(b, langue)
                key["short_answers"][b.id] = b.attendu[langue]
                for nom, val in (("short_accept", acc), ("short_forme", forme), ("short_partiel", part)):
                    if val:
                        key[nom][b.id] = val
                if b.points is not None:
                    key["points_champs"][b.id] = b.points
                kind = NATURES[b.nature]
                valeurs = [b.attendu[langue]] + b.accepte.get(langue, []) + b.plausibles.get(langue, [])
                valeurs = list(dict.fromkeys(valeurs))
                vocab["fields"][b.id] = ({"kind": kind} if kind == "number" else
                                         {"kind": kind, "values": sorted(valeurs) if kind == "enum" else valeurs})
        elif q.type in ("code", "redaction") and d.get("criteres"):
            bareme["champs"][d["id"]] = {
                "points": q.points, **({"corrige": d["corrige"][langue].rstrip("\n")} if d.get("corrige") else {}),
                "criteres": [{"id": c["id"], "libelle": c["texte"][langue], "points": c["points"],
                              **{k: c[k] for k in ("essais", "contient", "verifie") if k in c}} for c in d["criteres"]]}
    for k in ("short_accept", "short_forme", "short_partiel", "points_champs"):
        if not key[k]:
            del key[k]
    return key, vocab, (bareme if bareme["champs"] and not traduction_de else None)


def confronter(ex: Examen, gabarit: dict):
    """Erreurs (liste) si les champs produits ne collent pas au gabarit du sujet imprimé."""
    err = []
    champs = {f["id"]: f for p in gabarit["pages"] for f in p["fields"]}
    pts_gab = {q["num"]: q.get("points") for q in gabarit.get("questions", [])}
    attendus = {"qcm": ("mcq",), "vrai_faux": ("truefalse", "mcq"), "blancs": ("short_text",),
                "code": ("code_grid", "text_box"), "redaction": ("text_box", "code_grid")}
    vus = set()
    for q in ex.questions():
        d = q.donnees
        ids = ([d["id"]] if "id" in d else [a["id"] for a in d.get("affirmations", [])]
               + [b.id for b in d.get("blancs", [])])
        for i in ids:
            f = champs.get(i)
            vus.add(i)
            if f is None:
                err.append(f"question {q.num} : le champ {i} n'existe pas dans le gabarit")
            elif f["type"] not in attendus[q.type]:
                err.append(f"question {q.num} : {i} est « {f['type']} » dans le gabarit, la source dit {q.type}")
        if q.num in pts_gab and pts_gab[q.num] is not None and abs(_pts(pts_gab[q.num]) - q.points) > 1e-6:
            err.append(f"question {q.num} : {_f(q.points)} pt dans la source, {_f(pts_gab[q.num])} pt sur le sujet imprimé")
    oublies = sorted(i for i, f in champs.items() if i not in vus and not i.startswith("identity"))
    if oublies:
        err.append(f"champs du gabarit absents de la source : {', '.join(oublies)}")
    return err
