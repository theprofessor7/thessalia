"""Énoncé en tête de la vue par question : découpé dans le PDF du sujet, la zone surlignée ; sans PDF, le texte."""
import io

import pytest

pytest.importorskip("flask")


def test_enonce_de_la_question(tmp_path):
    from test_app_examens import _attendre
    from test_sujet import SUJET
    from thessalia.__main__ import main as thessalia
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
               "-o", str(tmp_path / "sim"), "-n", "1"])
    c.post("/examens/essai/deposer", data={"classe": "supA_1", "langue": "fr",
                                           "scan": ((tmp_path / "sim" / "scans.pdf").open("rb"), "lot.pdf")},
           content_type="multipart/form-data")
    assert _attendre(c)["etat"] == "terminé"
    assert c.post("/examens/essai/corriger").status_code == 302

    page = c.get("/g/A").get_data(as_text=True)
    import re
    fid = re.search(r'href="/g/A/q/([^"]+)"', page).group(1)
    html = c.get(f"/g/A/q/{fid}").get_data(as_text=True)
    assert f"/g/A/q/{fid}/enonce.png" in html and 'class="enonce-carte"' in html
    r = c.get(f"/g/A/q/{fid}/enonce.png")
    assert r.status_code == 200 and r.data[:4] == b"\x89PNG"
    r.close()                                                           # Windows : fichier encore ouvert sinon
    assert (prod / "enonces").is_dir()                                  # cache dans l'examen, jamais dans le dépôt

    for p in prod.glob("sujet_*.pdf"):                                  # sans PDF : 404, la page garde le texte
        p.unlink()
    for p in (prod / "enonces").glob("*.png"):
        p.unlink()
    assert c.get(f"/g/A/q/{fid}/enonce.png").status_code == 404
