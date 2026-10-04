"""Niveau 2 — moteurs de reconnaissance pour les réponses courtes (interchangeables).

Interface commune :
    backend.recognize(images, contexts) -> [[(texte, confiance 0..1), …], …]
    une liste de candidats par image, le meilleur d'abord.

Moteurs LOCAUX et gratuits (par défaut, aucune donnée ne sort de la machine) :
    trocr      HuggingFace microsoft/trocr-*-handwritten (modèle téléchargé une fois) — recommandé
    rapidocr   modèles PP-OCR inclus dans le paquet pip ; imprimé surtout
    tesseract  aucun modèle à télécharger ; faible en cursive (témoin)
Options PAYANTES, désactivées tant qu'aucune clé n'est fournie (opt-in explicite) :
    claude     API Anthropic (vision) ; ANTHROPIC_API_KEY
    google     Google Cloud Vision ; GOOGLE_APPLICATION_CREDENTIALS

`contexts` = liste de dicts {"prompt": "type(42) →", "kind": "enum"|"number"|"text"} : seuls
les modèles de langage s'en servent (le contexte aide à lire un mot griffonné).
"""
from __future__ import annotations

import base64
import json
import os
import re

import cv2
import numpy as np


def _pad(img, px=8):
    return cv2.copyMakeBorder(img, px, px, px, px, cv2.BORDER_CONSTANT, value=255)


class TesseractBackend:
    name = "tesseract"

    def __init__(self, lang="eng"):
        import pytesseract
        self.t = pytesseract
        self.lang = lang

    def recognize(self, images, contexts=None):
        out = []
        for img in images:
            im = _pad(img)
            if im.shape[0] < 48:
                f = 48 / im.shape[0]
                im = cv2.resize(im, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
            d = self.t.image_to_data(im, lang=self.lang, config="--psm 7", output_type=self.t.Output.DICT)
            words = [(w, float(c)) for w, c in zip(d["text"], d["conf"]) if w.strip() and float(c) >= 0]
            text = " ".join(w for w, _ in words)
            conf = (sum(c for _, c in words) / len(words) / 100) if words else 0.0
            out.append([(text, conf)])
        return out


class RapidOCRBackend:
    name = "rapidocr"

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR()

    def recognize(self, images, contexts=None):
        out = []
        for img in images:
            im = cv2.cvtColor(_pad(img), cv2.COLOR_GRAY2BGR)
            res, _ = self.engine(im, use_det=False, use_cls=False, use_rec=True)
            if res:
                text, conf = res[0][0], float(res[0][1])
                out.append([(text, conf)])
            else:
                out.append([("", 0.0)])
        return out


class TrOCRBackend:
    """microsoft/trocr-base-handwritten (ou -small-, -large-). Non testé dans l'environnement de
    développement (Hugging Face inaccessible) : à valider sur ta machine."""
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


CLAUDE_PROMPT = """You are transcribing a student's handwritten answer from a scanned exam (Python course).
The question context printed before the blank was: {prompt}
Transcribe EXACTLY what the student wrote as their final answer:
- if a word is crossed out / scribbled over, ignore it and keep only the answer that is not crossed out;
- do NOT correct the student's answer, even if it is wrong; keep their spelling, case, quotes and punctuation;
- if you cannot read part of it, give your best guess and lower the confidence.
Reply with JSON only: {{"text": "...", "alternatives": ["...", "..."], "confidence": 0.0-1.0, "crossed_out": "..." }}"""


class ClaudeBackend:
    """OPTION PAYANTE (opt-in). API Anthropic (vision) : `pip install anthropic` + ANTHROPIC_API_KEY
    (clé de la Console Anthropic, facturée à l'usage, distincte d'un abonnement Claude).
    Non testé dans l'environnement de développement (pas d'accès API) : à valider avant usage.
    Les vignettes envoyées ne contiennent que la réponse, jamais le nom de l'étudiant."""
    name = "claude"
    paid = True

    def __init__(self, model="claude-sonnet-5-5", max_tokens=200):
        _require_env("ANTHROPIC_API_KEY", "claude")
        import anthropic
        self.client = anthropic.Anthropic()
        self.model, self.max_tokens = model, max_tokens

    def recognize(self, images, contexts=None):
        out = []
        for i, img in enumerate(images):
            ctx = (contexts or [{}] * len(images))[i]
            ok, buf = cv2.imencode(".png", _pad(img, 6))
            msg = self.client.messages.create(
                model=self.model, max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": base64.b64encode(buf).decode()}},
                    {"type": "text", "text": CLAUDE_PROMPT.format(prompt=ctx.get("prompt", "?"))}]}])
            out.append(parse_json_answer("".join(b.text for b in msg.content if b.type == "text")))
        return out


def parse_json_answer(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    text = str(d.get("text", raw.strip()))
    conf = float(d.get("confidence", 0.5) or 0.5)
    cands = [(text, conf)] + [(str(a), conf * 0.6) for a in d.get("alternatives", []) if str(a) != text]
    return cands


class GoogleVisionBackend:
    """OPTION PAYANTE (opt-in). Google Cloud Vision (DOCUMENT_TEXT_DETECTION) : google-cloud-vision
    + GOOGLE_APPLICATION_CREDENTIALS. Non testé dans l'environnement de développement."""
    name = "google"
    paid = True

    def __init__(self):
        _require_env("GOOGLE_APPLICATION_CREDENTIALS", "google")
        from google.cloud import vision
        self.v = vision
        self.client = vision.ImageAnnotatorClient()

    def recognize(self, images, contexts=None):
        out = []
        for img in images:
            ok, buf = cv2.imencode(".png", _pad(img, 10))
            resp = self.client.document_text_detection(image=self.v.Image(content=buf.tobytes()),
                                                       image_context={"language_hints": ["en", "fr"]})
            ann = resp.full_text_annotation
            text = (ann.text or "").replace("\n", " ").strip()
            confs = [w.confidence for p in ann.pages for b in p.blocks for pa in b.paragraphs for w in pa.words]
            out.append([(text, float(np.mean(confs)) if confs else 0.0)])
        return out


def _require_env(var, name):
    if not os.environ.get(var):
        raise SystemExit(
            f"Le moteur « {name} » est une option payante désactivée : définir {var} pour l'activer "
            f"(les vignettes anonymes seront envoyées à un service externe). "
            f"Sans clé, utiliser un moteur local : --backend trocr | tesseract | rapidocr.")


BACKENDS = {"tesseract": TesseractBackend, "rapidocr": RapidOCRBackend, "trocr": TrOCRBackend,
            "claude": ClaudeBackend, "google": GoogleVisionBackend}


def get_backend(name, **kw):
    if name not in BACKENDS:
        raise ValueError(f"moteur inconnu : {name} ({', '.join(BACKENDS)})")
    return BACKENDS[name](**kw)
