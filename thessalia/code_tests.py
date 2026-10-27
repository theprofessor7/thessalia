"""Pré-cochage du code par EXÉCUTION : `python -m thessalia precocher sorties/<classe> [--reparateur qwen3:14b]`.

Le code transcrit d'un cadre tourne isolé (`python -I`, 5 s au plus, `input()` simulé) avec les saisies des tests
du sujet (`keys/<sujet>.tests.py`, écrits une fois avec le corrigé). Un critère est PRÉ-COCHÉ seulement si ses tests
passent ; un échec ne décide rien (il reste à l'enseignant). Jamais validé seul : l'enseignant confirme (Entrée).

Avant d'exécuter, on répare les fautes que l'enseignant tolère (cf. `_reparer`) : symboles hors Python (`=<`, `≠`),
`=` pour `==`, deux-points ou parenthèses oubliés, mots-clés en majuscule, `²`, `x` pour `*`, virgules oubliées dans
`print`, `12€`, nom de variable écrit de deux façons. Option : un modèle local (Ollama) répare ce que les règles ne
savent pas réparer, sous CONTRÔLE (`garde`) : seules les fautes tolérées ont le droit de changer, sinon la
réparation est refusée et le cadre reste à l'enseignant (le modèle « corrige » parfois la logique malgré la consigne).

Mesuré sur le BIS le 27 octobre (45 cadres testables, 113 critères cochés par l'enseignant) : transcriptions de
session 67 critères retrouvés, 0 à tort ; transcriptions locales (Qwen3-VL 8B) 41, 0 à tort.
Un programme qui ne tourne pas même réparé : signal « infraction lourde ? » (l'enseignant décide le malus).
Résultat rangé dans `<classe>/code_tests.json` (clé cNN_qX.Y), lu par l'outil de correction.
"""
from __future__ import annotations

import ast
import builtins
import difflib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

FICHIER = "code_tests.json"
CACHE_MODELE = Path("data/models/reparations_{modele}.json")   # hors dépôt : contient du code d'étudiants
DELAI = 5                                                        # s par exécution
OLLAMA = "http://localhost:11434/api/chat"

# ------------------------------------------------------------------ exécution isolée
RUNNER = r'''
import builtins, sys, json
saisies = json.loads(sys.argv[2]); n = [0]
def fausse_saisie(invite=""):
    if n[0] >= len(saisies):
        raise EOFError("plus de saisie")
    n[0] += 1
    return saisies[n[0] - 1]
builtins.input = fausse_saisie
try:
    exec(compile(open(sys.argv[1], encoding="utf-8").read(), "copie", "exec"), {"__name__": "__main__"})
    etat = "ok"
except SystemExit:
    etat = "ok"
except BaseException as e:
    etat = type(e).__name__
sys.stdout.flush()
print("\n@@FIN@@" + json.dumps({"etat": etat, "saisies": n[0]}))
'''


