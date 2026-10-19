"""Niveau 2 — détecteur dédié au séparateur décimal : point ou virgule ?

En Python « 2,5 » est une faute (un tuple), « 2.5 » est juste. Les lecteurs (TrOCR, lecteur de chiffres)
distinguent mal ce petit signe. Ce module cherche le signe sur la vignette et estime P(virgule) :

    1. vignette nettoyée (`clean`, cf. ocr_prep) : composantes connexes ; les chiffres sont les grandes
       composantes, leur hauteur médiane `h` sert d'unité, leur bas médian de ligne de base ;
    2. le séparateur est l'encre isolée entre deux chiffres voisins, dans la moitié basse (le bon intervalle
       est donné par la lecture du moteur quand elle contient un séparateur) ;
    3. traits en unités de `h` : hauteur, largeur, allongement, remplissage, inclinaison, position par
       rapport à la ligne de base, queue vers la gauche… ;
    4. vignette BRUTE (`crop`) : le nettoyage efface une bande d'environ 1 mm autour du soulignement, là où
       passe justement la queue d'une virgule. On recale la vignette nettoyée dans la brute et on regarde si
       le signe descend jusqu'au soulignement et s'il en ressort dessous ;
    5. régression logistique régularisée (numpy seul), apprise sur les décimaux vérifiés par l'enseignant,
       réentraînable en quelques secondes : `python -m thessalia separateur <dossiers> --save image`.

Trois modèles possibles (`kind`) : « image » (traits ci-dessus), « lecteur » (scores des candidats TrOCR
avec virgule / avec point, recalibrés), « image+lecteur » (les deux).

    det = Separateur.load()                                        # data/models/separateur.npz (hors dépôt)
    r = det.predict(clean=img_clean, crop=img_brute, candidates=ocr["candidates"], apres=1)
    r -> {"p_virgule": 0.93, "decision": "," | "." | None, "trouve": True, "raison": "..."}

`decision` n'est donnée qu'en dehors de ]bas, haut[ ; les seuils enregistrés sont les plus larges que la
validation croisée par classe a montrés SANS AUCUNE erreur (et 0/1, jamais de décision, si la mesure n'en
permet pas). Sinon `decision` vaut None : P(virgule) reste un indice pour pré-sélectionner, jamais une
décision silencieuse.

Mesure du 19 octobre 2026 (254 décimaux vérifiés, 79 virgules, 15 classes du sujet FR ; chaque classe
prédite par un modèle appris sur les autres) : AUC 0,88 (image), 0,88 (lecteur), 0,90 (image+lecteur).
AUCUNE zone sans erreur : des seuils choisis sans erreur sur les autres classes font encore des erreurs sur
la classe testée (image+lecteur : 12 points sûrs dont 1 virgule écrite, 3 virgules sûres dont 2 points
écrits). Le modèle appris garde donc bas = 0 et haut = 1 : indice seulement. Comme indice, il range mieux
que la proposition actuelle (au seuil 0,5 : 35 erreurs sur 233 contre 48 ; P <= 0,1 : 101 décimaux dont
3 virgules écrites). Une partie des erreurs vient sans doute de la vérité elle-même (cf. rapport).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import cv2
import numpy as np

MODEL = Path("data") / "models" / "separateur.npz"   # hors dépôt (appris sur des copies d'étudiants)

FEATURES = ("hauteur", "largeur", "log_allongement", "aire", "remplissage", "haut", "bas", "centre",
            "sous_base", "pente", "excentricite", "queue_gauche", "morceaux", "ecart", "bas_max")
RAW_FEATURES = ("brut_trouve", "brut_hauteur", "brut_bas", "brut_touche_ligne", "dessous_aire",
                "dessous_haut", "dessous_decalage", "ligne", "brut_pente", "brut_queue_gauche")
IMAGE_FEATURES = FEATURES + RAW_FEATURES
READER_FEATURES = ("lecteur_virgule", "lecteur_point")
KINDS = ("image", "lecteur", "image+lecteur")


def _gray(img):
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _ink(img):
    return (_gray(img) < 200).astype(np.uint8)


# ---------------------------------------------------------------- vignette nettoyée

def locate(img, apres=None):
    """Vignette nettoyée -> (masque du séparateur, géométrie) ou (None, raison).

    `apres` : nombre de chiffres avant le séparateur s'il est connu (lecture du moteur de texte) ; sinon on
    prend l'intervalle entre deux chiffres qui contient le plus d'encre basse."""
    ink = _ink(img)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    comps = [dict(i=i, x0=int(st[i, 0]), y0=int(st[i, 1]), x1=int(st[i, 0] + st[i, 2]),
                  y1=int(st[i, 1] + st[i, 3]), area=int(st[i, 4])) for i in range(1, n) if st[i, 4] >= 3]
    if not comps:
        return None, "vignette vide"
    hmax = max(c["y1"] - c["y0"] for c in comps)
    big = [c for c in comps if c["y1"] - c["y0"] >= 0.55 * hmax]
    t0, b0 = min(c["y0"] for c in big), max(c["y1"] for c in big)
    # une grande virgule n'est pas un chiffre : étroite et qui ne monte pas dans le tiers supérieur
    big = sorted((c for c in big if not (c["y1"] - c["y0"] < 0.8 * hmax and c["x1"] - c["x0"] < 0.45 * hmax
                                         and c["y0"] > t0 + 0.35 * (b0 - t0))), key=lambda c: c["x0"])
    digits = []   # grandes composantes ; deux grands morceaux superposés = un seul chiffre
    for c in big:
        if digits:
            d = digits[-1]
            ov = min(c["x1"], d["x1"]) - max(c["x0"], d["x0"])
            if ov > 0.5 * min(c["x1"] - c["x0"], d["x1"] - d["x0"]):
                d.update(x0=min(d["x0"], c["x0"]), y0=min(d["y0"], c["y0"]), x1=max(d["x1"], c["x1"]),
                         y1=max(d["y1"], c["y1"]))
                continue
        digits.append(dict(c))
    if len(digits) < 2:
        return None, "moins de deux chiffres séparés"
    base = float(np.median([d["y1"] for d in digits]))
    top = float(np.median([d["y0"] for d in digits]))
    h = max(base - top, 4.0)
    bigids = {c["i"] for c in big}
    gaps = []
    for k in range(len(digits) - 1):
        a, b = digits[k], digits[k + 1]
        gx0, gx1 = (a["x0"] + a["x1"]) / 2, (b["x0"] + b["x1"]) / 2
        members = [c for c in comps if c["i"] not in bigids and gx0 < (c["x0"] + c["x1"]) / 2 < gx1
                   and (c["y0"] + c["y1"]) / 2 >= top + 0.45 * h]
        gaps.append(dict(members=members, x0=a["x1"], x1=b["x0"], low=sum(c["area"] for c in members)))
    gap = gaps[apres - 1] if apres is not None and 1 <= apres <= len(gaps) else max(gaps, key=lambda g: g["low"])
    if not gap["members"]:
        return None, "aucun signe isolé entre les chiffres (collé à un chiffre ?)"
    ids = [c["i"] for c in gap["members"]]
    return np.isin(lab, ids), dict(h=h, base=base, top=top, n=len(ids), gap=(gap["x1"] - gap["x0"]) / h,
                                   gx0=gap["x0"], gx1=gap["x1"])


def _shape(xs, ys, h):
    """Inclinaison (< 0 : trait penché comme « / ») et décalage vers la gauche du bas du tracé."""
    xx, yy = xs.astype(float), ys.astype(float)
    cov = np.cov(np.stack([xx, yy])) if len(ys) > 2 else np.eye(2)
    ev, evec = np.linalg.eigh(cov + 1e-6 * np.eye(2))
    pente = float(evec[0, 1] * evec[1, 1])
    mid = (yy.min() + yy.max() + 1) / 2
    up, lo = xx[yy < mid], xx[yy >= mid]
    queue = float((up.mean() - lo.mean()) / h) if len(up) and len(lo) else 0.0
    return pente, float(np.sqrt(ev[1] / max(ev[0], 1e-6))), queue


def features(mask, geo):
    ys, xs = np.nonzero(mask)
    h, base = geo["h"], geo["base"]
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    H, W = (y1 - y0) / h, (x1 - x0) / h
    pente, exc, queue = _shape(xs, ys, h)
    return np.array([H, W, np.log((H + 0.02) / (W + 0.02)), len(ys) / h ** 2,
                     len(ys) / max(1, (y1 - y0) * (x1 - x0)), (y0 - base) / h, (y1 - base) / h,
                     ((y0 + y1) / 2 - base) / h, float((ys > base).mean()), pente, np.log(exc), queue,
                     geo["n"], geo["gap"], (ys.max() - base) / h], float)


# ---------------------------------------------------------------- vignette brute

def _align(clean_ink, crop_ink):
    """Position (dx, dy) de la vignette nettoyée dans la vignette brute (même page redressée) et score."""
    ch, cw = clean_ink.shape
    pad = cv2.copyMakeBorder(crop_ink.astype(np.float32), ch, ch, cw, cw, cv2.BORDER_CONSTANT, value=0)
    res = cv2.matchTemplate(pad, clean_ink.astype(np.float32), cv2.TM_CCORR_NORMED)
    _, score, _, (x, y) = cv2.minMaxLoc(res)
    return x - cw, y - ch, float(score)


def raw_features(crop, clean, mask, geo):
    """Traits du séparateur sur la vignette BRUTE (cf. en-tête, point 4) :
    partie haute = encre brute au-dessus du soulignement qui touche le séparateur nettoyé ; touche_ligne =
    elle descend jusqu'au soulignement ; dessous = encre qui part juste sous le soulignement, sous le signe ou
    un peu à sa gauche (queue). Zéros (brut_trouve = 0) si la vignette brute est inutilisable."""
    zero = np.zeros(len(RAW_FEATURES))
    g = _gray(crop)
    ink = (g < 0.62 * float(np.percentile(g, 90))).astype(np.uint8)
    dx, dy, score = _align(_ink(clean), ink)
    if score < 0.4:
        return zero
    H, W = ink.shape
    h, base = geo["h"], geo["base"] + dy
    line = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, max(15, int(0.3 * W))), np.uint8))
    rows = np.nonzero(line.sum(1) > 0.2 * W)[0]
    rows = rows[(rows > base - 0.4 * h) & (rows < base + 1.0 * h)]
    if not len(rows):
        return zero
    la = lb = int(rows[0])   # soulignement : premier bloc de lignes encrées sous la ligne de base
    for r in rows[1:]:
        if r != lb + 1:
            break
        lb = int(r)
    up = ink.copy()
    up[la:] = 0
    sep = np.zeros_like(up)
    ys, xs = np.nonzero(mask)
    ys, xs = ys + dy, xs + dx
    ok = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
    sep[ys[ok], xs[ok]] = 1
    n, lab, st, _ = cv2.connectedComponentsWithStats(up, connectivity=8)
    hit = set(np.unique(lab[(cv2.dilate(sep, np.ones((3, 3), np.uint8)) > 0) & (up > 0)]).tolist()) - {0}
    hit = [i for i in hit if st[i, 3] < 1.2 * h]
    if not hit:
        return zero
    uy, ux = np.nonzero(np.isin(lab, hit))
    x0, x1, y0, y1 = ux.min(), ux.max() + 1, uy.min(), uy.max() + 1
    d0, d1 = lb + 1, min(H, int(lb + 1 + 0.6 * h))
    c0, c1 = max(0, int(x0 - 0.4 * h)), min(W, int(x1 + 0.1 * h))
    da = dh = dd = 0.0
    if d1 > d0 and c1 > c0:
        nb, lbl, sb, _ = cv2.connectedComponentsWithStats(ink[d0:d1, c0:c1], connectivity=8)
        keep = [i for i in range(1, nb) if sb[i, 1] <= 2 and sb[i, 3] < 0.8 * h and sb[i, 2] < 0.8 * h]
        if keep:
            by, bx = np.nonzero(np.isin(lbl, keep))
            da, dh, dd = len(by) / h ** 2, (by.max() + 1) / h, ((bx.mean() + c0) - ux.mean()) / h
    pente, _, queue = _shape(ux, uy, h)
    return np.array([1.0, (y1 - y0) / h, (y1 - base) / h, float(y1 >= la - 1), da, dh, dd, (la - base) / h,
                     pente, queue])


def extract(img, apres=None, crop=None):
    """Vignette nettoyée (+ brute si fournie) -> (vecteur de IMAGE_FEATURES, None) ou (None, raison)."""
    mask, geo = locate(img, apres)
    if mask is None:
        return None, geo
    r = raw_features(crop, img, mask, geo) if crop is not None else np.zeros(len(RAW_FEATURES))
    return np.concatenate([features(mask, geo), r]), None


def reader_features(candidates):
    """Candidats TrOCR [[texte, score], ...] -> (meilleur score avec virgule, meilleur score avec point)."""
    c = candidates or []
    return np.array([max([float(s) for t, s in c if "," in t] + [0.0]),
                     max([float(s) for t, s in c if "." in t] + [0.0])])


def vector(kind, clean=None, crop=None, candidates=None, apres=None):
    """Vecteur de traits du modèle `kind` -> (vecteur, None) ou (None, raison)."""
    parts = []
    if "image" in kind:
        if clean is None:
            return None, "pas de vignette nettoyée"
        x, why = extract(clean, apres, crop)
        if x is None:
            return None, why
        parts.append(x)
    if "lecteur" in kind:
        if not candidates:
            return None, "pas de candidats du moteur de texte"
        parts.append(reader_features(candidates))
    return np.concatenate(parts), None


# ---------------------------------------------------------------- modèle

def fit(X, y, l2=10.0, iters=3000, lr=0.1):
    """Régression logistique régularisée (descente de gradient, numpy). Retourne les paramètres."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    w, b = np.zeros(Z.shape[1]), 0.0
    for _ in range(iters):
        g = 1 / (1 + np.exp(-(Z @ w + b))) - y
        w -= lr * (Z.T @ g / len(y) + l2 * w / len(y))
        b -= lr * g.mean()
    return dict(mu=mu, sd=sd, w=w, b=np.array(b))


