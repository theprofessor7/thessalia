"""Détecteur de séparateur décimal : images synthétiques seulement (aucune donnée d'étudiant)."""
import numpy as np
import cv2

from thessalia import separateur as S


def draw(sep, dx=0, dy=0, thick=3, tail=10, line=False):
    """« 2.5 » ou « 2,5 » sur fond blanc ; `line` : soulignement imprimé sous les chiffres (vignette brute)."""
    img = np.full((70, 150), 255, np.uint8)
    base = 45 + dy
    cv2.putText(img, "2", (12 + dx, base), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 3)
    cv2.putText(img, "5", (66 + dx, base), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 3)
    cx = 52 + dx
    if sep == ".":
        cv2.circle(img, (cx, base - 3), thick, 0, -1)
    else:
        cv2.circle(img, (cx, base - 4), thick, 0, -1)
        cv2.line(img, (cx + 1, base - 2), (cx - 4, base - 2 + tail), 0, 2)
    if line:
        cv2.line(img, (0, base + 4), (149, base + 4), 0, 2)
    return img


def clean_of(raw):
    """Nettoyage simulé : la bande du soulignement (et ce qui la touche) disparaît, comme dans ocr_prep."""
    out = raw.copy()
    rows = np.nonzero((raw < 128).sum(1) > 0.8 * raw.shape[1])[0]
    out[rows.min() - 2:rows.max() + 3] = 255
    return out


def test_locate_trouve_le_signe_entre_les_chiffres():
    for sep in ".,":
        mask, geo = S.locate(draw(sep), apres=1)
        assert mask is not None, geo
        ys, xs = np.nonzero(mask)
        assert 40 < xs.mean() < 62          # entre le 2 et le 5
        assert geo["h"] > 15


def test_traits_virgule_plus_haute_et_plus_basse_que_le_point():
    fp, _ = S.extract(draw("."))
    fv, _ = S.extract(draw(","))
    i = S.FEATURES.index
    assert fv[i("hauteur")] > fp[i("hauteur")]
    assert fv[i("bas")] > fp[i("bas")]
    assert fv[i("log_allongement")] > fp[i("log_allongement")]


def test_vignette_brute_retrouve_la_queue_effacee():
    raw = draw(",", line=True)
    clean = clean_of(raw)
    x, why = S.extract(clean, 1, crop=raw)
    assert x is not None, why
    def j(name):
        return len(S.FEATURES) + S.RAW_FEATURES.index(name)
    assert x[j("brut_trouve")] == 1
    assert x[j("dessous_aire")] > 0          # la queue ressort sous le soulignement
    raw_p = draw(".", line=True)
    xp, _ = S.extract(clean_of(raw_p), 1, crop=raw_p)
    assert xp[j("dessous_aire")] == 0


def test_apprentissage_prediction_et_sauvegarde(tmp_path):
    rng = np.random.default_rng(0)
    X, y = [], []
    for k in range(40):
        sep = ".," [k % 2]
        img = draw(sep, dx=int(rng.integers(-3, 4)), dy=int(rng.integers(-3, 4)), thick=int(rng.integers(2, 4)),
                   tail=int(rng.integers(8, 13)))
        x, _ = S.extract(img, 1)
        X.append(x)
        y.append(int(sep == ","))
    det = S.Separateur(S.fit(np.array(X), np.array(y)), "image")
    assert det.predict(clean=draw(","), apres=1)["p_virgule"] > 0.5
    assert det.predict(clean=draw("."), apres=1)["p_virgule"] < 0.5
    # seuils par défaut : jamais de décision seule, seulement un indice
    assert det.predict(clean=draw(","), apres=1)["decision"] is None
    p = det.save(tmp_path / "sep.npz")
    det2 = S.Separateur.load(p)
    assert det2.kind == "image" and det2.bas == 0 and det2.haut == 1
    assert abs(det2.predict(clean=draw(","))["p_virgule"] - det.predict(clean=draw(","))["p_virgule"]) < 1e-6
    det2.bas, det2.haut = 0.2, 0.8
    assert det2.predict(clean=draw(","))["decision"] == ","
    assert det2.predict(clean=draw("."))["decision"] == "."


def test_rien_a_trouver():
    r = S.Separateur(S.fit(np.eye(len(S.IMAGE_FEATURES))[:2].repeat(3, 0), np.array([0, 0, 0, 1, 1, 1]))).predict(
        clean=np.full((40, 80), 255, np.uint8))
    assert r["trouve"] is False and r["decision"] is None and r["raison"]


def test_seuils_sans_erreur():
    P = np.array([0.01, 0.05, 0.30, 0.60, 0.90, 0.97])
    y = np.array([0, 0, 1, 0, 1, 1])
    bas, haut = S.safe_thresholds(P, y)
    assert bas < 0.30 and haut > 0.60                 # aucune erreur au-delà des seuils
    assert not ((P <= bas) & (y == 1)).any() and not ((P >= haut) & (y == 0)).any()
    assert S.safe_thresholds(np.array([0.0, 1.0]), np.array([1, 0])) == (0.0, 1.0)   # rien de sûr


def test_indices_du_lecteur():
    f = S.reader_features([["2,5", 0.99], ["2.5", 0.3], ["25", 0.1]])
    assert f.tolist() == [0.99, 0.3]
    assert S.apres_of({"value": "3.14", "candidates": []}) == 1
    assert S.apres_of({"value": "314", "candidates": [["31,4", 0.5]]}) == 2
    assert S.apres_of({"value": None}) is None


def test_indice_change_le_separateur_de_la_proposition_seulement():
    from thessalia.correction import Classe
    it = {"proposition": "2.5"}
    assert Classe._separateur(it, {"lecture": "2.5", "p_virgule": 0.8})
    assert it["proposition"] == "2,5" and it["lecture_machine"] == "2.5" and "virgule proposée" in it["raison"]
    it = {"proposition": "2,5"}
    assert Classe._separateur(it, {"lecture": "2,5", "p_virgule": 0.1}) and it["proposition"] == "2.5"
    it = {"proposition": "2.5"}                       # entrée périmée (relecture depuis) : ignorée
    assert not Classe._separateur(it, {"lecture": "3.5", "p_virgule": 0.9}) and it["proposition"] == "2.5"
    it = {"proposition": "25"}                        # entier : rien
    assert not Classe._separateur(it, {"lecture": "25", "p_virgule": 0.9})
