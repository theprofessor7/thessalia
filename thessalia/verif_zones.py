"""Contrôle d'un fichier de zones (généré à côté du PDF d'un sujet) contre le PDF lui-même :
`python -m thessalia verif-zones <sujet.pdf> <zones.json> [-o rapport.md] [--tolerance 0.3]`.

Le PDF fait foi : ses rectangles vectoriels sont lus au 1/100 de mm (comme `template`). Chaque zone du .json est
rapprochée de l'élément du PDF de même nature (case, grille, blanc, cadre), puis comparée. Le rapport, en Markdown,
est écrit pour être collé tel quel dans le prompt de l'outil qui génère le sujet : il dit précisément quoi corriger.

Conventions vérifiées (unités : mm, origine en haut à gauche de la page, pages numérotées à partir de 1) :
  - case à cocher, case de grille, cadre : le bord EXTÉRIEUR de la bordure ;
  - blanc : x et largeur du trait ; le bas de la zone posé sur le haut du trait (zone d'écriture au-dessus) ;
  - repères de coin : carrés pleins dessinés en vectoriel (pas des images), position réelle page par page.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import pymupdf

from .common import MM_PER_PT
from .template_builder import _trait_typst

ECHELLES = [(1.0, "aucune"), (0.75, "positions multipliées par 4/3 (pixels CSS pris pour des points)"),
            (4 / 3, "positions multipliées par 3/4"), (25.4 / 96, "positions en pixels CSS (96 dpi), pas en mm"),
            (25.4 / 72, "positions en points PDF, pas en mm")]
NATURE = {"checkbox": "case", "sid_cell": "case", "codebox": "cadre", "text_box": "cadre", "blank": "trait"}


def _lum(c):
    return 1.0 if not c else 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def elements(page):
    """Éléments utiles d'une page, en mm : cases, cadres, traits (blancs), repères (vectoriels ou images)."""
    pw, ph = page.rect.width * MM_PER_PT, page.rect.height * MM_PER_PT
    out, vus = [], set()

    def coin(x, y, w, h):
        return min(x, pw - x - w) < 25 and min(y, ph - y - h) < 25      # un repère est près d'un coin

    for g in page.get_drawings():
        items = g.get("items") or []
        ep = (g.get("width") or 0) * MM_PER_PT / 2
        t = _trait_typst(g) if g.get("type") == "f" else None
        if t is not None and _lum(g.get("fill")) < 0.35:      # soulignement Typst : mince rectangle rempli
            x0, y0, x1, y1 = (v * MM_PER_PT for v in t)
            if x1 - x0 >= 8:
                out.append({"nature": "trait", "haut_trait": y0, "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})
            continue
        if not items or any(it[0] != "re" for it in items):
            continue
        if g.get("type") == "s" and len(items) == 1:        # rectangle tracé au trait : bord extérieur
            r = items[0][1]
            items = [("re", pymupdf.Rect(r.x0 - ep / MM_PER_PT, r.y0 - ep / MM_PER_PT,
                                         r.x1 + ep / MM_PER_PT, r.y1 + ep / MM_PER_PT))]
        rs = sorted(([v * MM_PER_PT for v in it[1]] for it in items), key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
        o = rs[0]
        x, y, w, h = o[0], o[1], o[2] - o[0], o[3] - o[1]
        cle = (round(x, 1), round(y, 1), round(w, 1), round(h, 1), len(rs), g.get("type"))
        if cle in vus:
            continue
        vus.add(cle)
        sombre_f, sombre_t = _lum(g.get("fill")) < 0.35, _lum(g.get("color")) < 0.35 and g.get("color") is not None
        e = None
        if len(rs) == 1 and g.get("type") == "f" and sombre_f:
            if 2.5 <= w <= 8 and 2.5 <= h <= 8 and abs(w - h) < 0.6 and coin(x, y, w, h):
                e = {"nature": "repère", "forme": "plein (vectoriel)"}
            elif h <= 1.2 and w >= 8:
                e = {"nature": "trait", "haut_trait": y}
        elif len(rs) == 1 and g.get("type") in ("s", "fs") and sombre_t:
            e = {"nature": "case" if max(w, h) < 10 else "cadre" if w >= 30 and h >= 10 else None}
        elif len(rs) == 2 and sombre_f:
            i = rs[1]
            cotes = [i[1] - o[1] > 0.05, o[2] - i[2] > 0.05, o[3] - i[3] > 0.05, i[0] - o[0] > 0.05]
            if all(cotes):
                if 4.5 <= w <= 8 and abs(w - h) < 0.6 and coin(x, y, w, h):      # pas une case (3,7 mm)
                    e = {"nature": "repère", "forme": "creux (vectoriel)"}
                elif max(w, h) < 10:
                    e = {"nature": "case"}
                elif w >= 30 and h >= 10:
                    e = {"nature": "cadre"}
            elif cotes == [False, False, True, False] and w >= 8:
                e = {"nature": "trait", "haut_trait": i[3]}
        if e and e["nature"]:
            out.append(e | {"x": x, "y": y, "w": w, "h": h})
    for im in page.get_image_info():
        x0, y0, x1, y1 = [v * MM_PER_PT for v in im["bbox"]]
        w, h = x1 - x0, y1 - y0
        if 3 <= w <= 8 and abs(w - h) < 0.6 and coin(x0, y0, w, h):
            out.append({"nature": "repère", "forme": f"IMAGE {im['width']}×{im['height']} px", "x": x0, "y": y0,
                        "w": w, "h": h})
    return out


def _ecarts(z, e, k):
    """Écarts (dx, dy, dw, dh) entre la zone (facteur d'échelle k appliqué à toutes ses valeurs) et le PDF."""
    x, y, w, h = z["x_mm"] * k, z["y_mm"] * k, z["w_mm"] * k, z["h_mm"] * k
    if e["nature"] == "trait":
        return {"dx": e["x"] - x, "dw": e["w"] - w, "dbas": e["haut_trait"] - (y + h)}
    return {"dx": e["x"] - x, "dy": e["y"] - y, "dw": e["w"] - w, "dh": e["h"] - h}


def apparier(zones, pages, k):
    """Pour chaque zone, l'élément du PDF de même nature le plus proche (coin haut gauche, échelle k)."""
    res, pris = [], set()
    for z in zones:
        nat = NATURE.get(z.get("kind"))
        cands = [(i, e) for i, e in enumerate(pages.get(z.get("page"), [])) if e["nature"] != "repère"
                 and (nat is None or e["nature"] == nat)]
        x, y = z["x_mm"] * k, z["y_mm"] * k
        best = min(cands, key=lambda c: abs(c[1]["x"] - x) + abs(c[1]["y"] - y), default=None)
        if best is None or abs(best[1]["x"] - x) + abs(best[1]["y"] - y) > 8:
            res.append((z, None))
        else:
            pris.add((z.get("page"), best[0]))
            res.append((z, best[1]))
    return res, pris


def controler(pdf, fichier, tolerance=0.3):
    import pymupdf
    doc = pymupdf.open(str(pdf))
    data = json.loads(Path(fichier).read_text(encoding="utf-8"))
    zones = data.get("zones", [])
    pages = {i: elements(p) for i, p in enumerate(doc, 1)}
    L = [f"# Contrôle des zones : `{Path(fichier).name}` contre `{Path(pdf).name}`", "",
         f"Référence : le PDF lui-même (rectangles vectoriels), en mm, origine en haut à gauche de la page. "
         f"Tolérance : {tolerance:g} mm. Conventions attendues : case, case de grille et cadre = bord extérieur de "
         f"la bordure ; blanc = x et largeur du trait, bas de la zone posé sur le haut du trait ; repères = carrés "
         f"pleins dessinés en vectoriel, position réelle page par page.", ""]

    def proches(k):
        return sum(1 for z, e in apparier(zones, pages, k)[0] if e and abs(e["x"] - z["x_mm"] * k) < 0.5)
    k, raison = max(ECHELLES, key=lambda s: proches(s[0]))
    if proches(k) <= proches(1.0):
        k, raison = 1.0, "aucune"
    paires, pris = apparier(zones, pages, k)
    bonnes, mauvaises, absentes = [], [], []
    for z, e in paires:
        if e is None:
            absentes.append(z)
            continue
        d = _ecarts(z, e, k)
        d = {c: v for c, v in d.items() if abs(v) > tolerance}
        (mauvaises if d else bonnes).append((z, e, d))
    ok = len(bonnes) == len(zones) and k == 1.0
    if k == 1.0:
        L += [f"**Résultat : {len(bonnes)} zones conformes sur {len(zones)}.**" + ("" if ok else " Corrections ci-dessous."),
              ""]
    else:
        L += [f"**Résultat : aucune zone conforme ({len(zones)} zones) : l'unité est fausse (section 1).** Une fois le "
              f"facteur corrigé, {len(bonnes)} seraient justes ; les autres sont à corriger aussi (sections 3 et 4).", ""]

    L += ["## 1. Unité et échelle", ""]
    if raison == "aucune":
        L += [f"- Pages du PDF : {len(doc)}, format {doc[0].rect.width * MM_PER_PT:.1f} × "
              f"{doc[0].rect.height * MM_PER_PT:.1f} mm. Les positions du .json sont bien en mm.", ""]
    else:
        L += [f"- **Les positions x/y du .json ne sont pas en mm : {raison}.** Avec le facteur ×{k:.4g}, les "
              f"positions retombent sur les éléments du PDF. Les écarts ci-dessous sont ceux qui RESTENT une fois ce "
              f"facteur appliqué à toutes les valeurs (positions ET tailles) ; le tableau donne les valeurs exactes "
              f"à écrire.",
              f"- Valeurs hors de la page dans le .json : "
              f"{sum(1 for z in zones if z['y_mm'] + z['h_mm'] > 297 or z['x_mm'] + z['w_mm'] > 210)} zones.", ""]

    L += ["## 2. Repères de coin", ""]
    decl = data.get("fiducials", {})
    if decl and not _repères_declares(decl):
        L += ["- Déclaré dans le .json : " + " ; ".join(
            f"{c} {v.get('kind', '?')} {v.get('size_mm', '?')} mm « {v.get('pos', '?')} »"
            for c, v in decl.items() if isinstance(v, dict)), ""]
    groupes = {}
    for n, els in pages.items():
        rep = tuple(sorted((round(e["x"], 1), round(e["y"], 1), round(e["w"], 1), e["forme"])
                           for e in els if e["nature"] == "repère"))
        groupes.setdefault(rep, []).append(n)
    L += ["| Pages | Repères réels (x, y du coin haut gauche, côté, forme) |", "|---|---|"]
    for rep, ns in groupes.items():
        L.append(f"| {_plages(ns)} | " + ("<br>".join(f"x {x} · y {y} · {w} mm · {f}" for x, y, w, f in rep)
                                          or "**aucun repère trouvé**") + " |")
    probl, bloquant = [], False
    formes = {f for rep in groupes for *_, f in rep}
    if any(f.startswith("IMAGE") for f in formes):
        bloquant = True
        probl.append("les repères sont des **images** : les dessiner en vectoriel (un `div` à fond noir), sinon "
                     "`template` ne les voit pas")
    if any("creux" in f for f in formes):
        bloquant = True
        probl.append("des repères sont **creux** : l'alignement de Thessalia cherche 4 carrés **pleins** (un trait de "
                     "1 mm scanné à 100 dpi fait 4 pixels, fragile) ; pour l'orientation, ajouter une marque à côté "
                     "du repère haut gauche plutôt que creuser les autres")
    if any("hollow" in str(v.get("kind", "")) or "creux" in str(v.get("kind", ""))
           for v in decl.values() if isinstance(v, dict)) and not any("creux" in f for f in formes):
        probl.append("le .json déclare des repères **creux** : l'alignement de Thessalia cherche 4 carrés **pleins** "
                     "(un trait de 1 mm scanné à 100 dpi fait 4 pixels, fragile) ; pour l'orientation, ajouter une "
                     "marque à côté du repère haut gauche plutôt que creuser les autres")
    if len(groupes) > 1:
        probl.append("les repères ne sont **pas au même endroit sur toutes les pages** : écrire leur position page par "
                     "page dans le .json (ou les placer pareil partout)")
    if decl and any("0 mm" in str(v.get("pos", "")) for v in decl.values() if isinstance(v, dict)):
        probl.append("le .json annonce « coin de page, décalage 0 mm » : écrire les coordonnées réelles ci-dessus")
    declares = _repères_declares(decl)
    if declares:
        faux = []
        for n, els in pages.items():
            reels = [e for e in els if e["nature"] == "repère"]
            for nom, r in declares:
                if not any(abs(e["x"] - r["x"]) <= tolerance and abs(e["y"] - r["y"]) <= tolerance
                           and abs(e["w"] - r.get("w", e["w"])) <= tolerance for e in reels):
                    meme = [e for e in reels if abs(e["w"] - r.get("w", e["w"])) <= 1] or reels
                    pres = min(meme, key=lambda e: abs(e["x"] - r["x"]) + abs(e["y"] - r["y"]), default=None)
                    faux.append((nom, n, r, pres))
        if faux:
            par = {}
            for nom, n, r, pres in faux:
                cle = (nom, r["x"], r["y"], None if pres is None else (round(pres["x"], 2), round(pres["y"], 2)))
                par.setdefault(cle, []).append(n)
            bloquant = True
            probl.append("les positions **déclarées** des repères ne correspondent pas au PDF : écrire les positions "
                         "réelles (tableau ci-dessus), page par page si elles changent :<br>" + "<br>".join(
                             f"`{nom}` déclaré x {x} · y {y} → réel x {pr[0]} · y {pr[1]} (pages {_plages(ns)})"
                             if pr else f"`{nom}` déclaré x {x} · y {y} → absent (pages {_plages(ns)})"
                             for (nom, x, y, pr), ns in par.items()))
    L += [""] + [f"- {p}" for p in probl] + ([""] if probl else [])

    if mauvaises:
        L += ["## 3. Écarts systématiques par type de zone", "",
              "| Type | Zones | dx médian | dy médian | dw médian | dh médian | bas du blanc / trait |",
              "|---|---|---|---|---|---|---|"]
        for kind in sorted({z.get("kind") for z, _, _ in mauvaises}):
            ds = [_ecarts(z, e, k) for z, e, _ in bonnes + mauvaises if z.get("kind") == kind]
            med = {c: statistics.median([d[c] for d in ds if c in d]) for c in ("dx", "dy", "dw", "dh", "dbas")
                   if any(c in d for d in ds)}
            L.append(f"| {kind} | {len(ds)} | " + " | ".join(f"{med[c]:+.2f}" if c in med else "—"
                                                              for c in ("dx", "dy", "dw", "dh", "dbas")) + " |")
        L += ["", "(écart = PDF − .json, en mm, après le facteur d'échelle éventuel)", "",
              "## 4. Zones à corriger", "",
              "| Zone | Type | Page | .json x, y, w, h | PDF x, y, w, h (à écrire) | Écarts > tolérance |",
              "|---|---|---|---|---|---|"]
        vus = {}
        for z, e, d in mauvaises:
            sig = (z.get("kind"), tuple((c, round(v, 1)) for c, v in d.items()))
            vus[sig] = vus.get(sig, 0) + 1
            if vus[sig] > 3:
                continue
            zx = f"{z['x_mm']:.2f}, {z['y_mm']:.2f}, {z['w_mm']:.2f}, {z['h_mm']:.2f}"
            if e["nature"] == "trait":
                px = f"{e['x']:.2f}, {e['haut_trait'] - z['h_mm']:.2f}, {e['w']:.2f}, {z['h_mm']:.2f}"
            else:
                px = f"{e['x']:.2f}, {e['y']:.2f}, {e['w']:.2f}, {e['h']:.2f}"
            L.append(f"| {z['id']} | {z.get('kind')} | {z.get('page')} | {zx} | {px} | "
                     + ", ".join(f"{c} {v:+.2f}" for c, v in d.items()) + " |")
        L += [f"| … | {k_} | | | | **{n - 3} autre{'s' if n > 4 else ''} zone{'s' if n > 4 else ''}** `{k_}` "
              f"avec les mêmes écarts |"
              for (k_, _), n in vus.items() if n > 3]
        L.append("")
    if absentes:
        L += ["## 5. Zones sans élément correspondant dans le PDF", ""]
        L += [f"- `{z['id']}` ({z.get('kind')}, page {z.get('page')}, x {z['x_mm']}, y {z['y_mm']})" for z in absentes]
        L.append("")
    oublis = [(n, e) for n, els in pages.items() for i, e in enumerate(els)
              if e["nature"] in ("case", "cadre", "trait") and (n, i) not in pris]
    if oublis:
        L += ["## 6. Éléments du PDF sans zone dans le .json", "",
              "(à vérifier : une case ou un blanc oublié n'est jamais lu)", ""]
        L += [f"- page {n} : {e['nature']} x {e['x']:.2f} · y {e['y']:.2f} · {e['w']:.2f} × {e['h']:.2f}"
              for n, e in oublis[:40]]
        if len(oublis) > 40:
            L.append(f"- … et {len(oublis) - 40} autres")
        L.append("")
    if bloquant and ok:
        i = next(i for i, l in enumerate(L) if l.startswith("**Résultat"))
        L[i] = f"**Résultat : les {len(zones)} zones sont conformes, mais les repères de coin sont à corriger (section 2).**"
    return "\n".join(L), ok and not bloquant


def _repères_declares(decl):
    """Repères déclarés avec des coordonnées (`positions_mm`, `orient_mark.position_mm`), sinon []."""
    out = [(nom, r) for nom, r in (decl.get("positions_mm") or {}).items() if isinstance(r, dict) and "x" in r]
    o = (decl.get("orient_mark") or {}).get("position_mm")
    if isinstance(o, dict) and "x" in o:
        out.append(("orient_mark", o))
    return out


def _plages(ns):
    out, deb = [], None
    for i, n in enumerate(ns):
        if deb is None:
            deb = n
        if i + 1 == len(ns) or ns[i + 1] != n + 1:
            out.append(str(deb) if deb == n else f"{deb}-{n}")
            deb = None
    return ", ".join(out)


def run(pdf, fichier, sortie=None, tolerance=0.3):
    rapport, ok = controler(pdf, fichier, tolerance)
    if sortie:
        Path(sortie).write_text(rapport, encoding="utf-8")
        print(f"Rapport écrit dans {sortie} ({'conforme' if ok else 'corrections à faire'}).")
    else:
        print(rapport)
    return 0 if ok else 1
