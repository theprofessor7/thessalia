"""Test de bout en bout sur 1 copie synthétique (~1 min) : simulate -> process -> zéro erreur QCM."""
import json
from argparse import Namespace
from pathlib import Path

import pytest

from thessalia.pipeline import Processor
from thessalia.simulate import main as simulate

ROOT = Path(__file__).resolve().parent.parent

# anciens sujets d'examen : sur le PC de l'enseignant seulement (hors dépôt public)
_LOCAL = Path(__file__).resolve().parent.parent
sujets_locaux = pytest.mark.skipif(not (_LOCAL / "templates" / "26_27_Examen_Socle_Python_FR.pdf").exists()
                                   or not (_LOCAL / "keys" / "socle_python_FR.key.json").exists(),
                                   reason="anciens sujets absents (hors dépôt public)")


@sujets_locaux
def test_end_to_end(tmp_path):
    tpl = ROOT / "templates/socle_python_FR.json"
    blank = ROOT / "templates/26_27_Examen_Socle_Python_FR.pdf"
    simulate(Namespace(template=str(tpl), blank=str(blank), out=str(tmp_path / "sim"), copies=1, seed=3, hard=False))
    copies = Processor(tpl, blank, overlays=False, log=lambda *a: None).run([tmp_path / "sim/scans.pdf"], tmp_path / "out")
    assert len(copies) == 1 and copies[0]["missing_pages"] == []
    truth = json.load(open(tmp_path / "sim/truth.json"))["copies"][0]["answers"]
    for fid, t in truth.items():
        got = copies[0]["answers"][fid]
        if got["status"] != "review":
            assert sorted(got["selected"]) == sorted(t["selected"]), fid
    # Niveau 2 : les vignettes nettoyées des réponses courtes sont produites
    shorts = [i for i in copies[0]["fields"].values() if i.get("type") == "short_text"]
    assert len(shorts) == 37 and any(i.get("clean") for i in shorts)
