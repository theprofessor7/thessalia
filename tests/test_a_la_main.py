"""Copies à reprendre sur le papier : page absente ou illisible, jamais passée sous silence."""
from thessalia.report import copies_a_la_main, texte_a_la_main

TEMPLATE = {"pages": [
    {"page": 1, "fields": [{"id": "q1", "type": "mcq"}]},
    {"page": 2, "fields": [{"id": "q2.1", "type": "short_text"}, {"id": "q2.2", "type": "short_text"}]},
    {"page": 3, "fields": []},
]}


def test_pages_absentes_et_illisibles():
    copies = [
        {"copy_id": "copy_001", "missing_pages": [], "unreadable": []},
        {"copy_id": "copy_002", "missing_pages": [1, 2]},
        {"copy_id": "copy_003", "missing_pages": [3], "unreadable": [{"source": "lot.pdf#9", "error": "repères"}]},
    ]
    liste = copies_a_la_main(copies, TEMPLATE)
    assert [c["copie"] for c in liste] == ["copy_002", "copy_003"]
    assert liste[0]["champs"] == ["q1", "q2.1", "q2.2"]
    assert liste[1]["champs"] == [] and liste[1]["illisibles"] == ["lot.pdf#9 : repères"]
    lignes = texte_a_la_main(liste)
    assert "2 copie(s)" in lignes[0] and "aucune réponse lue" in lignes[2]
    assert texte_a_la_main([]) == []
