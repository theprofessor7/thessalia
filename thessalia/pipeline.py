"""Orchestration : fichiers scannés -> copies -> résultats.

Regroupement en copies : les pages sont identifiées par comparaison avec le
sujet vierge ; une nouvelle copie commence quand le numéro de page identifié
ne progresse pas (ex. ... p16, p17, p1 -> nouvelle copie). Les pages
manquantes sont signalées. Une page illisible (fiducials non trouvés) est
rattachée à la copie en cours et signalée.

Copie hors format : des pages non reconnues mais écrites, qui ne peuvent appartenir ni à la copie qui précède
(déjà complète) ni à celle qui suit (elle commence à sa page 1), forment une copie à part (feuille tapée d'un
élève avec aménagement, autre format…). Rien n'y est lu : l'enseignant la voit en entier et la note à la main.
Ces copies sont numérotées après les autres, pour ne pas décaler les numéros (et les décisions) des copies lues.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from .align import AlignmentError, ReferenceSet, align_page
from .common import RESULT_SCHEMA, load_json, normalize_background, px_per_mm, render_pdf_pages, save_json
from .extract import save_crops, save_qcm_crops
from .grade import grade_copy
from .loader import load_scans
from .ocr_prep import PrepConfig, mark_stacking, prepare_field
from .omr import OMRConfig, read_page
from .report import copies_a_la_main, draw_overlay, texte_a_la_main, write_batch_csv, write_review_csv


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

    def _check_template(self, copies, min_median=0.85):
        """Mauvais gabarit (sujet FR lu avec le gabarit EN ou l'inverse) : les deux sujets ont la même
        mise en page, tout s'aligne et rien n'échoue. Seul le score de reconnaissance des pages le
        trahit : médiane 0,96-0,97 avec le bon gabarit (lots EN et supA 1), 0,75 avec le mauvais
        (lots « sup nb » lus en FR). Sous 0,85 : alerte visible, en tête de la revue."""
        scores = sorted(p["match_score"] for c in copies for p in c["pages"].values())
        if not scores:
            return
        med = scores[len(scores) // 2]
        if med < min_median:
            msg = (f"GABARIT DOUTEUX : score de reconnaissance médian {med:.2f} (attendu > 0,9). "
                   f"Le sujet scanné n'est probablement pas « {self.template['exam_id']} » (FR / EN ?) : "
                   f"résultats à ne pas utiliser.")
            copies[0]["review"].insert(0, {"item": "lot", "reason": msg})
            self.log("  !! " + msg)

    def _check_sha(self, blank_pdf):
        import hashlib

        sha = hashlib.sha256(Path(blank_pdf).read_bytes()).hexdigest()
        if sha != self.template.get("source_sha256"):
            self.log("ATTENTION : le PDF vierge diffère de celui qui a servi à construire le gabarit.")

    # ------------------------------------------------------------------ copies
    def _new_copy(self, n):
        return {"schema": RESULT_SCHEMA, "exam_id": self.template["exam_id"], "copy_id": f"copy_{n:03d}",
                "pages": {}, "unreadable": [], "answers": {}, "fields": {}, "review": []}

    def _illisible(self, c, label, err):
        c["unreadable"].append({"source": label, "error": err})
        c["review"].append({"item": label, "reason": f"page illisible : {err}"})

    def _orphelines(self, cur, last, nouvelle_page, orph, hors_format):
        """Pages non reconnues (écrites) entre deux pages reconnues ; nouvelle_page : page reconnue qui suit (None
        en fin de lot). Suite de la même copie : ce sont ses pages illisibles. Sinon : la fin de la copie en cours
        (s'il lui manque des pages), le début de la suivante (si elle ne commence pas à 1), le reste hors format.
        Retourne les pages du début de la copie suivante."""
        if not orph:
            return []
        if nouvelle_page is not None and nouvelle_page > last:
            for sp, err in orph:
                self._illisible(cur, sp.label, err)
            return []
        fin = min(self.template["page_count"] - last, len(orph))
        for sp, err in orph[:fin]:
            self._illisible(cur, sp.label, err)
            self.log(f"  {sp.label}: rattachée à {cur['copy_id']} (page illisible)")
        reste = orph[fin:]
        debut = min((nouvelle_page or 1) - 1, len(reste))
        suivante = reste[len(reste) - debut:] if debut else []
        reste = reste[:len(reste) - debut]
        if reste:
            hors_format.append(reste)
            self.log(f"  {', '.join(sp.label for sp, _ in reste)}: écrites mais sans repères, entre deux copies "
                     f"complètes → copie hors format, à noter à la main")
        return suivante

    def _hors_format(self, n, pages, out_dir):
        c = self._new_copy(n)
        c.update(hors_format=True, annexes=[], missing_pages=[], flat={})
        d = out_dir / c["copy_id"] / "pages"
        d.mkdir(parents=True, exist_ok=True)
        for i, (sp, err) in enumerate(pages, 1):
            p = d / f"hors_format_{i:02d}.jpg"
            g = sp.gray
            s = min(1.0, 1400 / max(g.shape))
            cv2.imwrite(str(p), cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else g,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
            c["annexes"].append({"source": sp.label, "img": str(p.relative_to(out_dir)).replace("\\", "/")})
            c["unreadable"].append({"source": sp.label, "error": err})
        c["review"].append({"item": "copie", "reason": f"copie hors format ({len(pages)} page(s) sans repères : "
                            f"{', '.join(sp.label for sp, _ in pages)}) : rien n'est lu, à noter à la main"})
        save_json(c, out_dir / c["copy_id"] / "result.json")
        return c

    def run(self, scan_paths, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        copies, cur, last = [], None, 0
        self.blank_pages, self.other_pages, pending = [], [], []
        orph, hors_format = [], []
        N = self.template["page_count"]
        from .loader import count_pages
        jauge = getattr(self.log, "progression", None)
        total = count_pages(scan_paths) if jauge else 0
        for i_page, sp in enumerate(load_scans(scan_paths, self.dpi), 1):
            if total:
                jauge(100 * (i_page - 1) // total, f"page {i_page}/{total}"
                      + (f" · copie {len(copies)}" if copies else ""))
            expected = last % N + 1
            try:
                al = align_page(sp.gray, sp.px_mm, self.ref, expected_page=expected)
            except AlignmentError as e:
                if _is_blank(sp.gray, sp.px_mm):
                    self.blank_pages.append(sp.label)
                    self.log(f"  {sp.label}: page blanche, ignorée")
                    continue
                if cur is None:
                    # avant la première copie : feuille de présence, bordereau… (lots Booster : une
                    # liste d'émargement en tête de chaque PDF). Ignorée mais consignée ; si c'était
                    # la page 1 d'une copie, elle lui est rendue plus bas comme « page illisible ».
                    pending.append((sp.label, str(e)))
                    self.log(f"  {sp.label}: page hors copie avant la première copie "
                             f"(feuille de présence ?), ignorée")
                    continue
                orph.append((sp, str(e)))      # rattachée plus loin, selon la page reconnue qui suit
                self.log(f"  {sp.label}: ÉCHEC alignement — {e}")
                continue
            first = cur is None
            suivante = [] if first else self._orphelines(cur, last, al.page, orph, hors_format)
            orph = []
            if cur is None or al.page <= last:
                cur = self._new_copy(len(copies) + 1)
                copies.append(cur)
                for o, err in suivante:
                    self._illisible(cur, o.label, err)
                    self.log(f"  {o.label}: rattachée à {cur['copy_id']} (page illisible)")
            if first:
                # la première copie ne commence pas à la page 1 : les pages non reconnues juste avant
                # sont sans doute ses premières pages, pas une feuille de présence
                k = min(al.page - 1, len(pending))
                for label, err in pending[len(pending) - k:]:
                    self._illisible(cur, label, err)
                    self.log(f"  {label}: finalement rattachée à {cur['copy_id']} (page illisible)")
                self.other_pages = [label for label, _ in pending[:len(pending) - k]]
            last = al.page
            self._process_page(cur, sp, al, out_dir)
        if cur is None:  # aucune copie reconnue dans le lot
            self.other_pages = [label for label, _ in pending]
        else:
            self._orphelines(cur, last, None, orph, hors_format)
        self._check_template(copies)
        for c in copies:
            self._finalize(c, out_dir)
        n_lues = len(copies)
        for pages in hors_format:
            copies.append(self._hors_format(len(copies) + 1, pages, out_dir))
        if hors_format:
            self.log(f"  {len(hors_format)} copie(s) hors format (numéros {n_lues + 1} et suivants) : à noter à la main "
                     "dans l'outil de correction")
        for ligne in texte_a_la_main(copies_a_la_main(copies, self.template)):
            self.log(ligne)
        save_json({"schema": RESULT_SCHEMA + "/batch", "exam_id": self.template["exam_id"],
                   "n_copies": len(copies), "blank_pages": self.blank_pages, "other_pages": self.other_pages, "elapsed_s": round(time.time() - t0, 1),
                   "copies": [{k: c[k] for k in ("copy_id", "missing_pages", "unreadable", "flat")}
                              | {"n_review": len(c["review"]), "grade": c.get("grade")}
                              | ({"hors_format": True} if c.get("hors_format") else {}) for c in copies]},
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
            save_qcm_crops(al.image, fields, self.dpi, cdir / "crops", (self.template.get("page_size_mm") or [210])[0])
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
