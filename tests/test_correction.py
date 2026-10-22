from thessalia.correction import Decisions, group_of


def test_groups_wanted_by_teacher():
    names = ["supA_3", "supA_PRENOM_NOM", "supc_1", "supD", "supD_2", "supNA_1", "supNA_NOM", "sup_nb_4"]
    assert [group_of(n) for n in names] == ["A", "A", "C", "D", "D", "NA", "NA", "NB"]


def test_decisions_roundtrip(tmp_path):
    d = Decisions(tmp_path / "c.sqlite")
    d.set("supD", "c01_q3.1", "faux")
    d.set("supD", "c01_q1", options=["a", "c"])
    assert d.of("supD")["c01_q3.1"]["verdict"] == "faux"
    assert d.of("supD")["c01_q1"]["options"] == ["a", "c"]
    d.set("supD", "c01_q3.1", None, texte="3")          # la lecture s'ajoute sans effacer le verdict
    assert d.of("supD")["c01_q3.1"] == {"verdict": "faux", "texte": "3", "options": None}
    d.set("supD", "c01_q3.1", "juste")                   # et le verdict change sans effacer la lecture
    assert d.of("supD")["c01_q3.1"]["texte"] == "3"
    d.clear("supD", "c01_q3.1")
    assert "c01_q3.1" not in d.of("supD")
    assert d.of("supE") == {}


def test_bareme_verifie_les_points():
    import pytest
    from thessalia.correction import _verifier_bareme
    tpl = {"questions": [{"num": 12, "points": 1.0}],
           "pages": [{"page": 8, "fields": [{"id": "q12", "type": "code_grid", "question": 12}]}]}
    ok = {"champs": {"q12": {"points": 1.0, "criteres": [{"id": "1", "points": 0.5}, {"id": "2", "points": 0.5}]}}}
    _verifier_bareme(ok, tpl)
    faux = {"champs": {"q12": {"points": 1.0, "criteres": [{"id": "1", "points": 0.5}]}}}
    with pytest.raises(SystemExit):
        _verifier_bareme(faux, tpl)


def test_code_vide_crayon_pale():
    import numpy as np
    from thessalia.code_vide import encre
    img = np.full((400, 800), 250, np.uint8)
    img[::20, :] = 225          # quadrillage clair
    img[:, ::20] = 225
    assert encre(img) < 2.0      # quadrillage seul : vide
    for y in range(80, 300, 40):  # écriture au crayon pâle (gris ~170) : lettres de 3 px d'épaisseur
        for x in range(100, 600, 14):
            img[y:y + 12, x:x + 3] = 170
            img[y + 9:y + 12, x:x + 8] = 170
    assert encre(img) > 2.0
