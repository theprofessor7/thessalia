"""Application : identifiant et mot de passe avant toute page."""
import json

import pytest

pytest.importorskip("flask")

from thessalia.compte import Compte                                   # noqa: E402
from thessalia.serve import create_app                               # noqa: E402


def test_connexion(tmp_path):
    (tmp_path / "examens").mkdir()
    compte = Compte(tmp_path / "data" / "compte.json")
    c = create_app([], tmp_path / "d.sqlite", examens=tmp_path / "examens", compte=compte).test_client()

    # premier lancement : création du compte, toute page y mène
    assert c.get("/examens").headers["Location"].endswith("/premiere-connexion")
    assert c.post("/api/decision", json={}).status_code == 401
    r = c.post("/premiere-connexion", data={"identifiant": "prof", "mdp": "court", "mdp2": "court"})
    assert "au moins 8" in r.get_data(as_text=True)
    r = c.post("/premiere-connexion", data={"identifiant": "prof", "mdp": "motdepasse1", "mdp2": "motdepasse2"})
    assert "pas identiques" in r.get_data(as_text=True)
    c.post("/premiere-connexion", data={"identifiant": "prof", "mdp": "motdepasse1", "mdp2": "motdepasse1"})
    assert c.get("/examens").status_code == 200                      # connecté aussitôt
    assert "motdepasse1" not in (tmp_path / "data" / "compte.json").read_text(encoding="utf-8")   # jamais en clair

    # déconnexion, puis connexion : mauvais mot de passe refusé, bon accepté, retour à la page demandée
    c.post("/deconnexion")
    r = c.get("/examens")
    assert r.status_code == 302 and "/connexion?suite=/examens" in r.headers["Location"]
    r = c.post("/connexion", data={"identifiant": "prof", "mdp": "faux-faux-faux", "suite": "/examens"})
    assert "incorrect" in r.get_data(as_text=True)
    r = c.post("/connexion", data={"identifiant": "PROF", "mdp": "motdepasse1", "suite": "/examens"})
    assert r.headers["Location"].endswith("/examens")
    r = c.post("/connexion", data={"identifiant": "prof", "mdp": "motdepasse1", "suite": "//ailleurs.example"})
    assert r.headers["Location"] == "/"                                 # jamais de redirection vers un autre site
    assert c.get("/premiere-connexion").headers["Location"].endswith("/connexion")   # un seul compte

