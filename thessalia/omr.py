"""Lecture des cases à cocher (QCM, vrai/faux).

Pour chaque case :
    1. position nominale (gabarit, mm) -> pixels de la page redressée ;
    2. raffinement local : on recherche le contour de la case vierge
       (template matching ±2 mm) pour absorber les déformations du papier que
       l'homographie globale ne corrige pas (feuille gondolée, scanner à
       défilement). Une case mal recalée (noircie, gribouillée) reçoit le
       décalage interpolé à partir des cases voisines bien recalées ;
    3. taux d'encre dans l'intérieur de la case (bordure exclue), sur l'image
       normalisée par le fond, moins le même taux mesuré sur la page vierge ;
    4. classification à deux seuils : vide / ambiguë / cochée / noircie.

Toute case ambiguë, ou toute question à choix unique avec plusieurs cases,
passe en statut "review" : c'est ce qui permet de viser 95 %+ de décisions
automatiques justes tout en envoyant les cas douteux à l'humain.

Grille du numéro étudiant (`digit_grid`) : chaque colonne est lue comme un QCM à choix unique (mêmes
recalage, seuils, ratures, cases noircies), puis les colonnes sont assemblées (`decide_grid`).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .common import mm_rect_to_px, normalize_background, px_per_mm


@dataclass
class OMRConfig:
    ink_level: float = 0.60        # pixel "encre" si < 60 % de la luminosité du papier
    faint_level: float = 0.84      # pixel "trace claire" (crayon, encre pâle)
    faint_min: float = 0.12        # case vide mais >= 12 % de traces claires -> ambiguë
    inset_mm: float = 0.35         # marge retirée à l'intérieur de la bordure
    empty_max: float = 0.06        # taux d'encre <= : vide
    checked_min: float = 0.14      # taux d'encre >= : cochée
    full_min: float = 0.80         # taux d'encre >= : case noircie
    halo_rature: float = 0.08      # encre autour d'une case très encrée >= : rature probable -> revue
    rature_min_fill: float = 0.55  # ... à partir de ce taux d'encre (une croix déborde aussi un peu)
    core_min: float = 0.02         # case "cochée" sans encre au centre : bordure redessinée -> revue
    full_policy: str = "auto"      # "auto" | "checked" | "cancelled" | "review"
    inset_grille_mm: float = 1.0   # même marge pour une case de grille de chiffres (cases collées)
    search_mm: float = 2.0         # rayon de recherche du raffinement local
    search_grille_mm: float = 1.0  # … pour une colonne de grille autour de la grille, une case autour de sa colonne
    search_grille_page_mm: float = 5.0  # … pour la grille entière (décalage de 2,5 mm vu en simulation difficile)
    marge_grille_mm: float = 5.0   # contexte autour de la grille (en-têtes C1…, chiffres 0-9) : la rend unique
    accord_grille: float = 0.35    # haut, bas et grille entière d'accord à cette part de case près, sinon revue
    max_dev_mm: float = 0.8        # écart max à la prédiction des cases voisines
    min_match: float = 0.45        # score mini du template matching
    trust_match: float = 0.75      # au-dessus : recalage local toujours retenu

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__})


def _ink_ratio(norm, box, level):
    x0, y0, x1, y1 = box
    roi = norm[max(0, y0):y1, max(0, x0):x1]
    if roi.size == 0:
        return 0.0
    return float((roi < level).mean())


def _locate(norm_scan, norm_blank, outer_px, k, cfg, search_mm=None, offset=(0, 0)):
    """Retourne (dx, dy, score) du meilleur recalage de la case vierge dans le scan."""
    m = int(round(0.8 * k))
    s = int(round((search_mm or cfg.search_mm) * k))
    x0, y0, x1, y1 = outer_px
    ox, oy = int(round(offset[0])), int(round(offset[1]))   # recherche centrée sur un décalage déjà connu
    H, W = norm_scan.shape
    tx0, ty0, tx1, ty1 = x0 - m, y0 - m, x1 + m, y1 + m
    sx0, sy0, sx1, sy1 = tx0 - s + ox, ty0 - s + oy, tx1 + s + ox, ty1 + s + oy
    if sx0 < 0 or sy0 < 0 or sx1 > W or sy1 > H:
        return 0, 0, 0.0
    tpl = norm_blank[ty0:ty1, tx0:tx1]
    roi = norm_scan[sy0:sy1, sx0:sx1]
    if tpl.std() < 1e-3:
        return 0, 0, 0.0
    res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(res)
    return loc[0] - s + ox, loc[1] - s + oy, float(mx)


def _ring_ratio(norm, outer, dx, dy, k, level, r_in_mm=0.4, r_out_mm=2.5):
    x0, y0, x1, y1 = outer[0] + dx, outer[1] + dy, outer[2] + dx, outer[3] + dy
    a, b = int(round(r_in_mm * k)), int(round(r_out_mm * k))
    H, W = norm.shape
    X0, Y0, X1, Y1 = max(0, x0 - b), max(0, y0 - b), min(W, x1 + b), min(H, y1 + b)
    roi = norm[Y0:Y1, X0:X1] < level
    m = np.ones(roi.shape, bool)
    m[max(0, y0 - a - Y0):y1 + a - Y0, max(0, x0 - a - X0):x1 + a - X0] = False
    return float(roi[m].mean()) if m.any() else 0.0


def classify(fill, cfg: OMRConfig):
    if fill >= cfg.full_min:
        return "full"
    if fill >= cfg.checked_min:
        return "checked"
    if fill <= cfg.empty_max:
        return "empty"
    return "ambiguous"


def read_page(aligned_img, blank_img, fields, dpi, cfg: OMRConfig | None = None, norm_scan=None):
    """Lit toutes les cases d'une page. Retourne {field_id: résultat}."""
    cfg = cfg or OMRConfig()
    k = px_per_mm(dpi)
    norm_scan = norm_scan if norm_scan is not None else normalize_background(aligned_img, k)
    norm_blank = normalize_background(blank_img, k)
    grilles = [f for f in fields if f["type"] == "digit_grid"]
    omr_fields = [f for f in fields if f["type"] in ("mcq", "truefalse")] + [c for g in grilles for c in colonnes(g)]
    # 1) raffinement local de toutes les cases de la page
    # grille : motif régulier (une case tous les 4,8 mm), une case ou une colonne se recale aussi bien sur sa
    # voisine -> chiffre faux. On recale d'abord la grille entière avec ses en-têtes, puis chaque colonne, puis
    # chaque case, tout près à chaque fois (simulation Midterm, 2 et 5 novembre 2026)
    recal = {g["id"]: recaler_grille(norm_scan, norm_blank, g, dpi, cfg) for g in grilles}
    locs = {}
    for f in omr_fields:
        colonne = (0, 0)
        if f["type"] == "digit_col":
            gdx, gdy = recal[f["grille"]]["decalage"]
            bb = [mm_rect_to_px(o["bbox_mm"], dpi) for o in f["options"]]
            col = (min(b[0] for b in bb), min(b[1] for b in bb), max(b[2] for b in bb), max(b[3] for b in bb))
            cdx, cdy, csc = _locate(norm_scan, norm_blank, col, k, cfg, cfg.search_grille_mm, (gdx, gdy))
            colonne = (cdx, cdy) if csc >= cfg.min_match else (gdx, gdy)
        for o in f["options"]:
            outer = mm_rect_to_px(o["bbox_mm"], dpi)
            if f["type"] == "digit_col":
                dx, dy, sc = _locate(norm_scan, norm_blank, outer, k, cfg, cfg.search_grille_mm, colonne)
            else:
                dx, dy, sc = _locate(norm_scan, norm_blank, outer, k, cfg)
            cx, cy = (outer[0] + outer[2]) / 2, (outer[1] + outer[3]) / 2
            locs[(f["id"], o["id"])] = (dx, dy, sc, cx, cy)
    # 2) champ de déformation lisse : moyenne pondérée (gaussienne, 25 mm) des
    #    recalages fiables voisins -> prédiction pour les cases mal recalées
    #    (case noircie, gribouillée) sans supposer un décalage uniforme
    reliable = [(dx, dy, cx, cy, key) for key, (dx, dy, sc, cx, cy) in locs.items() if sc >= cfg.trust_match]
    sigma = 25.0 * k

    def predict(key, cx, cy):
        w_sum, acc = 0.0, np.zeros(2)
        for dx, dy, x, y, kk in reliable:
            if kk == key:
                continue
            w = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))
            w_sum += w
            acc += w * np.array([dx, dy])
        return acc / w_sum if w_sum > 1e-6 else np.zeros(2)

    out = {}
    for f in omr_fields:
        opts = {}
        for o in f["options"]:
            key = (f["id"], o["id"])
            dx, dy, sc, cx, cy = locs[key]
            used = "local"
            if sc < cfg.trust_match:
                pred = predict(key, cx, cy)
                if sc < cfg.min_match or np.hypot(dx - pred[0], dy - pred[1]) > cfg.max_dev_mm * k:
                    dx, dy = pred
                    used = "voisins"
            dx, dy = int(round(dx)), int(round(dy))
            # grille : cases collées, chaque trait est partagé avec la voisine ; un pixel de décalage met du trait
            # dans la mesure -> marge plus large (mesuré sur la simulation Midterm, 2 novembre 2026)
            inset = max(cfg.inset_mm, cfg.inset_grille_mm) if f["type"] == "digit_col" else cfg.inset_mm
            inner = mm_rect_to_px(o["inner_mm"], dpi, pad_mm=-inset)
            inner_s = (inner[0] + dx, inner[1] + dy, inner[2] + dx, inner[3] + dy)
            fill = _ink_ratio(norm_scan, inner_s, cfg.ink_level) - _ink_ratio(norm_blank, inner, cfg.ink_level)
            fill = max(0.0, fill)
            faint = max(0.0, _ink_ratio(norm_scan, inner_s, cfg.faint_level)
                        - _ink_ratio(norm_blank, inner, cfg.faint_level))
            # halo : encre dans un anneau de 0,4 à 2,5 mm autour de la case.
            # Une croix déborde de quelques traits fins ; une rature (gribouillis
            # d'annulation) déborde en masse.
            outer_px = mm_rect_to_px(o["bbox_mm"], dpi)
            halo = max(0.0, _ring_ratio(norm_scan, outer_px, dx, dy, k, cfg.ink_level)
                       - _ring_ratio(norm_blank, outer_px, 0, 0, k, cfg.ink_level))
            # cœur : carré central (50 % du côté). Une vraie marque (croix, coche, barre)
            # passe par le centre ; une case redessinée après correcteur n'encre que le bord.
            cx, cy = (inner_s[0] + inner_s[2]) // 2, (inner_s[1] + inner_s[3]) // 2
            hw = max(2, (inner_s[2] - inner_s[0]) // 4)
            core = max(0.0, _ink_ratio(norm_scan, (cx - hw, cy - hw, cx + hw, cy + hw), cfg.ink_level)
                       - _ink_ratio(norm_blank, (cx - hw - dx, cy - hw - dy, cx + hw - dx, cy + hw - dy), cfg.ink_level))
            state = classify(fill, cfg)
            border_only = state == "checked" and core < cfg.core_min
            if border_only:
                state = "ambiguous"
            # rature probable : à trancher par un humain. Pas dans une grille : les cases s'y touchent, l'anneau
            # mesure les cases voisines ; une rature y coche deux chiffres d'une colonne -> revue quand même
            if (state in ("checked", "full") and fill >= cfg.rature_min_fill and halo >= cfg.halo_rature
                    and f["type"] != "digit_col"):
                state = "ambiguous"
            if state == "empty" and faint >= cfg.faint_min:
                state = "ambiguous"  # trace claire : crayon, gomme, encre pâle
            # une case vide ressemble à la case vierge (recalage >= 0,77 mesuré) : « vide » sans
            # avoir retrouvé la case, c'est qu'on mesure à côté (page mal alignée) -> revue
            lost = state == "empty" and sc < cfg.min_match
            if lost:
                state = "ambiguous"
            opts[o["id"]] = {
                "label": o.get("label", ""),
                "fill": round(fill, 4),
                "faint": round(faint, 4),
                "halo": round(halo, 4),
                "core": round(core, 4),
                "state": state,
                "shift_px": [dx, dy],
                "match": round(sc, 3),
                "loc": used,
                "lost": lost,
                # les autres cases de la page sont bien recalées : la page est alignée, c'est cette
                # case qui a disparu du scan (recouverte de correcteur, vu sur supNA 2)
                "erased": lost and any(kk != key for *_, kk in reliable),
                "box_px": list(inner_s),
            }
        out[f["id"]] = decide(f, opts, cfg)
    for g in grilles:
        out[g["id"]] = decide_grid(g, {c["colonne"]: out.pop(c["id"]) for c in colonnes(g)}, recal[g["id"]])
    return out


def colonnes(grille):
    """Les colonnes d'une grille de chiffres, comme des QCM à choix unique (une case par chiffre)."""
    return [{"id": f"{grille['id']}.{c['id']}", "colonne": c["id"], "type": "digit_col", "mode": "single",
             "grille": grille["id"], "options": c["options"]} for c in grille["columns"]]


def recaler_grille(norm_scan, norm_blank, grille, dpi, cfg: OMRConfig):
    """Décalage de la grille entière, et s'il est sûr. Le milieu de la grille se répète d'une case à l'autre ;
    le haut (en-têtes C1…) et le bas ne se répètent pas. Les trois recalages doivent concorder, à moins d'une
    fraction de case près, et aucun ne doit buter au bord de la recherche : sinon la grille part en revue
    (copies 4 et 11 de la simulation du 5 novembre : colonnes lues une case trop haut ou trop bas)."""
    k = px_per_mm(dpi)
    bb = [mm_rect_to_px(o["bbox_mm"], dpi) for c in grille["columns"] for o in c["options"]]
    x0, y0, x1, y1 = min(b[0] for b in bb), min(b[1] for b in bb), max(b[2] for b in bb), max(b[3] for b in bb)
    hauteurs = sorted({b[1] for b in bb})
    pas = min((b - a for a, b in zip(hauteurs, hauteurs[1:]) if b - a > 2), default=5 * k)
    largeurs = sorted({b[0] for b in bb})
    pas = min(pas, min((b - a for a, b in zip(largeurs, largeurs[1:]) if b - a > 2), default=pas))
    m, bord = int(round(cfg.marge_grille_mm * k)), int(round(1.5 * k))
    s = int(round(cfg.search_grille_page_mm * k))
    zones = {"grille": (x0 - m, y0 - m, x1 + m, y1 + m),
             "haut": (x0 - m, y0 - m, x1 + m, y0 + bord),
             "bas": (x0 - m, y1 - bord, x1 + m, y1 + m)}
    r = {nom: _locate(norm_scan, norm_blank, z, k, cfg, cfg.search_grille_page_mm) for nom, z in zones.items()}
    dx, dy, _ = r["grille"]
    raisons = []
    for nom, (ex, ey, sc) in r.items():
        if sc <= 0:
            raisons.append(f"{nom} non retrouvé")
        elif max(abs(ex), abs(ey)) >= s:
            raisons.append(f"{nom} au bord de la recherche ({ex}, {ey} px)")
        elif max(abs(ex - dx), abs(ey - dy)) > cfg.accord_grille * pas:
            raisons.append(f"{nom} décalé de ({ex}, {ey}) px, grille de ({dx}, {dy}) px")
    return {"decalage": (dx, dy) if r["grille"][2] > 0 else (0, 0), "sur": not raisons, "raisons": raisons,
            "scores": {nom: round(v[2], 3) for nom, v in r.items()}}


def decide_grid(grille, cols, recalage=None):
    """Assemble les colonnes lues en numéro. « ok » seulement si la grille est sûrement recalée (`recalage`),
    chaque colonne est nette, les chiffres sont contigus depuis la 1re colonne et leur nombre est celui attendu
    (`digits`) ; sinon « review » avec la raison. La valeur garde « ? » à la place d'une colonne douteuse."""
    flags, chiffres, douteux = [], [], False
    if recalage is not None and not recalage["sur"]:
        flags.append("grille mal recalée, chiffres peut-être décalés d'une case : "
                     + "; ".join(recalage["raisons"]))
    for cid, r in cols.items():
        if r["status"] == "review":
            douteux = True
            chiffres.append("?")
            flags.append(f"colonne {cid} : " + "; ".join(r["flags"]))
        else:
            chiffres.append(r["selected"][0] if r["selected"] else "")
    remplies = [d != "" for d in chiffres]
    n = sum(remplies)
    attendu = grille.get("digits")
    if not douteux:
        if n == 0 and not flags:   # grille mal recalée : « vide » n'est pas sûr non plus
            return {"type": "digit_grid", "value": None, "status": "blank", "flags": ["grille vide"], "columns": cols}
        premier_vide = remplies.index(False) if False in remplies else len(remplies)
        if any(remplies[premier_vide:]):
            flags.append("colonne vide au milieu du numéro")
        if attendu and n != attendu:
            flags.append(f"{n} chiffres au lieu de {attendu}")
    return {"type": "digit_grid", "value": "".join(d for d in chiffres if d) or None,
            "status": "review" if flags else "ok", "flags": flags, "columns": cols, "recalage": recalage}


def decide(field, opts, cfg: OMRConfig):
    flags = []
    selected = []
    n_checked = sum(o["state"] == "checked" for o in opts.values())
    full_review = False
    for oid, o in opts.items():
        st = o["state"]
        if st == "checked":
            selected.append(oid)
        elif st == "full":
            policy = cfg.full_policy
            if policy == "auto":
                # noircie sans autre case cochée dans le champ : manière de cocher
                # (observé sur copies réelles) ; à côté d'une case cochée : annulation probable
                policy = "checked" if n_checked == 0 else "review"
            if policy == "checked":
                selected.append(oid)
                flags.append(f"{oid}:noircie (lue cochée)")
            elif policy == "review":
                full_review = True
                flags.append(f"{oid}:noircie à côté d'une case cochée, annulation ?" if n_checked
                             else f"{oid}:noircie, cochée ou annulée ?")
            # "cancelled" : case annulée, ignorée
        elif st == "ambiguous":
            if o.get("lost"):
                why = (f"case non retrouvée, recalage {o['match']:.2f} : "
                       + ("effacée au correcteur ?" if o.get("erased") else "page mal alignée ?"))
            elif o["fill"] >= cfg.rature_min_fill and o.get("halo", 0) >= cfg.halo_rature:
                why = f"rature probable, halo {o['halo']:.2f}"
            elif o["fill"] >= cfg.checked_min and o.get("core", 1) < cfg.core_min:
                why = "encre sur le bord seulement : case corrigée/redessinée ?"
            else:
                why = "trace claire" if o["fill"] <= cfg.empty_max else f"encre {o['fill']:.2f}"
            flags.append(f"{oid}:ambiguë ({why})")
    mode = field.get("mode", "single")
    status = "ok"
    if any(o["state"] == "ambiguous" for o in opts.values()):
        status = "review"
    if full_review:
        status = "review"
    if mode == "single" and len(selected) > 1:
        status = "review"
        flags.append("plusieurs cases cochées (choix unique)")
    if not selected and status == "ok":
        status = "blank"
    # confiance : distance du taux d'encre le plus proche d'un seuil
    margins = []
    for o in opts.values():
        f_ = o["fill"]
        margins.append(min(abs(f_ - cfg.empty_max), abs(f_ - cfg.checked_min)) if cfg.empty_max < f_ < cfg.checked_min
                       else (cfg.empty_max - f_ if f_ <= cfg.empty_max else f_ - cfg.checked_min))
    return {
        "type": field["type"],
        "mode": mode,
        "selected": selected,
        "status": status,
        "flags": flags,
        "min_margin": round(float(min(margins)) if margins else 0.0, 4),
        "options": opts,
    }
