"""Construit le gabarit JSON à partir du PDF vierge généré par WeasyPrint.

Le PDF est vectoriel : chaque case, soulignement de réponse, cadre et fiducial
est un rectangle PDF dont on lit les coordonnées exactes. Aucune mesure
manuelle, aucune détection d'image : le gabarit est exact au 1/100 de mm et se
régénère en une commande quand le sujet change.

Règles de reconnaissance (adaptées au template v3) :
    fiducial     rectangle plein sombre ~5x5 mm près d'un coin
    case         bordure sombre (4 côtés) carrée de 2,5 à 6 mm
    blanc        bordure sombre inférieure seule (border-bottom), largeur >= 10 mm
    cadre        bordure sombre (4 côtés), >= 40 x 12 mm ; libellé "PROGRAMME"/"PROGRAM"
                 -> code_grid, sinon text_box
    identité     soulignement gris dans le tableau de la page 1
    question     span "Question N" (+ barème "1,00 pt" sur la même ligne)

Le JSON produit est ensuite éditable à la main (mode single/multi, vocabulaire
attendu, etc.) ; les champs ajoutés à la main sont conservés si on régénère
avec --merge.
"""
from __future__ import annotations

import hashlib
import re
import string
from pathlib import Path

from .common import A4_MM, MM_PER_PT, TEMPLATE_SCHEMA, load_json, save_json

RE_QUESTION = re.compile(r"^\s*Question\s+(\d+)\s*$", re.I)
RE_POINTS = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*pts?\s*$", re.I)
RE_EXERCISE = re.compile(r"^\s*(Exercice|Exercise)\s+(\d+)\s*[—–-]\s*(.*)$", re.I)
RE_MULTI = re.compile(r"plusieurs|several|multiple|all that apply|ceux qui|those that", re.I)
TETE_MM, PIED_MM = 20.0, 280.0   # en-tête courant (y ≈ 12,5 mm) et « Page n / 17 » (y ≈ 285,7 mm) exclus des énoncés
TF_LABELS = {"V", "F", "T", "VRAI", "FAUX", "TRUE", "FALSE"}
IDENTITY_KEYS = [
    (re.compile(r"^pr[ée]nom|^first", re.I), "prenom"),
    (re.compile(r"^nom|^name|^last", re.I), "nom"),
    (re.compile(r"^groupe|^group", re.I), "groupe"),
    (re.compile(r"^n°|^num|^student|^id", re.I), "numero"),
]


