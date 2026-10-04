"""Utilitaires partagés : unités, JSON, rendu des pages de référence, prétraitement."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

MM_PER_PT = 25.4 / 72.0
A4_MM = (210.0, 297.0)

TEMPLATE_SCHEMA = "thessalia/template@1"
RESULT_SCHEMA = "thessalia/result@1"


# --------------------------------------------------------------------------- JSON
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- unités
def px_per_mm(dpi: float) -> float:
    return dpi / 25.4


def mm_rect_to_px(rect_mm, dpi, pad_mm=0.0):
    """[x, y, w, h] en mm -> (x0, y0, x1, y1) entiers en pixels (bornes incluses/exclues)."""
    k = px_per_mm(dpi)
    x, y, w, h = rect_mm
    x0 = int(round((x - pad_mm) * k))
    y0 = int(round((y - pad_mm) * k))
    x1 = int(round((x + w + pad_mm) * k))
    y1 = int(round((y + h + pad_mm) * k))
    return x0, y0, x1, y1


def clip_box(box, shape):
    x0, y0, x1, y1 = box
    h, w = shape[:2]
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


# --------------------------------------------------------------------------- images
def to_ink_gray(img: np.ndarray) -> np.ndarray:
    """Image couleur/gris -> niveau de gris où l'encre (noire OU bleue) est sombre.

    Le minimum des canaux RGB rend l'encre bleue aussi sombre que la noire
    (le bleu a un canal rouge faible), alors qu'une conversion standard la
    rend gris moyen.
    """
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = img[:, :, :3]
    return img.min(axis=2)


def normalize_background(gray: np.ndarray, px_mm: float) -> np.ndarray:
    """Divise par une estimation du fond (papier) : 1.0 = blanc papier, 0 = noir.

    Compense l'ombrage du scanner, le papier grisé, l'éclairage d'une photo.
    """
    # ~8 mm : plus large que tout trait, case noircie (3,7 mm) ou caractère,
    # pour que le fond estimé reste celui du papier
    k = max(3, int(round(8.0 * px_mm)) | 1)
    small = cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    bg = cv2.dilate(small, cv2.getStructuringElement(cv2.MORPH_RECT, (k // 2 | 1, k // 2 | 1)))
    bg = cv2.GaussianBlur(bg, (0, 0), k / 2)
    bg = cv2.resize(bg, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)
    norm = gray.astype(np.float32) / np.maximum(bg.astype(np.float32), 30.0)
    return np.clip(norm, 0.0, 1.0)


def render_pdf_pages(pdf_path, dpi: int, pages=None) -> list[np.ndarray]:
    """Rend les pages d'un PDF en niveaux de gris (uint8) à la résolution donnée."""
    import pymupdf

    doc = pymupdf.open(pdf_path)
    out = []
    for i, page in enumerate(doc):
        if pages is not None and i not in pages:
            continue
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
        out.append(to_ink_gray(arr).copy())
    return out