def proba(params, X):
    Z = (np.atleast_2d(np.asarray(X, float)) - params["mu"]) / params["sd"]
    return 1 / (1 + np.exp(-(Z @ params["w"] + params["b"])))


class Separateur:
    """P(virgule) d'un séparateur décimal ; ne tranche seul qu'en dehors de ]bas, haut[.

    Par défaut bas = 0 et haut = 1 : jamais de décision, seulement un indice. `train` enregistre les seuils
    les plus larges que la validation croisée par classe a montrés sans aucune erreur."""

    def __init__(self, params, kind="image", bas=0.0, haut=1.0, meta=None):
        self.params, self.kind, self.bas, self.haut, self.meta = params, kind, float(bas), float(haut), meta or {}

    @classmethod
    def load(cls, path=MODEL):
        z = np.load(path, allow_pickle=False)
        return cls({k: z[k] for k in ("mu", "sd", "w", "b")}, str(z["kind"]), float(z["bas"]), float(z["haut"]),
                   json.loads(str(z["meta"])))

    def save(self, path=MODEL):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, kind=self.kind, bas=self.bas, haut=self.haut,
                 meta=json.dumps(self.meta, ensure_ascii=False), **self.params)
        return path

    def decide(self, p):
        if p >= self.haut:
            return ",", f"virgule (P(virgule) = {p:.2f})"
        if p <= self.bas:
            return ".", f"point (P(virgule) = {p:.2f})"
        return None, f"séparateur incertain (P(virgule) = {p:.2f})"

    def predict(self, clean=None, crop=None, candidates=None, apres=None):
        """Vignettes en gris uint8 (`clean` nettoyée, `crop` brute), candidats TrOCR éventuels, `apres` =
        chiffres avant le séparateur si connus -> dict(p_virgule: float | None, decision: "," | "." | None,
        trouve: bool, raison: texte lisible)."""
        x, why = vector(self.kind, clean, crop, candidates, apres)
        if x is None:
            return {"p_virgule": None, "decision": None, "trouve": False, "raison": why}
        p = float(proba(self.params, x)[0])
        d, why = self.decide(p)
        return {"p_virgule": round(p, 3), "decision": d, "trouve": True, "raison": why}


