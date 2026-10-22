import zipfile

from thessalia.excel import ecrire_xlsx


def test_xlsx_lisible(tmp_path):
    p = ecrire_xlsx(tmp_path / "n.xlsx", [("Notes", [["Élève", "Total"], ["DUPONT Éloïse & co", 12.5]], [20, 8]),
                                          ("Absents", [["Élève"]], [20])])
    z = zipfile.ZipFile(p)
    assert z.testzip() is None
    s = z.read("xl/worksheets/sheet1.xml").decode()
    assert "DUPONT Éloïse &amp; co" in s and "<v>12.5</v>" in s
    assert 'name="Absents"' in z.read("xl/workbook.xml").decode()
