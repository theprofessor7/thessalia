"""Mise en page Typst d'un sujet et de son corrigé (docs/FORMAT_SUJET.md, § 7).

Typst s'installe par `pip install typst`, sans dépendance système (WeasyPrint demandait GTK sous Windows).
Dimensions reprises du template v5 : repères 5 mm à 16 mm des bords, cases 3,7 mm (trait 0,53 mm), grille
6,5 x 4,8 mm (trait 0,4 mm). Conventions attendues par `template_builder` : « Question N » et « 0,25 pt » sur une
ligne, en-têtes V/F au-dessus des cases, étiquette d'identité au-dessus d'une ligne grise, « les N chiffres »
dans la consigne de la grille, cadre libellé « Code ». Seuls les blancs ont une bordure d'un seul côté (un filet
de titre en serait un aussi) : les filets sont des `line`.

Chaque case, blanc et cadre émet une étiquette `<zone>` (position exacte) : `typst query` en fait le fichier de
zones, contrôlé contre le PDF par `verif_zones`.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .corrige import variantes
from .modele import RE_BLANC, VF, Examen, _f

LARGEUR = {"court": "15.88mm", "moyen": "34.4mm", "long": "58.21mm"}
MOTS = {
    "fr": {"exercice": "Exercice", "points": "points", "consignes": "Consignes", "code": "Code ({n} lignes)",
           "reponse": "Réponse", "affirmation": "Affirmation", "fin": "Fin de l'épreuve",
           "entete": "Nom : ........................  Prénom : ........................",
           "id": {"nom": "Nom", "prenom": "Prénom", "groupe": "Groupe"},
           "grille": "N° étudiant : reportez les {n} chiffres de votre numéro{prefixe}, en commençant par la "
                     "1re colonne. Noircissez complètement la case du chiffre, une seule par colonne.",
           "prefixe": ", sans la lettre du préfixe", "exemple": "Exemple", "ignore": "on ignore le",
           "corrige": "Corrigé", "attendu": "Réponse attendue", "attendus": "Réponses attendues",
           "bonne": "Bonne réponse", "vrai": "VRAI", "faux": "FAUX", "bareme": "Barème", "code_att": "Code attendu",
           "accepte": "aussi accepté", "forme": "écart de forme (moitié des points)", "total": "Total",
           "tol": {"guillemets": "avec ou sans guillemets", "guillemets_forme": "entre guillemets : écart de forme",
                   "espaces_virgules": "espaces après les virgules facultatifs",
                   "espace_ponctuation": "espace avant ! ou ? facultative"},
           "liste_inc": "liste à {k} élément(s) près : {p} pt", "partiel": "{p} pt pour {r}"},
    "en": {"exercice": "Exercise", "points": "points", "consignes": "Instructions", "code": "Code ({n} lines)",
           "reponse": "Answer", "affirmation": "Statement", "fin": "End of the test",
           "entete": "Last name: ........................  First name: ........................",
           "id": {"nom": "Last name", "prenom": "First name", "groupe": "Group"},
           "grille": "Student ID: report the {n} digits of your number{prefixe}, starting from the 1st column. "
                     "Completely blacken the box of the digit, only one per column.",
           "prefixe": ", without the prefix letter", "exemple": "Example", "ignore": "ignore the",
           "corrige": "Answer key", "attendu": "Expected answer", "attendus": "Expected answers",
           "bonne": "Correct option", "vrai": "TRUE", "faux": "FALSE", "bareme": "Grading", "code_att": "Expected code",
           "accepte": "also accepted", "forme": "form issue (half points)", "total": "Total",
           "tol": {"guillemets": "with or without quotes", "guillemets_forme": "in quotes: form issue",
                   "espaces_virgules": "spaces after commas optional",
                   "espace_ponctuation": "space before ! or ? optional"},
           "liste_inc": "list missing up to {k} element(s): {p} pt", "partiel": "{p} pt for {r}"},
}

PREAMBULE = r"""
#let ACCENT = rgb("#1f3a5f")
#let GRIS = luma(95)
#let FOND = luma(244)
#show raw: set text(font: "DejaVu Sans Mono", size: 0.92em)
#let zone(id, kind, w, h, decal: 0pt) = place(top + left, context {
  let p = here().position()
  [#metadata((id: id, kind: kind, page: p.page, x: (p.x - decal).mm(), y: (p.y - decal).mm(),
              w: w.mm(), h: h.mm())) <zone>]
})
#let case(id, kind: "checkbox", w: 3.17mm, h: 3.17mm, s: 0.53mm) = box(width: w, height: h, stroke: s,
  baseline: 0.4mm, zone(id, kind, w + s, h + s, decal: s / 2))
