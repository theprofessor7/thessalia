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


def test_progression_telechargement(monkeypatch):
    """Plusieurs fichiers dans un modèle : une jauge globale, le journal ne garde que les étapes."""
    import io
    import json
    flux = [{"status": "pulling manifest"},
            {"status": "pulling a", "digest": "a", "total": 3_000_000_000, "completed": 0},
            {"status": "pulling a", "digest": "a", "total": 3_000_000_000, "completed": 1_500_000_000},
            {"status": "pulling b", "digest": "b", "total": 1_000_000_000, "completed": 1_000_000_000},
            {"status": "pulling a", "digest": "a", "total": 3_000_000_000, "completed": 3_000_000_000},
            {"status": "verifying sha256 digest"}, {"status": "success"}]
    corps = b"".join(json.dumps(m).encode() + b"\n" for m in flux)
    monkeypatch.setattr(ollama_local.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(corps))
    monkeypatch.setattr(ollama_local, "demarrer", lambda log: True)
    monkeypatch.setattr(ollama_local, "modeles_installes", lambda: ["qwen3-vl:4b-instruct"])
    journal, jauge = [], []
    log = lambda *a: journal.append(" ".join(map(str, a)))            # noqa: E731
    log.progression = lambda pc, texte: jauge.append((pc, texte))
    ollama_local.telecharger_modele("qwen3-vl:4b-instruct", log)
    assert [pc for pc, _ in jauge] == [0, 50, 62, 100] and jauge[-1][1] == "4.0 / 4.0 Go"
    assert not any("%" in l for l in journal) and "  verifying sha256 digest" in journal
    journal.clear()                                                   # sans jauge (ligne de commande) : tous les 10 %
    ollama_local.telecharger_modele("qwen3-vl:4b-instruct", journal.append)
    assert [l for l in journal if "%" in l] == ["  0 % (0.0 / 3.0 Go)", "  50 % (1.5 / 3.0 Go)",
                                               "  62 % (2.5 / 4.0 Go)", "  100 % (4.0 / 4.0 Go)"]


def test_jauge_sur_la_page(tmp_path, monkeypatch):
    monkeypatch.setattr(ollama_local, "etat", lambda: {"installe": True, "lance": True, "windows": True, "modeles": []})
    monkeypatch.setattr(extensions, "trocr_etat", lambda: {"biblio": True, "poids": True, "installe": True})
    import threading
    fin = threading.Event()

    def lent(nom, log):
        log.progression(42, "1.3 / 3.0 Go")
        fin.wait(5)
    monkeypatch.setattr(ollama_local, "telecharger_modele", lent)
    (tmp_path / "examens").mkdir()
    c = create_app([], tmp_path / "d.sqlite", examens=tmp_path / "examens").test_client()
    c.post("/reglages/extension", data={"id": "qwen3-vl:4b-instruct", "action": "telecharger"})
    for _ in range(50):
        if (c.get("/tache").get_json() or {}).get("progression"):
            break
        time.sleep(0.05)
    assert c.get("/tache").get_json()["progression"] == {"pc": 42, "texte": "1.3 / 3.0 Go"}
    page = c.get("/reglages").get_data(as_text=True)
    assert 'style="width:42%"' in page and "42 %" in page
    fin.set()
    _attendre(c)


def test_sortie_comme_une_console():
    """Une tâche dont une bibliothèque interroge la console (isatty : transformers, tqdm) ne s'arrête pas."""
    import sys
    from thessalia.web_examens import Taches
    t = Taches().lancer("x", "essai", lambda log: print("tty :", sys.stdout.isatty(), sys.stdout.encoding))
    for _ in range(50):
        if t["etat"] != "en cours":
            break
        time.sleep(0.05)
    assert t["etat"] == "terminé" and t["journal"] == ["tty : False utf-8"], t["journal"]


def test_pause_puis_reprise():
    """Pause : la tâche s'arrête au prochain message, sans être avalée par un `except Exception` ; la reprise
    relance la même tâche, qui saute ce qui est déjà fait."""
    import threading
    from thessalia.web_examens import Taches
    fait, go = [], threading.Event()

    def lire(log):
        for i in range(5):
            if i in fait:
                continue                      # déjà lu : sauté à la reprise
            try:
                log(f"copie {i}")
            except Exception:                 # un module qui avale ses erreurs ne doit pas avaler la pause
                pass
            fait.append(i)
            if i == 1:
                go.wait(2)
    T = Taches()
    t = T.lancer("x", "Lire", lire, reprenable=True)
    while len(fait) < 2:
        time.sleep(0.01)
    T.pause()
    go.set()
    for _ in range(100):
        if t["etat"] != "en cours":
            break
        time.sleep(0.02)
    assert t["etat"] == "en pause" and fait == [0, 1]       # copie 2 annoncée puis arrêtée avant d'être faite
    t2 = T.reprendre()
    for _ in range(100):
        if t2["etat"] != "en cours":
            break
        time.sleep(0.02)
    assert t2["etat"] == "terminé" and fait == [0, 1, 2, 3, 4]
    with pytest.raises(RuntimeError):
        T.pause()                                            # plus rien à mettre en pause


def test_avancement_des_modules_vers_la_jauge():
    """Un module de calcul (second lecteur…) signale son avancement : la jauge de la tâche le montre, sans rien en
    ligne de commande."""
    from thessalia import avancement
    from thessalia.web_examens import Taches
    avancement.signaler(3, 10, "rien de branché : sans effet")
    T = Taches()

    def relire(log):
        avancement.signaler(52, 249, "relecture : 52/249")
    t = T.lancer("x", "Lecture approfondie", relire)
    for _ in range(50):
        if t["etat"] != "en cours":
            break
        time.sleep(0.02)
    assert t["etat"] == "terminé" and t["progression"] == {"pc": 20, "texte": "relecture : 52/249"}
    assert avancement._jauge is None                                   # débranchée à la fin de la tâche
