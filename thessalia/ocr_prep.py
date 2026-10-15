"""Niveau 2 — préparation des vignettes de réponses courtes.

Pour chaque blanc :
    1. découpe de la zone sur la page redressée ET sur la page vierge ;
    2. recalage local de la vignette vierge (±2 mm) : la feuille gondolée
       décale le texte imprimé d'1 mm ou plus ;
    3. masque de l'impression = encre de la vierge dilatée (0,5 mm) ;
       encre étudiant = encre du scan hors de ce masque. Le soulignement, le
       texte de la ligne du dessus, la consigne disparaissent ;
    4. vide ? (très peu d'encre étudiant) -> statut "blank" sans OCR ;
    5. recadrage sur l'encre + marge, image propre (encre noire sur blanc)
       prête pour n'importe quel moteur.

Les traits d'écriture qui croisent le soulignement sont coupés là où ils le
touchent ; c'est sans conséquence pour la lecture (quelques pixels).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .common import clip_box, mm_rect_to_px, normalize_background, px_per_mm


@dataclass
class PrepConfig:
    pad_mm: float = 1.0          # marge autour de la zone du gabarit
    up_mm: float = 3.0           # l'écriture dépasse souvent au-dessus de la zone
    search_mm: float = 2.0       # recalage local de la vignette vierge
    ink_level: float = 0.62      # pixel encre si < 62 % du papier
    mask_dilate_mm: float = 0.5  # tolérance autour de l'impression
    blank_ink_mm2: float = 1.5   # moins de 1,5 mm² d'encre étudiant -> vide
    out_margin_mm: float = 1.0
    above_mm: float = 4.5        # bas du tracé au plus 4,5 mm au-dessus du soulignement
    center_mm: float = 4.2       # ... et centre du tracé au plus 4,2 mm au-dessus
    clip_mm: float = 6.0         # rien au-delà de 6 mm au-dessus du soulignement (ligne du dessus)
    # recoller les tracés coupés par le soulignement : désactivé par défaut. Mesuré sur le lot EN
    # (TrOCR base) : 200 -> 227 réponses acceptées mais 1 -> 3 erreurs acceptées (cf. HANDOFF §3)
    bridge_line: bool = False
    bridge_mm: float = 0.4       # tracé qui traverse la ligne : décalage toléré entre l'entrée et la sortie


def mark_stacking(fields):
    """Indique pour chaque blanc s'il a une ligne de réponse juste au-dessus (< 10 mm)."""
    shorts = [f for f in fields if f.get("type") == "short_text" and "line_mm" in f]
    for f in shorts:
        x, y, w, h = f["line_mm"]
        f["_has_above"] = any(
            g is not f and g["page"] == f["page"] and 0 < y - g["line_mm"][1] < 10
            and min(x + w, g["line_mm"][0] + g["line_mm"][2]) - max(x, g["line_mm"][0]) > 5
            for g in shorts)
    return fields


def _grow_vertical(seed, allowed, steps, down=True):
    """Prolonge `seed` colonne par colonne (vers le bas ou le haut) tant qu'on reste dans `allowed`."""
    out = seed.copy()
    for _ in range(steps):
        nxt = np.zeros_like(out)
        if down:
            nxt[1:] = out[:-1]
        else:
            nxt[:-1] = out[1:]
        nxt &= allowed
        if not (nxt & ~out).any():
            break
        out |= nxt
    return out


