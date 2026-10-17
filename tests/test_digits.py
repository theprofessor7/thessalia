import cv2
import numpy as np

from thessalia.digits import DigitReader, PACKAGED, segment, shape
from thessalia.vocab import propose_digits, snap

NUM = {"kind": "number", "values": ["ERROR"]}


def _draw(text):
    img = np.full((70, 60 * len(text) + 20, ), 255, np.uint8)
    cv2.putText(img, text, (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.8, 0, 3, cv2.LINE_AA)
    return img


def test_segment_digits_and_separator():
    assert shape(segment(_draw("7"))) == "d"
    assert shape(segment(_draw("1024"))) == "dddd"
    assert shape(segment(_draw("2.5"))) == "d.d"
    assert segment(np.full((40, 80), 255, np.uint8)) == []


def test_reader_packaged_model():
    r = DigitReader(PACKAGED)
    text, conf = r.read(_draw("3.0"))
    assert len(text) == 3 and text[1] == "." and 0 < conf <= 1
    assert r.read(np.full((40, 80), 255, np.uint8)) == (None, 0.0)


def test_digits_only_propose():
    # nombre libre en revue : la lecture des chiffres devient la proposition, le statut ne change pas
    r = propose_digits(snap([("3 3", 0.9)], NUM), NUM, "3", 0.99)
    assert r["status"] == "review" and r["value"] == "3" and r["suggestions"][0] == "3"
    assert r["digits"]["agree"] is False
    assert propose_digits(snap([("15 .", 0.9)], NUM), NUM, "15", 0.99)["digits"]["agree"] is True
    # décimal, une seule lecture voit une virgule : le doute profite à l'étudiant, point proposé
    r = propose_digits(snap([("2 2", 0.9)], NUM), NUM, "2,5", 0.99)
    assert r["value"] == "2.5" and r["suggestions"][:2] == ["2.5", "2,5"] and "incertain" in r["reason"]
    r = propose_digits(snap([("2,5", 0.9)], NUM), NUM, "2.5", 0.99)
    assert r["value"] == "2.5" and r["status"] == "review"
    # les deux lectures voient une virgule : elle est détectée, on la garde
    r = propose_digits(snap([("2,5", 0.9)], NUM), NUM, "2,5", 0.99)
    assert r["value"] == "2,5" and r["suggestions"][:2] == ["2,5", "2.5"] and "détectée" in r["reason"]
    # un mot du vocabulaire accepté n'est pas remplacé par des chiffres
    r = propose_digits(snap([("ERROR", 0.8)], NUM), NUM, "68808", 0.3)
    assert r["status"] == "ok" and r["value"] == "ERROR"


def test_integer_acceptance_needs_fine_tuned_engine():
    # entier de 2 chiffres, deux lectures d'accord, moteur sûr : accepté seulement si demandé (TrOCR affiné)
    assert propose_digits(snap([("22", 0.999)], NUM), NUM, "22", 0.9)["status"] == "review"
    assert propose_digits(snap([("22", 0.999)], NUM), NUM, "22", 0.9, accept_numbers=True)["status"] == "ok"
    # chiffre seul, désaccord, moteur peu sûr, décimal : toujours en revue
    for read, digits, conf in [("3", "3", 0.999), ("22", "27", 0.999), ("22", "22", 0.95), ("2.5", "2.5", 0.999)]:
        r = propose_digits(snap([(read, conf)], NUM), NUM, digits, 0.99, accept_numbers=True)
        assert r["status"] == "review", (read, digits, conf)
