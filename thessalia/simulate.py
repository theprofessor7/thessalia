"""Générateur de copies synthétiques remplies puis « scannées », avec vérité terrain.

Sert à tester et calibrer la chaîne avant (et en complément) des vrais scans :
    - marques variées : croix, coche, case noircie, gribouillis, croix qui
      déborde, point d'hésitation (vérité = vide), trait parasite à côté ;
    - encre bleue ou noire, épaisseur variable ;
    - écriture factice dans les blancs, l'identité et les cadres de code ;
    - scan : rotation, perspective, déformation non linéaire du papier, flou,
      bruit, ombrage, JPEG, résolution 150-300 dpi, pages à l'envers.

Sortie : un PDF multi-pages (toutes les copies à la suite, comme un chargeur
de scanner) + truth.json.
"""
from __future__ import annotations

import io
import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .common import load_json, px_per_mm

SIM_DPI = 300

CODE_SNIPPETS = [
    ["a = int(input(\"Premier nombre : \"))", "b = int(input(\"Second nombre : \"))", "somme = a + b",
     "print(\"La somme vaut\", somme)"],
    ["longueur = float(input(\"Longueur : \"))", "largeur = float(input(\"Largeur : \"))",
     "p = 2 * (longueur + largeur)", "print(\"Le perimetre est :\", p, \"cm\")"],
    ["note = int(input(\"Note : \"))", "if note < 0 or note > 20:", "    print(\"Note invalide\")",
     "elif note < 8:", "    print(\"Insuffisant\")", "elif note < 10:", "    print(\"Rattrapage\")",
     "else:", "    print(\"Passable\")"],
    ["n = int(input(\"n : \"))", "for i in range(1, 11):", "    print(n, \"x\", i, \"=\", n * i)"],
    ["s = 0", "c = 0", "v = int(input(\"Valeur : \"))", "while v != 0:", "    s = s + v", "    c = c + 1",
     "    v = int(input(\"Valeur : \"))", "print(\"Somme :\", s)"],
]
SHORT_ANSWERS = ["int", "float", "str", "bool", "3", "2", "1024", "2.5", "11", "14", "print", "input",
                 "Grand", "Petit", "ERREUR", "42", "427", "6", "0", "A-B-C", "XY"]
NAMES = ["Martin", "Bernard", "Dubois", "Durand", "Leroy", "Moreau", "Laurent", "Nguyen", "Garcia", "Petit"]
FIRST = ["Alice", "Hugo", "Lina", "Nathan", "Emma", "Louis", "Chloe", "Adam", "Ines", "Leo"]


# --------------------------------------------------------------------------- dessin
def _pen(rng, hard):
    color = rng.choice([(25, 40, 150), (30, 30, 35), (20, 60, 170)])  # RGB bleu / noir
    return {"color": color, "w_mm": rng.uniform(0.3, 0.6) if not hard else rng.uniform(0.25, 0.7)}


def _line(img, p0, p1, pen, k):
    t = max(1, int(round(pen["w_mm"] * k)))
    cv2.line(img, tuple(map(int, p0)), tuple(map(int, p1)), pen["color"], t, cv2.LINE_AA)


def _stroke(img, pts, pen, k):
    for a, b in zip(pts[:-1], pts[1:]):
        _line(img, a, b, pen, k)


