import pytest

from thessalia.correction import points_champs

GABARIT = {"questions": [{"num": 5, "points": 0.75}],
           "pages": [{"fields": [{"id": "q5.1", "type": "short_text", "question": 5},
                                 {"id": "q5.2", "type": "short_text", "question": 5}]}]}


def test_repartition_du_corrige():
    assert points_champs({"points_champs": {"q5.1": 0.5, "q5.2": 0.25}}, GABARIT) == {"q5.1": 0.5, "q5.2": 0.25}
    assert points_champs({}, GABARIT) == {}


@pytest.mark.parametrize("pc", [{"q5.1": 0.5, "q5.2": 0.5}, {"q5.1": 0.75}, {"q9.1": 0.25}])
def test_repartition_refusee(pc):
    with pytest.raises(SystemExit):
        points_champs({"points_champs": pc}, GABARIT)


def test_forme_et_partiel_du_corrige():
    from thessalia.notes import FORME, JUSTE, PARTIEL, judge, points_partiels
    assert judge('"EMSE"', "EMSE", "text", forme=['"EMSE"']) == FORME
    assert judge("EMSE", "EMSE", "text", forme=['"EMSE"']) == JUSTE
    p = {"{prix}": 0.25}
    assert judge("{prix}", "{prix:.2f}", "text", partiel=p) == PARTIEL
    assert points_partiels(" {prix} ", "text", p) == 0.25
    assert points_partiels("{nom}", "text", p) == 0.0
