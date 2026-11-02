import json

import pymupdf

from thessalia.common import MM_PER_PT
from thessalia.verif_zones import controler

PT = 1 / MM_PER_PT


def _pdf(tmp_path):
    doc = pymupdf.open()
    p = doc.new_page(width=210 * PT, height=297 * PT)
    for x, y in ((9, 14), (196, 14), (9, 278), (196, 278)):                 # repères pleins vectoriels
        p.draw_rect(pymupdf.Rect(x * PT, y * PT, (x + 5) * PT, (y + 5) * PT), color=None, fill=(0, 0, 0))
    p.draw_rect(pymupdf.Rect(30 * PT, 50 * PT, 33.7 * PT, 53.7 * PT), color=(0, 0, 0), width=0.5)   # case
    p.draw_rect(pymupdf.Rect(60 * PT, 80 * PT, 90 * PT, 80.4 * PT), color=None, fill=(0, 0, 0))    # trait d'un blanc
    f = tmp_path / "s.pdf"
    doc.save(str(f))
    return f


def _zones(tmp_path, k=1.0):
    z = {"zones": [{"id": "q1_opt0", "kind": "checkbox", "page": 1, "x_mm": 30 * k, "y_mm": 50 * k,
                    "w_mm": 3.7 * k, "h_mm": 3.7 * k},
                   {"id": "q2", "kind": "blank", "page": 1, "x_mm": 60 * k, "y_mm": 75 * k, "w_mm": 30 * k,
                    "h_mm": 5 * k}]}
    f = tmp_path / f"z{k}.json"
    f.write_text(json.dumps(z), encoding="utf-8")
    return f


def test_zones_conformes(tmp_path):
    rapport, ok = controler(_pdf(tmp_path), _zones(tmp_path))
    assert ok, rapport
    assert "2 zones conformes sur 2" in rapport and "plein (vectoriel)" in rapport


def test_echelle_4_3_detectee(tmp_path):
    rapport, ok = controler(_pdf(tmp_path), _zones(tmp_path, 4 / 3))
    assert not ok
    assert "multipliées par 4/3" in rapport
