"""Étape 4 de l'application : Ollama et ses modèles installés en un clic (Ollama simulé, rien n'est téléchargé)."""
import io
import time

import pytest

pytest.importorskip("flask")

from thessalia import ollama_local                                   # noqa: E402
from thessalia.serve import create_app                               # noqa: E402

from test_sujet import SUJET                                          # noqa: E402


def test_boutons_ollama(tmp_path, monkeypatch):
    present = set()
    monkeypatch.setattr(ollama_local, "etat", lambda: {"installe": True, "lance": True, "windows": True, "modeles": [
        {"nom": n, "role": r, "taille": t, "present": n in present} for n, r, t in ollama_local.MODELES]})
    monkeypatch.setattr(ollama_local, "telecharger_modele", lambda nom, log: (log(f"{nom} est prêt."), present.add(nom)))
    (tmp_path / "examens").mkdir()
    c = create_app([], tmp_path / "d.sqlite", examens=tmp_path / "examens").test_client()
    c.post("/examens/nouveau", data={"nom": "essai", "source": (io.BytesIO(SUJET.encode()), "examen.yaml")},
           content_type="multipart/form-data")
    page = c.get("/examens/essai").get_data(as_text=True)
    assert "qwen3-vl:8b-instruct" in page and page.count(">Télécharger</button>") == 3
    c.post("/examens/essai/ollama/modele", data={"nom": "qwen3-vl:4b-instruct"})
    for _ in range(50):
        t = c.get("/tache").get_json()
        if t["etat"] != "en cours":
            break
        time.sleep(0.1)
    assert t["etat"] == "terminé" and t["journal"] == ["qwen3-vl:4b-instruct est prêt."]
    assert c.get("/examens/essai").get_data(as_text=True).count(">Télécharger</button>") == 2


def test_modele_inconnu_refuse():
    with pytest.raises(SystemExit, match="inconnu"):
        ollama_local.telecharger_modele("n_importe_quoi", log=lambda *a: None)
