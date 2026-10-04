"""Orchestration : fichiers scannés -> copies -> résultats.

Regroupement en copies : les pages sont identifiées par comparaison avec le
sujet vierge ; une nouvelle copie commence quand le numéro de page identifié
ne progresse pas (ex. ... p16, p17, p1 -> nouvelle copie). Les pages
manquantes sont signalées. Une page illisible (fiducials non trouvés) est
rattachée à la copie en cours et signalée.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from .align import AlignmentError, ReferenceSet, align_page
from .common import RESULT_SCHEMA, load_json, normalize_background, px_per_mm, render_pdf_pages, save_json
from .extract import save_crops
from .grade import grade_copy
from .loader import load_scans
from .ocr_prep import PrepConfig, mark_stacking, prepare_field
from .omr import OMRConfig, read_page
from .report import draw_overlay, write_batch_csv, write_review_csv


def _is_blank(gray, px_mm, max_ink=0.002):
    """Feuille vierge (verso blanc, intercalaire) : quasi aucun trait d'écriture ou d'impression.

    On ne compte que l'encre « fine » (traits < 2 mm) : les grands aplats sombres
    (bord du plateau, couvercle dans un scan A3) ne sont pas du contenu.
    """
    m = int(15 * px_mm)
    core = gray[m:-m, m:-m] if min(gray.shape) > 3 * m else gray
    ink = (normalize_background(core, px_mm) < 0.6).astype(np.uint8)
    ker = max(3, int(2 * px_mm))
    thick = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (ker, ker)))
    thick = cv2.dilate(thick, cv2.getStructuringElement(cv2.MORPH_RECT, (ker, ker)))
    thin = ink & (1 - thick)
    return float(thin.mean()) < max_ink


class Processor:
    def __init__(self, template_path, blank_pdf, dpi=200, omr_cfg: OMRConfig | None = None,
                 answer_key=None, overlays=True, crops=True, log=print, bridge_line=False):
        self.template = load_json(template_path)
        self.dpi = dpi
        self.cfg = omr_cfg or OMRConfig.from_dict(self.template.get("omr"))
        blanks = render_pdf_pages(blank_pdf, dpi)
        if len(blanks) != self.template["page_count"]:
            raise ValueError("Le PDF vierge ne correspond pas au gabarit (nombre de pages).")
        self._check_sha(blank_pdf)
        self.ref = ReferenceSet(self.template, blanks, dpi)
        self.fields = {p["page"]: mark_stacking(p["fields"]) for p in self.template["pages"]}
        self._bn = {}
        self.key = load_json(answer_key) if answer_key else None
        self.overlays, self.crops, self.log = overlays, crops, log
        self.prep_cfg = PrepConfig(bridge_line=bridge_line)

    def _check_sha(self, blank_pdf):
        import hashlib

        sha = hashlib.sha256(Path(blank_pdf).read_bytes()).hexdigest()
        if sha != self.template.get("source_sha256"):
            self.log("ATTENTION : le PDF vierge diffère de celui qui a servi à construire le gabarit.")

    # ------------------------------------------------------------------ copies
    def _new_copy(self, n):
        return {"schema": RESULT_SCHEMA, "exam_id": self.template["exam_id"], "copy_id": f"copy_{n:03d}",
                "pages": {}, "unreadable": [], "answers": {}, "fields": {}, "review": []}

    def run(self, scan_paths, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        copies, cur, last = [], None, 0
        self.blank_pages = []
        N = self.template["page_count"]
        for sp in load_scans(scan_paths, self.dpi):
            expected = last % N + 1
            try:
                al = align_page(sp.gray, sp.px_mm, self.ref, expected_page=expected)
            except AlignmentError as e:
                if _is_blank(sp.gray, sp.px_mm):
                    self.blank_pages.append(sp.label)
                    self.log(f"  {sp.label}: page blanche, ignorée")
                    continue
                if cur is None:
                    cur = self._new_copy(len(copies) + 1)
                    copies.append(cur)
                cur["unreadable"].append({"source": sp.label, "error": str(e)})
                cur["review"].append({"item": sp.label, "reason": f"page illisible : {e}"})
                self.log(f"  {sp.label}: ÉCHEC alignement — {e}")
                continue
            if cur is None or al.page <= last:
                cur = self._new_copy(len(copies) + 1)
                copies.append(cur)
            last = al.page
            self._process_page(cur, sp, al, out_dir)
        for c in copies:
            self._finalize(c, out_dir)
        save_json({"schema": RESULT_SCHEMA + "/batch", "exam_id": self.template["exam_id"],
                   "n_copies": len(copies), "blank_pages": self.blank_pages, "elapsed_s": round(time.time() - t0, 1),
                   "copies": [{k: c[k] for k in ("copy_id", "missing_pages", "flat")}
                              | {"n_review": len(c["review"]), "grade": c.get("grade")} for c in copies]},
                  out_dir / "results.json")
        write_batch_csv(copies, self.template, out_dir / "results.csv")
        write_review_csv(copies, out_dir / "review.csv")
        return copies

    def _process_page(self, cur, sp, al, out_dir):
        cdir = out_dir / cur["copy_id"]
        page = al.page
        fields = self.fields.get(page, [])
        if page in cur["pages"]:
            cur["review"].append({"item": f"page {page}", "reason": f"page en double ({sp.label})"})
        norm = normalize_background(al.image, px_per_mm(self.dpi))
        omr = read_page(al.image, self.ref.pages[page - 1], fields, self.dpi, self.cfg, norm_scan=norm)
        overlay_rel = ""
        if self.overlays:
            op = cdir / "pages" / f"p{page:02d}_overlay.jpg"
            draw_overlay(al.image, fields, omr, self.dpi, op)
            overlay_rel = str(op.relative_to(out_dir))
        if self.crops:
            cur["fields"].update(save_crops(al.image, fields, self.dpi, cdir / "crops", out_dir))
            # Niveau 2 : vignettes nettoyées des réponses courtes (encre étudiant seule)
            blank_n = self._blank_norm(page)
            for f in fields:
                if f["type"] != "short_text":
                    continue
                r = prepare_field(al.image, self.ref.pages[page - 1], f, self.dpi, self.prep_cfg,
                                  norm_scan=norm, norm_blank=blank_n)
                info = cur["fields"].setdefault(f["id"], {"type": "short_text"})
                info.update({"blank": r["blank"], "suspect": r.get("suspect", False), "ink_mm2": r["ink_mm2"]})
                if r["clean"] is not None:
                    cp = cdir / "crops" / f"{f['id']}.clean.png"
                    cv2.imwrite(str(cp), r["clean"])
                    info["clean"] = str(cp.relative_to(out_dir))
        cur["pages"][page] = {
            "source": sp.label, "rotation": al.rotation, "match_score": round(al.score, 3),
            "match_margin": round(al.margin, 3), "fiducials_inferred": al.fiducials.inferred,
            "warnings": al.warnings, "overlay": overlay_rel,
        }
        for w in al.warnings:
            cur["review"].append({"item": f"page {page}", "reason": w, "overlay": overlay_rel})
        for fid, r in omr.items():
            cur["answers"][fid] = r
            if r["status"] == "review":
                cur["review"].append({"item": fid, "reason": "; ".join(r["flags"]), "overlay": overlay_rel})
        n_rev = sum(r["status"] == "review" for r in omr.values())
        self.log(f"  {sp.label} -> {cur['copy_id']} p{page:<2} rot={al.rotation:<3} "
                 f"score={al.score:.2f} qcm={len(omr)} à_revoir={n_rev}"
                 + (f"  [{'; '.join(al.warnings)}]" if al.warnings else ""))

    def _blank_norm(self, page):
        if page not in self._bn:
            self._bn[page] = normalize_background(self.ref.pages[page - 1], px_per_mm(self.dpi))
        return self._bn[page]

    def _finalize(self, c, out_dir):
        present = set(c["pages"])
        omr_pages = {p["page"] for p in self.template["pages"]
                     if any(f["type"] in ("mcq", "truefalse") for f in p["fields"])}
        c["missing_pages"] = sorted(set(range(1, self.template["page_count"] + 1)) - present)
        for mp in sorted(omr_pages - present):
            c["review"].append({"item": f"page {mp}", "reason": "page manquante (contient des QCM)"})
        flat = {}
        for p in self.template["pages"]:
            for f in p["fields"]:
                if f["type"] not in ("mcq", "truefalse"):
                    continue
                r = c["answers"].get(f["id"])
                for o in f["options"]:
                    k = f"{f['id']}.{o['id']}"
                    flat[k] = None if r is None or r["status"] == "review" and \
                        r["options"][o["id"]]["state"] == "ambiguous" else (o["id"] in r["selected"])
        c["flat"] = flat
        if self.key:
            c["grade"] = grade_copy(c["answers"], self.template, self.key)
        c["pages"] = {str(k): v for k, v in sorted(c["pages"].items())}
        save_json(c, out_dir / c["copy_id"] / "result.json")
