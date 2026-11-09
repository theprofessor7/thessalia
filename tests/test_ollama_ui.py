"""Page Réglages : extensions installées en un clic (Ollama simulé, rien n'est téléchargé)."""
import time

import pytest

pytest.importorskip("flask")

from thessalia import extensions, ollama_local                       # noqa: E402
from thessalia.serve import create_app                               # noqa: E402


def _attendre(c):
    for _ in range(50):
        t = c.get("/tache").get_json()
        if t and t["etat"] != "en cours":
            return t
        time.sleep(0.1)
    raise AssertionError("tâche trop longue")


def test_extensions(tmp_path, monkeypatch):
    present = set()
    monkeypatch.setattr(ollama_local, "etat", lambda: {"installe": True, "lance": True, "windows": True, "modeles": [
        {"nom": n, "role": r, "taille": t, "present": n in present} for n, r, t in ollama_local.MODELES]})
    monkeypatch.setattr(ollama_local, "telecharger_modele", lambda nom, log: (log(f"{nom} est prêt."), present.add(nom)))
    monkeypatch.setattr(ollama_local, "supprimer_modele", lambda nom, log: (log(f"{nom} supprimé."), present.discard(nom)))
    monkeypatch.setattr(extensions, "trocr_etat", lambda: {"biblio": True, "poids": True, "installe": True})
    (tmp_path / "examens").mkdir()
    c = create_app([], tmp_path / "d.sqlite", examens=tmp_path / "examens").test_client()
    page = c.get("/reglages").get_data(as_text=True)
    assert "Lecteur d&#39;écriture" in page and "qwen3-vl:8b-instruct" in page and page.count(">Télécharger</button>") == 3
    r = c.post("/reglages/extension", data={"id": "qwen3-vl:4b-instruct", "action": "telecharger"})
    assert r.headers["Location"] == "/reglages"
    t = _attendre(c)
    assert t["etat"] == "terminé" and t["journal"] == ["qwen3-vl:4b-instruct est prêt."]
    page = c.get("/reglages").get_data(as_text=True)
    assert page.count(">Télécharger</button>") == 2 and ">Supprimer</button>" in page
    c.post("/reglages/extension", data={"id": "qwen3-vl:4b-instruct", "action": "supprimer"})
    assert _attendre(c)["journal"] == ["qwen3-vl:4b-instruct supprimé."]
    c.post("/reglages/extension", data={"id": "trocr", "action": "inconnue"})
    assert _attendre(c)["etat"] == "erreur"


def test_modele_inconnu_refuse():
    with pytest.raises(SystemExit, match="inconnu"):
        ollama_local.telecharger_modele("n_importe_quoi", log=lambda *a: None)
    with pytest.raises(SystemExit, match="inconnu"):
        ollama_local.supprimer_modele("n_importe_quoi", log=lambda *a: None)
