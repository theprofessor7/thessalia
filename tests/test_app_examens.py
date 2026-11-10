"""Application : un examen de bout en bout, du sujet source à l'outil de correction."""
import io
import time

import pytest

pytest.importorskip("flask")

from thessalia.__main__ import main as thessalia                     # noqa: E402
from thessalia.serve import create_app                               # noqa: E402

from test_sujet import SUJET                                          # noqa: E402


def _attendre(client, max_s=300):
    t0 = time.time()
    while time.time() - t0 < max_s:
        t = client.get("/tache").get_json()
        if t and t["etat"] != "en cours":
            return t
        time.sleep(0.3)
    raise AssertionError("tâche trop longue")


def test_examen_de_bout_en_bout(tmp_path, monkeypatch):
    racine = tmp_path / "examens"
    racine.mkdir()
    app = create_app([], tmp_path / "decisions.sqlite", examens=racine)
    c = app.test_client()
    assert c.get("/").headers["Location"].endswith("/examens")

    # source refusée : l'erreur est affichée avec sa ligne
    r = c.post("/examens/nouveau", data={"nom": "essai", "source": (io.BytesIO(SUJET.replace("bonne: a", "bonne: z").encode()), "examen.yaml")},
               content_type="multipart/form-data")
    page = c.get("/examens/essai").get_data(as_text=True)
    assert "Source refusée" in page and "bonne réponse « z »" in page

    # source corrigée, PDF produits
    c.post("/examens/essai/source", data={"source": (io.BytesIO(SUJET.encode()), "examen.yaml")}, content_type="multipart/form-data")
    assert "contrôle réussi" in c.get("/examens/essai").get_data(as_text=True)
    c.post("/examens/essai/produire")
    t = _attendre(c)
    assert t["etat"] == "terminé", t["journal"]
    page = c.get("/examens/essai").get_data(as_text=True)
    assert "sujet_ESSAI_FR.pdf" in page and "corrige_ESSAI_EN.pdf" in page
    assert c.get("/examens/essai/pdf/sujet_ESSAI_FR.pdf").status_code == 200
    assert c.get("/examens/essai/pdf/..%2Fexamen.yaml").status_code == 404

    # copies simulées déposées et lues
    prod = racine / "essai" / "produit"
    thessalia(["simulate", "-t", str(prod / "gabarits" / "gabarit_ESSAI_FR.json"), "-b", str(prod / "sujet_ESSAI_FR.pdf"),
               "-o", str(tmp_path / "sim"), "-n", "2"])
    scans = (tmp_path / "sim" / "scans.pdf").read_bytes()
    c.post("/examens/essai/deposer", data={"classe": "supA_1", "langue": "fr", "scan": (io.BytesIO(scans), "lot.pdf")},
           content_type="multipart/form-data")
    t = _attendre(c)
    assert t["etat"] == "terminé", t["journal"]
    page = c.get("/examens/essai").get_data(as_text=True)
    assert "supA_1" in page and "pas encore lue" not in page

    # correction ouverte sur les classes de l'examen
    assert c.post("/examens/essai/corriger").headers["Location"] == "/"
    accueil = c.get("/").get_data(as_text=True)
    assert "supA_1" in accueil and "<small>essai</small>" in accueil       # menu : examen ouvert en correction
    # une décision prise dans l'outil est rangée dans l'examen, jamais dans la base commune
    import sqlite3
    r = c.post("/api/decision", json={"classe": "supA_1", "cle": "c01_q2", "verdict": "juste", "texte": "Bonjour, Alice !"})
    assert r.status_code == 200
    compte = lambda p: sqlite3.connect(p).execute("SELECT COUNT(*) FROM decision WHERE classe='supA_1'").fetchone()[0]
    assert compte(racine / "essai" / "decisions.sqlite") == 1 and compte(tmp_path / "decisions.sqlite") == 0
    assert "sujets à produire" not in c.get("/examens").get_data(as_text=True)   # corriger ne « change » pas le sujet
    assert (racine / "essai" / "verite" / "supA_1.appris.json").exists()

    # liste des élèves de l'examen, puis notes exportées dans l'examen (journal de la tâche, téléchargement)
    from thessalia.excel import ecrire_xlsx
    from thessalia.identite import _xlsx_rows
    ecrire_xlsx(tmp_path / "liste.xlsx", [("Liste", [["NOM", "Prénom", "Classe"], ["MARTIN", "Alice", "supA_1"],
                                                     ["DURAND", "Paul", "supA_1"]], [10, 10, 10])])
    r = c.post("/examens/essai/liste", data={"liste": ((tmp_path / "liste.xlsx").open("rb"), "liste.xlsx")},
               content_type="multipart/form-data")
    assert "2%20%C3%A9l%C3%A8ves" in r.headers["Location"]
    assert "liste_eleves.xlsx" in c.get("/examens/essai").get_data(as_text=True)
    c.post("/examens/essai/notes")
    t = _attendre(c)
    assert t["etat"] == "terminé", t["journal"]
    assert any("2 copies, 2 absents, 2 à vérifier" in l for l in t["journal"]), t["journal"]
    xl = racine / "essai" / "notes" / "notes.xlsx"
    assert len(_xlsx_rows(xl)) == 3                                       # en-tête + 2 copies
    assert c.get("/examens/essai/notes.xlsx").data == xl.read_bytes()
    c.post("/examens/essai/notes")                                        # second export : l'ancien est gardé
    assert _attendre(c)["etat"] == "terminé"
    assert len(list((racine / "essai" / "notes").glob("*.xlsx"))) == 2

    # sujet validé : seulement après une mesure sans écart sur des lectures vérifiées par l'enseignant
    import json
    from thessalia import projet as projet_mod
    from thessalia.ocr_run import NOUVEAU
    monkeypatch.setattr(projet_mod, "VALIDATION_MIN", 2)
    monkeypatch.setattr(projet_mod.Projet, "lire_courtes", lambda self, log=print: log("relu"))
    cl = racine / "essai" / "classes" / "supA_1"
    (cl / "short_answers.csv").write_text("copy", encoding="utf-8")

    def lu(copie, valeur):
        r = cl / copie / "result.json"
        doc = json.loads(r.read_text(encoding="utf-8"))
        doc["fields"]["q2"]["ocr"] = {"value": valeur, "status": "review", "reason": NOUVEAU}
        r.write_text(json.dumps(doc), encoding="utf-8")
    lu("copy_001", "Bonjour, Alice !")
    lu("copy_002", "Bonjour Alice")                                      # la machine lit sans virgule…
    c.post("/api/decision", json={"classe": "supA_1", "cle": "c02_q2", "verdict": "juste"})   # …l'enseignant : juste
    page = c.get("/examens/essai").get_data(as_text=True)
    assert "1/2 justes" in page and "note différente" in page
    r = c.post("/examens/essai/valider/fr")
    assert "refus" in r.headers["Location"]
    key = racine / "essai" / "produit" / "corriges" / "ESSAI_FR.key.json"
    assert "lecture_validee" not in json.loads(key.read_text(encoding="utf-8"))
    lu("copy_002", "Bonjour, Alice !")
    assert "2/2 justes" in c.get("/examens/essai").get_data(as_text=True)
    c.post("/examens/essai/valider/fr")
    assert _attendre(c)["journal"] == ["relu"]
    k = json.loads(key.read_text(encoding="utf-8"))
    assert k["lecture_validee"] is True and k["lecture_validee_mesure"]["justes"] == 2
    assert "lecture validée" in c.get("/examens/essai").get_data(as_text=True)

    # arrondi au demi-point supérieur : réglage général (page Réglages)
    from thessalia import reglages as R
    from thessalia.excel import note_finale
    monkeypatch.setattr(R, "FICHIER", tmp_path / "data" / "reglages.json")
    assert note_finale(13.1) == 13.5 and note_finale(13.1, arrondi=False) == 13.1 and note_finale(20.25, False) == 20
    assert 'name="arrondi" value="1" checked' in c.get("/reglages").get_data(as_text=True)
    c.post("/reglages/parametres", data={"arrondi": "0"})                  # interrupteur coupé
    assert R.lire()["arrondi_demi_point"] is False
    assert "exacte, sans arrondi" in c.get("/examens/essai").get_data(as_text=True)
    c.post("/examens/essai/notes")
    assert _attendre(c)["etat"] == "terminé"
    assert _xlsx_rows(racine / "essai" / "notes" / "notes.xlsx")[0]["K"] == "Note finale (max 20)"
    c.post("/reglages/parametres", data={"arrondi": ["0", "1"]})           # interrupteur remis
    assert R.lire()["arrondi_demi_point"] is True

    # ce que la machine retient d'une décision (message de l'outil) : une seule classe, rien à proposer ailleurs
    r = c.post("/api/decision", json={"classe": "supA_1", "cle": "c01_q2", "verdict": "faux"}).get_json()
    assert r["retenu"]["lecture"] == "Bonjour, Alice !" and r["retenu"]["verdict"] == "faux"
    assert (r["retenu"]["n"], r["retenu"]["total"]) == (1, 2)                  # c02 : même lecture, jugée juste
    assert r["retenu"]["autres_classes"] is False and r["exemple"] is False
    r = c.post("/api/decision", json={"classe": "supA_1", "cle": "c01_q2", "verdict": "juste", "texte": "Bonjour, Alice !"})
    assert r.get_json()["exemple"] is True and r.get_json()["retenu"]["n"] == 2
    r = c.post("/api/decision", json={"classe": "supA_1", "cle": "c01_q1", "options": ["a"]}).get_json()
    assert "retenu" not in r                                                   # QCM : pas de mémoire des verdicts

    # page Apprentissage : mémoire des verdicts de l'examen ouvert, exemples validés, lecteurs pas encore affinables
    page = c.get("/apprentissage").get_data(as_text=True)
    assert "Mémoire de vos verdicts" in page and "<code>Bonjour, Alice !</code>" in page
    assert "Lecteur de chiffres" in page and "<td>essai</td><td>supA_1</td><td>1</td>" in page
    c.post("/apprentissage/chiffres/affiner")
    t = _attendre(c)
    assert t["etat"] == "erreur" and ("nombres validés" in t["journal"][-1] or "Réglages" in t["journal"][-1])

    # contrôle des noms avant l'export : copies sans élève, puis une copie à risque (nom proche d'un absent)
    page = c.get("/examens/essai").get_data(as_text=True)
    assert "2 sans élève" in page and "Exporter quand même" in page
    ecrire_xlsx(tmp_path / "liste.xlsx", [("Liste", [["NOM", "Prénom", "Classe"], ["MARTIN", "Alice", "supA_1"],
                                                     ["MARTINS", "Léa", "supA_1"], ["DURAND", "Paul", "supA_1"]], [10, 10, 10])])
    c.post("/examens/essai/liste", data={"liste": ((tmp_path / "liste.xlsx").open("rb"), "liste.xlsx")},
           content_type="multipart/form-data")
    for copie, eleve in (("copy_001", "MARTIN Alice"), ("copy_002", "DURAND Paul")):
        assert c.post("/api/identite", json={"classe": "supA_1", "copie": copie, "etudiant": eleve}).status_code == 200
    page = c.get("/examens/essai").get_data(as_text=True)
    assert "2 à risque" in page and "sans élève</span>" not in page and "Exporter quand même" in page   # DURAND : voisin de l'absente
    assert c.post("/examens/essai/verif-noms").headers["Location"] == "/verif-noms"
    page = c.get("/verif-noms").get_data(as_text=True)
    assert page.index("MARTIN Alice") < page.index("DURAND Paul") and "nom proche de MARTINS Léa" in page
    c.post("/examens/essai/noms-verifies")
    page = c.get("/examens/essai").get_data(as_text=True)
    assert "2 à risque, vérifiées" in page and "Exporter quand même" not in page


def test_assistant_etapes():
    """Assistant de la page d'examen : grisé seulement par un vrai prérequis ; ouvert sur la première étape à faire."""
    from thessalia.web_examens import etapes_examen
    e = {"erreurs": [], "produit": False, "classes": [], "lues": 0, "courtes": 0}
    et, n = etapes_examen(e, None, False, False, True)
    assert n == 2 and et[2]["bloque"] and et[4]["bloque"] and not et[1]["bloque"]
    e.update(produit=True, classes=[{"classe": "A"}], lues=1)
    et, n = etapes_examen(e, None, False, False, True)
    assert n == 4 and not any(x["bloque"] for x in et)                  # lectures automatiques proposées
    assert etapes_examen(e, None, False, False, False)[1] == 5          # sans lecteur : droit à la correction
    e.update(produit=False)                                              # source changée : la classe reste visible
    assert etapes_examen(e, None, True, False, True)[0][2]["bloque"] is None
    assert etapes_examen(e, {"titre": "Exporter les notes"}, True, True, True)[1] == 6   # tâche : son étape
