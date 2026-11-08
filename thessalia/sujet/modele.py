"""Contrôle strict d'un sujet et modèle prêt à mettre en page / à corriger (docs/FORMAT_SUJET.md).

`examen(chemin)` renvoie le modèle, ou lève `ErreurSujet` avec TOUTES les erreurs trouvées (ligne + correction).
Rien n'est deviné : une clé inconnue, une langue manquante, des points qui ne tombent pas juste, une réponse lue
comme une liste… refusent le fichier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .source import ErreurSujet, Liste, Table, Texte, charger, charger_texte

FORMAT = "thessalia-sujet/1"
TYPES = ("qcm", "vrai_faux", "blancs", "code", "redaction", "texte", "brut")
NATURES = {"texte": "text", "nombre": "number", "mot": "enum"}
TAILLES = ("court", "moyen", "long")
TOLERANCES = ("guillemets", "guillemets_forme", "espaces_virgules", "espace_ponctuation", "liste_incomplete")
VF = {"fr": ("V", "F"), "en": ("T", "F")}          # libellés des cases Vrai / Faux par langue
RE_BLANC = re.compile(r"\[\[([A-Za-z_]\w*)(?::(\w+))?\]\]")

CLES_EXAMEN = {"id", "langues", "matiere", "titre", "sous_titre", "duree", "version", "session", "points",
               "identite", "numero_etudiant", "consignes", "logo"}
CLES_EXERCICE = {"titre", "points", "contexte", "questions"}
CLES_QUESTION = {"num", "type", "points", "enonce", "explication", "note"}
CLES_TYPE = {"qcm": {"choix", "bonne", "plusieurs"}, "vrai_faux": {"affirmations"},
             "blancs": {"lignes", "code", "blancs"},
             "code": {"cadre", "corrige", "criteres", "avant", "interdit", "tests_python"},
             "redaction": {"lignes", "criteres"}, "texte": {"contenu"}, "brut": {"contenu"}}
CLES_BLANC = {"attendu", "nature", "points", "accepte", "forme", "partiel", "plausibles", "tolerances", "explication"}
CLES_CRITERE = {"texte", "points", "essais", "contient", "verifie"}


@dataclass
class Blanc:
    nom: str
    id: str
    taille: str
    attendu: dict                     # {langue: texte}
    nature: str = "texte"
    points: float | None = None       # None : partage égal
    accepte: dict = field(default_factory=dict)       # {langue: [textes]}
    forme: dict = field(default_factory=dict)
    partiel: dict = field(default_factory=dict)       # {langue: {texte: points}}
    plausibles: dict = field(default_factory=dict)
    tolerances: list = field(default_factory=list)    # noms, ou ("liste_incomplete", {manque_max, points})
    explication: dict | None = None


@dataclass
class Question:
    num: int
    type: str
    points: float
    enonce: dict | None
    ligne: int
    donnees: dict = field(default_factory=dict)       # selon le type (choix, bonne, blancs, criteres…)


@dataclass
class Exercice:
    titre: dict
    points: float | None
    contexte: dict | None
    questions: list


@dataclass
class Examen:
    id: str
    langues: list
    entete: dict
    exercices: list
    points: float

    def questions(self):
        return [q for e in self.exercices for q in e.questions]


def examen(chemin) -> Examen:
    return _Controle(charger(chemin)).examen()


def examen_texte(texte: str) -> Examen:
    return _Controle(charger_texte(texte)).examen()


def _pts(x) -> float:
    return round(float(x), 6)


class _Controle:
    def __init__(self, racine: Table):
        self.r, self.err = racine, []

    # ---------------------------------------------------------------- outils
    def e(self, obj, msg):
        self.err.append(f"ligne {getattr(obj, 'ligne', '?')} : {msg}")

    def cles(self, t, permises, ou, obligatoires=()):
        if not isinstance(t, Table):
            self.e(t, f"{ou} : il faut des clés (« nom: valeur »)")
            return False
        for k in t:
            if k not in permises:
                proche = [p for p in permises if _proche(k, p)]
                self.err.append(f"ligne {t.lignes[k]} : {ou} : clé inconnue « {k} »"
                                + (f" (vouliez-vous « {proche[0]} » ?)" if proche else "")
                                + f" ; clés possibles : {', '.join(sorted(permises))}")
        for k in obligatoires:
            if k not in t:
                self.e(t, f"{ou} : « {k} » manquant")
        return True

    def texte(self, v, ou, obligatoire=True):
        """Texte visible : {langue: texte}. Une valeur seule vaut pour toutes les langues."""
        if v is None:
            if obligatoire:
                self.e(self.r, f"{ou} : texte manquant")
            return None
        if isinstance(v, Texte):
            self.coupe(v, ou)
            return {l: str(v) for l in self.langues}
        if isinstance(v, Table) and set(v) <= set(self.langues):
            manque = [l for l in self.langues if l not in v]
            if manque:
                self.e(v, f"{ou} : texte manquant en {', '.join(manque)}")
            out = {}
            for l, t in v.items():
                if not isinstance(t, Texte):
                    self.e(t, f"{ou} ({l}) : un texte est attendu")
                else:
                    self.coupe(t, f"{ou} ({l})")
                    out[l] = str(t)
            return out
        self.e(v, f"{ou} : un texte est attendu, ou un texte par langue ({', '.join(self.langues)})")
        return None

    def coupe(self, t, ou):
        if t.commentaire:
            self.e(t, f"{ou} : le texte s'arrête avant « {t.commentaire[:30]} » (YAML prend « # » pour un "
                      f"commentaire) ; mettez tout le texte entre guillemets")

    def reponse(self, v, ou):
        """Réponse (texte exact) : refuse ce que YAML lirait comme liste ou structure, en proposant la correction."""
        if isinstance(v, (Liste, Table)) and not (isinstance(v, Table) and v and set(v) <= set(self.langues)):
            nature = "une liste" if isinstance(v, Liste) else "une structure (accolades)"
            src = v.source.strip().replace("'", "''")
            self.e(v, f"{ou} est lue comme {nature} ; écrivez-la entre guillemets simples : '{src}'")
            return None
        t = self.texte(v, ou)
        if t:
            for l, s in t.items():
                if "\n" in s:
                    self.e(v, f"{ou} : contient un vrai retour à la ligne ; pour le texte \\n, écrivez la réponse "
                              f"entre guillemets simples")
        return t

    def reponses(self, v, ou):
        """Liste de réponses, éventuellement par langue : {langue: [textes]}."""
        if v is None:
            return {}
        if isinstance(v, Table) and set(v) <= set(self.langues):
            out = {}
            for l in self.langues:
                out[l] = self.reponses(v.get(l, Liste()), f"{ou} ({l})").get(l, []) if l in v else []
            return out
        if not isinstance(v, Liste):
            self.e(v, f"{ou} : une liste est attendue, entre crochets : [réponse 1, réponse 2]")
            return {}
        rep = [self.reponse(x, f"{ou}, élément {i + 1}") for i, x in enumerate(v)]
        return {l: [r[l] for r in rep if r] for l in self.langues}

    def nombre(self, v, ou, obligatoire=True):
        if v is None:
            if obligatoire:
                self.e(self.r, f"{ou} : nombre manquant")
            return None
        if isinstance(v, Texte):
            try:
                return _pts(str(v).replace(",", "."))
            except ValueError:
                pass
        self.e(v, f"{ou} : un nombre est attendu (ex. 0.25 ou 0,25), pas « {getattr(v, 'source', v)} »")
        return None

    def egal(self, obj, total, attendu, ou):
        if total is not None and attendu is not None and abs(total - attendu) > 1e-6:
            self.e(obj, f"{ou} : les points ne tombent pas juste ({_f(total)} au lieu de {_f(attendu)})")

    # ---------------------------------------------------------------- examen
    def examen(self) -> Examen:
        r = self.r
        self.cles(r, {"format", "examen", "exercices"}, "fichier", ("format", "examen", "exercices"))
        if r.get("format") != FORMAT:
            self.e(r.get("format", r), f"format : « {FORMAT} » attendu")
        ex = r.get("examen", Table())
        self.cles(ex, CLES_EXAMEN, "examen", ("id", "langues", "titre", "points"))
        lg = ex.get("langues")
        self.langues = [str(x) for x in lg] if isinstance(lg, Liste) and lg else ["fr"]
        if not (isinstance(lg, Liste) and lg):
            self.e(ex, "examen.langues : liste des langues attendue, ex. [fr, en]")
        entete = {k: self.texte(ex.get(k), f"examen.{k}", obligatoire=k == "titre")
                  for k in ("matiere", "titre", "sous_titre", "version", "session", "consignes")}
        entete["duree"] = str(ex.get("duree", ""))
        entete["logo"] = str(ex["logo"]) if "logo" in ex else None
        entete["identite"] = [str(x) for x in ex.get("identite", [])]
        ne = ex.get("numero_etudiant")
        if ne is not None:
            self.cles(ne, {"chiffres", "exemple", "ignorer_prefixe"}, "examen.numero_etudiant", ("chiffres",))
            entete["numero_etudiant"] = {"chiffres": int(self.nombre(ne.get("chiffres"), "chiffres") or 0),
                                         "exemple": str(ne.get("exemple", "")),
                                         "ignorer_prefixe": str(ne.get("ignorer_prefixe", "false")) == "true"}
        points = self.nombre(ex.get("points"), "examen.points")

        exercices, num = [], 0
        lst = r.get("exercices")
        if not isinstance(lst, Liste) or not lst:
            self.e(lst if lst is not None else r, "exercices : liste d'exercices attendue")
            lst = Liste()
        for i, e in enumerate(lst, 1):
            if not self.cles(e, CLES_EXERCICE, f"exercice {i}", ("titre", "questions")):
                continue
            qs = []
            for q in e.get("questions", Liste()):
                if isinstance(q, Table) and q.get("type") in ("texte", "brut"):
                    qs.append(self.question(q, None))
                    continue
                num += 1
                qs.append(self.question(q, num))
            pe = self.nombre(e.get("points"), f"exercice {i}, points", obligatoire=False)
            self.egal(e, _pts(sum(q.points for q in qs if q)), pe, f"exercice {i}")
            exercices.append(Exercice(self.texte(e.get("titre"), f"exercice {i}, titre"), pe,
                                      self.texte(e.get("contexte"), f"exercice {i}, contexte", False),
                                      [q for q in qs if q]))
        total = _pts(sum(q.points for x in exercices for q in x.questions))
        self.egal(ex, total, points, "examen")
        if self.err:
            raise ErreurSujet(self.err)
        return Examen(str(ex["id"]), self.langues, entete, exercices, points)

    # ---------------------------------------------------------------- questions
    def question(self, q, num):
        ou = f"question {num}" if num else "texte"
        if not isinstance(q, Table):
            self.e(q, f"{ou} : il faut des clés (type:, points:, enonce:…)")
            return None
        t = str(q.get("type", ""))
        if t not in TYPES:
            self.e(q.get("type", q), f"{ou} : type « {t} » inconnu ; types possibles : {', '.join(TYPES)}")
            return None
        self.cles(q, CLES_QUESTION | CLES_TYPE[t], ou, ("type",) if t in ("texte", "brut") else ("type", "points", "enonce"))
        if t in ("texte", "brut"):
            if t == "brut" and RE_BLANC.search(str(q.get("contenu", ""))):
                self.e(q, f"{ou} : pas de zone de réponse dans un bloc brut")
            return Question(0, t, 0.0, None, q.ligne, {"contenu": self.texte(q.get("contenu"), ou)})
        if "num" in q and str(q["num"]) != str(num):
            self.e(q["num"], f"{ou} : écrit num: {q['num']}, mais c'est la question {num} dans l'ordre du fichier")
        pts = self.nombre(q.get("points"), f"{ou}, points") or 0.0
        out = Question(num, t, pts, self.texte(q.get("enonce"), f"{ou}, énoncé"), q.ligne,
                       {"explication": self.texte(q.get("explication"), ou, False),
                        "note": self.texte(q.get("note"), ou, False)})
        getattr(self, "q_" + t)(q, out, ou)
        return out

    def q_qcm(self, q, out, ou):
        choix = q.get("choix")
        if not isinstance(choix, Liste) or len(choix) < 2:
            self.e(q, f"{ou} : « choix » : au moins deux choix, en liste")
            return
        out.donnees["choix"] = [self.texte(c, f"{ou}, choix {i + 1}") for i, c in enumerate(choix)]
        lettres = "abcdefghij"[:len(choix)]
        b = q.get("bonne")
        bonnes = [str(x) for x in b] if isinstance(b, Liste) else [str(b)] if b is not None else []
        plusieurs = str(q.get("plusieurs", "false")) == "true"
        for x in bonnes:
            if x not in lettres:
                self.e(b, f"{ou} : bonne réponse « {x} » : une lettre de a à {lettres[-1]} attendue")
        if not bonnes or (not plusieurs and len(bonnes) != 1):
            self.e(b if b is not None else q, f"{ou} : choix unique : exactement une bonne réponse "
                                              f"(sinon écrivez plusieurs: true)")
        out.donnees.update(bonnes=bonnes, plusieurs=plusieurs, id=f"q{out.num}")

    def q_vrai_faux(self, q, out, ou):
        aff = q.get("affirmations")
        if not isinstance(aff, Liste) or not aff:
            self.e(q, f"{ou} : « affirmations » : liste attendue")
            return
        items, pts = [], []
        for i, a in enumerate(aff, 1):
            self.cles(a, {"texte", "reponse", "points", "explication"}, f"{ou}, affirmation {i}", ("texte", "reponse"))
            rep = str(a.get("reponse", "")).upper()
            if rep not in ("V", "F"):
                self.e(a.get("reponse", a), f"{ou}, affirmation {i} : reponse V ou F")
            items.append({"id": f"q{out.num}.{i}", "texte": self.texte(a.get("texte"), f"{ou}, affirmation {i}"),
                          "vrai": rep == "V", "explication": self.texte(a.get("explication"), ou, False),
                          "points": self.nombre(a.get("points"), "points", False)})
        donnes = [x["points"] for x in items if x["points"] is not None]
        if donnes:
            if len(donnes) != len(items):
                self.e(q, f"{ou} : points donnés pour certaines affirmations seulement")
            self.egal(q, _pts(sum(donnes)), out.points, ou)
        out.donnees["affirmations"] = items

    def q_blancs(self, q, out, ou):
        # ordre des blancs, identique dans chaque langue : énoncé, code, puis lignes
        morceaux = [out.enonce or {}, self.texte(q.get("code"), ou, False) or {}]
        lignes = q.get("lignes")
        if lignes is not None and not isinstance(lignes, Liste):
            self.e(lignes, f"{ou} : « lignes » : liste attendue")
            lignes = Liste()
        lignes = [self.texte(x, f"{ou}, ligne {i + 1}") or {} for i, x in enumerate(lignes or [])]
        out.donnees.update(code=morceaux[1] or None, lignes=lignes)
        ordre = {}
        for l in self.langues:
            ordre[l] = [(m.group(1), m.group(2) or "moyen") for t in morceaux + lignes for m in RE_BLANC.finditer(t.get(l, ""))]
        ref = ordre[self.langues[0]]
        for l in self.langues[1:]:
            if [n for n, _ in ordre[l]] != [n for n, _ in ref]:
                self.e(q, f"{ou} : les blancs ne sont pas les mêmes, ou pas dans le même ordre, en {self.langues[0]} "
                          f"({', '.join(n for n, _ in ref)}) et en {l} ({', '.join(n for n, _ in ordre[l])})")
        noms = [n for n, _ in ref]
        for n in {n for n in noms if noms.count(n) > 1}:
            self.e(q, f"{ou} : le blanc [[{n}]] est placé deux fois")
        for n, tl in ref:
            if tl not in TAILLES:
                self.e(q, f"{ou} : taille « {tl} » du blanc [[{n}]] : {', '.join(TAILLES)}")
        defs = q.get("blancs", Table())
        if not isinstance(defs, Table):
            self.e(defs, f"{ou} : « blancs » : un blanc par nom attendu")
            return
        for n in defs:
            if n not in noms:
                self.err.append(f"ligne {defs.lignes[n]} : {ou} : le blanc « {n} » est défini mais jamais placé "
                                f"dans le texte ([[{n}]])")
        if not noms:
            self.e(q, f"{ou} : aucun blanc [[nom]] dans l'énoncé, le code ou les lignes")
        blancs = []
        for k, (n, tl) in enumerate(ref, 1):
            if n not in defs:
                self.e(q, f"{ou} : le blanc [[{n}]] est placé mais pas défini sous « blancs »")
                continue
            bid = f"q{out.num}" if len(ref) == 1 else f"q{out.num}.{k}"
            blancs.append(self.blanc(defs[n], n, bid, tl, f"{ou}, blanc {n}"))
        donnes = [b.points for b in blancs if b and b.points is not None]
        if donnes:
            if len(donnes) != len(blancs):
                self.e(q, f"{ou} : points donnés pour certains blancs seulement ; donnez-les tous, ou aucun "
                          f"(partage égal)")
            self.egal(q, _pts(sum(donnes)), out.points, ou)
        out.donnees["blancs"] = [b for b in blancs if b]

    def blanc(self, d, nom, bid, taille, ou):
        if not self.cles(d, CLES_BLANC, ou, ("attendu",)):
            return None
        nature = str(d.get("nature", "texte"))
        if nature not in NATURES:
            self.e(d["nature"], f"{ou} : nature « {nature} » : {', '.join(NATURES)}")
        tol = []
        tv = d.get("tolerances", Liste())
        for x in tv if isinstance(tv, Liste) else [tv]:
            if isinstance(x, Texte) and str(x) in TOLERANCES and str(x) != "liste_incomplete":
                tol.append(str(x))
            elif isinstance(x, Table) and list(x) == ["liste_incomplete"]:
                li = x["liste_incomplete"]
                self.cles(li, {"manque_max", "points"}, f"{ou}, liste_incomplete", ("manque_max", "points"))
                tol.append(("liste_incomplete", {"manque_max": int(self.nombre(li.get("manque_max"), "manque_max") or 0),
                                                 "points": self.nombre(li.get("points"), "points")}))
            else:
                self.e(x, f"{ou} : tolérance inconnue « {getattr(x, 'source', '') or x} » ; possibles : "
                          f"{', '.join(TOLERANCES)}")
        partiel = {}
        p = d.get("partiel")
        if p is not None:
            par_langue = isinstance(p, Table) and set(p) <= set(self.langues) and all(isinstance(v, Table) for v in p.values())
            for l in self.langues:
                tab = p.get(l) if par_langue else p
                if not isinstance(tab, Table):
                    self.e(p, f"{ou} : « partiel » : {{réponse: points}} attendu" + (f" ({l})" if par_langue else ""))
                    continue
                partiel[l] = {str(k): self.nombre(v, f"{ou}, partiel « {k} »") for k, v in tab.items()}
        return Blanc(nom, bid, taille, self.reponse(d.get("attendu"), f"{ou} : la réponse attendue") or {},
                     nature, self.nombre(d.get("points"), f"{ou}, points", False),
                     self.reponses(d.get("accepte"), f"{ou}, accepte"), self.reponses(d.get("forme"), f"{ou}, forme"),
                     partiel, self.reponses(d.get("plausibles"), f"{ou}, plausibles"), tol,
                     self.texte(d.get("explication"), ou, False))

    def criteres(self, q, out, ou, obligatoires=True):
        cr = q.get("criteres")
        if cr is None and not obligatoires:
            return []
        if not isinstance(cr, Liste) or not cr:
            self.e(q, f"{ou} : « criteres » : liste des critères du barème attendue")
            return []
        res = []
        for i, c in enumerate(cr, 1):
            self.cles(c, CLES_CRITERE, f"{ou}, critère {i}", ("texte", "points"))
            res.append({"id": str(i), "texte": self.texte(c.get("texte"), f"{ou}, critère {i}"),
                        "points": self.nombre(c.get("points"), f"{ou}, critère {i}, points") or 0.0,
                        **{k: c[k] for k in ("essais", "contient", "verifie") if k in c}})
        self.egal(q, _pts(sum(c["points"] for c in res)), out.points, ou)
        return res

    def q_code(self, q, out, ou):
        cadre = q.get("cadre", Table())
        self.cles(cadre, {"lignes"}, f"{ou}, cadre", ("lignes",))
        out.donnees.update(id=f"q{out.num}", lignes=int(self.nombre(cadre.get("lignes"), "lignes") or 3),
                           corrige=self.texte(q.get("corrige"), f"{ou}, corrigé"),
                           criteres=self.criteres(q, out, ou), tests_python=q.get("tests_python") and str(q["tests_python"]))
        for k in ("avant", "interdit"):
            if k in q:
                self.e(q[k], f"{ou} : « {k} » n'est pas encore pris en charge par la correction ; utilisez "
                             f"tests_python pour l'instant")

    def q_redaction(self, q, out, ou):
        out.donnees.update(id=f"q{out.num}", lignes=int(self.nombre(q.get("lignes"), f"{ou}, lignes") or 4),
                           criteres=self.criteres(q, out, ou, obligatoires=False))


def _proche(a, b):
    """Faute de frappe probable (une lettre en plus, en moins ou changée)."""
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[i + 1:] == b[i + 1:] or a[i:] == b[i + 1:] or a[i + 1:] == b[i:]


def _f(x):
    return f"{x:g}".replace(".", ",")