# ---------------------------------------------------------------- exemples vérifiés, mesure, apprentissage

DECIMAL = re.compile(r"-?(\d+)([.,])\d+")


def apres_of(ocr):
    """Chiffres avant le séparateur d'après la lecture du moteur (proposition, sinon premier candidat
    décimal) ; None si inconnu."""
    for t in [ocr.get("value") or ""] + [c[0] for c in (ocr.get("candidates") or [])]:
        m = DECIMAL.fullmatch(str(t).strip())
        if m:
            return len(m.group(1))
    return None


def class_dirs(paths):
    out = []
    for p in map(Path, paths):
        if (p / "results.json").exists():
            out.append(p)
        elif p.is_dir():
            out += sorted(q for q in p.iterdir() if (q / "results.json").exists())
    return out


def examples(dirs, truth_dir="data/truth", lists_dir="data/listes", db="data/correction.sqlite"):
    """Décimaux vérifiés par l'enseignant (`Classe.labels` : vérité validée, texte tapé, juste vérifié) ->
    liste de dict(classe, cle, verite, y (1 = virgule), clean, crop, candidates, proposition, apres).
    Lecture seule : la base de décisions n'est jamais modifiée."""
    from .correction import Classe, Decisions
    dec, exams, out = Decisions(db), {}, []
    for d in class_dirs(dirs):
        c = Classe(d, exams, dec, truth_dir=truth_dir, lists_dir=lists_dir)
        for k, v in sorted(c.labels().items()):
            m = DECIMAL.fullmatch(v.strip())
            if not m:
                continue
            num, fid = k.split("_", 1)
            f = c.doc(f"copy_{int(num[1:]):03d}").get("fields", {}).get(fid) or {}
            if not f.get("clean"):
                continue
            o = f.get("ocr") or {}
            clean = cv2.imread(str(d / f["clean"].replace("\\", "/")), cv2.IMREAD_GRAYSCALE)
            crop = cv2.imread(str(d / f["crop"].replace("\\", "/")), cv2.IMREAD_GRAYSCALE) if f.get("crop") else None
            if clean is None:
                continue
            out.append(dict(classe=d.name, cle=k, verite=v.strip(), y=int(m.group(2) == ","), clean=clean,
                            crop=crop, candidates=o.get("candidates"), proposition=o.get("value"),
                            apres=apres_of(o)))
    return out


