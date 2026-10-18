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

Normalisation : casse, espaces, guillemets, point final parasite, et formes équivalentes
(« <class 'int'> » -> « int »). Distance : Levenshtein où les confusions
classiques de l'écriture manuscrite coûtent moins cher (0/O, 1/l/I, 5/S…).

Décision : accepté si la meilleure distance relative est faible ET nettement
inférieure à la deuxième, ET si la lecture principale du moteur ressemble au mot
retenu ; sinon « review » avec les meilleures propositions.
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
        # point final parasite : les moteurs entraînés sur des phrases terminent presque toujours
        # par « . » (« int . », « 15 . ») ; aucune réponse courte attendue ne finit par un point
        s = re.sub(r"[\s.]+$", "", s)
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


NUM_FIX = str.maketrans({"o": "0", "O": "0", "l": "1", "I": "1", "|": "1", "S": "5", "s": "5",
                         "B": "8", "Z": "2", "z": "2", "—": "-", "–": "-", "_": "-"})


def parse_number(s: str):
    """Nombre tel qu'écrit, séparateur décimal compris : « 2,5 » reste « 2,5 » et n'est PAS « 2.5 »
    (écrire une virgule est une faute courante en Python, que l'enseignant veut voir)."""
    t = normalize(s, "number").translate(NUM_FIX)
    if re.fullmatch(r"-?\d+([.,]\d+)?", t):
        return t
    return None


def other_separator(number: str):
    """« 2.5 » -> « 2,5 » et inversement ; None pour un entier."""
    if "." in number:
        return number.replace(".", ",")
    if "," in number:
        return number.replace(",", ".")
    return None


DECIMAL_COMMA = "nombre décimal : virgule détectée, à vérifier"
DECIMAL_POINT = "nombre décimal : point ou virgule à vérifier"
DECIMAL_UNSURE = "nombre décimal : séparateur incertain, point proposé (virgule à vérifier)"


def favor_point(number: str):
    """Séparateur incertain : le doute profite à l'étudiant (décision de l'enseignant), on propose le
    point. Compter à tort une virgule serait une erreur au détriment de l'étudiant. Une virgule
    détectée (les deux lectures concordent) est en revanche conservée."""
    return number.replace(",", ".")


def _both_separators(sugg, number):
    """Propositions d'un nombre décimal : l'écriture retenue, l'autre séparateur, puis le reste."""
    return ([number, other_separator(number)] + [s for s in sugg if favor_point(s) != favor_point(number)])[:3]


SECONDARY = "mot reconnu par une lecture secondaire, lecture principale différente : à confirmer"


