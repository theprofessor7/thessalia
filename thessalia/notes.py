"""Jugement d'une réponse courte face au corrigé : la règle de notation de l'enseignant (outil de correction).

Règle globale de l'enseignant (18 octobre 2026), comparaison au corrigé (`short_answers`) :
  juste        identique (espaces en trop aux bords, guillemets typographiques ignorés ; « _ » = espace en q7),
               ou équivalence décidée par l'enseignant (Error = ERREUR toute casse, Zero = Zéro) : 100 %
  forme        écart de forme seulement : casse (`grand`), parenthèses (`print()`), guillemets (`"427"`),
               espaces : 50 %. Pas en q7 (texte) : on y demande l'affichage exact, l'espace compte (`X Y`
               pour `XY` = `end=""` non compris), donc tout écart y est faux
  calcul       champ numérique : un calcul qui se termine par la bonne valeur (`2^10 = 1024`) est jugé
               sur cette valeur finale (juste ; « mathématiquement juste », enseignant, 19 octobre)
  faux         tout le reste, dont « 2,5 » pour « 2.5 » (virgule décimale) : 0
  vide         zone vide : 0
  en attente   pas encore validée : pas de points, la note est marquée incomplète
Exceptions possibles dans le corrigé, par champ : `short_accept` (juste), `short_reject` (faux), `short_forme`
(écart de forme, ex. guillemets autour de ce qu'affiche un print), `short_partiel` ({réponse: points}, ex. Midterm
q9 `{prix}` seul = 0,25 sur 0,75 : statut « partiel », points tirés du corrigé).

Points d'une question répartis également entre ses blancs (q2 = 0,75 pt -> 6 x 0,125), comme pour les QCM,
sauf répartition fixée par le corrigé (`points_champs`, Midterm q5 et q9).
"""
from __future__ import annotations

import re
import unicodedata

from .vocab import normalize

# décision de l'enseignant (14 octobre 2026) : langue d'examen, pas une faute ; toute casse
EQUIV_GROUPS = [{"erreur", "error"}]
# dans un seul sens (réponse, corrigé) : `Zero` reste juste pour `Zéro` (copie FR, décision du 14 octobre) ;
# sur copie EN, q14 demande ce que le programme affiche (`print("Zero")`) : `Zéro` est faux (21 octobre)
EQUIV_ONE_WAY = {("zero", "zéro")}

JUSTE, FORME, FAUX, VIDE, ATTENTE = "juste", "forme", "faux", "vide", "en attente"
PARTIEL = "partiel"  # points partiels prévus par le corrigé pour CETTE réponse (`short_partiel`)
ILLISIBLE = "illisible"  # décision de l'enseignant seulement (rare) : 0 point, distinct dans le suivi
RATE = {JUSTE: 1.0, FORME: 0.5, FAUX: 0.0, VIDE: 0.0, ILLISIBLE: 0.0}  # règle globale de l'enseignant


def clean(s: str, kind: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    if kind == "text":
        s = s.replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def _equiv(a: str, b: str) -> bool:
    a, b = a.casefold(), b.casefold()
    return any(a in g and b in g for g in EQUIV_GROUPS) or (a, b) in EQUIV_ONE_WAY


def judge(answer, expected: str, kind: str, accept=(), reject=(), forme=(), partiel=None) -> str:
    """Statut d'une réponse courte face au corrigé (voir l'en-tête du module)."""
    if answer is None:
        return ATTENTE
    a, e = clean(answer, kind), clean(expected, kind)
    if not a:
        return VIDE
    if a == e or a in {clean(x, kind) for x in accept} or _equiv(a, e):
        return JUSTE
    if a in {clean(x, kind) for x in reject}:
        return FAUX
    if a in {clean(x, kind) for x in forme}:
        return FORME
    if a in {clean(x, kind) for x in (partiel or {})}:
        return PARTIEL
    if kind == "text":
        return FAUX  # q7 : affichage exact demandé, la casse et les espaces font partie de la réponse
    if kind == "number":
        # calcul posé qui aboutit à la bonne valeur (`2^10 = 1024`) : « mathématiquement juste » (décision de
        # l'enseignant, 19 octobre) ; on juge la valeur après le dernier « = » avec les mêmes règles
        m = re.fullmatch(r"(.+)=\s*([^=]+)", a)
        if m and m.group(1).strip():
            fin = judge(m.group(2), expected, kind, accept, reject)
            if fin in (JUSTE, FORME):
                return fin
    # casse, guillemets, parenthèses finales, espaces (normalize ne touche ni aux chiffres ni à la virgule :
    # « 2,5 » reste différent de « 2.5 »)
    if normalize(a, kind) == normalize(e, kind):
        return FORME
    # appel complet au lieu du nom : `print("...")` pour `print` (parenthèses et guillemets = forme)
    call = re.fullmatch(r"\s*(\w+)\s*\(.*\)\s*", a)
    if kind == "enum" and call and call.group(1).casefold() == e.casefold():
        return FORME
    return FAUX


def points_partiels(answer, kind, partiel) -> float:
    """Points prévus par le corrigé pour cette réponse (`short_partiel`), 0 si elle n'y est pas."""
    a = clean(answer or "", kind)
    return next((float(p) for x, p in (partiel or {}).items() if clean(x, kind) == a), 0.0)