def _vectors(kind, ex):
    X, keep = [], []
    for i, e in enumerate(ex):
        x, _ = vector(kind, e["clean"], e["crop"], e["candidates"], e["apres"])
        if x is not None:
            X.append(x)
            keep.append(i)
    return np.array(X), np.array(keep, int)


def safe_thresholds(P, y, marge=0.02):
    """Seuils les plus larges SANS AUCUNE erreur sur des prédictions croisées : point seulement sous la plus
    petite P(virgule) d'une virgule écrite, virgule seulement au-dessus de la plus grande P(virgule) d'un
    point écrit, avec une marge. bas = 0 / haut = 1 (jamais) si la marge ne laisse rien."""
    v, pt = P[y == 1], P[y == 0]
    bas = float(v.min() - marge) if len(v) else 0.0
    haut = float(pt.max() + marge) if len(pt) else 1.0
    return (bas if bas > 0 else 0.0), (haut if haut < 1 else 1.0)


def _loco(X, y, groups, l2):
    """Prédictions croisées : chaque classe est prédite par un modèle appris sur les autres seulement."""
    P = np.full(len(y), np.nan)
    for g in sorted(set(groups)):
        te = groups == g
        if (~te).sum() >= 10 and len(set(y[~te])) == 2:
            P[te] = proba(fit(X[~te], y[~te], l2=l2), X[te])
    return P