def snap(candidates, spec, accept=0.34, margin=0.30, far=0.65, lead=0.65, weak=0.05, exact_margin=0.15):
    """candidates : [(texte, confiance 0..1), …] du moteur (meilleur d'abord).

    Retourne {value, status ('ok'|'review'), confidence, suggestions, raw}.
    """
    kind = spec.get("kind", "text")
    values = spec.get("values", [])
    raw = candidates[0][0] if candidates else ""
    if not candidates or not raw.strip():
        return {"value": None, "status": "review", "reason": "illisible", "suggestions": [], "raw": raw}

    # lectures secondaires presque nulles ignorées : `float` à 1,00 avec une variante `bool` à 0,014 était une
    # « hésitation ». Mesuré sur EN, supA 1, supA 2, supB 1 : quelques acceptées de plus, aucune fausse.
    candidates = candidates[:1] + [c for c in candidates[1:] if c[1] >= weak]
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
    # marge 0,30 (0,25 jusqu'au 8 octobre) : sur supA 2, lot jamais vu, deux `bool` et un `int` mal lus
    # (« troot », « is it ») étaient acceptés `float` et `list`. Mesuré sur EN, supA 1, supA 2 avec la règle
    # de la lecture secondaire ci-dessous : 346 acceptées dont 342 justes -> 298 dont 298. Réglé sur ces
    # trois lots : à confirmer sur un lot validé de plus.
    ok = d1 <= accept and (d2 - d1) >= margin
    # la lecture principale EST un mot du vocabulaire : un mot voisin (`print` / `printf`, une lettre d'écart)
    # ne suffit plus à créer une hésitation ; il faut qu'une autre lecture soit aussi proche ou presque.
    # Choix de l'enseignant (17 octobre) ; risque connu : `printf` lu sans son « f » serait accepté `print`.
    if not ok and kind == "enum" and d1 == 0 and normalize(raw, kind) == normalize(best, kind):
        ok = d2 >= exact_margin
    # un nombre libre n'a pas de vocabulaire pour le rattraper : un 14 lu 44 est un nombre
    # valide. Mesuré sur le lot EN (TrOCR base) : les nombres mal lus ont la même confiance que
    # les bons (0,90 à 0,99), aucun seuil ne les sépare. Par défaut il part donc toujours en revue,
    # sa lecture en proposition ; `min_conf` dans le vocabulaire du champ rétablit l'acceptation
    # pour un moteur dont la confiance a été mesurée fiable.
    free = kind == "number" and best not in values
    if ok and free:
        min_conf = spec.get("min_conf")
        ok = min_conf is not None and conf >= min_conf
    # point ou virgule : les moteurs ne les distinguent pas de façon fiable (lot EN : formes qui se
    # recouvrent à 100 dpi). Un nombre décimal part donc toujours en revue, avec les deux écritures.
    decimal = kind == "number" and parse_number(best) is not None and other_separator(best) is not None
    if decimal:
        ok = False
        sugg = _both_separators(sugg, best)
    # lecture très loin de tout le vocabulaire : le mot « le plus proche » n'a plus de sens (« input »
    # lu « im-ment » était proposé « lire », pris pour une traduction). Mesuré sur EN + supA 1 : au-delà
    # de 0,65 la proposition est juste 12 fois sur 48 (30 sur 52 entre 0,55 et 0,65) ; seuil choisi par
    # l'enseignant. On montre la lecture brute, visiblement fausse, plutôt qu'un mot plausible ; les
    # mots proches restent en suggestions.
    if kind == "enum" and d1 > far:
        return {"value": raw, "status": "review", "reason": "hors vocabulaire : aucun mot proche, lecture brute",
                "distance": round(d1, 3), "second": round(d2, 3), "confidence": round(conf, 3),
                "suggestions": sugg, "raw": raw}
    # mot reconnu par une lecture secondaire alors que la lecture principale en est très loin : le moteur
    # a « trouvé » un mot du vocabulaire dans une de ses variantes (`int` lu « what », 3ᵉ lecture « List »
    # -> `list` ; `Grand` lu « bool », 2ᵉ lecture « Error » -> `ERREUR`). On n'accepte que si la lecture
    # principale ressemble elle aussi au mot retenu (distance <= `lead`). Seuil 0,65 confirmé par
    # l'enseignant : à 0,70 un `bool` lu « inward », 3ᵉ lecture « inh. », restait accepté `int` (supA 2) ;
    # le prix est de 6 bonnes réponses d'EN en revue (`str` lu « ska », « rtd » : 0,67).
    weak = ok and best in values and rel(normalize(raw, kind), normalize(best, kind)) > lead
    if weak:
        ok = False
    return {"value": best, "status": "ok" if ok else "review",
            "reason": None if ok else (SECONDARY if weak else
                                       "hors vocabulaire" if d1 > accept else
                                       (DECIMAL_COMMA if "," in best else DECIMAL_POINT) if decimal else
                                       "nombre libre : lecture à confirmer" if free
                                       else "hésitation entre propositions"),
            "distance": round(d1, 3), "second": round(d2, 3), "confidence": round(conf, 3),
            "suggestions": sugg, "raw": raw}


