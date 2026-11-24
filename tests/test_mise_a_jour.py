"""Mise à jour en un clic : avance rapide seulement, refus si un fichier suivi a été modifié sur ce PC."""
import shutil
import subprocess

import pytest

from thessalia import mise_a_jour as M

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git absent")


def git(d, *a):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=d, check=True, capture_output=True)


@pytest.fixture
def depots(tmp_path, monkeypatch):
    amont, ici = tmp_path / "amont", tmp_path / "ici"
    amont.mkdir()
    git(amont, "init", "-q", "-b", "main")
    (amont / "a.py").write_text("x = 1\n")
    git(amont, "add", "."); git(amont, "commit", "-qm", "Premier état")
    git(tmp_path, "clone", "-q", str(amont), str(ici))
    monkeypatch.setattr(M, "DEPOT", ici)
    return amont, ici


def test_deja_a_jour_puis_nouveaute(depots):
    amont, ici = depots
    journal = []
    M.mettre_a_jour(journal.append)
    assert journal[-1] == "Thessalia est déjà à jour."
    (amont / "a.py").write_text("x = 2\n")
    git(amont, "commit", "-qam", "Correctif des noms")
    journal = []
    M.mettre_a_jour(journal.append)
    assert "  · Correctif des noms" in journal
    assert journal[-1].startswith("Mise à jour installée")
    assert (ici / "a.py").read_text() == "x = 2\n"


def test_refus_si_fichier_modifie(depots):
    amont, ici = depots
    (amont / "a.py").write_text("x = 2\n")
    git(amont, "commit", "-qam", "Correctif")
    (ici / "a.py").write_text("x = 99\n")
    with pytest.raises(SystemExit, match="a.py"):
        M.mettre_a_jour(lambda *a: None)
    assert (ici / "a.py").read_text() == "x = 99\n"        # rien d'écrasé


def test_sans_git_clone(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "DEPOT", tmp_path)
    assert "git clone" in M.possible() and M.version() is None
