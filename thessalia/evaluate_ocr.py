"""Évaluation Niveau 2 : lectures OCR + snapping vs vérité terrain.

Vérité : {"cNN_qX.Y": "texte"} ; "" = vide ; suffixe "?" = lecture incertaine (exclue des taux).
Métriques par moteur :
    brut      lecture brute == vérité (après normalisation)
    auto      part des réponses acceptées automatiquement (statut ok)
    justes    part des acceptées qui sont justes  <- le chiffre qui compte
    revue     part envoyée à l'humain (avec propositions)
    top3      la bonne réponse figure parmi les 3 propositions (utile pour la revue en 1 clic)
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from .vocab import normalize, parse_number, snap


# même réponse dans la langue de l'autre sujet (décision de l'enseignant) : pas une faute, donc une
# acceptation `Error` -> `ERREUR` n'est pas comptée fausse
EQUIV = {"error": "erreur", "zero": "zéro"}


def same(a, b, kind):
    if kind == "number":
        na, nb = parse_number(a) or normalize(a, kind), parse_number(b) or normalize(b, kind)
        return EQUIV.get(na.lower(), na) == EQUIV.get(nb.lower(), nb) if na != nb else True
    if kind == "text":
        return normalize(a, "enum") == normalize(b, "enum")  # tolérant aux espaces pour le texte
    na, nb = normalize(a, kind), normalize(b, kind)
    return EQUIV.get(na, na) == EQUIV.get(nb, nb)


def evaluate(ocr: dict, truth: dict, vocab: dict, accept=0.34, margin=0.30, verbose=False, flagged=()):
    """flagged : clés mises en revue par une règle sur l'image (deux mots, mot barré) que `snap` ne voit pas."""
    st = Counter()
    by_q = defaultdict(Counter)
    errors = []
    for key, t in truth.items():
        fid = key.split("_", 1)[1]
        spec = vocab.get(fid, {"kind": "text"})
        kind = spec.get("kind", "text")
        unsure = t.endswith("?")
        t = t.rstrip("?")
        if unsure:
            st["incertaines (exclues)"] += 1
            continue
        if t == "":
            continue  # les vides sont traités en amont (détection d'encre), pas par l'OCR
        cands = ocr.get(key)
        if not cands:
            st["vide_a_tort"] += 1
            continue
        st["n"] += 1
        q = fid.split(".")[0]
        by_q[q]["n"] += 1
        raw = cands[0][0]
        if same(raw, t, kind):
            st["brut_ok"] += 1
            by_q[q]["brut_ok"] += 1
        r = snap(cands, spec, accept, margin)
        if kind == "text":
            st["texte (revue)"] += 1
            continue
        st["snap_n"] += 1
        good = r["value"] is not None and same(r["value"], t, kind)
        in_top = any(same(s, t, kind) for s in r["suggestions"])
        st["top3"] += in_top
        if r["status"] == "ok" and key in flagged:
            st["revue (image)"] += 1
            st["revue"] += 1
        elif r["status"] == "ok":
            st["auto"] += 1
            by_q[q]["auto"] += 1
            if good:
                st["auto_ok"] += 1
                by_q[q]["auto_ok"] += 1
            else:
                errors.append((key, t, raw, r["value"], r.get("distance"), r.get("second")))
        else:
            st["revue"] += 1
    return st, by_q, errors


def proposals(values: dict, truth: dict, vocab: dict):
    """Champs `number` : (n, justes) — la valeur proposée (acceptée ou en revue) est-elle la bonne ?"""
    n = good = 0
    for key, t in truth.items():
        spec = vocab.get(key.split("_", 1)[1], {})
        if spec.get("kind") != "number" or t.endswith("?") or t == "" or key not in values:
            continue
        n += 1
        good += values[key] is not None and same(str(values[key]), t, "number")
    return n, good


def report(name, st, by_q, errors, show=12):
    n, sn = st["n"], st["snap_n"]
    lines = [f"== {name}",
             f"  lecture brute exacte : {st['brut_ok']}/{n} ({100 * st['brut_ok'] / max(n, 1):.1f} %)",
             f"  champs à vocabulaire : {sn} ; acceptés auto {st['auto']} ({100 * st['auto'] / max(sn, 1):.1f} %),"
             f" dont justes {st['auto_ok']} ({100 * st['auto_ok'] / max(st['auto'], 1):.1f} %) ;"
             f" revue {st['revue']} (dont {st['revue (image)']} par l'image) ; bonne réponse dans le top 3 : {100 * st['top3'] / max(sn, 1):.1f} %",
             f"  texte libre (q7, toujours en revue) : {st['texte (revue)']} ; incertaines exclues : {st['incertaines (exclues)']}"]
    for q in sorted(by_q, key=lambda s: int(s[1:])):
        c = by_q[q]
        lines.append(f"    {q:4s} brut {c['brut_ok']:3d}/{c['n']:3d}  auto {c['auto']:3d} (justes {c['auto_ok']})")
    for e in errors[:show]:
        lines.append(f"    ERREUR {e}")
    return "\n".join(lines)


def main(ocr_path, truth_path, vocab_path, name=None):
    ocr = json.load(open(ocr_path))
    truth = json.load(open(truth_path))
    vocab = json.load(open(vocab_path))["fields"]
    st, by_q, errors = evaluate(ocr, truth, vocab)
    print(report(name or ocr_path, st, by_q, errors))
