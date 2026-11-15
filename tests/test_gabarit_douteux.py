"""Mauvaise langue au dépôt (sujet EN lu avec le gabarit FR) : l'alerte « GABARIT DOUTEUX » remonte jusqu'à la
ligne de la classe, en rouge, et pas seulement dans le journal."""
import json

from thessalia.projet import Projet


def _classe(d, nom, results, review=None):
    (d / "scans").mkdir(parents=True, exist_ok=True)
    (d / "scans" / f"{nom}.pdf").write_bytes(b"%PDF-1.4")
    (d / "scans" / f"{nom}.json").write_text(json.dumps({"langue": "fr"}), encoding="utf-8")
    c = d / "classes" / nom
    c.mkdir(parents=True)
    (c / "results.json").write_text(json.dumps(results), encoding="utf-8")
    if review:
        (c / "review.csv").write_text(review, encoding="utf-8")


def test_alerte_gabarit_sur_la_ligne_de_la_classe(tmp_path):
    d = tmp_path / "examens" / "x"
    base = {"n_copies": 2, "copies": [{"n_review": 1}, {"n_review": 0}]}
    _classe(d, "bonne", base)
    _classe(d, "nouvelle", base | {"gabarit_douteux": 0.77})
    _classe(d, "ancienne", base, "copy;item;reason\ncopy_001;lot;GABARIT DOUTEUX : score de reconnaissance "
                                 "médian 0.75 (attendu ≥ 0,85)\n")
    lignes = {c["classe"]: c for c in Projet(d).classes()}
    assert not lignes["bonne"]["gabarit_douteux"]
    assert lignes["nouvelle"]["gabarit_douteux"] == 0.77
    assert lignes["ancienne"]["gabarit_douteux"] == 0.75          # classe lue avant : relu dans review.csv
