"""Copie hors format : des pages écrites sans les repères du sujet (feuille tapée d'un élève avec aménagement),
glissées entre deux copies complètes, forment une copie à part, notée à la main — jamais collées à la copie
voisine (l'élève serait compté absent), jamais lues comme vides."""
import io
import json
from types import SimpleNamespace

import pytest

from thessalia.pipeline import Processor


def _proc(n_pages=4):
    p = Processor.__new__(Processor)
    p.template, p.log = {"page_count": n_pages}, lambda *a: None
    return p


def _pages(*labels):
    return [(SimpleNamespace(label=l), "fiducials introuvables") for l in labels]


def _copie():
    return {"copy_id": "copy_001", "unreadable": [], "review": []}


def test_pages_entre_deux_copies_completes():
    p, cur, hf = _proc(), _copie(), []
    suivante = p._orphelines(cur, 4, 1, _pages("lot#5", "lot#6"), hf)   # copie complète (4/4), la suivante en p1
    assert suivante == [] and cur["unreadable"] == []
    assert [[sp.label for sp, _ in g] for g in hf] == [["lot#5", "lot#6"]]


def test_page_illisible_au_milieu_reste_dans_sa_copie():
    p, cur, hf = _proc(), _copie(), []
    assert p._orphelines(cur, 2, 4, _pages("lot#3"), hf) == []        # p2, ?, p4 : c'est la page 3 de la copie
    assert [u["source"] for u in cur["unreadable"]] == ["lot#3"] and hf == []


def test_fin_de_copie_puis_debut_de_la_suivante_puis_hors_format():
    p, cur, hf = _proc(), _copie(), []
    # copie arrêtée en p3 (il lui manque p4), la suivante reconnue d'abord en p2 (il lui manque p1)
    suivante = p._orphelines(cur, 3, 2, _pages("lot#4", "lot#5", "lot#6"), hf)
    assert [u["source"] for u in cur["unreadable"]] == ["lot#4"]       # sa page 4
    assert [sp.label for sp, _ in suivante] == ["lot#6"]                # page 1 de la copie suivante
    assert [[sp.label for sp, _ in g] for g in hf] == [["lot#5"]]


def test_fin_de_lot():
    p, cur, hf = _proc(), _copie(), []
    p._orphelines(cur, 4, None, _pages("lot#9"), hf)                    # après la dernière copie, complète
    assert cur["unreadable"] == [] and len(hf) == 1


pytest.importorskip("flask")


def test_copie_tapee_dans_le_lot(tmp_path):
    """De bout en bout : 2 copies simulées et une feuille tapée entre elles ; la feuille devient la copie 3,
    se note dans l'outil, et la note part à l'export."""
    import pymupdf

    from test_app_examens import _attendre
    from test_sujet import SUJET
    from thessalia.__main__ import main as thessalia
    from thessalia.excel import ecrire_xlsx
    from thessalia.identite import _xlsx_rows
    from thessalia.serve import create_app

    racine = tmp_path / "examens"
    racine.mkdir()
    c = create_app([], tmp_path / "decisions.sqlite", examens=racine).test_client()
    c.post("/examens/nouveau", data={"nom": "essai", "source": (io.BytesIO(SUJET.encode()), "examen.yaml")},
           content_type="multipart/form-data")
    c.post("/examens/essai/produire")
    assert _attendre(c)["etat"] == "terminé"
    prod = racine / "essai" / "produit"
    thessalia(["simulate", "-t", str(prod / "gabarits" / "gabarit_ESSAI_FR.json"), "-b", str(prod / "sujet_ESSAI_FR.pdf"),
               "-o", str(tmp_path / "sim"), "-n", "2"])
    lot = pymupdf.open(tmp_path / "sim" / "scans.pdf")
    n = lot.page_count // 2
    tapee = lot.new_page(n, width=595, height=842)                     # entre la copie 1 et la copie 2
    tapee.insert_text((60, 80), "Élève inventé\n\n" + "\n".join(f"Question {i} : réponse tapée {i}" for i in range(1, 30)),
                      fontsize=12)
    scans = lot.tobytes()
    c.post("/examens/essai/deposer", data={"classe": "supA_1", "langue": "fr", "scan": (io.BytesIO(scans), "lot.pdf")},
           content_type="multipart/form-data")
    t = _attendre(c)
    assert t["etat"] == "terminé", t["journal"]

    cl = racine / "essai" / "classes" / "supA_1"
    res = json.loads((cl / "results.json").read_text(encoding="utf-8"))
    assert [x.get("hors_format", False) for x in res["copies"]] == [False, False, True]
    assert all(not x["unreadable"] for x in res["copies"][:2])          # rien de collé aux copies voisines
    doc = json.loads((cl / "copy_003" / "result.json").read_text(encoding="utf-8"))
    assert len(doc["annexes"]) == 1 and (cl / doc["annexes"][0]["img"]).exists()

    assert c.post("/examens/essai/corriger").status_code == 302
    page = c.get("/c/supA_1/copy_003").get_data(as_text=True)
    assert "Copie hors format" in page and "Note à saisir" in page
    assert c.get("/img/supA_1/" + doc["annexes"][0]["img"]).status_code == 200
    # aucune réponse « à décider » inventée pour cette copie
    accueil = c.get("/g/A/copies").get_data(as_text=True)
    assert "note à saisir" in accueil

    r = c.post("/c/supA_1/copy_003/note-hors-format", data={"note": "abc"})
    assert "pas+un+nombre" in r.headers["Location"]
    r = c.post("/c/supA_1/copy_003/note-hors-format", data={"note": "999"})
    assert "refus" in r.headers["Location"]
    r = c.post("/c/supA_1/copy_003/note-hors-format", data={"note": "1,5"})
    assert "enregistr" in r.headers["Location"], r.headers["Location"]
    assert "Notée à la main" in c.get("/c/supA_1/copy_003").get_data(as_text=True)

    # export : la note saisie compte, l'élève n'est pas absent
    ecrire_xlsx(tmp_path / "liste.xlsx", [("Liste", [["NOM", "Prénom", "Classe"], ["MARTIN", "Alice", "supA_1"],
                                                     ["DURAND", "Paul", "supA_1"], ["PETIT", "Zoé", "supA_1"]], [10, 10, 10])])
    c.post("/examens/essai/liste", data={"liste": ((tmp_path / "liste.xlsx").open("rb"), "liste.xlsx")},
           content_type="multipart/form-data")
    r = c.post("/api/identite", json={"classe": "supA_1", "copie": "copy_003", "etudiant": "PETIT Zoé"})
    assert r.status_code == 200, r.get_json()
    c.post("/examens/essai/notes")
    t = _attendre(c)
    assert t["etat"] == "terminé", t["journal"]
    lignes = _xlsx_rows(racine / "essai" / "notes" / "notes.xlsx")
    zoe = next(list(l.values()) for l in lignes if "PETIT Zoé" in l.values())
    assert "1.5" in [str(x) for x in zoe], zoe
    assert any("3 copies, 2 absents" in l for l in t["journal"]), t["journal"]   # PETIT Zoé n'est pas absente
