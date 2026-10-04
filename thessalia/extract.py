"""Découpe des zones non-OMR sur la page redressée.

Ces vignettes sont l'entrée des niveaux suivants :
    identity    -> OCR du nom / n° étudiant (niveau 2)
    short_text  -> OCR contraint + snapping vocabulaire (niveau 2)
    text_box    -> HTR texte libre (niveau 3, ou lecture humaine)
    code_grid   -> HTR code Python (niveau 3)
"""
from __future__ import annotations

from pathlib import Path

import cv2

from .common import clip_box, mm_rect_to_px

CROP_TYPES = ("identity", "short_text", "text_box", "code_grid")


def crop_field(aligned_img, field, dpi, pad_mm=1.0):
    box = clip_box(mm_rect_to_px(field["bbox_mm"], dpi, pad_mm=pad_mm), aligned_img.shape)
    x0, y0, x1, y1 = box
    return aligned_img[y0:y1, x0:x1], box


def save_crops(aligned_img, fields, dpi, out_dir: Path, rel_to: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = {}
    for f in fields:
        if f["type"] not in CROP_TYPES:
            continue
        img, box = crop_field(aligned_img, f, dpi)
        p = out_dir / f"{f['id']}.png"
        cv2.imwrite(str(p), img)
        saved[f["id"]] = {"type": f["type"], "crop": str(p.relative_to(rel_to)), "box_px": list(box)}
    return saved