#let blanc(id, l) = box(width: l, height: 5mm, stroke: (bottom: 0.6pt), baseline: 1.2mm,
  zone(id, "blank", l, 5mm - 0.3pt))
#let c(s) = box(fill: FOND, inset: (x: 2pt), outset: (y: 2.5pt), radius: 1.5pt, raw(s))
#let bloc(s, lang: none) = block(fill: FOND, stroke: (left: 2pt + ACCENT), inset: (x: 8pt, y: 6pt),
  width: 100%, radius: 1pt, raw(s, block: true, lang: lang))
#let code_trous(body) = block(fill: FOND, stroke: (left: 2pt + ACCENT), inset: (x: 8pt, y: 8pt), width: 100%,
  radius: 1pt, { set par(leading: 1.3em); set text(font: "DejaVu Sans Mono", size: 0.92em); body })
#let filet = line(length: 100%, stroke: 1.2pt + ACCENT)
#let question(n, pts, body) = block(breakable: false, width: 100%, above: 5mm, below: 1mm, {
  grid(columns: (1fr, auto), align: (left + bottom, right + bottom),
    text(weight: "bold", fill: ACCENT, size: 11.5pt)[Question #n],
    box(stroke: 0.5pt, inset: (x: 4pt, y: 2pt), text(size: 9pt, weight: "bold")[#pts pt]))
  v(1.5mm)
  body
})
#let exercice(titre) = block(breakable: false, above: 7mm, below: 2mm, width: 100%, {
  filet; v(-1mm); text(size: 13pt, weight: "bold", fill: ACCENT, titre); v(-1mm); filet })
#let contexte(body) = block(fill: luma(248), stroke: (left: 2pt + luma(170)), inset: 8pt, width: 100%, body)
#let note(body) = text(size: 9pt, fill: GRIS, body)
#let cadre(id, h, label) = block(width: 100%, height: h, stroke: 0.4mm, above: 2mm, {
  layout(t => zone(id, "codebox", t.width + 0.4mm, h + 0.4mm, decal: 0.2mm))
  pad(x: 2mm, y: 1.5mm, text(size: 8pt, fill: GRIS, label)) })
