"""Service en ligne (option payante) : réglages depuis l'application, clé masquée, estimation, plafond respecté."""
import json
from types import SimpleNamespace

import numpy as np
import cv2
import pytest

from thessalia import lecteur_code as L


@pytest.fixture
def ici(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "REGLAGES", tmp_path / "data" / "lecteur.json")
    monkeypatch.setattr(L, "CLE_FICHIER", tmp_path / "data" / "lecteur.cle")
    monkeypatch.setattr(L, "DEPENSES", tmp_path / "data" / "lecteur_depenses.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return tmp_path


def test_reglages_service_et_cle(ici):
    et = L.etat_en_ligne()
    assert et["cle_service"] == "claude" and et["service"]["mesure"] and "clé à coller" in et["manque"]
    with pytest.raises(ValueError):
        L.enregistrer_cle("sk ant")
    L.enregistrer_cle("  sk-ant-api03-abcdefWXYZ \n")
    et = L.etat_en_ligne()
    assert et["cle"] == "…WXYZ" and et["cle_fichier"] and "clé à coller" not in et["manque"]
    assert "sk-ant" not in json.dumps({k: v for k, v in et.items() if k != "services"})   # jamais la clé en clair

    # autre service : ses valeurs par défaut (modèle et prix à saisir : non mesuré) ; le plafond est gardé
    L.enregistrer(plafond="5,5")
    L.enregistrer(service="mistral")
    r = L.reglages()
    assert r["fournisseur"] == "openai" and r["adresse"] == "https://api.mistral.ai/v1" and r["plafond_dollars"] == 5.5
    et = L.etat_en_ligne()
    assert not et["service"]["mesure"] and "modèle à indiquer" in et["manque"] and any("prix" in m for m in et["manque"])
    L.enregistrer(service="mistral", modele=" pixtral-x ", prix_entree="2", prix_sortie="6", adresse="ignorée")
    r = L.reglages()
    assert r["modele"] == "pixtral-x" and r["adresse"] == "https://api.mistral.ai/v1"      # adresse fixe hors « autre »
    L.supprimer_cle()
    assert L.etat_en_ligne()["cle"] is None


def test_anciens_reglages_sans_service(ici):
    L.REGLAGES.parent.mkdir(parents=True)
    L.REGLAGES.write_text(json.dumps({"fournisseur": "openai", "modele": "m", "adresse": "https://x/v1"}), encoding="utf-8")
    assert L.reglages()["service"] == "autre"


class _Faux:
    def __init__(self):
        self.envois = 0

    def lire(self, png, consigne):
        self.envois += 1
        return "```python\nprint('ok')\n```", 1_000_000, 100_000          # 4 $ + 2 $ au prix de Claude


def _plans(tmp_path, n):
    d = tmp_path / "classe"
    (d / "crops").mkdir(parents=True)
    cv2.imwrite(str(d / "crops" / "c.png"), np.full((300, 2800), 255, np.uint8))
    ex = SimpleNamespace(fields={"q5": {"question": 5}}, template={"questions": [{"num": 5, "prompt": "Écrire f"}]})
    items = [("q5", f"c{i:02d}_q5", {"crop": "crops\\c.png"}) for i in range(1, n + 1)]
    return [(d, SimpleNamespace(exam=ex), {"q5": {}}, d / L.LECTURES, {}, items)]


def test_estimation_puis_plafond(ici, monkeypatch):
    plans = _plans(ici, 3)
    monkeypatch.setattr(L, "a_transcrire", lambda dossiers, champs=None: plans)
    e = L.estimer([])
    # image réduite à 1400 x 150 : 280 jetons + 500 de texte, 300 en réponse, × 3 cadres
    assert e["cadres"] == 3 and e["cout"] == round((3 * 780 * 4 + 3 * 300 * 20) / 1e6, 2) and e["reste"] == 10.0

    faux = _Faux()
    monkeypatch.setattr(L, "lecteur", lambda r: faux)
    with pytest.raises(SystemExit, match="pas prêt"):                 # pas de clé : rien n'est envoyé
        L.run_en_ligne([])
    assert faux.envois == 0
    L.enregistrer_cle("sk-ant-essai-1234")
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda nom, *a: True)
    L.run_en_ligne([])
    # 6 $ par cadre, plafond 10 $ : le deuxième envoi dépasse, le troisième n'est jamais fait
    assert faux.envois == 2
    lu = json.loads((ici / "classe" / L.LECTURES).read_text(encoding="utf-8"))
    assert lu["c01_q5"]["code"] == "print('ok')" and lu["c01_q5"]["cout"] == 6.0
    assert L.depense()["total_dollars"] == 12.0
    assert L.estimer([])["cadres_possibles"] == 0
    with pytest.raises(SystemExit, match="Plafond atteint"):
        L.run_en_ligne([])
    assert faux.envois == 2


def test_page_reglages_et_routes(ici, monkeypatch):
    pytest.importorskip("flask")
    from thessalia.serve import create_app
    app = create_app([], ici / "decisions.sqlite", examens=ici / "examens")
    c = app.test_client()
    page = c.get("/reglages").get_data(as_text=True)
    assert 'id="en-ligne"' in page and "coller la clé ici" in page and "Claude (Anthropic)" in page
    monkeypatch.setattr(L, "verifier_cle", lambda: (False, "clé refusée par le service"))
    r = c.post("/reglages/en-ligne/cle", data={"action": "enregistrer", "cle": "sk-ant-mauvaise-0000"})
    assert "Attention" in r.headers["Location"] and r.headers["Location"].endswith("#en-ligne")
    page = c.get("/reglages").get_data(as_text=True)
    assert "…0000" in page and "sk-ant-mauvaise" not in page
    c.post("/reglages/en-ligne", data={"service": "chatgpt"})
    page = c.get("/reglages").get_data(as_text=True)
    assert "Non mesuré" in page and "modèle à indiquer" in page
    c.post("/reglages/en-ligne/cle", data={"action": "supprimer"})
    assert not L.CLE_FICHIER.exists()
