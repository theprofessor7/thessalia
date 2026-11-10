"""Apprentissage : un lecteur affiné n'est adopté que s'il fait mieux, et l'ancien se rétablit."""
import json

import pytest

from thessalia import apprentissage as A


@pytest.fixture
def modeles(tmp_path, monkeypatch):
    cfg = {k: tmp_path / f"digits_{k}.npz" for k in ("service", "candidat", "precedent")}
    monkeypatch.setattr(A, "CHIFFRES", cfg)
    return cfg


def _candidat(cfg, contenu, mieux=True):
    cfg["candidat"].write_text(contenu)
    A._ecrire_mesure(cfg["candidat"], {"date": "x", "n": 40, "reference": 30, "affine": 36 if mieux else 29, "mieux": mieux})


def test_adopter_puis_revenir(modeles):
    cfg = modeles
    _candidat(cfg, "v1", mieux=False)
    with pytest.raises(SystemExit, match="ne fait pas mieux"):
        A.adopter("chiffres", log=lambda *a: None)
    assert not cfg["service"].exists()
    A.ecarter("chiffres", log=lambda *a: None)
    assert not cfg["candidat"].exists() and not A._meta(cfg["candidat"]).exists()

    _candidat(cfg, "v1")
    A.adopter("chiffres", log=lambda *a: None)
    assert cfg["service"].read_text() == "v1" and A.lire_mesure(cfg["service"])["affine"] == 36
    _candidat(cfg, "v2")
    A.adopter("chiffres", log=lambda *a: None)
    assert cfg["service"].read_text() == "v2" and cfg["precedent"].read_text() == "v1"
    A.revenir("chiffres", log=lambda *a: None)                     # l'ancien remis en service…
    assert cfg["service"].read_text() == "v1" and cfg["precedent"].read_text() == "v2"
    A.revenir("chiffres", log=lambda *a: None)                     # …et un second clic annule
    assert cfg["service"].read_text() == "v2"
    with pytest.raises(SystemExit, match="aucun modèle"):
        A.adopter("chiffres", log=lambda *a: None)


def test_classe_de_test():
    """Lecteur d'écriture : mesuré sur la classe la plus récente qui a assez de lectures vérifiées."""
    ls = [{"ecriture": 50, "date": 1}, {"ecriture": 80, "date": 3}, {"ecriture": 5, "date": 9}]
    assert A.classe_de_test(ls) is ls[1]
    assert A.classe_de_test([{"ecriture": 80, "date": 3}]) is None      # une seule classe : rien pour mesurer
