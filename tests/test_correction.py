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
