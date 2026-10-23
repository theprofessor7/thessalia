import zipfile
from datetime import datetime

from thessalia.excel import arrondi_demi, ecrire_xlsx, sauvegarder


def test_xlsx_lisible(tmp_path):
    p = ecrire_xlsx(tmp_path / "n.xlsx", [("Notes", [["Élève", "Total"], ["DUPONT Éloïse & co", 12.5]], [20, 8]),
                                          ("Absents", [["Élève"]], [20])])
    z = zipfile.ZipFile(p)
    assert z.testzip() is None
    s = z.read("xl/worksheets/sheet1.xml").decode()
    assert "DUPONT Éloïse &amp; co" in s and "<v>12.5</v>" in s
    assert 'name="Absents"' in z.read("xl/workbook.xml").decode()


def test_arrondi_demi_point_superieur():
    assert arrondi_demi(15.083) == 15.5
    assert arrondi_demi(9.542) == 10
    assert arrondi_demi(15.0) == 15
    assert arrondi_demi(15.0000001) == 15
    assert arrondi_demi(12.5) == 12.5
    assert arrondi_demi(0) == 0
    assert arrondi_demi(None) is None


def test_sauvegarde_avant_ecrasement(tmp_path):
    p = tmp_path / "notes.xlsx"
    assert sauvegarder(p) is None                       # rien à sauver
    p.write_bytes(b"v1")
    t = datetime(2026, 10, 23, 14, 5)
    c1 = sauvegarder(p, t)
    assert c1.name == "notes.avant-20261023-1405.xlsx" and c1.read_bytes() == b"v1"
    p.write_bytes(b"v2")
    c2 = sauvegarder(p, t)                              # même minute : pas d'écrasement de la première copie
    assert c2.name == "notes.avant-20261023-1405-2.xlsx" and c2.read_bytes() == b"v2"
    assert c1.read_bytes() == b"v1"