def _lum(fill):
    if not fill:
        return 1.0
    r, g, b = fill[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


def _mm(r):
    return [r.x0 * MM_PER_PT, r.y0 * MM_PER_PT, r.x1 * MM_PER_PT, r.y1 * MM_PER_PT]


def _xywh(b):
    return [round(b[0], 2), round(b[1], 2), round(b[2] - b[0], 2), round(b[3] - b[1], 2)]


def _classify_drawings(page):
    """Retourne les primitives utiles d'une page (coordonnées en mm, x0,y0,x1,y1)."""
    fid, boxes, blanks, frames, idlines = [], [], [], [], []
    pw, ph = page.rect.width * MM_PER_PT, page.rect.height * MM_PER_PT
    seen = set()
    for g in page.get_drawings():
        if g.get("type") not in ("f", "fs"):
            continue
        items = g["items"]
        if not items or any(it[0] != "re" for it in items):
            continue
        lum = _lum(g.get("fill"))
        rects = sorted((_mm(it[1]) for it in items), key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
        o = rects[0]
        w, h = o[2] - o[0], o[3] - o[1]
        key = (round(o[0], 1), round(o[1], 1), round(w, 1), round(h, 1), len(items))
        if key in seen:
            continue
        seen.add(key)

        if len(items) == 1:
            near_corner = (min(o[0], pw - o[2]) < 25) and (min(o[1], ph - o[3]) < 30)
            if lum < 0.35 and 3.5 <= w <= 7 and 3.5 <= h <= 7 and abs(w - h) < 0.5 and near_corner:
                fid.append(o)
            continue
        if len(items) != 2:
            continue
        i = rects[1]
        t, r_, b, l = i[1] - o[1], o[2] - i[2], o[3] - i[3], i[0] - o[0]
        sides = [s > 0.08 for s in (t, r_, b, l)]
        if all(sides) and lum < 0.35:
            if 2.5 <= w <= 6.5 and 2.5 <= h <= 6.5 and abs(w - h) < 0.6:
                boxes.append({"outer": o, "inner": i})
            elif w >= 40 and h >= 12:
                frames.append({"outer": o, "inner": i})
        elif sides == [False, False, True, False] and w >= 10 and h <= 9:
            (blanks if lum < 0.35 else idlines if lum < 0.75 else []).append(o)
    return fid, boxes, blanks, frames, idlines


def _spans(page):
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for s in line["spans"]:
                if s["text"].strip():
                    out.append({"text": s["text"].strip(), "bbox": _mm_tuple(s["bbox"])})
    return out


def _mm_tuple(b):
    return [v * MM_PER_PT for v in b]


def _words(page):
    return [
        {"text": w[4], "bbox": _mm_tuple(w[:4])}
        for w in page.get_text("words")
    ]


def _cy(b):
    return (b[1] + b[3]) / 2


def _text_right_of(words, box, stop_x=None, tol=1.6):
    cy = _cy(box)
    sel = [w for w in words if abs(_cy(w["bbox"]) - cy) < tol and w["bbox"][0] >= box[2] - 0.2
           and (stop_x is None or w["bbox"][2] <= stop_x)]
    sel.sort(key=lambda w: w["bbox"][0])
    return " ".join(w["text"] for w in sel).strip()


def _text_left_of(words, box, start_x, tol=2.2):
    cy = _cy(box)
    sel = [w for w in words if abs(_cy(w["bbox"]) - cy) < tol and w["bbox"][2] <= box[0] + 0.5
           and w["bbox"][0] >= start_x]
    sel.sort(key=lambda w: w["bbox"][0])
    return " ".join(w["text"] for w in sel).strip().lstrip("•").strip()


def build_template(pdf_path, exam_id=None) -> dict:
    import pymupdf

    pdf_path = Path(pdf_path)
    doc = pymupdf.open(pdf_path)
    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    # 1) passes : primitives + en-têtes de questions, dans l'ordre du document
    pages = []
    headers = []  # (page, y, qnum, points, exercise)
    current_ex = None
    for pno, page in enumerate(doc, start=1):
        fid, boxes, blanks, frames, idlines = _classify_drawings(page)
        spans, words = _spans(page), _words(page)
        for s in spans:
            m = RE_EXERCISE.match(s["text"])
            if m:
                current_ex = {"num": int(m.group(2)), "title": m.group(3).strip()}
            m = RE_QUESTION.match(s["text"])
            if m:
                pts = None
                for s2 in spans:
                    mp = RE_POINTS.match(s2["text"])
                    if mp and abs(_cy(s2["bbox"]) - _cy(s["bbox"])) < 3:
                        pts = float(mp.group(1).replace(",", "."))
                headers.append({"page": pno, "y": s["bbox"][1], "num": int(m.group(1)),
                                "points": pts, "exercise": current_ex})
        pages.append({"page": pno, "fid": fid, "boxes": boxes, "blanks": blanks,
                      "frames": frames, "idlines": idlines, "spans": spans, "words": words})

    def question_of(pno, y):
        best = None
        for h in headers:
            if (h["page"], h["y"]) <= (pno, y):
                best = h
        return best

    # 2) fiducials
    fid_sets = []
    for p in pages:
        if len(p["fid"]) == 4:
            c = sorted(((round((b[0] + b[2]) / 2, 2), round((b[1] + b[3]) / 2, 2)) for b in p["fid"]),
                       key=lambda t: (t[1], t[0]))
            tl, tr = sorted(c[:2]); bl, br = sorted(c[2:])
            size = round(p["fid"][0][2] - p["fid"][0][0], 2)
            fid_sets.append({"tl": tl, "tr": tr, "br": br, "bl": bl, "size": size})
    if not fid_sets:
        raise ValueError("Aucune page avec 4 fiducials détectés dans le PDF.")
    fid0 = fid_sets[0]
    per_page_fid = any(abs(f["tl"][0] - fid0["tl"][0]) > 0.05 or abs(f["br"][1] - fid0["br"][1]) > 0.05
                       for f in fid_sets)

    # 3) champs
    questions = {}  # num -> dict
    fields_by_page = {p["page"]: [] for p in pages}

    def qentry(h):
        q = questions.setdefault(h["num"], {"num": h["num"], "points": h["points"],
                                            "exercise": h["exercise"], "page": h["page"], "fields": []})
        return q

    for p in pages:
        pno, words = p["page"], p["words"]

        # -- identité (page 1)
        id_lines = [ln for ln in p["idlines"] if question_of(pno, ln[1]) is None]
        for k, ln in enumerate(sorted(id_lines, key=lambda b: (round(b[1]), b[0]))):
            label = ""
            above = [w for w in words if w["bbox"][3] <= ln[1] + 0.5 and ln[1] - w["bbox"][1] < 14
                     and ln[0] - 6 <= w["bbox"][0] <= ln[2]]
            above.sort(key=lambda w: (w["bbox"][1], w["bbox"][0]))
            if above:
                label = " ".join(w["text"] for w in above[:3])
            fid_ = f"identity.{k + 1}"
            for rx, key in IDENTITY_KEYS:
                if rx.search(label):
                    fid_ = f"identity.{key}"
                    break
            box = [ln[0] - 3, ln[1] - 9, ln[2] + 3, ln[3] + 1.5]
            fields_by_page[pno].append({"id": fid_, "type": "identity", "page": pno,
                                        "label": label.rstrip(" :"), "bbox_mm": _xywh(box)})

        # -- cases à cocher, regroupées par question puis par ligne
        by_q = {}
        for b in p["boxes"]:
            h = question_of(pno, b["outer"][1])
            if h is None:
                continue
            by_q.setdefault(h["num"], (h, []))[1].append(b)
        for qnum, (h, bxs) in by_q.items():
            q = qentry(h)
            rows = []
            for b in sorted(bxs, key=lambda b: (_cy(b["outer"]), b["outer"][0])):
                if rows and abs(_cy(rows[-1][0]["outer"]) - _cy(b["outer"])) < 1.5:
                    rows[-1].append(b)
                else:
                    rows.append([b])
            for r in rows:
                r.sort(key=lambda b: b["outer"][0])

            def opt(b, oid, label):
                return {"id": oid, "label": label, "bbox_mm": _xywh(b["outer"]),
                        "inner_mm": _xywh(b["inner"])}

            if max(len(r) for r in rows) >= 2:
                # tableau (ex. V/F) : en-têtes de colonnes au-dessus de la 1re ligne
                first = rows[0]
                col_labels = []
                for c, b in enumerate(first):
                    cx = (b["outer"][0] + b["outer"][2]) / 2
                    cand = [w for w in words if b["outer"][1] - 12 < w["bbox"][3] <= b["outer"][1]
                            and abs((w["bbox"][0] + w["bbox"][2]) / 2 - cx) < 3]
                    col_labels.append(cand[-1]["text"] if cand else string.ascii_uppercase[c])
                is_tf = all(c.upper() in TF_LABELS for c in col_labels)
                for i, r in enumerate(rows, start=1):
                    label = _text_right_of(words, r[-1]["outer"])
                    q["fields"].append({
                        "id": f"q{qnum}.{i}", "type": "truefalse" if is_tf else "mcq",
                        "mode": "single", "page": pno, "prompt": label,
                        "options": [opt(b, col_labels[c] if c < len(col_labels) else str(c), col_labels[c] if c < len(col_labels) else "")
                                    for c, b in enumerate(r)],
                    })
            else:
                opts = []
                for i, r in enumerate(rows):
                    b = r[0]
                    opts.append(opt(b, string.ascii_lowercase[i], _text_right_of(words, b["outer"])))
                q["fields"].append({"id": f"q{qnum}", "type": "mcq", "mode": "single",
                                    "page": pno, "options": opts})

        # -- blancs (réponses courtes)
        for b in sorted(p["blanks"], key=lambda b: (round(_cy(b)), b[0])):
            h = question_of(pno, b[1])
            if h is None:
                continue
            q = qentry(h)
            prev = [f for f in q["fields"] if f["type"] == "short_text" and f["page"] == pno
                    and abs(_cy(_xyxy(f["line_mm"])) - _cy(b)) < 1.5]
            start_x = max((_xyxy(f["line_mm"])[2] for f in prev), default=0)
            prompt = _text_left_of(words, b, start_x)
            box = [b[0] - 2, b[1] - 3, b[2] + 2, b[3] + 1.2]
            q["fields"].append({"id": None, "type": "short_text", "page": pno, "prompt": prompt,
                                "bbox_mm": _xywh(box), "line_mm": _xywh(b), "vocab": None})

        # -- cadres (texte libre / code)
        for fr in sorted(p["frames"], key=lambda f: f["outer"][1]):
            o = fr["outer"]
            h = question_of(pno, o[1])
            if h is None:
                continue
            q = qentry(h)
            inside = [s for s in p["spans"] if o[0] <= s["bbox"][0] and s["bbox"][2] <= o[2]
                      and o[1] <= s["bbox"][1] and s["bbox"][3] <= min(o[3], o[1] + 12)]
            label = " ".join(s["text"] for s in inside if s["text"].isupper() or s["text"][:1].isupper()).strip()
            is_code = bool(re.search(r"PROGRAM", label, re.I))
            q["fields"].append({"id": None, "type": "code_grid" if is_code else "text_box",
                                "page": pno, "label": label, "bbox_mm": _xywh(fr["inner"]),
                                **({"grid_mm": 5.0} if is_code else {})})

    # 4) identifiants stables et mode single/multi
    for qnum, q in sorted(questions.items()):
        prompt_words = []

        def _first_y(pno):
            ys = [(f.get("bbox_mm") or f["options"][0]["bbox_mm"])[1] for f in q["fields"] if f["page"] == pno]
            return min(ys) if ys else None

        for p in pages:
            if p["page"] == q["page"]:
                hy = next(h["y"] for h in headers if h["num"] == qnum)
                fy = _first_y(q["page"])
                if fy is None and not q["fields"]:
                    fy = hy + 30
                # énoncé en bas de page, cadres sur la page suivante : l'énoncé va jusqu'au pied de page
                prompt_words = [s["text"] for s in p["spans"] if hy + 4 < s["bbox"][1] < (fy or PIED_MM) - 0.5]
                if fy is None:
                    nxt = min((f["page"] for f in q["fields"]), default=None)
                    for p2 in pages:
                        if p2["page"] == nxt:
                            prompt_words += [s["text"] for s in p2["spans"]
                                             if TETE_MM < s["bbox"][1] < _first_y(nxt) - 0.5]
        q["prompt"] = " ".join(prompt_words)[:400]
        shorts = [f for f in q["fields"] if f["type"] == "short_text"]
        for i, f in enumerate(shorts, start=1):
            f["id"] = f"q{qnum}.{i}" if len(shorts) > 1 else f"q{qnum}"
        frames = [f for f in q["fields"] if f["type"] in ("code_grid", "text_box")]
        for i, f in enumerate(frames):
            f["id"] = f"q{qnum}.{string.ascii_lowercase[i]}" if len(frames) > 1 else f"q{qnum}"
        for f in q["fields"]:
            if f["type"] == "mcq" and f["id"] == f"q{qnum}":
                f["mode"] = "multi" if RE_MULTI.search(q["prompt"]) else "single"
        kinds = {f["type"] for f in q["fields"]}
        if len(kinds) > 1:  # évite les collisions d'id entre types dans une même question
            for f in q["fields"]:
                if f["type"] in ("code_grid", "text_box") and not re.search(r"\.[a-z]$", f["id"]):
                    f["id"] += ".code" if f["type"] == "code_grid" else ".text"

    tpl_pages = []
    for p in pages:
        flds = list(fields_by_page[p["page"]])
        for q in questions.values():
            for f in q["fields"]:
                if f["page"] == p["page"]:
                    flds.append({**f, "question": q["num"]})
        entry = {"page": p["page"], "fields": flds}
        if per_page_fid:
            entry["fiducials_mm"] = next((f for f in fid_sets), fid0)
        tpl_pages.append(entry)

    return {
        "schema": TEMPLATE_SCHEMA,
        "exam_id": exam_id or pdf_path.stem,
        "source_pdf": pdf_path.name,
        "source_sha256": sha,
        "page_count": len(pages),
        "page_size_mm": [round(doc[0].rect.width * MM_PER_PT, 2), round(doc[0].rect.height * MM_PER_PT, 2)]
        if len(doc) else list(A4_MM),
        "fiducials_mm": {k: fid0[k] for k in ("tl", "tr", "br", "bl")},
        "fiducial_size_mm": fid0["size"],
        "questions": [
            {"num": q["num"], "id": f"q{q['num']}", "points": q["points"],
             "exercise": q["exercise"], "page": q["page"], "prompt": q["prompt"],
             "field_ids": [f["id"] for f in q["fields"]]}
            for q in sorted(questions.values(), key=lambda q: q["num"])
        ],
        "pages": tpl_pages,
    }


def _xyxy(r):
    return [r[0], r[1], r[0] + r[2], r[1] + r[3]]


def merge_manual_edits(new: dict, old: dict) -> dict:
    """Reporte les réglages faits à la main (mode, vocab, points, champs 'manual')."""
    keep_keys = ("mode", "vocab", "expected_lang", "notes")
    old_fields = {f["id"]: f for p in old.get("pages", []) for f in p["fields"]}
    for p in new["pages"]:
        for f in p["fields"]:
            of = old_fields.get(f["id"])
            if of:
                for k in keep_keys:
                    if k in of:
                        f[k] = of[k]
        for of in (f for op in old.get("pages", []) if op["page"] == p["page"] for f in op["fields"]):
            if of.get("manual"):
                p["fields"].append(of)
    return new


def summarize(tpl: dict) -> str:
    from collections import Counter

    c = Counter(f["type"] for p in tpl["pages"] for f in p["fields"])
    nbox = sum(len(f["options"]) for p in tpl["pages"] for f in p["fields"] if "options" in f)
    lines = [f"{tpl['exam_id']}: {tpl['page_count']} pages, {len(tpl['questions'])} questions, "
             f"{nbox} cases à cocher", "  champs: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items()))]
    for p in tpl["pages"]:
        ids = [f["id"] + ("[" + f.get("mode", "") + "]" if f["type"] == "mcq" else "") for p2 in [p] for f in p2["fields"]]
        if ids:
            lines.append(f"  p{p['page']:>2}: " + " ".join(ids))
    return "\n".join(lines)


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="PDF vierge -> gabarit JSON")
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--exam-id")
    ap.add_argument("--merge", help="gabarit existant dont on conserve les réglages manuels")
    a = ap.parse_args(argv)
    tpl = build_template(a.pdf, a.exam_id)
    if a.merge and Path(a.merge).exists():
        tpl = merge_manual_edits(tpl, load_json(a.merge))
    save_json(tpl, a.out)
    print(summarize(tpl))


if __name__ == "__main__":
    main()