def draw_mark(img, box_mm, kind, pen, rng, k):
    x, y, w, h = box_mm
    cx, cy = (x + w / 2) * k, (y + h / 2) * k
    s = min(w, h) / 2 * k            # cases rectangulaires (grille du numéro) : la marque tient dans la case
    sx, sy = w / 2 * k, h / 2 * k
    j = lambda: rng.uniform(-0.15, 0.15) * s
    if kind == "cross":
        o = rng.uniform(0.6, 1.15)
        _line(img, (cx - o * s + j(), cy - o * s + j()), (cx + o * s + j(), cy + o * s + j()), pen, k)
        _line(img, (cx + o * s + j(), cy - o * s + j()), (cx - o * s + j(), cy + o * s + j()), pen, k)
    elif kind == "big_cross":
        o = rng.uniform(1.3, 1.8)
        _line(img, (cx - o * s, cy - o * s + j()), (cx + o * s, cy + o * s + j()), pen, k)
        _line(img, (cx + o * s, cy - o * s + j()), (cx - o * s, cy + o * s + j()), pen, k)
    elif kind == "check":
        _stroke(img, [(cx - 0.7 * s + j(), cy + j()), (cx - 0.1 * s + j(), cy + 0.7 * s + j()),
                      (cx + 0.9 * s + j(), cy - 1.1 * s + j())], pen, k)
    elif kind == "full":
        pts = np.array([[cx - sx, cy - sy], [cx + sx, cy - sy], [cx + sx, cy + sy], [cx - sx, cy + sy]], np.int32)
        cv2.fillPoly(img, [pts], pen["color"], cv2.LINE_AA)
    elif kind == "scribble":
        n = rng.randint(5, 8)
        pts = [(cx - 0.8 * s + 1.6 * s * (i % 2) + j(), cy - 0.8 * s + 1.6 * s * i / n + j()) for i in range(n + 1)]
        _stroke(img, pts, pen, k)
    elif kind == "light_cross":  # crayon à papier clair
        p2 = dict(pen, color=(150, 150, 160), w_mm=0.3)
        draw_mark(img, box_mm, "cross", p2, rng, k)
    elif kind == "dot":  # hésitation : vérité = vide
        r = max(1, int(0.25 * k))
        cv2.circle(img, (int(cx + j()), int(cy + j())), r, pen["color"], -1, cv2.LINE_AA)
    elif kind == "stray":  # trait qui frôle la case sans y entrer : vérité = vide
        yy = (y + h + 0.9) * k
        _line(img, (cx - 1.5 * s, yy), (cx + 6 * s, yy + j()), pen, k)


def draw_text(img, text, org_mm, height_mm, pen, k, rng):
    font = rng.choice([cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, cv2.FONT_HERSHEY_SCRIPT_COMPLEX])
    scale = height_mm * k / 22.0
    t = max(1, int(round(pen["w_mm"] * k * 0.8)))
    cv2.putText(img, text, (int(org_mm[0] * k), int(org_mm[1] * k)), font, scale, pen["color"], t, cv2.LINE_AA)


# --------------------------------------------------------------------------- réponses
def pick_answers(field, rng, hard):
    opts = [o["id"] for o in field["options"]]
    if field.get("mode") == "multi":
        sel = [o for o in opts if rng.random() < 0.45]
    else:
        r = rng.random()
        if r < 0.08:
            sel = []
        elif r < 0.12:
            sel = rng.sample(opts, 2)
        else:
            sel = [rng.choice(opts)]
    marks = {}
    for o in opts:
        if o in sel:
            kinds = ["cross"] * 6 + ["check"] * 3 + ["full", "scribble"]
            if hard:
                kinds += ["big_cross", "light_cross", "check"]
            marks[o] = rng.choice(kinds)
        else:
            r = rng.random()
            if r < (0.05 if hard else 0.02):
                marks[o] = "dot"
            elif r < (0.12 if hard else 0.06):
                marks[o] = "stray"
    return sel, marks


