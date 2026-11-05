import numpy as np
import pymupdf

from thessalia.common import MM_PER_PT, mm_rect_to_px, render_pdf_pages
from thessalia.omr import decide_grid, read_page
from thessalia.template_builder import build_template

PT = 1 / MM_PER_PT


def _col(sel=(), review=False):
    return {"selected": list(sel), "status": "review" if review else ("ok" if sel else "blank"),
            "flags": ["ambiguë"] if review else []}


def test_decide_grid():
    g = {"id": "identity.grille", "digits": 3}
    ok = decide_grid(g, {"C1": _col("2"), "C2": _col("0"), "C3": _col("7"), "C4": _col()})
    assert ok["status"] == "ok" and ok["value"] == "207"
    assert decide_grid(g, {"C1": _col("2"), "C2": _col(), "C3": _col("7")})["status"] == "review"   # trou
    assert decide_grid(g, {"C1": _col("2"), "C2": _col("0")})["status"] == "review"                 # 2 chiffres sur 3
    assert decide_grid(g, {"C1": _col("2"), "C2": _col("0"), "C3": _col("7"), "C4": _col("1")})["status"] == "review"
    r = decide_grid(g, {"C1": _col("2"), "C2": _col(review=True), "C3": _col("7")})
    assert r["status"] == "review" and r["value"] == "2?7" and "colonne C2" in r["flags"][0]
    assert decide_grid(g, {"C1": _col(), "C2": _col()})["status"] == "blank"
    # grille mal recalée : colonnes nettes mais peut-être lues une case à côté -> revue, même « vide »
    douteux = {"decalage": (0, 0), "sur": False, "raisons": ["bas décalé"]}
    r = decide_grid(g, {"C1": _col("2"), "C2": _col("0"), "C3": _col("7")}, douteux)
    assert r["status"] == "review" and "mal recalée" in r["flags"][0]
    assert decide_grid(g, {"C1": _col(), "C2": _col()}, douteux)["status"] == "review"


def _grille_pdf(tmp_path):
    doc = pymupdf.open()
    p = doc.new_page(width=210 * PT, height=297 * PT)
    for x, y in ((9, 15), (196, 15), (9, 279), (196, 279)):
        p.draw_rect(pymupdf.Rect(x * PT, y * PT, (x + 5) * PT, (y + 5) * PT), color=None, fill=(0, 0, 0))
    p.insert_text((30 * PT, 60 * PT), "Reportez les 3 chiffres", fontsize=9)
    for d in range(10):
        p.insert_text((32 * PT, (82 + 5 * d) * PT), str(d), fontsize=8)
        for c in range(4):
            if d == 0:
                p.insert_text(((41 + 7 * c) * PT, 76 * PT), f"C{c + 1}", fontsize=6)
            x, y = 38 + 7 * c, 78.5 + 5 * d
            sh = p.new_shape()                    # bordure comme WeasyPrint : 2 rectangles, remplissage pair-impair
            sh.draw_rect(pymupdf.Rect(x * PT, y * PT, (x + 6.5) * PT, (y + 4.8) * PT))
            sh.draw_rect(pymupdf.Rect((x + 0.3) * PT, (y + 0.3) * PT, (x + 6.2) * PT, (y + 4.5) * PT))
            sh.finish(color=None, fill=(0, 0, 0), even_odd=True)
            sh.commit()
    f = tmp_path / "g.pdf"
    doc.save(str(f))
    return f


def test_template_trouve_la_grille(tmp_path):
    t = build_template(_grille_pdf(tmp_path))
    g = [x for pg in t["pages"] for x in pg["fields"] if x["type"] == "digit_grid"]
    assert len(g) == 1 and g[0]["digits"] == 3
    assert [c["id"] for c in g[0]["columns"]] == ["C1", "C2", "C3", "C4"]
    assert [o["id"] for o in g[0]["columns"][0]["options"]] == [str(d) for d in range(10)]


def test_grille_decalee_de_plus_d_une_demi_case(tmp_path):
    """Page décalée de 3,5 mm (plus qu'une demi-case, hors de portée de l'ancien recalage par colonne) : la grille
    est recalée en entier, le chiffre lu est le bon. L'ancien code lisait 318 pour 207 (simulation Midterm du
    5 novembre : colonnes lues une case à côté)."""
    f = _grille_pdf(tmp_path)
    t = build_template(f)
    page = t["pages"][0]
    g = [x for x in page["fields"] if x["type"] == "digit_grid"][0]
    vierge = render_pdf_pages(f, 200)[0]
    scan = vierge.copy()
    for col, chiffre in zip(g["columns"], "207"):            # cases noircies dans le scan
        x0, y0, x1, y1 = mm_rect_to_px(next(o for o in col["options"] if o["id"] == chiffre)["inner_mm"], 200)
        scan[y0:y1, x0:x1] = 0
    d = int(round(3.5 * 200 / 25.4))
    decale = np.full_like(scan, 255)
    decale[d:, :] = scan[:-d, :]
    r = read_page(decale, vierge, page["fields"], 200)[g["id"]]
    assert r["status"] == "ok" and r["value"] == "207", r["flags"]
    assert abs(r["recalage"]["decalage"][1] - d) <= 2
