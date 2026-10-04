"""Niveau 2 — lecteur de chiffres pour les réponses numériques.

Les moteurs de texte (TrOCR…) lisent mal un nombre isolé : sur le lot EN, un chiffre seul est souvent
lu en double (« 3 » -> « 3 3 ») et la première lecture n'est le bon nombre que 114 fois sur 250.
Ici la vignette nettoyée est découpée en glyphes (chiffres, séparateur décimal, signe), puis chaque
chiffre est classé par un petit réseau de convolution.

    lecteur = DigitReader()                 # modèle local s'il existe, sinon le modèle affiné fourni
    texte, confiance = lecteur.read(img)    # ("2.5", 0.93) ou (None, 0.0)

L'inférence n'utilise que numpy (aucune dépendance en plus). Deux modèles sont fournis (0,85 Mo chacun) :
    digits_mnist.npz    entraîné sur MNIST seul : confond les « 1 » à la française avec des « 7 » ;
    digits_affine.npz   le même, affiné sur les chiffres du lot EN (examen blanc, 21 copies). Il ne
                        contient que des poids, aucune image : partage entre collègues autorisé par
                        l'enseignant. Utilisé par défaut.
`python -m thessalia digits-train` affine sur un autre lot dont la vérité est validée et écrit un
modèle local (data/models/digits.npz), prioritaire sur les modèles fournis.

La lecture n'est qu'une PROPOSITION pour la revue : un nombre libre n'est jamais accepté seul.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

PACKAGED = Path(__file__).parent / "data" / "digits_mnist.npz"      # base MNIST (point de départ de l'affinage)
TUNED = Path(__file__).parent / "data" / "digits_affine.npz"       # affiné sur le lot EN, utilisé par défaut
LOCAL = Path("data") / "models" / "digits.npz"   # modèle affiné sur vos propres lots (hors dépôt)


def segment(img):
    """Vignette nettoyée (gris, encre sombre) -> glyphes triés de gauche à droite :
    dict(kind 'digit' | 'sep' | 'minus', box (x0, y0, x1, y1), mask bool)."""
    ink = (img < 200).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    comps = [dict(ids=[i], x0=int(st[i, 0]), y0=int(st[i, 1]), x1=int(st[i, 0] + st[i, 2]),
                  y1=int(st[i, 1] + st[i, 3]), area=int(st[i, 4])) for i in range(1, n) if st[i, 4] >= 4]
    if not comps:
        return []

    def H(c):
        return c["y1"] - c["y0"]

    def W(c):
        return c["x1"] - c["x0"]

    hmax = max(H(c) for c in comps)
    big = [c for c in comps if H(c) >= 0.5 * hmax]
    top, bottom = min(c["y0"] for c in big), max(c["y1"] for c in big)

    def comma(c):  # virgule haute : étroite, et qui ne monte pas dans le tiers supérieur des chiffres
        return H(c) < 0.75 * hmax and W(c) < 0.3 * hmax and c["y0"] > top + 0.35 * (bottom - top)

    small = [c for c in comps if H(c) < 0.5 * hmax or comma(c)]
    big = sorted((c for c in big if not comma(c)), key=lambda c: c["x0"])
    top, bottom = min(c["y0"] for c in big), max(c["y1"] for c in big)

    def join(m, c):
        m["ids"] += c["ids"]
        m.update(x0=min(m["x0"], c["x0"]), y0=min(m["y0"], c["y0"]), x1=max(m["x1"], c["x1"]), y1=max(m["y1"], c["y1"]))

    digits = []
    for c in big:  # deux grands morceaux superposés = un seul chiffre
        if digits and min(c["x1"], digits[-1]["x1"]) - max(c["x0"], digits[-1]["x0"]) > 0.5 * min(W(c), W(digits[-1])):
            join(digits[-1], c)
        else:
            digits.append(dict(c, kind="digit"))
    out = list(digits)
    for c in sorted(small, key=lambda c: c["x0"]):
        cx, cy = (c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2
        low = cy > top + 0.6 * (bottom - top)
        over = [d for d in digits if min(c["x1"], d["x1"]) - max(c["x0"], d["x0"]) > 0.5 * W(c)]
        if over:  # recouvre un chiffre (pied posé sur la ligne, barre) : même glyphe
            join(over[0], c)
            continue
        left = [d for d in digits if d["x1"] <= cx]
        right = [d for d in digits if d["x0"] >= cx]
        if not low and left and c["x0"] - left[-1]["x1"] < 0.3 * hmax and cy < top + 0.4 * (bottom - top):
            join(left[-1], c)  # barre du 5 ou du 7 détachée, en haut à droite
        elif low and left and right and c["area"] >= 6:
            # petit, bas, entre deux chiffres : point ou virgule (un seul par intervalle)
            if not any(o["kind"] == "sep" and o["x0"] > left[-1]["x0"] and o["x1"] < right[0]["x1"] for o in out):
                out.append(dict(c, kind="sep"))
        elif not low and W(c) > 1.5 * H(c) and not left and right:
            out.append(dict(c, kind="minus"))
        # le reste (points isolés en bord, résidus du soulignement) est ignoré
    out.sort(key=lambda c: c["x0"])
    for c in out:
        c["box"] = (c["x0"], c["y0"], c["x1"], c["y1"])
        # virgule si le séparateur est nettement plus haut que large. Indication FAIBLE : sur le lot EN
        # les formes des points et des virgules se recouvrent (25 bons choix sur 35). `ocr` n'en tient
        # pas compte : il propose toujours le point d'abord (vocab.favor_point).
        c["char"] = "," if c["kind"] == "sep" and H(c) >= 1.1 * W(c) else "."
        c["mask"] = np.isin(lab[c["y0"]:c["y1"], c["x0"]:c["x1"]], c["ids"])
    return out


def shape(glyphs):
    """« d.d » pour 2,5 : sert à vérifier un découpage contre une vérité."""
    return "".join({"digit": "d", "sep": ".", "minus": "-"}[g["kind"]] for g in glyphs)


def to_mnist(mask):
    """Glyphe -> 28×28 float32 (encre = 1), cadré comme MNIST : 20×20, centré sur le centre de masse."""
    h, w = mask.shape
    f = 20.0 / max(h, w)
    g = cv2.resize(mask.astype(np.float32), (max(1, round(w * f)), max(1, round(h * f))), interpolation=cv2.INTER_AREA)
    out = np.zeros((28, 28), np.float32)
    m = cv2.moments(g)
    cx, cy = (m["m10"] / m["m00"], m["m01"] / m["m00"]) if m["m00"] else (g.shape[1] / 2, g.shape[0] / 2)
    x0 = min(max(int(round(14 - cx)), 0), 28 - g.shape[1])
    y0 = min(max(int(round(14 - cy)), 0), 28 - g.shape[0])
    out[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] = g
    return np.clip(out / max(float(out.max()), 1e-6), 0, 1)


def _conv3(x, w, b):
    """Convolution 3×3, marge 1. x : (n, c, h, w) ; w : (o, c, 3, 3)."""
    xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
    win = np.lib.stride_tricks.sliding_window_view(xp, (3, 3), axis=(2, 3))
    return np.maximum(np.einsum("nchwij,ocij->nohw", win, w, optimize=True) + b[None, :, None, None], 0)


def _pool2(x):
    n, c, h, w = x.shape
    return x.reshape(n, c, h // 2, 2, w // 2, 2).max(axis=(3, 5))


class DigitReader:
    def __init__(self, model=None):
        path = Path(model) if model else next(p for p in (LOCAL, TUNED, PACKAGED) if p.exists())
        self.path = path
        self.w = {k: v.astype(np.float32) for k, v in np.load(path).items()}

    def proba(self, x):
        """x : (n, 28, 28) -> probabilités (n, 10). Même réseau que digits_train.Net."""
        w = self.w
        x = _pool2(_conv3(x[:, None].astype(np.float32), w["c1.weight"], w["c1.bias"]))
        x = _pool2(_conv3(_conv3(x, w["c2.weight"], w["c2.bias"]), w["c3.weight"], w["c3.bias"]))
        x = np.maximum(x.reshape(len(x), -1) @ w["f1.weight"].T + w["f1.bias"], 0)
        z = x @ w["f2.weight"].T + w["f2.bias"]
        e = np.exp(z - z.max(1, keepdims=True))
        return e / e.sum(1, keepdims=True)

    def read(self, img, glyphs=None):
        """-> (texte, confiance) ; confiance = la plus faible probabilité parmi les chiffres lus.
        (None, 0.0) si la vignette ne contient aucun chiffre découpable."""
        glyphs = segment(img) if glyphs is None else glyphs
        dig = [g for g in glyphs if g["kind"] == "digit"]
        if not dig:
            return None, 0.0
        p = self.proba(np.stack([to_mnist(g["mask"]) for g in dig]))
        it = iter(p.argmax(1).tolist())
        text = "".join(str(next(it)) if g["kind"] == "digit" else g["char"] if g["kind"] == "sep" else "-"
                       for g in glyphs)
        return text, float(p.max(1).min())
