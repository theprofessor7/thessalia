"""Sujet nouveau : pas d'acceptation d'office tant que le corrigé ne porte pas lecture_validee."""
import json
from pathlib import Path

import pytest

from thessalia.ocr_run import lecture_validee

# anciens sujets d'examen : sur le PC de l'enseignant seulement (hors dépôt public)
_LOCAL = Path(__file__).resolve().parent.parent
sujets_locaux = pytest.mark.skipif(not (_LOCAL / "templates" / "26_27_Examen_Socle_Python_FR.pdf").exists()
                                   or not (_LOCAL / "keys" / "socle_python_FR.key.json").exists(),
                                   reason="anciens sujets absents (hors dépôt public)")


def test_lecture_validee(tmp_path):
    (tmp_path / "x.vocab.json").write_text(json.dumps({"exam_id": "sujet-x", "fields": {}}), encoding="utf-8")
    assert lecture_validee(tmp_path / "x.vocab.json") is False                     # pas de corrigé
    (tmp_path / "x.key.json").write_text(json.dumps({"exam_id": "sujet-x"}), encoding="utf-8")
    assert lecture_validee(tmp_path / "x.vocab.json") is False                     # drapeau absent
    (tmp_path / "x.key.json").write_text(json.dumps({"exam_id": "sujet-x", "lecture_validee": True}), encoding="utf-8")
    assert lecture_validee(tmp_path / "x.vocab.json") is True


@sujets_locaux
def test_sujets_du_depot():
    assert lecture_validee("keys/socle_python_FR.vocab.json") is True
    assert lecture_validee("keys/python_core_EN.vocab.json") is True
    assert lecture_validee("keys/socle_python_FR_B.vocab.json") is False         # BIS : pas encore mesuré
