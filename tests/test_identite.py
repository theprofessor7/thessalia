"""Identification des copies : rapprochement lecture -> liste, fichier copie;etudiant (noms inventés)."""
from thessalia.identite import classer, ecrire_attribution, lire_attributions

ELEVES = ["DUPONT Marie", "DURAND Paul", "MARTIN Léa", "LE GALL--MOREAU Jean Baptiste"]


def test_classer_tolere_libelle_et_fautes():
    lus = {"nom": [["Nom: Durant", 0.6], ["Nom Durand.", 0.3]], "prenom": [["Prénom : Paul", 0.7]]}
    assert classer(lus, ELEVES)[0][0] == "DURAND Paul"
    lus = {"nom": [["LE GALL MOREAU", 0.5]], "prenom": [["Jean-Baptiste", 0.5]]}
    assert classer(lus, ELEVES)[0][0] == "LE GALL--MOREAU Jean Baptiste"
    lus = {"nom": [["Martin", 0.9]], "prenom": [["Lea", 0.9]]}
    r = classer(lus, ELEVES)
    assert r[0][0] == "MARTIN Léa" and r[0][1] - r[1][1] > 0.3


def test_attributions(tmp_path):
    ids = ["copy_001", "copy_002", "copy_003"]
    ecrire_attribution("supX_1", ids, "copy_002", "DUPONT Marie", tmp_path)
    assert lire_attributions("supX_1", tmp_path) == {"copy_002": "DUPONT Marie"}
    txt = (tmp_path / "supX_1.csv").read_text(encoding="utf-8-sig")
    assert "copy_001;supX_1_copie001" in txt          # provisoire gardé pour les autres copies
    ecrire_attribution("supX_1", ids, "copy_002", "", tmp_path)
    assert lire_attributions("supX_1", tmp_path) == {}


def test_repartir_un_eleve_par_copie():
    from thessalia.identite import repartir
    eleves = ["DUPONT Marie", "DURAND Paul", "MARTIN Léa"]
    # copie 2 ressemble un peu à tout le monde : copie par copie, DUPONT gagnerait deux fois
    scores = {"c1": {"DUPONT Marie": 0.9, "DURAND Paul": 0.5, "MARTIN Léa": 0.3},
              "c2": {"DUPONT Marie": 0.7, "DURAND Paul": 0.65, "MARTIN Léa": 0.4},
              "c3": {"DUPONT Marie": 0.3, "DURAND Paul": 0.3, "MARTIN Léa": 0.8}}
    assert repartir(scores, eleves) == {"c1": "DUPONT Marie", "c2": "DURAND Paul", "c3": "MARTIN Léa"}


def test_liste_unique_exigee(tmp_path, monkeypatch):
    import pytest
    from thessalia import identite
    from thessalia.excel import ecrire_xlsx
    monkeypatch.setattr(identite, "LISTS_DIR", tmp_path)
    lignes = [["NOM", "Prénom", "Classe"], ["DUPONT", "Léa", "SUPA"]]
    ecrire_xlsx(tmp_path / "Liste SUP.xlsx", [("Feuil1", lignes, [10, 10, 10])])
    (tmp_path / "~$Liste SUP.xlsx").write_bytes(b"verrou Excel")       # liste ouverte dans Excel : ignoré
    assert sum(len(v) for v in identite.lire_liste().values()) == 1
    ecrire_xlsx(tmp_path / "Liste classe SUP et SPE.xlsx", [("SUP", lignes, [10, 10, 10])])
    with pytest.raises(ValueError, match="Plusieurs listes"):
        identite.lire_liste()
