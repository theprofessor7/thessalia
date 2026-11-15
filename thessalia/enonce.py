"""Énoncé d'une question tel que l'élève l'a vu : découpé dans le PDF du sujet vierge, la zone à corriger
surlignée. Affiché en tête de la vue par question de l'outil de correction (le texte du gabarit perd les retours
à la ligne et la mise en forme du code).

La question va de son titre « Question N » au titre suivant (question ou exercice) sur la même page, sinon
jusqu'au bas du contenu de la page. Titre introuvable : une bande autour de la zone. Rien ne se décide ici :
en cas d'échec, l'outil garde l'énoncé en texte."""
from __future__ import annotations

import re
from pathlib import Path

MM = 72 / 25.4
TITRE = re.compile(r"^\s*(question|exercice|exercise)\b", re.I)


def pdf_du_sujet(template: dict, dossiers) -> Path | None:
    """PDF du sujet vierge : nom donné par le gabarit, ou `sujet_<exam_id>.pdf` (examen de l'application)."""
    noms = [template.get("source_pdf"), f"sujet_{template.get('exam_id')}.pdf"]
    for d in dossiers:
        for n in noms:
            if n and d and (Path(d) / Path(n).name).exists():
                return Path(d) / Path(n).name
    return None


def _cadre(page, champ, num):
    """Rectangle (points PDF) de la question qui contient le champ."""
    import pymupdf
    w, h = page.rect.width, page.rect.height
    x0, y0, bw, bh = (v * MM for v in champ["bbox_mm"])
    blocs = [b for b in page.get_text("blocks") if b[4].strip() and b[1] < h - 40]   # sans le pied de page
    titre = next((b for b in blocs if re.match(rf"^\s*question\s*{num}\b", b[4], re.I) and b[1] <= y0 + 2), None)
    marge = 0.07 * w
    if titre is None:
        return pymupdf.Rect(marge, max(0, y0 - 90), w - marge, min(h, y0 + bh + 40))
    haut = titre[1] - 6
    suivants = [b[1] for b in blocs if TITRE.match(b[4]) and b[1] > max(haut + 12, y0 + bh)]
    if suivants:
        bas = min(suivants) - 4
    else:
        bas = max([b[3] for b in blocs if b[1] >= haut] + [y0 + bh]) + 6
    return pymupdf.Rect(marge, haut, w - marge, min(h, max(bas, y0 + bh + 6)))


def image_question(pdf: Path, template: dict, fid: str, sortie: Path, dpi: int = 150) -> Path | None:
    """PNG de la question du champ `fid`, zone surlignée. Refait si le PDF est plus récent. None si impossible."""
    champ = next((f for p in template["pages"] for f in p["fields"] if f["id"] == fid), None)
    if not champ or not champ.get("bbox_mm") or not pdf:
        return None
    sortie = Path(sortie)
    if sortie.exists() and sortie.stat().st_mtime >= Path(pdf).stat().st_mtime:
        return sortie
    import pymupdf
    with pymupdf.open(pdf) as doc:
        n = champ.get("page", 1) - 1
        if not 0 <= n < doc.page_count:
            return None
        page = doc[n]
        clip = _cadre(page, champ, champ.get("question"))
        x0, y0, bw, bh = (v * MM for v in champ["bbox_mm"])
        zone = pymupdf.Rect(x0 - 2, y0 - 2, x0 + bw + 2, y0 + bh + 2)
        petit = bh < 40          # blanc à compléter : surligné ; grand cadre (code) : contour seul
        page.draw_rect(zone, color=(0.93, 0.55, 0.05), fill=(1, 0.86, 0.25) if petit else None,
                       fill_opacity=0.35, width=1.4 if petit else 2.2)
        sortie.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(clip=clip, dpi=dpi).save(sortie)
    return sortie
