"""Compte de l'application : un identifiant et un mot de passe par installation, demandés avant toute page.

Le mot de passe n'est jamais enregistré en clair : seulement son empreinte (hachage salé, werkzeug), dans
`data/compte.json`, hors dépôt. Oubli : supprimer ce fichier ; un nouveau compte est demandé au lancement suivant,
les examens ne sont pas touchés.

Ce que cela protège : l'application ouverte sur un PC laissé sans surveillance, ou un autre utilisateur du même PC
qui ouvrirait l'adresse. Ce que cela ne protège pas : les fichiers eux-mêmes (copies, notes), lisibles par
quiconque a accès au dossier ; pour cela, la session Windows de l'enseignant.
"""
from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

COMPTE = Path("data/compte.json")
LONGUEUR_MIN = 8


class Compte:
    def __init__(self, chemin=COMPTE):
        self.chemin = Path(chemin)

    def existe(self) -> bool:
        return self.chemin.exists()

    def identifiant(self) -> str | None:
        return json.loads(self.chemin.read_text(encoding="utf-8"))["identifiant"] if self.existe() else None

    def creer(self, identifiant: str, mdp: str, mdp2: str):
        """Premier lancement ; ValueError avec un message lisible si la saisie ne convient pas."""
        identifiant = (identifiant or "").strip()
        if self.existe():
            raise ValueError("un compte existe déjà sur ce PC")
        if not identifiant:
            raise ValueError("choisissez un identifiant")
        if len(mdp or "") < LONGUEUR_MIN:
            raise ValueError(f"le mot de passe doit faire au moins {LONGUEUR_MIN} caractères")
        if mdp != mdp2:
            raise ValueError("les deux mots de passe ne sont pas identiques")
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(json.dumps({"identifiant": identifiant, "empreinte": generate_password_hash(mdp),
                                           "cree": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    def verifier(self, identifiant: str, mdp: str) -> bool:
        if not self.existe():
            return False
        d = json.loads(self.chemin.read_text(encoding="utf-8"))
        ok = check_password_hash(d["empreinte"], mdp or "")
        return ok and (identifiant or "").strip().casefold() == d["identifiant"].casefold()

    def cle_session(self) -> str:
        """Clé qui signe le cookie de session, propre à ce PC (créée une fois, à côté du compte)."""
        p = self.chemin.with_name("session.cle")
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(secrets.token_hex(32), encoding="utf-8")
        return p.read_text(encoding="utf-8").strip()


def proteger(app, compte: Compte):
    """Toute page demande d'être connecté ; premier lancement : création du compte."""
    from datetime import timedelta

    from flask import jsonify, redirect, render_template, request, session

    app.secret_key = compte.cle_session()
    app.permanent_session_lifetime = timedelta(hours=12)
    app.config.update(SESSION_COOKIE_SAMESITE="Strict", SESSION_COOKIE_HTTPONLY=True)
    libres = {"connexion", "premiere_connexion", "static"}

    def suite_sure(url):
        return url if url and url.startswith("/") and not url.startswith("//") else "/"

    @app.before_request
    def garde():
        if request.endpoint in libres or session.get("connecte"):
            return None
        if request.path.startswith("/api/") or request.path == "/tache":
            return jsonify({"erreur": "session expirée : recharger la page pour se reconnecter"}), 401
        if not compte.existe():
            return redirect("/premiere-connexion")
        return redirect("/connexion?suite=" + request.full_path.rstrip("?"))

    @app.route("/premiere-connexion", methods=["GET", "POST"])
    def premiere_connexion():
        if compte.existe():
            return redirect("/connexion")
        erreur = None
        if request.method == "POST":
            f = request.form
            try:
                compte.creer(f.get("identifiant"), f.get("mdp"), f.get("mdp2"))
                session.clear()
                session.permanent = True
                session["connecte"] = True
                return redirect("/")
            except ValueError as e:
                erreur = str(e)
        return render_template("connexion.html", premiere=True, erreur=erreur, longueur=LONGUEUR_MIN,
                               identifiant=request.form.get("identifiant", ""))

    @app.route("/connexion", methods=["GET", "POST"])
    def connexion():
        if not compte.existe():
            return redirect("/premiere-connexion")
        erreur = None
        suite = suite_sure(request.values.get("suite"))
        if request.method == "POST":
            if compte.verifier(request.form.get("identifiant"), request.form.get("mdp")):
                session.clear()
                session.permanent = True
                session["connecte"] = True
                return redirect(suite)
            time.sleep(1)            # ralentit les essais au hasard
            erreur = "identifiant ou mot de passe incorrect"
        return render_template("connexion.html", premiere=False, erreur=erreur, suite=suite,
                               identifiant=request.form.get("identifiant", ""), chemin=str(compte.chemin))

    @app.route("/deconnexion", methods=["POST"])
    def deconnexion():
        session.clear()
        return redirect("/connexion")

    app.jinja_env.globals.update(avec_compte=True)

    @app.context_processor
    def utilisateur():
        return {"utilisateur": compte.identifiant() if session.get("connecte") else None}
