from pathlib import Path

import pytest

from thessalia.template_builder import build_template

T = Path(__file__).resolve().parent.parent / "templates"


@pytest.mark.parametrize("pdf", ["26_27_Examen_Socle_Python_FR.pdf", "26_27_Exam_Python_Core_EN.pdf"])
def test_builder_finds_everything(pdf):
    tpl = build_template(T / pdf)
    fields = [f for p in tpl["pages"] for f in p["fields"]]
    kinds = {k: sum(f["type"] == k for f in fields) for k in ("mcq", "truefalse", "short_text", "code_grid", "identity")}
    assert tpl["page_count"] == 17
    assert len(tpl["questions"]) == 19
    assert kinds == {"mcq": 2, "truefalse": 6, "short_text": 37, "code_grid": 8, "identity": 4}
    assert sum(len(f["options"]) for f in fields if "options" in f) == 24
    assert list(tpl["fiducials_mm"]["tl"]) == [11.5, 17.5]