SURE_DIGITS = 0.99
NUMBER_ACCEPT_CONF = 0.99
NUMBER_SURE = "nombre : les deux lectures concordent, très sûr, à confirmer"


def propose_digits(r, spec, number, conf, accept=0.34, accept_numbers=False):
    """Ajoute à un résultat de `snap` (champ `number`) la lecture du lecteur de chiffres.

    Elle devient la proposition d'un champ en revue, sauf si le moteur de texte a reconnu un mot du
    vocabulaire (« ERROR »). `agree` signale que les deux lectures donnent le même nombre. Elle ne change
    le statut que si `accept_numbers` (moteur de texte affiné, cf. NUMBER_ACCEPT_CONF).
    """
    r["digits"] = {"value": number, "confidence": round(conf, 3)}
    # le moteur de texte penche pour un mot (« ERROR ») : on le garde s'il est accepté, ou s'il est
    # assez proche alors que les « chiffres » sont peu sûrs (des lettres découpées en chiffres).
    # Mesuré sur le lot EN : mots lus avec une confiance chiffres <= 0,57, distance <= 0,60.
    d = r.get("distance", 1.0)
    word = r.get("value") in spec.get("values", []) and (d <= accept or (d <= 0.6 and conf < 0.6))
    if r["status"] == "ok" or word:
        if number not in r["suggestions"]:
            r["suggestions"] = r["suggestions"][:2] + [number]
        return r
    text = parse_number(r["value"]) if r.get("value") is not None else None
    r["digits"]["agree"] = text is not None and favor_point(text) == favor_point(number)
    decimal = other_separator(number) is not None
    # virgule « détectée » seulement si les DEUX lectures la voient (lot EN : 4 vraies virgules sur 5 ;
    # une seule lecture : 6 sur 8 pour le texte, 10 sur 14 pour la forme). Sinon le doute profite à
    # l'étudiant : point proposé, virgule en second choix.
    comma = decimal and "," in number and text is not None and "," in text
    if decimal and not comma:
        number = favor_point(number)
    r["value"] = number
    r["suggestions"] = [number] + [s for s in r["suggestions"] if s != number][:2]
    if decimal:
        r["suggestions"] = _both_separators(r["suggestions"], number)
    # « très sûr » : entier, deux lectures d'accord, confiance des chiffres >= 0,99. Mesuré le 5 octobre :
    # 18/18 justes sur EN, 7/7 sur supA 1 (à 0,95 il restait un « 3.14 » lu « 314 »). Trop peu de cas
    # pour accepter seul : la réponse reste en revue, seulement signalée (validation groupée).
    r["sure"] = bool(not decimal and r["digits"]["agree"] and conf >= SURE_DIGITS)
    # acceptation d'un entier d'au moins 2 chiffres quand les deux lectures concordent et que le moteur de
    # texte (TrOCR affiné) est sûr. Mesuré le 17 octobre avec `trocr_commun` sur deux lots jamais vus :
    # 89 justes sur 89 (supA 2 : 33, supB 1 : 56). Un chiffre seul reste en revue : 2 fautes sur 85
    # (`3` lu `5`, `2` bouclé lu `9`, les deux lectures d'accord à 1,00). Avec TrOCR d'origine, `3` lu `43`.
    # 18 octobre, supB 3 jamais vu : `trocr_commun` 58 justes sur 59 (`42` lu `49`), `trocr_v2` 50 sur 50.
    if (accept_numbers and not decimal and r["digits"]["agree"] and r.get("confidence", 0) >= NUMBER_ACCEPT_CONF
            and len(str(number).lstrip("-")) >= 2):
        r.update(status="ok", reason=None)
        return r
    r["reason"] = ((DECIMAL_COMMA if comma else DECIMAL_UNSURE) if decimal else
                   NUMBER_SURE if r["sure"] else
                   "nombre : les deux lectures concordent, à confirmer" if r["digits"]["agree"]
                   else "nombre : lecture à confirmer")
    return r
