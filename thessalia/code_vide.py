"""Cadres de code (ou d'explication) vides : mesure de l'écriture de l'étudiant dans la vignette.

Le crayon pâle a autant de pixels sombres qu'un cadre vide (mesuré le 22 octobre sur q18) : on ne compte pas
le sombre mais ce qui se détache du fond local, après avoir retiré les longues lignes droites (quadrillage,
bord du cadre) et l'étiquette imprimée en haut à gauche. Ce n'est qu'une PROPOSITION « vide » : l'enseignant
voit l'image et confirme.
"""
from __future__ import annotations

import cv2
import numpy as np


def encre(img: np.ndarray) -> float:
    """Part (en ‰) de la surface couverte par des traits d'écriture."""
    if img is None:
        return 0.0
    h, w = img.shape
    im = img[int(h * .04):int(h * .97), int(w * .015):int(w * .985)]
    im[: max(1, int(h * .08)), : int(w * .12)] = 255            # étiquette « PROGRAMME » / « EXPLICATION »
    fond = cv2.medianBlur(im, 31)
    trait = ((fond.astype(np.int16) - im) > 28).astype(np.uint8) * 255
    for k in ((max(40, w // 12), 1), (1, max(40, h // 6))):     # lignes du quadrillage et du cadre
        lignes = cv2.morphologyEx(trait, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, k))
        trait = cv2.subtract(trait, cv2.dilate(lignes, np.ones((3, 3), np.uint8)))
    trait = cv2.morphologyEx(trait, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))   # poussières
    return 1000.0 * (trait > 0).mean()
