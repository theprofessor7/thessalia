"""Sorties : overlays de contrôle, CSV batch, liste des points à revoir."""
from __future__ import annotations

import csv
from pathlib import Path

import cv2

from .common import mm_rect_to_px

COLORS = {  # BGR
    "checked": (40, 160, 40),
    "full": (0, 0, 200),
    "ambiguous": (0, 140, 255),
    "empty": (160, 160, 160),
}


def draw_overlay(aligned_img, fields, omr_page, dpi, path: Path, scale=0.6):
    vis = cv2.cvtColor(aligned_img, cv2.COLOR_GRAY2BGR)
    for f in fields:
        if f["type"] in ("mcq", "truefalse"):
            res = omr_page.get(f["id"])
            if not res:
                continue
            for oid, o in res["options"].items():
                x0, y0, x1, y1 = o["box_px"]
                c = COLORS[o["state"]]
                cv2.rectangle(vis, (x0 - 4, y0 - 4), (x1 + 4, y1 + 4), c, 2 if o["state"] != "empty" else 1)
                cv2.putText(vis, f"{o['fill']:.2f}", (x1 + 6, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.35, c, 1,
                            cv2.LINE_AA)
            if res["status"] == "review":
                x0, y0, *_ = mm_rect_to_px(f["options"][0]["bbox_mm"], dpi)
                cv2.putText(vis, "A REVOIR", (max(0, x0 - 10), max(12, y0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            COLORS["ambiguous"], 1, cv2.LINE_AA)
        elif "bbox_mm" in f:
            x0, y0, x1, y1 = mm_rect_to_px(f["bbox_mm"], dpi, pad_mm=1.0)
            cv2.rectangle(vis, (x0, y0), (x1, y1), (200, 120, 0), 1)
            cv2.putText(vis, f["id"], (x0 + 2, y0 + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 120, 0), 1,
                        cv2.LINE_AA)
    if scale != 1:
        vis = cv2.resize(vis, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), vis, [cv2.IMWRITE_JPEG_QUALITY, 82])


def write_batch_csv(copies, template, path: Path):
    cols = []
    for p in template["pages"]:
        for f in p["fields"]:
            if f["type"] in ("mcq", "truefalse"):
                cols += [f"{f['id']}.{o['id']}" for o in f["options"]]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["copy", "pages_ok", "pages_missing", "n_review", "score"] + cols)
        for c in copies:
            flat = c["flat"]
            w.writerow([c["copy_id"], len(c["pages"]), " ".join(map(str, c["missing_pages"])), len(c["review"]),
                        c.get("grade", {}).get("total", "")]
                       + [("" if flat.get(k) is None else int(flat[k])) for k in cols])


def write_review_csv(copies, path: Path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["copy", "item", "reason", "overlay"])
        for c in copies:
            for r in c["review"]:
                w.writerow([c["copy_id"], r["item"], r["reason"], r.get("overlay", "")])


def copies_a_la_main(copies, template):
    """Copies qu'il faut reprendre sur le papier : page absente du scan ou page illisible.

    Les réponses de ces pages n'ont pas d'image : l'outil les laisse à décider (jamais « vide »), mais il faut
    savoir AVANT de corriger quelles copies papier sortir. `copies` : documents result.json (ou leur
    résumé avec copy_id, missing_pages, unreadable)."""
    par_page = {}
    for p in template["pages"]:
        par_page[p["page"]] = [f["id"] for f in p["fields"] if f["type"] in ("mcq", "truefalse", "short_text")]
    out = []
    for c in copies:
        manq, ill = c.get("missing_pages") or [], c.get("unreadable") or []
        if not manq and not ill:
            continue
        out.append({"copie": c["copy_id"], "pages": list(manq),
                    "illisibles": [u.get("source", "?") + " : " + u.get("error", "") for u in ill],
                    "champs": [fid for p in manq for fid in par_page.get(p, [])]})
    return out


def texte_a_la_main(liste):
    """Lignes de terminal pour `process` (vide si rien à signaler)."""
    if not liste:
        return []
    lignes = [f"!! {len(liste)} copie(s) à reprendre sur le papier (page absente ou illisible) :"]
    for c in liste:
        quoi = []
        if c["pages"]:
            quoi.append("page(s) absente(s) " + ", ".join(map(str, c["pages"]))
                        + (f" → {', '.join(c['champs'])}" if c["champs"] else " (aucune réponse lue sur ces pages)"))
        quoi += [f"page illisible ({u})" for u in c["illisibles"]]
        lignes.append(f"   {c['copie']} : " + " ; ".join(quoi))
    return lignes
