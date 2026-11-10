"""Chargement des scans : PDF (multi-pages), images, TIFF multipage, dossiers.

Chaque page est retournée avec sa résolution estimée (px/mm), nécessaire pour
calibrer la détection des fiducials.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .common import A4_MM, to_ink_gray

IMG_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


@dataclass
class ScanPage:
    source: str          # fichier d'origine
    index: int           # index de page dans ce fichier
    gray: np.ndarray     # uint8, encre sombre (min des canaux RGB)
    px_mm: float         # résolution estimée

    @property
    def label(self):
        return f"{Path(self.source).name}#{self.index + 1}"


def _estimate_px_mm(w, h):
    long_px, short_px = max(w, h), min(w, h)
    return 0.5 * (long_px / A4_MM[1] + short_px / A4_MM[0])


def _load_pdf(path: Path, dpi: int):
    import pymupdf

    doc = pymupdf.open(path)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
        # résolution réelle : la page PDF d'un scanner fait (à peu près) la taille du papier
        pw_mm = page.rect.width * 25.4 / 72
        yield ScanPage(str(path), i, to_ink_gray(arr).copy(), pix.w / pw_mm)


def _load_image(path: Path):
    im = Image.open(path)
    i = 0
    while True:
        frame = ImageOps.exif_transpose(im.convert("RGB"))
        arr = np.asarray(frame)
        yield ScanPage(str(path), i, to_ink_gray(arr).copy(), _estimate_px_mm(arr.shape[1], arr.shape[0]))
        i += 1
        try:
            im.seek(i)
        except EOFError:
            break


def _fichiers(paths):
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in IMG_EXT | {".pdf"})
        else:
            files.append(p)
    return files


def count_pages(paths) -> int:
    """Nombre de pages à lire (jauge d'avancement) ; 0 si inconnu."""
    n = 0
    for f in _fichiers(paths):
        if f.suffix.lower() == ".pdf":
            try:
                import pymupdf
                with pymupdf.open(f) as doc:
                    n += len(doc)
            except Exception:
                return 0
        elif f.suffix.lower() in IMG_EXT:
            n += 1
    return n


def load_scans(paths, dpi: int = 200):
    """Accepte fichiers et dossiers ; les dossiers sont lus en ordre alphabétique."""
    files = _fichiers(paths)
    for f in files:
        if f.suffix.lower() == ".pdf":
            yield from _load_pdf(f, dpi)
        elif f.suffix.lower() in IMG_EXT:
            yield from _load_image(f)
        else:
            raise ValueError(f"Format non supporté : {f}")
