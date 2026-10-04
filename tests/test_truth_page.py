import json
import re

from thessalia.common import save_json
from thessalia.truth_page import build


def test_truth_page(tmp_path):
    lot = tmp_path / "lot"
    save_json({"copy_id": "copy_001", "fields": {
        "q2.1": {"type": "short_text", "crop": "copy_001\crops\q2.1.png", "blank": False,
                 "ocr": {"value": "int", "status": "ok", "suggestions": ["int", "list"]}},
        "q3.1": {"type": "short_text", "crop": "copy_001\crops\q3.1.png", "blank": True, "suspect": False},
        "q12": {"type": "code_grid"}}}, lot / "copy_001" / "result.json")
    truth = tmp_path / "t.json"
    save_json({"c01_q2.1": "</script>str?"}, truth)
    html = build(lot, truth=truth, log=lambda *a: None).read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
    items = {it["key"]: it for it in data["items"]}
    assert set(items) == {"c01_q2.1", "c01_q3.1"}
    # la vérité existante pré-remplit (« ? » = incertaine) ; sinon la proposition ; un blanc vide reste vide
    assert items["c01_q2.1"]["value"] == "</script>str" and items["c01_q2.1"]["unsure"] and items["c01_q2.1"]["prop"] == "int"
    assert items["c01_q3.1"]["value"] == "" and items["c01_q3.1"]["status"] == "blank"
    assert items["c01_q2.1"]["img"] == "copy_001/crops/q2.1.png"
