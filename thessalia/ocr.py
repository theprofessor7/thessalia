"""Lecteur d'écriture des réponses courtes : TrOCR (HuggingFace microsoft/trocr-*-handwritten), local et gratuit,
téléchargé une fois ; ou le modèle affiné sur vos copies (page Apprentissage). Aucune donnée ne sort de la machine.

    backend.recognize(images, contexts) -> [[(texte, confiance 0..1), …], …]
    une liste de candidats par image, le meilleur d'abord.
"""
from __future__ import annotations

import cv2


def _pad(img, px=8):
    return cv2.copyMakeBorder(img, px, px, px, px, cv2.BORDER_CONSTANT, value=255)


class TrOCRBackend:
    """microsoft/trocr-base-handwritten par défaut, ou le dossier d'un modèle affiné."""
    name = "trocr"

    def __init__(self, model="microsoft/trocr-base-handwritten", beams=5, n_best=3, device=None):
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        self.torch = torch
        self.model_name = model
        self.proc = TrOCRProcessor.from_pretrained(model)
        self.model = VisionEncoderDecoderModel.from_pretrained(model).eval()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.beams, self.n_best = beams, n_best

    def recognize(self, images, contexts=None, batch=4):
        from PIL import Image
        out = []
        for i in range(0, len(images), batch):
            pil = [Image.fromarray(cv2.cvtColor(_pad(im, 12), cv2.COLOR_GRAY2RGB)) for im in images[i:i + batch]]
            px = self.proc(images=pil, return_tensors="pt").pixel_values.to(self.device)
            with self.torch.no_grad():
                gen = self.model.generate(px, num_beams=self.beams, num_return_sequences=self.n_best,
                                          max_new_tokens=24, output_scores=True, return_dict_in_generate=True)
            texts = self.proc.batch_decode(gen.sequences, skip_special_tokens=True)
            scores = gen.sequences_scores.exp().tolist()  # proba moyenne par token (approx.)
            for j in range(len(pil)):
                sl = slice(j * self.n_best, (j + 1) * self.n_best)
                out.append(list(zip(texts[sl], scores[sl])))
        return out
