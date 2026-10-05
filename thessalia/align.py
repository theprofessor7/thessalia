"""Alignement : fiducials -> homographie -> identification de page -> page redressée.

Principe
    1. Détecter les 4 carrés noirs (5 mm) dans les coins du scan.
       Ouverture morphologique ~3 mm : le texte, les traits, les grilles et
       l'écriture disparaissent, seuls les aplats épais survivent.
       Filtres : taille (±40 %), carré, plein, ne touche pas le bord de l'image.
       Si un seul fiducial manque (agrafe, pli, tache), il est reconstruit par
       parallélogramme à partir des 3 autres.
    2. Les 4 points étant symétriques, l'orientation (0/90/180/270°) est
       ambiguë : on génère les homographies compatibles avec le ratio du
       rectangle des fiducials, puis
    3. on identifie la page ET l'orientation en comparant une vignette
       redressée (40 dpi) à toutes les pages du sujet vierge (corrélation
       normalisée). Les pages peuvent donc être dans le désordre ou retournées.
    4. On redresse la page à la résolution de référence (200 dpi par défaut)
       dans le repère du PDF vierge : 1 mm du gabarit = ref_dpi/25.4 px.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .common import mm_rect_to_px, normalize_background, px_per_mm

CORNERS = ("tl", "tr", "br", "bl")


@dataclass
class Fiducials:
    points: np.ndarray            # (4,2) px dans le scan, ordre coins image tl,tr,br,bl
    found: list                   # coins réellement détectés
    inferred: list                # coins reconstruits
    candidates: int = 0


@dataclass
class AlignedPage:
    page: int                     # numéro de page du sujet (1-based), 0 si inconnu
    rotation: int                 # rotation détectée du scan (0/90/180/270)
    score: float                  # corrélation avec la page vierge (0..1)
    margin: float                 # écart avec la 2e meilleure page
    image: np.ndarray             # page redressée, niveaux de gris, ref_dpi
    dpi: int
    H: np.ndarray                 # homographie mm(gabarit) -> px(scan)
    fiducials: Fiducials | None = None
    warnings: list = field(default_factory=list)


class AlignmentError(RuntimeError):
    pass


# --------------------------------------------------------------------------- détection
def detect_fiducials(gray: np.ndarray, px_mm: float, size_mm: float = 5.0,
                      rect_mm=(187.0, 264.0)) -> Fiducials:
    work_pxmm = 4.0  # ~100 dpi suffisent pour localiser, on affine ensuite en pleine résolution
    s = min(1.0, work_pxmm / px_mm)
    small = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else gray
    k = px_mm * s
    paper = float(np.percentile(small, 95))
    # 0,62 et non 0,5 : certains scanners (lots Booster) rendent un aplat en gris uniforme à 128 sur
    # un papier à 255, soit exactement 50 % ; le repère était manqué d'un niveau de gris
    thr = 0.62 * paper
    binary = (small < thr).astype(np.uint8)
    ker = max(3, int(round(0.6 * size_mm * k)))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (ker, ker)))

    n, lab, stats, cents = cv2.connectedComponentsWithStats(opened, connectivity=8)
    H, W = small.shape
    exp_side = size_mm * k
    cands = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if x <= 1 or y <= 1 or x + w >= W - 1 or y + h >= H - 1:
            continue  # touche le bord : ombre du scanner
        if not (0.6 * exp_side <= w <= 1.45 * exp_side and 0.6 * exp_side <= h <= 1.45 * exp_side):
            continue
        if not (0.7 <= w / h <= 1.4) or area / float(w * h) < 0.75:
            continue
        cands.append((abs(np.log(w * h / exp_side ** 2)) - area / float(w * h), cents[i] / s))
    cands = [c for _, c in sorted(cands, key=lambda t: t[0])]

    if len(cands) > 16:  # garde les plus « carrés pleins » (rare : page très chargée)
        cands = cands[:16]
    sel, inferred = _select_rectangle(cands, rect_mm)
    if sel is None:
        e = AlignmentError(f"fiducials introuvables ({len(cands)} candidats, aucun rectangle "
                           f"{rect_mm[0]:.0f}x{rect_mm[1]:.0f} mm cohérent)")
        e.candidates = cands  # pour l'alignement de secours sur 2 repères
        raise e
    pts = [p if i in inferred else _refine_center(gray, p, px_mm, size_mm) for i, p in enumerate(sel)]
    return Fiducials(np.array(pts, np.float64), [CORNERS[i] for i in range(4) if i not in inferred],
                     [CORNERS[i] for i in inferred], len(cands))


def _clockwise(P):
    """Ordonne 4 points dans le sens horaire (repère image), en commençant par le plus haut-gauche."""
    P = np.asarray(P, np.float64)
    c = P.mean(axis=0)
    P = P[np.argsort(np.arctan2(P[:, 1] - c[1], P[:, 0] - c[0]))]
    start = int(np.argmin(P[:, 0] + P[:, 1]))
    return np.roll(P, -start, axis=0)


def _select_rectangle(cands, rect_mm, max_err=0.12):
    """Choisit les candidats formant le rectangle des fiducials, où qu'il soit dans l'image.

    Indépendant de la position et de l'orientation de la feuille (feuille A4 dans
    un scan A3, page couchée, marges du plateau) et de la résolution déclarée.
    Retourne (4 points ordonnés, indices reconstruits) ou (None, []).
    """
    from itertools import combinations

    ratio = max(rect_mm) / min(rect_mm)
    pts = [np.asarray(p, np.float64) for p in cands]
    best, best_err = None, max_err
    for combo in combinations(range(len(pts)), 4):
        P = _clockwise([pts[i] for i in combo])
        s = [np.linalg.norm(P[(i + 1) % 4] - P[i]) for i in range(4)]
        d = [np.linalg.norm(P[2] - P[0]), np.linalg.norm(P[3] - P[1])]
        l1, l2 = (s[0] + s[2]) / 2, (s[1] + s[3]) / 2
        if min(l1, l2) < 1:
            continue
        err = (abs(s[0] - s[2]) / l1 + abs(s[1] - s[3]) / l2 + abs(d[0] - d[1]) / np.mean(d)
               + abs(max(l1, l2) / min(l1, l2) - ratio) / ratio)
        if err < best_err:
            best, best_err = P, err
    if best is not None:
        return best, []
    # 3 fiducials : angle droit au sommet commun, côtés dans le bon rapport
    for combo in combinations(range(len(pts)), 3):
        for c in range(3):
            C = pts[combo[c]]
            A, B = (pts[combo[j]] for j in range(3) if j != c)
            u, v = A - C, B - C
            nu, nv = np.linalg.norm(u), np.linalg.norm(v)
            if min(nu, nv) < 1:
                continue
            err = abs(np.dot(u, v) / (nu * nv)) + abs(max(nu, nv) / min(nu, nv) - ratio) / ratio
            if err < best_err:
                best, best_err = (A, B, C, A + B - C), err
    if best is None:
        return None, []
    D = best[3]
    P = _clockwise(best)
    idx = int(np.argmin(np.linalg.norm(P - D, axis=1)))
    return P, [idx]


def _rectangles_from_pair(A, B, rect_mm, px_mm, tol=0.08):
    """Rectangles des fiducials compatibles avec 2 repères seulement (feuille passée de travers,
    deux coins hors du scan). La distance A-B doit être un côté ou la diagonale à l'échelle du scan ;
    chaque cas laisse deux rectangles possibles (de part et d'autre). Un scan n'est jamais en miroir.
    Retourne [(4 points horaires, indices des 2 points réels)]."""
    A, B = np.asarray(A, np.float64), np.asarray(B, np.float64)
    d = np.linalg.norm(B - A)
    if d < 1:
        return []
    u = (B - A) / d
    w, h = rect_mm
    out = []

    def add(C, D):
        P = _clockwise([A, B, C, D])
        real = [int(np.argmin(np.linalg.norm(P - X, axis=1))) for X in (A, B)]
        out.append((P, real))

    for side, other in ((w, h), (h, w)):
        s = d / side
        if abs(s / px_mm - 1) <= tol:
            for sign in (1, -1):
                n = sign * np.array([-u[1], u[0]]) * s * other
                add(B + n, A + n)
    s = d / np.hypot(w, h)
    if abs(s / px_mm - 1) <= tol:
        for a in (np.arctan2(h, w), -np.arctan2(h, w)):
            C = A + np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]) @ u * s * w
            add(C, A + B - C)
    return out


def _refine_center(gray, p, px_mm, size_mm):
    """Centre sous-pixel : barycentre des pixels sombres autour du point estimé."""
    r = int(round(size_mm * px_mm))
    x0, y0 = int(p[0]) - r, int(p[1]) - r
    x0c, y0c = max(0, x0), max(0, y0)
    roi = gray[y0c:int(p[1]) + r, x0c:int(p[0]) + r]
    if roi.size == 0:
        return np.asarray(p, np.float64)
    _, b = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ker = max(3, int(0.5 * size_mm * px_mm))
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (ker, ker)))
    n, lab, stats, cents = cv2.connectedComponentsWithStats(b)
    if n < 2:
        return np.asarray(p, np.float64)
    local = np.asarray(p) - (x0c, y0c)
    i = min(range(1, n), key=lambda i: np.hypot(*(cents[i] - local)) - 0.001 * stats[i][4])
    return cents[i] + (x0c, y0c)


# --------------------------------------------------------------------------- références
class ReferenceSet:
    """Pages vierges du sujet rendues à la résolution de référence + empreintes.

    Identification de page : on compare l'« encre imprimée » (obscurité après
    normalisation du fond) de la page vierge et du scan redressé, à 50 dpi,
    avec une tolérance de ±1,2 mm (dilatation) :
        rappel    = part de l'encre de la page vierge retrouvée dans le scan
        précision = part de l'encre du scan expliquée par la page vierge
        score     = F1 des deux
    Les zones où l'étudiant écrit sont masquées. Cette mesure est tolérante
    aux petits décalages (papier gondolé) et discriminante sur le texte, là où
    une corrélation globale est dominée par les éléments communs à toutes les
    pages (fiducials, en-tête, blanc).
    """

    MATCH_DPI = 50
    TOL_MM = 1.2

    def __init__(self, template: dict, blank_pages: list[np.ndarray], dpi: int):
        self.template = template
        self.dpi = dpi
        self.pages = blank_pages
        self.size_mm = template["page_size_mm"]
        fm = template["fiducials_mm"]
        self.fid_mm = np.array([fm[c] for c in CORNERS], np.float64)
        mshape = self.shape(self.MATCH_DPI)
        self.dark, self.dark_dil, self.masks = [], [], []
        for i, p in enumerate(blank_pages):
            t = cv2.resize(p, (mshape[1], mshape[0]), interpolation=cv2.INTER_AREA)
            d = self.darkness(t)
            m = self._mask(i + 1, mshape, self.MATCH_DPI)
            self.dark.append(d * m)
            self.dark_dil.append(self.dilate(d))
            self.masks.append(m)
        # 2e passe : tuiles de texte imprimé à 100 dpi, recalées localement
        self.tiles = [self._make_tiles(p, i + 1) for i, p in enumerate(blank_pages)]

    FINE_DPI = 100
    TILE_MM = (24.0, 10.0)
    SEARCH_MM = 2.5

    @classmethod
    def fine_prep(cls, img):
        n = normalize_background(img, px_per_mm(cls.FINE_DPI))
        return cv2.GaussianBlur(n, (0, 0), 0.8)

    def _make_tiles(self, page_img, page_no, max_tiles=48):
        fshape = self.shape(self.FINE_DPI)
        img = self.fine_prep(cv2.resize(page_img, (fshape[1], fshape[0]), interpolation=cv2.INTER_AREA))
        mask = self._mask(page_no, fshape, self.FINE_DPI)
        k = px_per_mm(self.FINE_DPI)
        tw, th = int(self.TILE_MM[0] * k), int(self.TILE_MM[1] * k)
        s = int(self.SEARCH_MM * k)
        tiles = []
        y = int(24 * k)  # sous l'en-tête courant (identique sur toutes les pages)
        while y + th + s < fshape[0]:
            x = int(15 * k)
            while x + tw + s < fshape[1] - int(15 * k):
                t = img[y:y + th, x:x + tw]
                if mask[y:y + th, x:x + tw].min() > 0:
                    ink = float((t < 0.7).mean())
                    if 0.03 < ink < 0.6 and t.std() > 0.08:
                        tiles.append((ink, x, y, t.copy()))
                x += tw
            y += th
        tiles.sort(key=lambda t: -t[0])
        return [(x, y, t) for _, x, y, t in tiles[:max_tiles]]

    def fine_score(self, scan_fine, page_idx):
        s = int(self.SEARCH_MM * px_per_mm(self.FINE_DPI))
        vals = []
        for x, y, t in self.tiles[page_idx]:
            roi = scan_fine[y - s:y + t.shape[0] + s, x - s:x + t.shape[1] + s]
            if roi.shape[0] < t.shape[0] or roi.shape[1] < t.shape[1]:
                continue
            vals.append(float(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max()))
        return float(np.median(vals)) if vals else 0.0

    @classmethod
    def darkness(cls, img):
        n = normalize_background(img, px_per_mm(cls.MATCH_DPI))
        d = 1.0 - cv2.GaussianBlur(n, (0, 0), 0.7)
        d[d < 0.08] = 0  # bruit, grain du papier
        return d.astype(np.float32)

    @classmethod
    def dilate(cls, d):
        r = max(1, int(round(cls.TOL_MM * px_per_mm(cls.MATCH_DPI))))
        return cv2.dilate(d, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))

    def _mask(self, page_no, shape, dpi):
        m = np.ones(shape, np.float32)
        zones = [[95, 8, 110, 16]]  # "Nom / Prénom" manuscrits de l'en-tête courant
        page = next((p for p in self.template["pages"] if p["page"] == page_no), {"fields": []})
        for f in page["fields"]:
            if "bbox_mm" in f:
                zones.append(f["bbox_mm"])
            for o in f.get("options", []):
                zones.append(o["bbox_mm"])
        for z in zones:
            x0, y0, x1, y1 = mm_rect_to_px(z, dpi, pad_mm=2.5)
            m[max(0, y0):y1, max(0, x0):x1] = 0
        return m

    def shape(self, dpi):
        k = px_per_mm(dpi)
        return int(round(self.size_mm[1] * k)), int(round(self.size_mm[0] * k))

    def match(self, d_scan, d_scan_dil, page_idx):
        m = self.masks[page_idx]
        ds = d_scan * m
        ref = self.dark[page_idx]
        recall = float(np.minimum(ref, d_scan_dil).sum() / max(ref.sum(), 1e-6))
        precision = float(np.minimum(ds, self.dark_dil[page_idx]).sum() / max(ds.sum(), 1e-6))
        return 2 * recall * precision / max(recall + precision, 1e-6)


def _warp(gray, H_mm2px, dpi, shape):
    k = px_per_mm(dpi)
    S_inv = np.diag([1 / k, 1 / k, 1.0])
    M = H_mm2px @ S_inv  # ref px -> scan px
    return cv2.warpPerspective(gray, M, (shape[1], shape[0]), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def align_page(gray: np.ndarray, px_mm: float, ref: ReferenceSet, expected_page: int | None = None,
               min_score: float = 0.6) -> AlignedPage:
    # pré-réduction proche de la résolution de référence (anti-crénelage)
    ref_pxmm = px_per_mm(ref.dpi)
    scale = 1.0
    if px_mm > 1.3 * ref_pxmm:
        scale = ref_pxmm / px_mm
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        px_mm *= scale

    size_mm = ref.template.get("fiducial_size_mm", 5.0)
    F = ref.fid_mm
    rect_mm = (np.linalg.norm(F[1] - F[0]), np.linalg.norm(F[2] - F[1]))
    two = None
    try:
        fid = detect_fiducials(gray, px_mm, size_mm, rect_mm)
    except AlignmentError as err:
        # résolution déclarée fausse (photo, PDF mal paginé) : on la ré-estime en supposant un A4
        h_, w_ = gray.shape
        est = 0.5 * (max(h_, w_) / 297.0 + min(h_, w_) / 210.0)
        fid = None
        if abs(est / px_mm - 1) >= 0.1:
            try:
                fid = detect_fiducials(gray, est, size_mm, rect_mm)
            except AlignmentError:
                pass
        if fid is None:
            two = _align_on_two(gray, px_mm, size_mm, rect_mm, ref, expected_page,
                                getattr(err, "candidates", []))
            if two is None:
                raise err
            fid = two[0]
    sc, page, rot, H, margin = two[1] if two else _identify(gray, fid.points, ref, expected_page)

    # Faux fiducial (agrafe, coin plié, tache carrée) : les 4 points ne ferment plus le
    # parallélogramme. On essaie de reconstruire chaque coin à partir des 3 autres et on garde
    # la variante si le texte imprimé se recale nettement mieux. Une vraie perspective (photo)
    # ouvre aussi le parallélogramme, mais l'homographie à 4 points y reste la meilleure.
    P = fid.points
    if not fid.inferred and np.linalg.norm(P[0] + P[2] - P[1] - P[3]) > CLOSURE_MM * px_mm:
        fshape = ref.shape(ReferenceSet.FINE_DPI)
        k = (4 - rot // 90) % 4
        best_fix = None
        for drop in range(4):
            Q = P.copy()
            Q[drop] = P[(drop + 1) % 4] + P[(drop - 1) % 4] - P[(drop + 2) % 4]
            fine = ReferenceSet.fine_prep(_warp(gray, _homography(Q, ref.fid_mm, k), ReferenceSet.FINE_DPI, fshape))
            s = ref.fine_score(fine, page - 1)
            if best_fix is None or s > best_fix[0]:
                best_fix = (s, drop, Q)
        fine4 = ReferenceSet.fine_prep(_warp(gray, H, ReferenceSet.FINE_DPI, fshape))
        if best_fix[0] > ref.fine_score(fine4, page - 1) + FIX_GAIN:
            _, drop, Q = best_fix
            fid.points = Q
            fid.inferred = [CORNERS[drop]]
            fid.found = [c for c in CORNERS if c != CORNERS[drop]]
            sc, page, rot, H, margin = _identify(gray, Q, ref, expected_page)

    if fid.inferred:
        # coin reconstruit par parallélogramme : approximatif (perspective, papier déformé près de
        # l'agrafe) -> on recale l'homographie sur le texte imprimé de la page
        H = _refine_on_text(gray, H, ref, page, fid, px_mm)

    warnings = []
    if two:
        # secours : jamais sans revue. Ce qui est hors du scan serait sinon lu « vide » en silence.
        seen =_warp(np.zeros_like(gray), H, ref.dpi, ref.shape(ref.dpi)) == 0
        out_pct = 100.0 * (1.0 - float(seen.mean()))
        if sc < TWO_MIN_SCORE:
            raise AlignmentError(f"fiducials introuvables (2 repères seulement, alignement de secours "
                                 f"trop peu ressemblant : {sc:.2f})")
        warnings.append(f"alignement de secours sur 2 repères ({','.join(fid.found)}) : page à vérifier"
                        + (f", {out_pct:.0f} % de la page hors du scan" if out_pct >= 0.5 else ""))
    elif fid.inferred:
        warnings.append(f"fiducial {','.join(fid.inferred)} reconstruit")
    if sc < min_score:
        warnings.append(f"ressemblance faible avec la page vierge ({sc:.2f})")
    if margin < 0.05 and page != expected_page:  # confirmé par la séquence -> pas d'alerte
        warnings.append(f"identification de page incertaine (marge {margin:.2f})")
    if expected_page and page != expected_page:
        warnings.append(f"page {page} reçue, page {expected_page} attendue dans la séquence")

    img = _warp(gray, H, ref.dpi, ref.shape(ref.dpi))
    if scale != 1.0:  # H exprimée pour l'image réduite -> la ramener au scan d'origine
        H = np.diag([1 / scale, 1 / scale, 1.0]) @ H
        fid.points = fid.points / scale
    return AlignedPage(page, rot, sc, margin, img, ref.dpi, H, fid, warnings)


CLOSURE_MM = 1.0   # défaut de fermeture du parallélogramme des fiducials au-delà duquel on doute d'un coin
FIX_GAIN = 0.05    # gain mini du score de texte pour préférer un coin reconstruit
TWO_MIN_SCORE = 0.75  # alignement de secours sur 2 repères : ressemblance mini avec la page vierge


def _align_on_two(gray, px_mm, size_mm, rect_mm, ref: ReferenceSet, expected_page, cands):
    """Secours quand seuls 2 repères sont visibles : on essaie chaque paire de candidats dont la
    distance est un côté ou la diagonale du rectangle, et on garde le rectangle dont la page
    redressée ressemble le plus au sujet. Retourne (Fiducials, résultat de `_identify`) ou None."""
    from itertools import combinations

    h_, w_ = gray.shape
    best = None
    for i, j in combinations(range(len(cands)), 2):
        A, B = (_refine_center(gray, cands[x], px_mm, size_mm) for x in (i, j))
        for P, real in _rectangles_from_pair(A, B, rect_mm, px_mm):
            c = P.mean(axis=0)
            if not (0 <= c[0] < w_ and 0 <= c[1] < h_):
                continue  # rectangle centré hors de l'image : mauvais côté
            try:
                res = _identify(gray, P, ref, expected_page)
            except AlignmentError:
                continue
            if best is None or res[0] > best[1][0]:
                best = (Fiducials(P, [CORNERS[x] for x in sorted(real)],
                                  [CORNERS[x] for x in range(4) if x not in real], len(cands)), res)
    return best


def _homography(P, fid_mm, k):
    """Homographie mm(gabarit) -> px(scan) si le coin image i est le coin gabarit (i+k)%4."""
    T = fid_mm.astype(np.float32)
    Tk = np.array([T[(i + k) % 4] for i in range(4)], np.float32)
    return cv2.getPerspectiveTransform(Tk, np.asarray(P, np.float32))


def _refine_on_text(gray, H, ref: ReferenceSet, page, fid: Fiducials, px_mm, min_match=0.6, min_points=8):
    """Réestime l'homographie à partir des tuiles de texte imprimé (+ les fiducials détectés).

    Chaque tuile de la page vierge est retrouvée dans la page redressée (±2,5 mm) : son décalage
    donne un point de correspondance gabarit (mm) -> scan (px). Retourne H inchangée si les
    correspondances sont trop peu nombreuses ou si le texte ne se recale pas mieux.
    """
    k = px_per_mm(ReferenceSet.FINE_DPI)
    s = int(ReferenceSet.SEARCH_MM * k)
    fshape = ref.shape(ReferenceSet.FINE_DPI)
    fine = ReferenceSet.fine_prep(_warp(gray, H, ReferenceSet.FINE_DPI, fshape))
    src, dst = [], []
    for x, y, t in ref.tiles[page - 1]:
        roi = fine[y - s:y + t.shape[0] + s, x - s:x + t.shape[1] + s]
        if roi.shape[0] < t.shape[0] or roi.shape[1] < t.shape[1]:
            continue
        _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED))
        if mx < min_match:
            continue
        c = np.array([x + t.shape[1] / 2, y + t.shape[0] / 2]) / k               # centre, mm gabarit
        seen = c + (np.array(loc, np.float64) - s) / k                             # où il est vu, mm
        src.append(c)
        dst.append(cv2.perspectiveTransform(seen.reshape(1, 1, 2), H).ravel())    # px du scan
    if len(src) < min_points:
        return H
    n_tiles = len(src)
    for i, c in enumerate(CORNERS):
        if c in fid.found:  # coin image i -> point gabarit que H lui associe
            src.append(cv2.perspectiveTransform(fid.points[i].reshape(1, 1, 2), np.linalg.inv(H)).ravel())
            dst.append(fid.points[i])
    H2, inl = cv2.findHomography(np.array(src, np.float64), np.array(dst, np.float64), cv2.RANSAC, 0.5 * px_mm)
    if H2 is None or int(inl[:n_tiles].sum()) < min_points:
        return H
    fine2 = ReferenceSet.fine_prep(_warp(gray, H2, ReferenceSet.FINE_DPI, fshape))
    return H2 if ref.fine_score(fine2, page - 1) >= ref.fine_score(fine, page - 1) else H


def _identify(gray, points, ref: ReferenceSet, expected_page):
    """Page et orientation pour 4 fiducials donnés. Retourne (score, page, rotation, H, marge)."""
    P = np.asarray(points, np.float32)
    T = ref.fid_mm.astype(np.float32)
    t_ratio = np.linalg.norm(T[1] - T[0]) / np.linalg.norm(T[2] - T[1])

    cands = []
    for k in range(4):  # P[i] (coin image i) correspond au coin gabarit (i+k)%4
        Tk = np.array([T[(i + k) % 4] for i in range(4)], np.float32)
        p_ratio = np.linalg.norm(P[1] - P[0]) / np.linalg.norm(P[2] - P[1])
        tk_ratio = np.linalg.norm(Tk[1] - Tk[0]) / np.linalg.norm(Tk[2] - Tk[1])
        if abs(np.log(p_ratio / tk_ratio)) > 0.12:
            continue
        cands.append(((4 - k) % 4 * 90, _homography(P, ref.fid_mm, k)))
    if not cands:
        raise AlignmentError(f"géométrie des fiducials incohérente (ratio {t_ratio:.3f} attendu)")

    mshape = ref.shape(ReferenceSet.MATCH_DPI)
    scores = []  # (score, page, rot, H)
    for rot, H in cands:
        d = ReferenceSet.darkness(_warp(gray, H, ReferenceSet.MATCH_DPI, mshape))
        dd = ReferenceSet.dilate(d)
        for pi in range(len(ref.pages)):
            scores.append((ref.match(d, dd, pi), pi + 1, rot, H))
    scores.sort(key=lambda t: -t[0])
    # 2e passe (texte, recalage local) sur les meilleurs candidats + la page attendue
    short = scores[:4]
    if expected_page and all(t[1] != expected_page for t in short):
        short.append(next(t for t in scores if t[1] == expected_page))
    fshape = ref.shape(ReferenceSet.FINE_DPI)
    cache, rescored = {}, []
    for s0, p, rot, H in short:
        if rot not in cache:
            cache[rot] = ReferenceSet.fine_prep(_warp(gray, H, ReferenceSet.FINE_DPI, fshape))
        rescored.append((0.25 * s0 + 0.75 * ref.fine_score(cache[rot], p - 1), p, rot, H))
    scores = sorted(rescored, key=lambda t: -t[0])
    best = scores[0]
    # a priori de séquence : à quasi-égalité, on préfère la page attendue
    if expected_page:
        exp = next((t for t in scores if t[1] == expected_page), None)
        if exp and exp[0] >= best[0] - 0.02:
            best = exp
    sc, page, rot, H = best
    others = [s for s, p, r, _ in scores if p != page]
    margin = sc - max(others) if others else sc
    return sc, page, rot, H, margin
