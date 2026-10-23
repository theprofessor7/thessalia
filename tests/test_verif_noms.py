"""Copies à risque sur la page de vérification des identités (noms inventés)."""
from thessalia.verif_noms import risques

LISTE = {"B": ["BERNARDOT Jean", "BERNARDET Paul", "COLIN Marc", "DUMAS Lou"],
         "D": ["MARTEL Ana", "MAURY Eve", "MOREL Ines", "NOLAN Rita", "PAGE Tom", "RIOU Zoe", "VIDAL Max"]}


def test_nom_proche_signale():
    att = [("supB_1", "copy_001", "BERNARDOT Jean"), ("supB_1", "copy_002", "BERNARDET Paul"),
           ("supB_1", "copy_003", "COLIN Marc"), ("supB_1", "copy_004", "DUMAS Lou")]
    r = risques(att, {"B": LISTE["B"]})
    assert r[("supB_1", "copy_001")] == ["nom proche de BERNARDET Paul"]
    assert r[("supB_1", "copy_003")] == []


def test_proche_d_un_absent():
    # MOREL absent : MARTEL (2 rangs avant) et MAURY (1 rang) sont signalés, VIDAL non
    present = ["MARTEL Ana", "MAURY Eve", "NOLAN Rita", "PAGE Tom", "RIOU Zoe", "VIDAL Max"]
    att = [("supD", f"copy_{i:03d}", e) for i, e in enumerate(present, 1)]
    r = risques(att, {"D": LISTE["D"]})
    assert r[("supD", "copy_001")] == ["proche d'un absent : MOREL Ines"]          # « MO » ≠ « MA » : par le rang
    assert r[("supD", "copy_006")] == []
    # même début qu'un absent, loin dans la liste
    att2 = [("supD", "copy_001", "MARTEL Ana")]
    liste2 = {"D": ["MARTEL Ana", "NOLAN Rita", "PAGE Tom", "RIOU Zoe", "VIDAL Max", "MAZEL Jo"]}
    r2 = risques(att2 + [("supD", f"copy_{i:03d}", e) for i, e in enumerate(liste2["D"][1:5], 2)], liste2)
    assert r2[("supD", "copy_001")] == ["proche d'un absent : MAZEL Jo"]


def test_autre_groupe_et_hors_liste():
    att = [("supD", "copy_001", "COLIN Marc"), ("supD", "copy_002", "INCONNU Al")]
    r = risques(att, LISTE)
    assert "élève du groupe B, copie scannée en D" in r[("supD", "copy_001")]
    assert r[("supD", "copy_002")] == ["élève absent de la liste"]
