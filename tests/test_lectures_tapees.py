"""Lectures tapées par l'enseignant : une erreur fréquente d'élève ({prix} pour {prix:.2f}) saisie une fois se
reprend en un clic, puis entre dans les mauvaises réponses plausibles de la lecture suivante."""
import json
from types import SimpleNamespace

from thessalia.correction import Decisions, lectures_tapees
from thessalia.projet import Projet


def test_compte_par_champ(tmp_path):
    dec = Decisions(tmp_path / "d.sqlite")
    dec.set("supA_1", "c01_q3.2", texte="{prix}")
    dec.set("supA_1", "c02_q3.2", texte="{prix}", verdict="faux")
    dec.set("supA_1", "c03_q3.2", verdict="juste")            # verdict seul : pas une lecture
    dec.set("supA_1", "c04_q3.1", texte="{prix}")             # autre champ
    dec.set("supH", "c01_q3.2", texte="{prix}")
    dec.set("supH", "c02_q3.2", texte="auto:x")               # pré-décision automatique : exclue
    classes = [SimpleNamespace(name=n, decisions=dec) for n in ("supA_1", "supH")]
    assert lectures_tapees(classes, "q3.2") == {"{prix}": 3}


def test_vocab_enrichi(tmp_path):
    p = Projet.__new__(Projet)
    vocab = tmp_path / "X_FR.vocab.json"
    vocab.write_text(json.dumps({"exam_id": "X_FR", "fields": {
        "q3.2": {"kind": "text", "values": ["{prix:.2f}"]}, "q1.1": {"kind": "number"}}}), encoding="utf-8")
    scans = tmp_path / "scans"
    scans.mkdir()
    for n, langue in (("supA_1", "fr"), ("supB_1", "en")):
        (scans / f"{n}.json").write_text(json.dumps({"langue": langue}), encoding="utf-8")
    p.scans = scans
    p.fichiers = lambda langue: {"vocab": vocab}
    p.classes = lambda: [{"classe": "supA_1", "lue": True}, {"classe": "supB_1", "lue": True}]
    p.stockage = lambda: {"db": tmp_path / "d.sqlite"}
    dec = Decisions(tmp_path / "d.sqlite")
    assert p.vocab_appris("fr", log=lambda *a: None) == vocab             # rien de tapé : vocabulaire d'origine
    dec.set("supA_1", "c01_q3.2", texte="{prix}")
    assert p.vocab_appris("fr", log=lambda *a: None) == vocab             # une seule copie : pas encore
    dec.set("supA_1", "c02_q3.2", texte="{prix}")
    dec.set("supB_1", "c01_q3.2", texte="{cout}")                         # classe EN : pas dans le vocabulaire FR
    dec.set("supA_1", "c01_q1.1", texte="2,5")
    dec.set("supA_1", "c02_q1.1", texte="2,5")                            # champ numérique : jamais
    out = p.vocab_appris("fr", log=lambda *a: None)
    assert out.name == "X_FR.vocab.appris.json"
    champs = json.loads(out.read_text(encoding="utf-8"))["fields"]
    assert champs["q3.2"]["values"] == ["{prix:.2f}", "{prix}"] and "values" not in champs["q1.1"]
    assert json.loads(vocab.read_text(encoding="utf-8"))["fields"]["q3.2"]["values"] == ["{prix:.2f}"]  # intact
