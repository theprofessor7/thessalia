"""Niveau 2 — rapprochement (« snapping ») d'une lecture OCR vers un vocabulaire attendu.

Spécification par champ (fichier *.vocab.json, clé = id du champ) :

    {"kind": "enum",   "values": ["int", "float", "str", "bool"]}
    {"kind": "number"}                              nombre libre (parsé) : toujours en revue
    {"kind": "number", "min_conf": 0.98}           … accepté seul si le moteur est sûr (opt-in mesuré)
    {"kind": "number", "values": ["ERROR"]}        nombre OU mot du vocabulaire
    {"kind": "text",   "values": ["Hello Alice"]}  texte libre : proposition + revue humaine

Règle d'or : le vocabulaire contient toutes les réponses PLAUSIBLES, justes ou
fausses (ici tous les types Python, pas seulement le bon). Sinon le snapping
transformerait l'erreur d'un étudiant en bonne réponse.

Normalisation : casse, espaces, guillemets, et formes équivalentes
(« <class 'int'> » -> « int »). Distance : Levenshtein où les confusions
classiques de l'écriture manuscrite coûtent moins cher (0/O, 1/l/I, 5/S…).

Décision : accepté si la meilleure distance relative est faible ET nettement
inférieure à la deuxième ; sinon « review » avec les meilleures propositions.
"""
from __future__ import annotations

import re
import unicodedata

CONFUSABLE = [
    "0oOQD", "1lI|i!7", "5sS", "2zZ", "8B", "6b", "9gq", "uvw", "nmh", "rn", "cCeéè", "aoα", "tf+",
    "\"'`´“”‘’", ".,", ":;", "-_~", "kK", "pP", "wW", "xX", "yY",
]
_CONF = {}
for grp in CONFUSABLE:
    for a in grp:
        for b in grp:
            if a != b:
                _CONF[(a, b)] = 0.35


def normalize(s: str, kind="enum") -> str:
    s = unicodedata.normalize("NFKC", s or "").strip()
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    m = re.fullmatch(r"<?\s*class\s*['\"]?\s*(\w+)\s*['\"]?\s*>?", s, re.I)  # <class 'int'>
    if m:
        s = m.group(1)
    if kind in ("enum", "number"):
        s = re.sub(r"\(\s*\)$", "", s.strip())  # print() -> print
        s = s.strip("'\" ").lower()
        s = re.sub(r"\s+", "", s)
    else:
        s = re.sub(r"\s+", " ", s)
    return s


def wdist(a: str, b: str) -> float:
    """Levenshtein pondéré (substitution d'une confusion classique = 0,35)."""
    n, m = len(a), len(b)
    prev = [float(j) for j in range(m + 1)]
    pprev = prev
    for i in range(1, n + 1):
        cur = [float(i)] + [0.0] * m
        for j in range(1, m + 1):
            ca, cb = a[i - 1], b[j - 1]
            sub = 0.0 if ca == cb else (_CONF.get((ca, cb), _CONF.get((ca.lower(), cb.lower()), 1.0))
                                         if ca.lower() != cb.lower() else 0.1)
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + sub)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb and ca != cb:
                cur[j] = min(cur[j], pprev[j - 2] + 0.5)  # inversion de deux lettres (« flaot »)
        pprev, prev = prev, cur
    return prev[m]


def rel(a, b):
    return wdist(a, b) / max(len(a), len(b), 1)


NUM_FIX = str.maketrans({"o": "0", "O": "0", "l": "1", "I": "1", "|": "1", "S": "5", "s": "5", ",": ".",
                         "B": "8", "Z": "2", "z": "2", "—": "-", "–": "-", "_": "-"})


def parse_number(s: str):
    t = normalize(s, "number").translate(NUM_FIX)
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return t
    return None


def snap(candidates, spec, accept=0.34, margin=0.25):
    """candidates : [(texte, confiance 0..1), …] du moteur (meilleur d'abord).

    Retourne {value, status ('ok'|'review'), confidence, suggestions, raw}.
    """
    kind = spec.get("kind", "text")
    values = spec.get("values", [])
    raw = candidates[0][0] if candidates else ""
    if not candidates or not raw.strip():
        return {"value": None, "status": "review", "reason": "illisible", "suggestions": [], "raw": raw}

    scored = {}  # valeur canonique -> (distance relative, confiance moteur)
    for text, conf in candidates:
        for v in values:
            d = rel(normalize(text, kind), normalize(v, kind))
            if v not in scored or d < scored[v][0]:
                scored[v] = (d, conf)
        if kind == "number":
            num = parse_number(text)
            if num is not None:
                d = 0.0 if num == normalize(text, kind) else 0.1  # corrigé (o->0 …) : petite pénalité
                if num not in scored or d < scored[num][0]:
                    scored[num] = (d, conf)
    ranked = sorted(scored.items(), key=lambda kv: (kv[1][0], -kv[1][1]))
    sugg = [v for v, _ in ranked[:3]]

    if kind == "text":
        best_v = ranked[0][0] if ranked and ranked[0][1][0] < 0.15 else raw
        return {"value": best_v, "status": "review", "reason": "texte libre : validation humaine",
                "suggestions": sugg or [raw], "raw": raw, "confidence": candidates[0][1]}
    if not ranked:
        return {"value": None, "status": "review", "reason": "hors vocabulaire", "suggestions": [raw], "raw": raw}
    best, (d1, conf) = ranked[0]
    d2 = ranked[1][1][0] if len(ranked) > 1 else 1.0
    ok = d1 <= accept and (d2 - d1) >= margin
    # un nombre libre n'a pas de vocabulaire pour le rattraper : un 14 lu 44 est un nombre
    # valide. Mesuré sur le lot EN (TrOCR base) : les nombres mal lus ont la même confiance que
    # les bons (0,90 à 0,99), aucun seuil ne les sépare. Par défaut il part donc toujours en revue,
    # sa lecture en proposition ; `min_conf` dans le vocabulaire du champ rétablit l'acceptation
    # pour un moteur dont la confiance a été mesurée fiable.
    free = kind == "number" and best not in values
    if ok and free:
        min_conf = spec.get("min_conf")
        ok = min_conf is not None and conf >= min_conf
    return {"value": best, "status": "ok" if ok else "review",
            "reason": None if ok else ("hors vocabulaire" if d1 > accept else
                                       "nombre libre : lecture à confirmer" if free
                                       else "hésitation entre propositions"),
            "distance": round(d1, 3), "second": round(d2, 3), "confidence": round(conf, 3),
            "suggestions": sugg, "raw": raw}