def measure(ex, kind="image", l2=10.0, seuils=None):
    """Validation croisée par classe (une classe n'est jamais vue par son modèle).

    seuils None : pour chaque classe, seuils sans erreur choisis sur les prédictions croisées des AUTRES
    classes seulement (validation imbriquée) ; sinon (bas, haut) fixés.
    Retourne (lignes par classe, total, (P, indices des exemples prédits))."""
    X, keep = _vectors(kind, ex)
    y = np.array([ex[i]["y"] for i in keep])
    groups = np.array([ex[i]["classe"] for i in keep])
    P = _loco(X, y, groups, l2)
    rows = []
    for g in sorted({e["classe"] for e in ex}):
        te = groups == g
        if seuils is None:
            Pin = _loco(X[~te], y[~te], groups[~te], l2)
            ok = ~np.isnan(Pin)
            bas, haut = safe_thresholds(Pin[ok], y[~te][ok])
        else:
            bas, haut = seuils
        p, yy = P[te], y[te]
        valid = ~np.isnan(p)
        sp, sv = valid & (p <= bas), valid & (p >= haut)
        rows.append(dict(classe=g, decimaux=sum(e["classe"] == g for e in ex),
                         virgules=sum(e["y"] for e in ex if e["classe"] == g), trouves=int(valid.sum()),
                         bas=bas, haut=haut, point_sur=int(sp.sum()), point_faux=int((sp & (yy == 1)).sum()),
                         virgule_sure=int(sv.sum()), virgule_faux=int((sv & (yy == 0)).sum()),
                         erreurs_05=int((valid & ((p >= 0.5) != (yy == 1))).sum())))
    tot = {k: sum(r[k] for r in rows) for k in ("decimaux", "virgules", "trouves", "point_sur", "point_faux",
                                                  "virgule_sure", "virgule_faux", "erreurs_05")}
    ok = ~np.isnan(P)
    a, b = P[ok][y[ok] == 1], P[ok][y[ok] == 0]
    tot["auc"] = float(np.mean(a[:, None] > b[None, :]) + 0.5 * np.mean(a[:, None] == b[None, :])) \
        if len(a) and len(b) else float("nan")
    return rows, tot, (P, keep)