#let reperes = {
  let r = rect(width: 5mm, height: 5mm, fill: black, stroke: none)
  place(top + left, dx: 16mm, dy: 16mm, r)
  place(top + left, dx: 189mm, dy: 16mm, r)
  place(top + left, dx: 16mm, dy: 276mm, r)
  place(top + left, dx: 189mm, dy: 276mm, r)
  place(top + left, dx: 183mm, dy: 277mm, rect(width: 3mm, height: 3mm, fill: black, stroke: none))
}
"""


def ts(t: str) -> str:
    """Littéral de chaîne Typst."""
    return '"' + t.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


RE_INLINE = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*|\*(.+?)\*|\^([^^]+)\^|\[\[(\w+)(?::(\w+))?\]\]")


class _Rendu:
    """Markdown réduit (docs § 3.2) -> contenu Typst ; les blancs [[nom]] -> cases soulignées avec leur zone."""

    def __init__(self, blancs=None, corrige=False, langue=None):
        self.blancs, self.corrige, self.langue = blancs or {}, corrige, langue

    def blanc(self, nom):
        b = self.blancs[nom]
        if self.corrige:
            return f"#box(stroke: (bottom: 0.6pt + luma(150)), inset: (x: 3pt), strong(text(fill: rgb(\"#1c7355\"), c({ts(b.attendu[self.langue])}))))"
        return f"#blanc({ts(b.id)}, {LARGEUR[b.taille]})"

    def inline(self, t):
        out, pos = [], 0
        for m in RE_INLINE.finditer(t):
            if m.start() > pos:
                out.append("#" + ts(t[pos:m.start()]))
            if m.group(1) is not None:
                out.append(f"#c({ts(m.group(1))})")
            elif m.group(2) is not None:
                out.append(f"#strong[{self.inline(m.group(2))}]")
            elif m.group(3) is not None:
                out.append(f"#emph[{self.inline(m.group(3))}]")
            elif m.group(4) is not None:
                out.append(f"#super[{self.inline(m.group(4))}]")
            else:
                out.append(self.blanc(m.group(5)))
            pos = m.end()
        if pos < len(t):
            out.append("#" + ts(t[pos:]))
        return "".join(out)

    def blocs(self, t):
        out, para, lignes, i = [], [], (t or "").split("\n"), 0

        def vider():
            if para:
                out.append(self.inline(" ".join(para)))
                para.clear()
        while i < len(lignes):
            l = lignes[i]
            if l.strip().startswith("```"):
                vider()
                lang, code = l.strip()[3:].strip(), []
                i += 1
                while i < len(lignes) and not lignes[i].strip().startswith("```"):
                    code.append(lignes[i])
                    i += 1
                out.append(f"#bloc({ts(chr(10).join(code))}, lang: {ts(lang) if lang else 'none'})")
            elif re.match(r"^\s*[-*] ", l) or re.match(r"^\s*\d+\. ", l):
                vider()
                enum = bool(re.match(r"^\s*\d+\. ", l))
                items = []
                while i < len(lignes) and re.match(r"^\s*(\d+\.|[-*]) ", lignes[i]):
                    items.append(re.sub(r"^\s*(\d+\.|[-*]) ", "", lignes[i]))
                    i += 1
                out.append(("#enum(" if enum else "#list(") + ", ".join(f"[{self.inline(x)}]" for x in items)
                           + (", tight: false)" if enum else ", tight: false)"))
                continue
            elif not l.strip():
                vider()
            else:
                para.append(l.strip())
            i += 1
        vider()
        return "\n\n".join(out)

    def code_trous(self, code):
        lignes = []
        for l in code.rstrip("\n").split("\n"):
            morceaux, pos = [], 0
            for m in RE_BLANC.finditer(l):
                if m.start() > pos:
                    morceaux.append(f"#raw({ts(l[pos:m.start()])})")
                morceaux.append(self.blanc(m.group(1)))
                pos = m.end()
            if pos < len(l):
                morceaux.append(f"#raw({ts(l[pos:])})")
            lignes.append("".join(morceaux) or "#raw(\" \")")
        return "#code_trous[" + "#linebreak()".join(lignes) + "]"


def _pts(x, langue):
    s = f"{x:.2f}"
    return s.replace(".", ",") if langue == "fr" else s


def _page(ex, langue, entete=True):
    m = MOTS[langue]
    head = (f'header: context {{ if counter(page).get().first() > 1 {{ align(right, pad(right: 10mm, text(size: 8.5pt, fill: GRIS, '
            f'{ts(m["entete"])}))) }} }},') if entete else ""
    return (f'#set page(paper: "a4", margin: (left: 22mm, right: 22mm, top: 25mm, bottom: 24mm), '
            f'background: reperes, header-ascent: 55%, {head} footer: context {{ '
            f'place(left + horizon, text(font: "DejaVu Sans Mono", size: 7pt, fill: GRIS, {ts(ex.id + " · p")} + '
            f'numbering("01", counter(page).get().first()) + "/" + numbering("01", counter(page).final().first()))); '
            f'align(center, text(size: 9pt, fill: GRIS, "Page " + str(counter(page).get().first()) + " / " + '
            f'str(counter(page).final().first()))) }})\n'
            f'#set text(font: "Libertinus Serif", size: 10.5pt, lang: "{langue}")\n'
            f'#set par(leading: 0.75em, spacing: 1.1em)\n')


def _couverture(ex, langue):
    m, e, out = MOTS[langue], ex.entete, []
    t = lambda k: (e.get(k) or {}).get(langue, "")
    logo = f"image({ts(Path(e['logo']).name)}, width: 30mm)," if e.get("logo") else ""
    meta = " · ".join(x for x in (e.get("duree"), f"{ex.points:g} points", t("version"), t("session")) if x)
    out.append(f"#align(center)[#stack(spacing: 3mm, {logo} text(size: 9.5pt, fill: GRIS, tracking: 0.08em, "
               f"upper({ts(t('matiere'))})), text(size: 22pt, weight: \"bold\", fill: ACCENT, {ts(t('titre'))}), "
               f"box(stroke: 1pt + rgb(\"#9b2335\"), inset: (x: 6pt, y: 3pt), radius: 2pt, "
               f"text(weight: \"bold\", fill: rgb(\"#9b2335\"), {ts(t('sous_titre'))})), text(size: 10pt, {ts(meta)}))]")
    ids = e.get("identite") or []
    if ids:
        cols = ", ".join(f"[#text(size: 8pt, fill: GRIS, tracking: 0.05em, upper({ts(m['id'].get(k, k))}))"
                         f"#v(7mm)#box(width: 100%, height: 0pt, stroke: (bottom: 0.6pt + luma(150)))]" for k in ids)
        out.append(f"#v(6mm)#grid(columns: ({', '.join(['1fr'] * len(ids))}), column-gutter: 8mm, {cols})")
    ne = e.get("numero_etudiant")
    if ne:
        n = ne["chiffres"]
        consigne = m["grille"].format(n=n, prefixe=m["prefixe"] if ne["ignorer_prefixe"] else "")
        exemple = ""
        if ne.get("exemple"):
            num = ne["exemple"]
            pre = re.match(r"^[A-Za-z]*", num).group(0) if ne["ignorer_prefixe"] else ""
            lignes = [f"#strong({ts(m['exemple'])})", f"#c({ts(num)})"]
            if pre:
                lignes.append(f"#{ts('→ ' + m['ignore'] + ' ')}#c({ts(pre)})")
            lignes += [f"#{ts(f'C{i + 1} → {d}')}" for i, d in enumerate(num[len(pre):][:n])]
            exemple = (', block(stroke: (left: 2pt + rgb("#9b2335")), inset: 6pt, fill: luma(250), '
                       f"text(size: 8.5pt)[{'#linebreak()'.join(lignes)}])")
        grille = (f"grid(columns: (6mm,) + (6.5mm,) * {n}, rows: (4.8mm,) * 11, align: center + horizon, [], "
                  f"..range(1, {n + 1}).map(i => text(size: 7pt, fill: GRIS)[C#i]), "
                  f"..range(10).map(d => (text(size: 8pt)[#d],) + range({n}).map(i => "
                  f"case(\"grille.C\" + str(i + 1) + \".\" + str(d), kind: \"sid_cell\", w: 6.1mm, h: 4.4mm, s: 0.4mm)))"
                  f".flatten())")
        out.append(f"#v(6mm)#block(stroke: 0.5pt + luma(160), inset: 8pt, radius: 2pt, width: 100%)["
                   f"#text(size: 9.5pt, {ts(consigne)})#v(2mm)#grid(columns: (auto, 1fr), column-gutter: 10mm, "
                   f"{grille}{exemple})]")
    if e.get("consignes"):
        out.append(f"#v(6mm)#block(fill: rgb(\"#fbfbf4\"), stroke: 1pt + rgb(\"#a89a5b\"), inset: 9pt, radius: 3pt, "
                   f"width: 100%)[#text(weight: \"bold\", fill: rgb(\"#7a6a14\"), {ts(m['consignes'])})\n\n"
                   f"{_Rendu().blocs(e['consignes'][langue])}]")
    return "\n".join(out)


def _questions_typst(ex, langue):
    m, out = MOTS[langue], []
    for i, exo in enumerate(ex.exercices, 1):
        pe = exo.points if exo.points is not None else sum(q.points for q in exo.questions)
        titre = f"{m['exercice']} {i} — {exo.titre[langue]} ({pe:g} {m['points']})"
        out.append(f"#exercice({ts(titre)})")
        if exo.contexte:
            out.append(f"#contexte[{_Rendu().blocs(exo.contexte[langue])}]")
        for q in exo.questions:
            out.append(_question(q, langue))
    out.append(f"#v(8mm)#align(center, text(size: 9pt, fill: GRIS, {ts(m['fin'])}))")
    return "\n\n".join(out)


def _question(q, langue):
    m, d = MOTS[langue], q.donnees
    if q.type in ("texte", "brut"):
        return _Rendu().blocs(d["contenu"][langue]) if q.type == "texte" else d["contenu"][langue]
    r = _Rendu({b.nom: b for b in d.get("blancs", [])})
    corps = [r.blocs(q.enonce[langue])]
    if q.type == "qcm":
        cases = ", ".join(f"case({ts(d['id'] + '_' + 'abcdefghij'[k])}), [{_Rendu().inline(c[langue])}]"
                          for k, c in enumerate(d["choix"]))
        corps.append(f"#grid(columns: (auto, 1fr), column-gutter: 3mm, row-gutter: 2.6mm, align: horizon, {cases})")
    elif q.type == "vrai_faux":
        v, f = VF.get(langue, ("V", "F"))
        lignes = ", ".join(f"case({ts(a['id'] + '_' + v)}), case({ts(a['id'] + '_' + f)}), [{_Rendu().inline(a['texte'][langue])}]"
                           for a in d["affirmations"])
        corps.append(f"#table(columns: (9mm, 9mm, 1fr), stroke: 0.4pt + luma(170), inset: 4.5pt, "
                     f"align: (center + horizon, center + horizon, left + horizon), "
                     f"table.header([*{v}*], [*{f}*], [*{m['affirmation']}*]), {lignes})")
    elif q.type == "blancs":
        if d.get("code"):
            corps.append(r.code_trous(d["code"][langue]))
        if d.get("lignes"):
            corps.append("#list(tight: false, " + ", ".join(f"[{r.inline(l[langue])}]" for l in d["lignes"]) + ")")
    elif q.type == "code":
        h = d["lignes"] * 8 + 6
        corps.append(f"#cadre({ts(d['id'])}, {h}mm, {ts(m['code'].format(n=d['lignes']))})")
    elif q.type == "redaction":
        h = d["lignes"] * 8 + 6
        corps.append(f"#cadre({ts(d['id'])}, {h}mm, {ts(m['reponse'])})")
    if d.get("note"):
        corps.append(f"#note[{_Rendu().inline(d['note'][langue])}]")
    return f"#question({q.num}, {ts(_pts(q.points, langue))})[\n{chr(10).join(corps)}\n]"


def typst_sujet(ex: Examen, langue: str) -> str:
    return (PREAMBULE + _page(ex, langue) + _couverture(ex, langue) + "\n#pagebreak()\n"
            + _questions_typst(ex, langue) + "\n")


# ---------------------------------------------------------------------------------------------------- corrigé
def typst_corrige(ex: Examen, langue: str) -> str:
    m, out = MOTS[langue], []
    e = ex.entete
    titre = f"{m['corrige']} — {e['titre'][langue]}" + (f" — {e['sous_titre'][langue]}" if e.get("sous_titre") else "")
    out.append(f"#text(size: 17pt, weight: \"bold\", fill: ACCENT, {ts(titre)})#linebreak()"
               f"#text(size: 9pt, fill: GRIS, {ts(ex.id + ' · ' + str(e.get('duree') or '') + ' · ' + f'{ex.points:g} points')})")
    vert = 'rgb("#1c7355")'
    rep = lambda lbl, corps: (f"#block(fill: rgb(\"#e8f4ef\"), stroke: (left: 4pt + {vert}), inset: 7pt, width: 100%)"
                              f"[#text(size: 8.5pt, weight: \"bold\", fill: {vert}, upper({ts(lbl)}))\n\n{corps}]")
    recap = []
    for i, exo in enumerate(ex.exercices, 1):
        pe = exo.points if exo.points is not None else sum(q.points for q in exo.questions)
        recap.append((f"{m['exercice']} {i} — {exo.titre[langue]}", pe))
        titre = f"{m['exercice']} {i} — {exo.titre[langue]} ({pe:g} {m['points']})"
        out.append(f"#exercice({ts(titre)})")
        for q in exo.questions:
            if q.type in ("texte", "brut"):
                continue
            d = q.donnees
            rq = _Rendu({b.nom: b for b in d.get("blancs", [])}, corrige=True, langue=langue)
            corps = [f"#text(size: 9.5pt, fill: GRIS)[{rq.blocs(q.enonce[langue])}]"]
            if q.type == "qcm":
                lignes = [f"#strong[{k})] {_Rendu().inline(d['choix']['abcdefghij'.index(k)][langue])}" for k in d["bonnes"]]
                corps.append(rep(m["bonne"], "#linebreak()".join(lignes)))
            elif q.type == "vrai_faux":
                lignes = []
                for a in d["affirmations"]:
                    ex_ = f" #text(size: 8.5pt, fill: GRIS)[{_Rendu().inline(a['explication'][langue])}]" if a.get("explication") else ""
                    lignes.append(f"[{_Rendu().inline(a['texte'][langue])} : #strong({ts(m['vrai'] if a['vrai'] else m['faux'])}){ex_}]")
                corps.append(rep(m["attendus"], "#list(" + ", ".join(lignes) + ")"))
            elif q.type == "blancs":
                items = []
                for b in d["blancs"]:
                    acc, forme, part = variantes(b, langue)
                    det = [m["tol"][t] for t in b.tolerances if isinstance(t, str)]
                    det += [m["liste_inc"].format(k=t[1]["manque_max"], p=_f(t[1]["points"])) for t in b.tolerances
                            if isinstance(t, tuple)]
                    det += [m["partiel"].format(p=_f(p), r=r) for r, p in b.partiel.get(langue, {}).items()]
                    det += [f"{m['accepte']} : {x}" for x in b.accepte.get(langue, [])]
                    pts = f" ({_f(b.points)} pt)" if b.points is not None else ""
                    ex_ = _Rendu().inline(b.explication[langue]) if b.explication else ""
                    item = f"#strong(c({ts(b.attendu[langue])}))" + (f"#{ts(pts)}" if pts else "") + f" {ex_}"
                    if det:
                        item += f" #linebreak()#text(size: 8.5pt, fill: GRIS, {ts(' ; '.join(det))})"
                    items.append(f"[{item}]")
                corps.append(rep(m["attendus"] if len(items) > 1 else m["attendu"],
                                 "#enum(" + ", ".join(items) + ")" if len(items) > 1 else items[0][1:-1]))
            elif q.type in ("code", "redaction"):
                if d.get("corrige"):
                    corps.append(rep(m["code_att"], f"#raw({ts(d['corrige'][langue].rstrip())}, block: true, lang: \"python\")"))
                if d.get("criteres"):
                    crit = ", ".join(f"[{_Rendu().inline(c['texte'][langue])} : #strong({ts(_f(c['points']) + ' pt')})]"
                                     for c in d["criteres"])
                    corps.append(f"#text(size: 9.5pt)[#strong({ts(m['bareme'] + ' :')}) #list({crit})]")
            if d.get("explication"):
                corps.append(f"#note[{_Rendu().inline(d['explication'][langue])}]")
            out.append(f"#question({q.num}, {ts(_pts(q.points, langue))})[\n{chr(10).join(corps)}\n]")
    lignes = ", ".join(f"[{ts(t)[1:-1]}], [{_f(p)}]" for t, p in recap)
    out.append(f"#v(6mm)#table(columns: (1fr, auto), stroke: 0.4pt + luma(170), {lignes}, "
               f"[*{m['total']}*], [*{_f(ex.points)}*])")
    page = (f'#set page(paper: "a4", margin: 16mm, footer: context align(center, text(size: 8pt, fill: GRIS, '
            f'"Page " + str(counter(page).get().first()) + " / " + str(counter(page).final().first()))))\n'
            f'#set text(font: "Libertinus Serif", size: 10.5pt, lang: "{langue}")\n')
    return PREAMBULE + page + "\n\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------------- production
def produire(ex: Examen, source: Path, dossier: Path, langue: str):
    """Sujet, corrigé et zones d'une langue dans `dossier` ; renvoie les chemins."""
    import typst

    dossier.mkdir(parents=True, exist_ok=True)
    if ex.entete.get("logo"):
        logo = (source.parent / ex.entete["logo"])
        if not logo.exists():
            raise SystemExit(f"logo introuvable : {logo}")
        shutil.copy(logo, dossier / logo.name)
    base = f"{ex.id}_{langue.upper()}"
    chemins = {}
    for nom, contenu in ((f"sujet_{base}", typst_sujet(ex, langue)), (f"corrige_{base}", typst_corrige(ex, langue))):
        typ = dossier / f"{nom}.typ"
        typ.write_text(contenu, encoding="utf-8")
        pdf = dossier / f"{nom}.pdf"
        try:
            typst.compile(str(typ), output=str(pdf), root=str(dossier))
        except Exception as e:      # erreur de Typst : la source Typst est gardée pour la retrouver
            raise SystemExit(f"Mise en page impossible ({typ}) : {e}") from None
        chemins[nom.split("_")[0]] = pdf
    zones = json.loads(typst.query(str(dossier / f"sujet_{base}.typ"), "<zone>", field="value", root=str(dossier)))
    zj = dossier / f"zones_{base}.json"
    zj.write_text(json.dumps({"exam_id": base, "format": "thessalia-typst", "page_size": "A4", "unit": "mm",
                              "zone_count": len(zones),
                              "zones": [{"id": z["id"], "kind": z["kind"], "page": z["page"],
                                         "x_mm": round(z["x"], 2), "y_mm": round(z["y"], 2),
                                         "w_mm": round(z["w"], 2), "h_mm": round(z["h"], 2)} for z in zones]},
                             ensure_ascii=False, indent=1), encoding="utf-8")
    chemins["zones"] = zj
    return chemins