def _bridge_line(ink, scan_ink, printed_raw, printed, r, k, cfg):
    """Recolle les tracés qui croisent l'impression (le soulignement surtout).

    Le masque de l'impression est dilaté de 0,5 mm : un jambage qui traverse la ligne est coupé
    sur ~1,3 mm et son bout reste détaché dessous (lu comme un point), le bas d'un chiffre posé
    sur la ligne est rogné. On rend à l'étudiant, colonne par colonne :
      - l'encre du scan dans la marge de dilatation, dans le prolongement d'un tracé ;
      - l'épaisseur de la ligne elle-même, seulement là où un tracé arrive dessus ET repart dessous.
    """
    ink = ink.astype(bool)
    core = cv2.dilate(printed_raw.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0  # impression ± 1 px
    halo = (printed > 0) & ~core & scan_ink
    steps = 2 * r + 2
    ext = _grow_vertical(ink, halo | ink, steps, True) | _grow_vertical(ink, halo | ink, steps, False)
    thick = int(round(1.0 * k)) + 2  # une ligne imprimée fait moins de 1 mm
    inside = core & scan_ink
    down = _grow_vertical(ext, inside | ext, thick, True) & inside
    up = _grow_vertical(ext, inside | ext, thick, False) & inside
    t = max(1, int(round(cfg.bridge_mm * k)))
    kh = np.ones((1, 2 * t + 1), np.uint8)
    wide = lambda m: cv2.dilate(m.astype(np.uint8), kh) > 0  # un jambage oblique ne ressort pas à la verticale
    bridge = (down & wide(up)) | (up & wide(down))
    return (ext | bridge).astype(np.uint8)


def prepare_field(aligned_img, blank_img, field, dpi, cfg: PrepConfig | None = None, norm_scan=None,
                  norm_blank=None):
    """Retourne dict(blank: bool, ink_mm2, clean: image uint8 | None, raw: image uint8, box_px)."""
    cfg = cfg or PrepConfig()
    k = px_per_mm(dpi)
    x, y, w, h = field["bbox_mm"]
    zone = [x - cfg.pad_mm, y - cfg.pad_mm - cfg.up_mm, w + 2 * cfg.pad_mm, h + 2 * cfg.pad_mm + cfg.up_mm]
    box = clip_box(mm_rect_to_px(zone, dpi), aligned_img.shape)
    x0, y0, x1, y1 = box
    ns = norm_scan if norm_scan is not None else normalize_background(aligned_img, k)
    nb = norm_blank if norm_blank is not None else normalize_background(blank_img, k)
    scan_n = ns[y0:y1, x0:x1]
    # vignette vierge un peu plus grande pour pouvoir la décaler
    s = int(round(cfg.search_mm * k))
    bx0, by0, bx1, by1 = clip_box((x0 - s, y0 - s, x1 + s, y1 + s), blank_img.shape)
    big = np.ones((y1 - y0 + 2 * s, x1 - x0 + 2 * s), np.float32)
    big[by0 - (y0 - s):by1 - (y0 - s), bx0 - (x0 - s):bx1 - (x0 - s)] = nb[by0:by1, bx0:bx1]
    # recalage : on cherche où la zone du scan se place dans la grande vignette vierge
    res = cv2.matchTemplate(big, scan_n, cv2.TM_CCOEFF_NORMED) if scan_n.std() > 1e-3 else None
    if res is not None:
        _, _, _, loc = cv2.minMaxLoc(res)
        ox, oy = loc
    else:
        ox, oy = s, s
    blank_n = big[oy:oy + scan_n.shape[0], ox:ox + scan_n.shape[1]]

    printed = (blank_n < 0.8).astype(np.uint8)
    r = max(1, int(round(cfg.mask_dilate_mm * k)))
    printed = cv2.dilate(printed, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    ink = (scan_n < cfg.ink_level) & (printed == 0)
    ink = ink.astype(np.uint8)
    if cfg.bridge_line and "line_mm" in field:
        ink = _bridge_line(ink, scan_n < cfg.ink_level, blank_n < 0.8, printed, r, k, cfg)
    # bruit isolé (poussière, grain) : composantes minuscules
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    min_area = max(2, int(0.04 * k * k))  # 0,04 mm²
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    ink = keep[lab].astype(np.uint8)
    # n'appartient à ce champ que ce qui repose sur SON soulignement : le bas du tracé
    # doit être à moins de `above_mm` au-dessus de la ligne (les lignes sont espacées
    # de 8 mm ; le bas de la réponse précédente est ~8 mm plus haut)
    if "line_mm" in field:
        lx, ly, lw, lh = field["line_mm"]
        base = (ly + lh) * k - y0
        stacked = field.get("_has_above", True)  # une ligne de réponse juste au-dessus ?
        above = cfg.above_mm if stacked else 9.0
        center_lim = cfg.center_mm if stacked else 9.0
        n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
        keep = np.zeros(n, bool)
        for i in range(1, n):
            top, hh = stats[i, cv2.CC_STAT_TOP], stats[i, cv2.CC_STAT_HEIGHT]
            bottom, center = top + hh, top + hh / 2
            if top > base + 2.0 * k:
                continue
            if bottom >= base - 2.0 * k:          # repose sur SA ligne : gardé (rogné plus bas)
                keep[i] = True
            elif bottom >= base - above * k and center >= base - center_lim * k:
                keep[i] = True                     # point sur un i, accent, chiffre un peu haut
        dropped = (keep[lab] == 0) & (lab > 0)
        ink = keep[lab].astype(np.uint8)
        if stacked:  # un tracé attaché à la réponse du dessus : on coupe ce qui la rejoint
            cut = int(max(0, base - cfg.clip_mm * k))
            ink[:cut] = 0
    else:
        dropped = np.zeros_like(ink, bool)

    ink_mm2 = float(ink.sum()) / (k * k)
    raw = (np.clip(scan_n, 0, 1) * 255).astype(np.uint8)
    out = {"box_px": [x0, y0, x1, y1], "ink_mm2": round(ink_mm2, 2), "raw": raw,
           "shift_px": [int(ox - s), int(oy - s)]}
    if ink_mm2 < cfg.blank_ink_mm2:
        # vide... sauf s'il y a de l'écriture écartée (réponse écrite trop haut, sur deux
        # lignes) : on ne déclare jamais « vide » une zone qui contient de l'encre étudiant
        dropped_mm2 = float(dropped.sum()) / (k * k)
        out.update(blank=True, clean=None, suspect=dropped_mm2 >= cfg.blank_ink_mm2,
                   dropped_mm2=round(dropped_mm2, 2))
        return out
    # image propre : niveaux de gris du scan là où il y a de l'encre étudiant (anti-crénelage conservé)
    soft = cv2.dilate(ink, np.ones((3, 3), np.uint8))
    clean = np.where(soft > 0, scan_n, 1.0)
    ys, xs = np.nonzero(ink)
    m = int(round(cfg.out_margin_mm * k))
    cy0, cy1 = max(0, ys.min() - m), min(ink.shape[0], ys.max() + m + 1)
    cx0, cx1 = max(0, xs.min() - m), min(ink.shape[1], xs.max() + m + 1)
    clean = (np.clip(clean[cy0:cy1, cx0:cx1], 0, 1) * 255).astype(np.uint8)
    out.update(blank=False, clean=clean)
    return out


def extra_word(clean, gap=0.6, width=1.0, share=0.30):
    """Écriture séparée en plus d'un mot : vrai si la vignette nettoyée contient, à côté du groupe d'encre
    principal, un second groupe séparé d'un espace d'au moins `gap` × la hauteur d'écriture, large d'au
    moins `width` × cette hauteur et portant au moins `share` de l'encre.

    Sert à refuser l'acceptation d'un mot seul quand l'étudiant en a écrit deux : sur supA 2, « Grand Petit »
    lu « Grand » par TrOCR était accepté (juste) alors que la réponse est fausse. Mesuré sur les acceptées
    de EN, supA 1 et supA 2 (372) : ce cas et 3 autres repérés (deux ratures devant `ERREUR` / `ERROR`, un
    « Ze ro » en deux morceaux) ; les petits résidus (points, traits, jusqu'à 0,3 × la hauteur) ne comptent pas.
    """
    ink = clean < 128
    rows = np.where(ink.any(1))[0]
    if not len(rows):
        return False
    h = rows[-1] - rows[0] + 1
    xs = np.where(ink.any(0))[0]
    groups, start, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x - prev - 1 >= gap * h:
            groups.append((start, prev))
            start = x
        prev = x
    groups.append((start, prev))
    if len(groups) < 2:
        return False
    total = ink.sum()
    second = sorted(groups, key=lambda g: -int(ink[:, g[0]:g[1] + 1].sum()))[1]
    return (second[1] - second[0] + 1) >= width * h and ink[:, second[0]:second[1] + 1].sum() >= share * total