def baseline(ex):
    """Situation actuelle : séparateur de la proposition de la machine contre le séparateur écrit."""
    from collections import Counter
    return Counter(("virgule" if e["y"] else "point",
                    "," if "," in str(e["proposition"] or "") else "." if "." in str(e["proposition"] or "")
                    else "aucun") for e in ex)


def train(ex, kind="image", l2=10.0, out=MODEL):
    """Modèle appris sur TOUS les exemples ; seuils = seuils sans erreur de la validation croisée."""
    X, keep = _vectors(kind, ex)
    y = np.array([ex[i]["y"] for i in keep])
    groups = np.array([ex[i]["classe"] for i in keep])
    P = _loco(X, y, groups, l2)
    ok = ~np.isnan(P)
    bas, haut = safe_thresholds(P[ok], y[ok])
    meta = dict(exemples=int(len(y)), virgules=int(y.sum()), classes=sorted(set(groups.tolist())), l2=l2)
    det = Separateur(fit(X, y, l2=l2), kind, bas, haut, meta)
    if out:
        det.save(out)
    return det


def _print_measure(kind, rows, tot):
    print(f"\n== modèle « {kind} » : validation croisée par classe, seuils choisis sans la classe testée")
    print(f"{'classe':16s} {'déc.':>4s} {'virg.':>5s} {'lus':>4s} {'bas':>5s} {'haut':>5s} "
          f"{'point sûr':>9s} {'dont virg.':>10s} {'virg. sûre':>10s} {'dont pts':>8s}")
    for r in rows:
        print(f"{r['classe']:16s} {r['decimaux']:4d} {r['virgules']:5d} {r['trouves']:4d} {r['bas']:5.2f} "
              f"{r['haut']:5.2f} {r['point_sur']:9d} {r['point_faux']:10d} {r['virgule_sure']:10d} "
              f"{r['virgule_faux']:8d}")
    print(f"{'TOTAL':16s} {tot['decimaux']:4d} {tot['virgules']:5d} {tot['trouves']:4d} {'':11s} "
          f"{tot['point_sur']:9d} {tot['point_faux']:10d} {tot['virgule_sure']:10d} {tot['virgule_faux']:8d}")
    print(f"AUC {tot['auc']:.3f} ; au seuil 0,5 : {tot['erreurs_05']} erreurs sur {tot['trouves']}.  "
          "« dont virg. » : virgule écrite déclarée point (favorise l'étudiant) ; "
          "« dont pts » : point écrit déclaré virgule (le PÉNALISE).")


def run(dirs, kinds=KINDS, l2=10.0, save=None, truth_dir="data/truth", lists_dir="data/listes",
        db="data/correction.sqlite", seuils=None, out=MODEL):
    """Commande `separateur` : mesure (et apprentissage si `save` = type de modèle à enregistrer)."""
    ex = examples(dirs, truth_dir, lists_dir, db)
    if not ex:
        print("aucun décimal vérifié dans ces dossiers")
        return None
    print(f"{len(ex)} décimaux vérifiés ({sum(e['y'] for e in ex)} virgules) dans "
          f"{len({e['classe'] for e in ex})} classes")
    b = baseline(ex)
    print("situation actuelle (séparateur de la proposition de la machine) :")
    for w in ("point", "virgule"):
        print(f"  {w} écrit : " + ", ".join(f"proposé « {s} » {b[(w, s)]}" for s in (".", ",", "aucun")))
    for kind in kinds:
        rows, tot, _ = measure(ex, kind, l2, seuils)
        _print_measure(kind, rows, tot)
    if save:
        det = train(ex, save, l2, out)
        print(f"\nmodèle « {save} » appris sur {det.meta['exemples']} exemples -> {out} ; seuils sans erreur "
              f"en validation croisée : point si P(virgule) <= {det.bas:.3f}, virgule si P(virgule) >= {det.haut:.3f}"
              + ("  (aucune décision seule : indice seulement)" if det.bas == 0 and det.haut == 1 else ""))
        return det
    return None