def executer(code, saisies):
    """Exécute `code` dans un processus Python isolé ; renvoie {etat, sortie, saisies (nombre lues)}."""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "copie.py"
        f.write_text(code, encoding="utf-8")
        r = Path(tmp) / "runner.py"
        r.write_text(RUNNER, encoding="utf-8")
        try:
            p = subprocess.run([sys.executable, "-I", "-X", "utf8", str(r), str(f), json.dumps(saisies)], cwd=tmp,
                               capture_output=True, text=True, timeout=DELAI, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return {"etat": "trop long", "sortie": "", "saisies": 0}
    out = p.stdout or ""
    if "@@FIN@@" not in out:
        return {"etat": "plantage", "sortie": out, "saisies": 0}
    sortie, fin = out.rsplit("@@FIN@@", 1)
    return {**json.loads(fin), "sortie": sortie}


def compile_ok(code):
    try:
        compile(code, "copie", "exec")
        return True
    except (SyntaxError, ValueError):
        return False


# ------------------------------------------------------------------ outils pour écrire les tests d'un sujet
def sans_accent(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(ch) != "Mn")


def nombres(s):
    return [float(x.replace(",", ".")) for x in re.findall(r"-?\d+(?:[.,]\d+)?", s)]


def contient(r, *vals):
    """L'exécution s'est terminée et sa sortie contient chacune de ces valeurs (à 0,01 près)."""
    ns = nombres(r["sortie"])
    return r["etat"] == "ok" and all(any(abs(n - v) < 0.011 for n in ns) for v in vals)


def dans_ordre(s, *vals):
    ns, i = nombres(s), 0
    for n in ns:
        if i < len(vals) and abs(n - vals[i]) < 0.011:
            i += 1
    return i == len(vals)


# ------------------------------------------------------------------ réparation des fautes tolérées (règles)
X_MULT = re.compile(r"(?<=[\w)])(?<!\bfor)\s+x\s+(?!in\b)(?=[\w(])")
MOTS = ["print", "input", "int", "float", "if", "elif", "else", "while", "for", "in", "range", "and", "or", "not",
        "True", "False", "break", "round"]
ENTETE = r"(if|elif|else|while|for|def)\b"


def reparer(code):
    """Essaie des réparations de plus en plus fortes ; garde la première qui compile (sinon la plus forte)."""
    essais = [_reparer(code, parentheses=False, virgules=False), _reparer(code, parentheses=False, virgules=True),
              _reparer(code, parentheses=True, virgules=True)]
    choisi = next((e for e in essais if compile_ok(e)), essais[-1])
    return _noms(choisi) if compile_ok(choisi) else choisi


def _noms(code):
    """Nom de variable écrit de deux façons (Prenom / prenom, cote1 / côté1) : on aligne sur le nom affecté."""
    arbre = ast.parse(code)
    affectes = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    utilises = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    plat = lambda x: sans_accent(x).replace("_", "")
    for u in sorted(utilises - affectes - set(dir(builtins))):
        proche = [a for a in sorted(affectes) if plat(a) == plat(u)] or difflib.get_close_matches(u, sorted(affectes), 1, 0.8)
        if proche:
            code = re.sub(rf"(?<![\w\"']){re.escape(u)}(?![\w])", proche[0], code)
    return code


def _virgules(s):
    """print("a" x "b") -> print("a", x, "b") : virgule oubliée entre une chaîne et une expression."""
    if "print" not in s:
        return s
    s = re.sub(r'("[^"]*")\s+(?=[\w(])', r"\1, ", s)
    s = re.sub(r'([\w)])\s+(?="[^"]*")', r"\1, ", s)
    return s.replace("print, ", "print ")


def _reparer(code, parentheses=True, virgules=True):
    t = re.sub(r"(\d)\s*€", r"\1", code)
    for a, b in [("“", '"'), ("”", '"'), ("«", '"'), ("»", '"'), ("’", "'"), ("‘", "'"),
                 ("≤", "<="), ("⩽", "<="), ("≥", ">="), ("⩾", ">="), ("≠", "!="), ("=<", "<="), ("=>", ">=")]:
        t = t.replace(a, b)
    lignes = []
    for l in t.splitlines():
        s = l
        for m in MOTS:                                   # Print, If… -> print, if (hors chaînes : approximatif)
            s = re.sub(rf"\b{m.capitalize()}\b", m, s) if m not in ("True", "False") else s
        s = re.sub(r"(\w+|\))\s*²", r"\1**2", s) if '"' not in s and "'" not in s else s
        s = X_MULT.sub(" * ", s) if '"' not in s and "'" not in s else s       # x pour multiplier
        tete = s.strip()
        if re.match(r"(if|elif|while)\b", tete):        # = seul dans une condition -> ==
            s = re.sub(r"(?<![=!<>])=(?!=)", "==", s)
        if re.match(ENTETE, tete) and ":" not in tete:   # deux-points oubliés
            s = s.rstrip() + ":"
        if virgules:
            s = _virgules(s)
        ouv, fer = s.count("("), s.count(")")
        if parentheses and ouv > fer:
            s = s.rstrip(": ") + ")" * (ouv - fer) + (":" if tete.endswith(":") or re.match(ENTETE, tete) else "")
        lignes.append(s)
    return "\n".join(lignes)


# ------------------------------------------------------------------ contrôle d'une réparation par modèle
JETON = re.compile(r"""("[^"\n]*"?|'[^'\n]*'?|[“”«»][^“”«»\n]*[“”«»]?|\d+(?:[.,]\d+)?|\w+|\*\*|==|!=|<=|>=|=<|=>|\S)""")
TOLERES = {"(", ")", ":", ",", ".", "=", "€", ";"}          # oubli ou ajout de ponctuation : toléré
EQUIV = {"=": "==", "=<": "<=", "=>": ">=", "x": "*", "≤": "<=", "≥": ">=", "≠": "!="}


def _jetons(code):
    out = []
    for t in JETON.findall(code):
        if t[0] in "\"'“”«»":                                 # texte : guillemets, accents, casse, espaces tolérés
            out.append('"' + re.sub(r"\s+", "", sans_accent(t.strip("\"'“”«» "))) + '"')
        elif re.fullmatch(r"\w+", t) and not t[0].isdigit():
            out.append(sans_accent(t))                         # casse (If, OR, Else) et accents tolérés
        elif t == "²":
            out += ["**", "2"]
        else:
            out.append(t)
    return out


def garde(avant, apres):
    """None si la réparation ne touche qu'aux fautes tolérées, sinon la première modification interdite (texte).
    Refusé, par exemple : `int(` ajouté, `on` changé en `or`, guillemets enlevés, texte changé en calcul."""
    a, b = _jetons(avant), _jetons(apres)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        va, vb = a[i1:i2], b[j1:j2]
        if all(t in TOLERES for t in va + vb):
            continue
        if op == "replace" and len(va) == len(vb) and all(EQUIV.get(x) == y or (x in TOLERES and y in TOLERES)
                                                          for x, y in zip(va, vb)):
            continue
        sa, sb = [t for t in va if t not in TOLERES], [t for t in vb if t not in TOLERES]
        if op == "replace" and sa and [EQUIV.get(t, t) for t in sa] == sb:
            continue                                            # « =< » + parenthèse en même temps
        if "".join(sa).replace("-", "_") == "".join(sb) or (
                re.fullmatch(r"[=!<>]+", "".join(va)) and sorted("".join(va)) == sorted("".join(vb))):
            continue                                            # « ! = » → « != », « age-n » → « age_n », « =! »
        if len(sa) == 1 == len(sb) and re.fullmatch(r"[a-z_]\w*", sa[0]) and re.fullmatch(r"[a-z_]\w*", sb[0]):
            r = difflib.SequenceMatcher(None, sa[0], sb[0]).ratio()
            if (sb[0] in MOTS and r >= 0.6) or (len(sa[0]) > 2 and sb[0] in a and r >= 0.75):
                continue                                        # mot Python mal écrit (impot, flaat) ou nom existant
        return f"{' '.join(va) or '∅'} → {' '.join(vb) or '∅'}"
    return None


REPARE = """Voici un programme Python écrit à la main par un étudiant, puis transcrit. Il ne s'exécute pas à cause de
fautes de SYNTAXE. Corrige UNIQUEMENT ce qui empêche l'exécution : virgules, parenthèses, guillemets, deux-points,
indentation, mot-clé mal écrit (on -> or), nom de variable écrit de deux façons.
INTERDIT : changer la logique, les calculs, les conditions, les bornes, les opérateurs, l'ordre des instructions ou
les textes affichés ; ajouter ce qui manque au programme. Un `x` utilisé pour multiplier devient `*`. Si le programme ne peut pas devenir exécutable sans changer sa logique, renvoie-le tel quel.
Réponds uniquement avec le code, sans explication.
<<<
{code}
>>>"""


def reparer_modele(code, modele, cache):
    """Réparation par un modèle local (Ollama, rien ne sort de la machine). Résultat mis en cache par code."""
    if code in cache:
        return cache[code]
    import urllib.request
    corps = {"model": modele, "stream": False, "think": False, "keep_alive": "10m",
             "options": {"temperature": 0, "num_predict": 800},
             "messages": [{"role": "user", "content": REPARE.format(code=code)}]}
    req = urllib.request.Request(OLLAMA, data=json.dumps(corps).encode(), headers={"Content-Type": "application/json"})
    t = json.load(urllib.request.urlopen(req, timeout=3600))["message"]["content"]
    m = re.search(r"```(?:python)?\n(.*?)```", t, re.S)
    t = (m.group(1) if m else t).strip().strip("<>").strip()
    cache[code] = t
    return t


# ------------------------------------------------------------------ tests écrits à partir du corrigé (sans programmer)
# Dans le barème (`keys/<sujet>.bareme.json`), pour un champ de code :
#   "corrige": "<programme corrigé>",
#   chaque critère peut porter :
#     "essais":   [["2024"], ["1900"]]   saisies qui prouvent le critère : pour CHACUNE, la sortie de l'élève doit
#                                         dire la même chose que celle du corrigé (voir `conforme`) ;
#     "verifie":  "sortie" (défaut) | "termine" (le programme va au bout) | "saisies" (lit autant de saisies) ;
#     "contient": ["int(input", "non|pas"]   le code contient chaque élément (« | » : l'un ou l'autre ; espaces,
#                                         casse et accents ignorés). Critère de forme, logique ou pas.
#   Un critère sans « essais » ni « contient » n'a pas de test (jugement de l'enseignant).
NEGATIONS = {"pas", "nest", "not", "ne"}            # « n'est pas », « not » : la même idée que « non »


def _mots(s):
    out = set()
    for m in re.findall(r"[a-z]+", sans_accent(s).replace("'", "")):
        if len(m) > 1:
            out.add("non" if m in NEGATIONS else m)
    return out


def _sans_espace(s):
    return re.sub(r"\s+", "", sans_accent(s))


def conforme(r, ref, discriminants):
    """La sortie `r` de l'élève dit-elle la même chose que celle du corrigé `ref` ? Compare seulement ce qui
    DISTINGUE les sorties du corrigé d'une saisie à l'autre : ses nombres (présents ; ceux des autres saisies,
    absents) et ses mots discriminants (« non », « gratuit »… : présents ou absents comme dans le corrigé). Le reste
    de la phrase est libre (« l'année est bissextile », « Année bisestile »)."""
    if r["etat"] != "ok":
        return False
    mots_d, nombres_d = discriminants
    ns = nombres(r["sortie"])
    a = lambda v: any(abs(n - v) < 0.011 for n in ns)
    nref = nombres(ref["sortie"])
    if not all(a(v) for v in nref):
        return False
    if any(a(v) for v in nombres_d - set(nref)):
        return False
    m, mref = _mots(r["sortie"]), _mots(ref["sortie"])
    return (mots_d & mref) <= m and not ((mots_d - mref) & m)


def tests_du_bareme(bareme):
    """{champ: test(code, run)} pour les champs du barème qui ont un « corrige »."""
    out = {}
    for fid, ch in (bareme.get("champs") or {}).items():
        if ch.get("corrige") and any("essais" in c or "contient" in c for c in ch["criteres"]):
            out[fid] = _test_corrige(ch)
    return out


def _test_corrige(ch):
    corrige = ch["corrige"]
    essais = sorted({json.dumps(e) for c in ch["criteres"] for e in c.get("essais", [])})
    refs = {e: executer(corrige, json.loads(e)) for e in essais}
    for e, r in refs.items():
        if r["etat"] != "ok":
            raise ValueError(f"le corrigé ne va pas au bout avec les saisies {e} ({r['etat']}) : barème à revoir")
    tous_mots = [_mots(r["sortie"]) for r in refs.values()]
    mots_d = set.union(*tous_mots) - set.intersection(*tous_mots) if tous_mots else set()
    nombres_d = {v for r in refs.values() for v in nombres(r["sortie"])}

    def test(code, run):
        res = {}
        plat = _sans_espace(code)
        for c in ch["criteres"]:
            if "essais" not in c and "contient" not in c:
                continue
            ok = all(any(_sans_espace(alt) in plat for alt in str(x).split("|")) for x in c.get("contient", []))
            mode = c.get("verifie", "sortie")
            for e in c.get("essais", []):
                if not ok:
                    break
                r, ref = run(e), refs[json.dumps(e)]
                ok = (r["etat"] == "ok" if mode == "termine" else
                      r["etat"] == "ok" and r["saisies"] == ref["saisies"] if mode == "saisies" else
                      conforme(r, ref, (mots_d, nombres_d)))
            res[c["id"]] = bool(ok)
        return res
    return test


# ------------------------------------------------------------------ tests d'un sujet
def charger_tests(exam_id, keys_dir="keys", variante=None):
    """Tests du sujet : module `keys/*.tests.py` dont EXAM_ID vaut exam_id (ou None). TESTS = {champ: fonction} ;
    `variante` (ex. « strict ») : TESTS_STRICT du même module, pour comparer deux lectures du barème."""
    if variante == "corrige":           # seulement les tests tirés du corrigé (barème)
        from .correction import _bareme
        return tests_du_bareme(_bareme(exam_id, keys_dir) or {}) or None
    python = {}
    for p in sorted(Path(keys_dir).glob("*.tests.py")):
        spec = importlib.util.spec_from_file_location(f"tests_{p.stem.replace('.', '_')}", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if getattr(mod, "EXAM_ID", None) == exam_id:
            python = getattr(mod, f"TESTS_{variante.upper()}") if variante else mod.TESTS
            break
    if variante:
        return python or None
    # le barème (corrigé de l'enseignant) prime ; le Python complète les champs qu'il ne couvre pas
    from .correction import _bareme
    return {**python, **tests_du_bareme(_bareme(exam_id, keys_dir) or {})} or None


def lisible(code):
    return bool(code) and code.strip() != "(vide)" and "[?]" not in code


def tester(code, f, tests):
    """Lance les tests du champ `f` sur `code` (déjà réparé). Chaque exécution n'est faite qu'une fois."""
    vus = {}

    def run(saisies):
        k = json.dumps(saisies)
        if k not in vus:
            vus[k] = executer(code, saisies)
        return vus[k]

    res = tests[f](code, run)
    essais = [{"saisies": json.loads(k), "etat": r["etat"], "sortie": r["sortie"][-400:]} for k, r in vus.items()]
    return {c: bool(ok) for c, ok in res.items()}, essais


def tourne(essais):
    """Au moins une exécution va au bout (ou ne s'arrête que faute de saisie)."""
    return any(e["etat"] in ("ok", "EOFError") for e in essais)


def precocher_cadre(code, f, tests, modele=None, cache=None):
    """Pré-cochage d'un cadre : réparation par règles, puis (option) par modèle contrôlé, puis tests.
    Renvoie un dict prêt pour `code_tests.json`, ou None si le champ n'a pas de test ou le code est illisible."""
    if f not in tests or not lisible(code):
        return None
    rep = reparer(code)
    criteres, essais = tester(rep, f, tests)
    out = {"lecture": code, "execute": rep, "reparation": "règles" if rep != code else "aucune"}
    if not tourne(essais) and modele:
        r = reparer_modele(code, modele, cache if cache is not None else {})
        refus = garde(code, r) if r else "réparation vide"
        if refus:
            out["refus_modele"] = refus
        else:
            rep2 = reparer(r)
            c2, e2 = tester(rep2, f, tests)
            if tourne(e2):
                rep, criteres, essais = rep2, c2, e2
                out.update(execute=rep, reparation=f"modèle {modele} (contrôlé)")
    out.update(criteres=criteres, essais=essais, tourne=tourne(essais))
    return out


# ------------------------------------------------------------------ commande
def run(dossiers, modele=None, force=False):
    from .correction import Classe, Decisions, Memory
    from .serve import _classes
    exams = {}
    for d in _classes(dossiers):
        c = Classe(d, exams, Decisions(), memory=Memory())
        tests = charger_tests(c.exam_id)
        if not tests:
            print(f"{c.name} : pas de tests pour le sujet {c.exam_id} (keys/*.tests.py), rien à faire")
            continue
        fc = CACHE_MODELE.with_name(CACHE_MODELE.name.format(modele=(modele or "").replace(":", "_")))
        cache = json.loads(fc.read_text(encoding="utf-8")) if modele and fc.exists() else {}
        p = d / FICHIER
        old = json.loads(p.read_text(encoding="utf-8")) if p.exists() and not force else {}
        out, n, coches = {}, 0, 0
        for it in c.code_items():
            code = it.get("transcription")
            if not code:
                continue
            prev = old.get(it["cle"])
            if prev and prev.get("lecture") == code and (prev.get("tourne") or not modele or "refus_modele" in prev
                                                         or prev.get("reparation", "").startswith("modèle")):
                out[it["cle"]] = prev
                continue
            r = precocher_cadre(code, it["champ"], tests, modele, cache)
            if r is None:
                continue
            out[it["cle"]], n = r, n + 1
            coches += sum(r["criteres"].values())
            if modele:
                fc.parent.mkdir(parents=True, exist_ok=True)
                fc.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {it['cle']} : {sum(r['criteres'].values())}/{len(r['criteres'])} critères pré-cochés"
                  f"{'' if r['tourne'] else ' · ne tourne pas (infraction lourde ?)'}", flush=True)
            p.write_text(json.dumps(out | {k: v for k, v in old.items() if k not in out}, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{c.name} : {len(out)} cadres testés ({n} nouveaux, {coches} critères pré-cochés) → {p}")
    if modele:
        try:
            import urllib.request
            urllib.request.urlopen(urllib.request.Request("http://localhost:11434/api/generate",
                                   data=json.dumps({"model": modele, "keep_alive": 0}).encode()), timeout=30)
        except Exception:
            pass