def remplir_grille(field, rng, hard):
    """Numéro écrit dans la grille : (valeur attendue, [(chiffres noircis, marque) par colonne]).
    Valeur None quand l'étudiant s'est trompé (2 cases dans une colonne, chiffre oublié) : la lecture doit
    alors partir en revue, jamais donner un numéro."""
    n = field.get("digits") or len(field["columns"])
    num = [str(rng.randint(0, 9)) for _ in range(n)]
    kinds = ["full"] * 6 + ["cross"] * 2 + ["check"] + (["big_cross", "scribble"] if hard else [])
    marks = [({d}, rng.choice(kinds)) for d in num] + [(set(), None)] * (len(field["columns"]) - n)
    valeur = "".join(num)
    r = rng.random()
    if hard and r < 0.06:                       # deux cases dans une colonne
        i = rng.randrange(n)
        autre = str((int(num[i]) + rng.randint(1, 9)) % 10)
        marks[i] = ({num[i], autre}, marks[i][1])
        valeur = None
    elif hard and r < 0.10:                     # chiffre oublié
        marks[rng.randrange(n)] = (set(), None)
        valeur = None
    return valeur, marks


# --------------------------------------------------------------------------- scan
def simulate_scan(rgb, rng, hard, out_dpi):
    h, w = rgb.shape[:2]
    k = px_per_mm(SIM_DPI)
    img = rgb.astype(np.float32)

    # déformation non linéaire (papier gondolé)
    amp = (rng.uniform(0.6, 1.5) if hard else rng.uniform(0.0, 0.6)) * k
    if amp > 0:
        gy, gx = np.mgrid[0:h:32, 0:w:32].astype(np.float32)
        fx = rng.uniform(0.5, 1.5) * 2 * np.pi / w
        fy = rng.uniform(0.5, 1.5) * 2 * np.pi / h
        ph = rng.uniform(0, 6.28)
        dx = amp * np.sin(gy * fy + ph) * np.cos(gx * fx * 0.5)
        dy = amp * np.sin(gx * fx + ph * 0.7)
        dx = cv2.resize(dx, (w, h), interpolation=cv2.INTER_CUBIC)
        dy = cv2.resize(dy, (w, h), interpolation=cv2.INTER_CUBIC)
        mx, my = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        img = cv2.remap(img, mx + dx, my + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # position sur le plateau : rotation, perspective, marge
    ang = rng.uniform(-5, 5) if hard else rng.uniform(-2.5, 2.5)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    jit = (4.0 if hard else 1.5) * k
    th = np.deg2rad(ang)
    R = np.float32([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    dst = np.float32([(R @ (p - np.float32([w / 2, h / 2]))) + np.float32([rng.uniform(-jit, jit), rng.uniform(-jit, jit)])
                      for p in src])
    # la feuille entière reste sur la vitre, avec 2 à 8 mm de marge (comme un vrai scan)
    margin = rng.uniform(2, 8) * k
    dst -= dst.min(axis=0) - margin
    W2, H2 = int(dst[:, 0].max() + margin), int(dst[:, 1].max() + margin)
    M = cv2.getPerspectiveTransform(src, dst)
    bed = rng.choice([245, 235, 60])  # couvercle blanc / gris / sombre
    img = cv2.warpPerspective(img, M, (W2, H2), flags=cv2.INTER_LINEAR, borderValue=(bed, bed, bed))

    # ombrage + teinte papier + bruit + flou
    yy, xx = np.mgrid[0:H2, 0:W2].astype(np.float32)
    shade = 1.0 - (rng.uniform(0.0, 0.18) if hard else rng.uniform(0, 0.08)) * (xx / W2)
    img = img * shade[..., None] * rng.uniform(0.9, 1.0)
    img += rng.uniform(0, 10)
    img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.6, 1.6 if hard else 1.1))
    img += np.random.default_rng(rng.randint(0, 1 << 30)).normal(0, 6 if hard else 3, img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)

    s = out_dpi / SIM_DPI
    img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return img


def main(a):
    rng = random.Random(a.seed)
    tpl = load_json(a.template)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    k = px_per_mm(SIM_DPI)

    import pymupdf
    doc = pymupdf.open(a.blank)
    blanks = []
    for page in doc:
        pix = page.get_pixmap(dpi=SIM_DPI, colorspace=pymupdf.csRGB, alpha=False)
        blanks.append(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3).copy())

    truth = {"exam_id": tpl["exam_id"], "copies": []}
    pdf = pymupdf.open()
    n_pages = 0

    def add_page(scan, dpi):
        # JPEG dans le PDF, comme un vrai scanner, avec la taille de page réelle (dpi par page)
        b = io.BytesIO()
        Image.fromarray(scan).save(b, "JPEG", quality=rng.randint(60, 85) if a.hard else 85)
        pg = pdf.new_page(width=scan.shape[1] / dpi * 72, height=scan.shape[0] / dpi * 72)
        pg.insert_image(pg.rect, stream=b.getvalue())

    for ci in range(a.copies):
        pen = _pen(rng, a.hard)
        out_dpi = rng.choice([150, 200, 300] if a.hard else [200, 300])
        copy_truth = {"copy_id": f"copy_{ci + 1:03d}", "dpi": out_dpi, "answers": {}, "upside_down": []}
        for pi, page in enumerate(tpl["pages"]):
            img = blanks[pi].copy()
            for f in page["fields"]:
                if f["type"] in ("mcq", "truefalse"):
                    sel, marks = pick_answers(f, rng, a.hard)
                    for o in f["options"]:
                        if o["id"] in marks:
                            draw_mark(img, o["bbox_mm"], marks[o["id"]], pen, rng, k)
                    copy_truth["answers"][f["id"]] = {"selected": sel, "marks": marks,
                                                      "mode": f.get("mode", "single")}
                elif f["type"] == "digit_grid":
                    valeur, marks = remplir_grille(f, rng, a.hard)
                    for col, (d, mk) in zip(f["columns"], marks):
                        for o in col["options"]:
                            if o["id"] in d:
                                draw_mark(img, o["bbox_mm"], mk, pen, rng, k)
                    copy_truth.setdefault("grilles", {})[f["id"]] = valeur
                elif f["type"] == "identity":
                    x, y, w, h = f["bbox_mm"]
                    txt = {"identity.nom": rng.choice(NAMES), "identity.prenom": rng.choice(FIRST),
                           "identity.groupe": rng.choice(["A1", "B2", "C3"]),
                           "identity.numero": str(rng.randint(20250000, 20259999))}.get(f["id"], "x")
                    draw_text(img, txt, (x + 4, y + h - 3), 5, pen, k, rng)
                    copy_truth.setdefault("identite", {})[f["id"]] = txt   # noms inventés : liste d'élèves de test
                elif f["type"] == "short_text" and rng.random() < 0.85:
                    x, y, w, h = f["line_mm"]
                    draw_text(img, rng.choice(SHORT_ANSWERS), (x + 2, y + h - 0.8), 4.5, pen, k, rng)
                elif f["type"] == "code_grid" and rng.random() < 0.9:
                    x, y, w, h = f["bbox_mm"]
                    lines = rng.choice(CODE_SNIPPETS)
                    for li, line in enumerate(lines):
                        yy = y + 14 + 5 * li * rng.choice([1, 2])
                        if yy > y + h - 3:
                            break
                        indent = (len(line) - len(line.lstrip())) / 4 * 10
                        draw_text(img, line.strip(), (x + 3 + indent, yy), 4, pen, k, rng)
            scan = simulate_scan(img, rng, a.hard, out_dpi)
            if rng.random() < (0.08 if a.hard else 0.04):
                scan = cv2.rotate(scan, cv2.ROTATE_180)
                copy_truth["upside_down"].append(pi + 1)
            add_page(scan, out_dpi)
            n_pages += 1
        truth["copies"].append(copy_truth)
        print(f"  copie {ci + 1}/{a.copies} ({out_dpi} dpi)")

    pdf.save(out / "scans.pdf", deflate=True)
    with open(out / "truth.json", "w", encoding="utf-8") as f:
        json.dump(truth, f, ensure_ascii=False, indent=1)
    print(f"-> {out / 'scans.pdf'} ({n_pages} pages), {out / 'truth.json'}")
