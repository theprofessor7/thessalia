"""Pages « Examens » de l'application : du sujet source aux copies lues, puis l'outil de correction.

Une tâche longue (produire les PDF, lire une classe) tourne en arrière-plan, une à la fois ; la page de l'examen
affiche son journal. Rien ne sort de la machine (serveur sur 127.0.0.1).
"""
from __future__ import annotations

import contextlib
import threading
import time
from pathlib import Path
from urllib.parse import quote

from . import ollama_local
from .projet import Projet, creer, nom_valide, outils, projets


class Taches:
    """Une seule tâche longue à la fois (lire des scans prend de la mémoire)."""

    def __init__(self):
        self.courante = None
        self._verrou = threading.Lock()

    def lancer(self, projet, titre, fn, apres=None):
        with self._verrou:
            if self.courante and self.courante["etat"] == "en cours":
                raise RuntimeError(f"une tâche tourne déjà : {self.courante['titre']}")
            t = {"projet": projet, "titre": titre, "etat": "en cours", "journal": [], "debut": time.time(), "fin": None,
                 "progression": None}
            self.courante = t

        def log(*a):
            t["journal"].append(" ".join(str(x) for x in a))
            del t["journal"][:-400]

        def progression(pc, texte=""):    # jauge affichée au-dessus du journal (téléchargements)
            t["progression"] = {"pc": max(0, min(100, int(pc))), "texte": texte}
        log.progression = progression

        class Sortie:                     # print des modules (preparer, excel…) → journal
            def write(self, s):
                for ligne in s.splitlines():
                    if ligne.strip():
                        log(ligne)
                return len(s)

            def flush(self):
                pass

        def corps():
            try:
                with contextlib.redirect_stdout(Sortie()):
                    fn(log)
                t["etat"] = "terminé"
                if apres:
                    apres()
            except SystemExit as e:
                t["etat"] = "erreur"
                log(str(e))
            except Exception as e:      # erreur imprévue : affichée telle quelle, jamais avalée
                t["etat"] = "erreur"
                log(f"{type(e).__name__} : {e}")
            t["fin"] = time.time()
        threading.Thread(target=corps, daemon=True).start()
        return t


def _vers(chemin, message):
    return f"{chemin}?m={quote(str(message))}"


def enregistrer(app, racine: Path, charger, memoire=None):
    """memoire : fonction qui résume la mémoire des verdicts des classes ouvertes (page Apprentissage)."""
    from flask import abort, jsonify, redirect, render_template, request, send_from_directory

    taches = Taches()
    etat = {"ouvert": None}          # examen dont les classes sont dans l'outil de correction

    def projet(nom) -> Projet:
        if not nom_valide(nom) or not (racine / nom).is_dir():
            abort(404)
        return Projet(racine / nom)

    def resume(p: Projet):
        ex, err = p.controle()
        cl = p.classes()
        return {"nom": p.nom, "titre": (ex.entete["titre"][ex.langues[0]] if ex else None), "id": ex.id if ex else None,
                "erreurs": err, "langues": ex.langues if ex else [], "questions": len(ex.questions()) if ex else 0,
                "points": ex.points if ex else None, "produit": p.produit_a_jour(), "classes": cl,
                "lues": sum(c["lue"] for c in cl), "courtes": sum(c["lue"] and c["courtes"] for c in cl), "copies": sum(c["copies"] or 0 for c in cl)}

    def resume_lues(p):
        return any(c["lue"] and c["courtes"] for c in p.classes())

    @app.context_processor
    def contexte_examens():
        return {"examen_ouvert": etat["ouvert"]}

    @app.route("/examens")
    def examens_page():
        return render_template("examens.html", examens=[resume(p) for p in projets(racine)], racine=str(racine),
                               message=request.args.get("m"))

    @app.post("/examens/nouveau")
    def nouvel_examen():
        nom = (request.form.get("nom") or "").strip()
        src = request.files.get("source")
        if not src or not src.filename:
            return redirect(_vers("/examens", "Choisissez le fichier examen.yaml."))
        images = {f.filename: f.read() for f in request.files.getlist("images") if f and f.filename}
        try:
            creer(nom, src.read(), racine, images)
        except ValueError as e:
            return redirect(_vers("/examens", str(e)))
        return redirect(f"/examens/{nom}")

    @app.route("/examens/<nom>")
    def examen_page(nom):
        p = projet(nom)
        t = taches.courante if taches.courante and taches.courante["projet"] == nom else None
        notes = p.notes_xlsx
        return render_template("examen.html", e=resume(p), pdfs=[f.name for f in p.pdfs()], tache=t,
                               ouvert=etat["ouvert"] == nom, message=request.args.get("m"), outils=outils(),
                               liste=p.liste(), reglages=p.reglages(), noms=p.controle_noms(), ollama=ollama_local.etat(), validation=p.mesure_lecture() if resume_lues(p) else {},
                               notes=time.strftime("%d/%m/%Y %H:%M", time.localtime(notes.stat().st_mtime))
                               if notes.exists() else None)

    @app.post("/examens/<nom>/source")
    def remplacer_source(nom):
        p = projet(nom)
        src = request.files.get("source")
        if not src or not src.filename:
            return redirect(_vers(f"/examens/{nom}", "Choisissez un fichier .yaml."))
        if p.source:
            p.source.rename(p.source.with_name(p.source.stem + f".avant-{time.strftime('%Y%m%d-%H%M%S')}.txt"))
        (p.dir / "examen.yaml").write_bytes(src.read())
        for f in request.files.getlist("images"):
            if f and f.filename and nom_valide(f.filename):
                (p.dir / f.filename).write_bytes(f.read())
        return redirect(f"/examens/{nom}")

    def lancer(nom, titre, fn, apres=None, retour=None):
        retour = retour or f"/examens/{nom}"
        try:
            taches.lancer(nom, titre, fn, apres)
        except RuntimeError as e:
            return redirect(_vers(retour, e))
        return redirect(retour)

    @app.post("/examens/<nom>/produire")
    def produire(nom):
        p = projet(nom)
        return lancer(nom, "Produire les sujets et corrigés", lambda log: p.produire(log=log))

    @app.route("/examens/<nom>/pdf/<fichier>")
    def pdf(nom, fichier):
        p = projet(nom)
        if not fichier.endswith(".pdf") or fichier not in {f.name for f in p.pdfs()}:
            abort(404)
        return send_from_directory(p.produit.resolve(), fichier)

    def apres_lecture(nom):
        def f():
            if etat["ouvert"] == nom:     # l'outil de correction voit aussitôt la classe lue
                p = Projet(racine / nom)
                charger(p.dossiers_lus(), p.stockage())
        return f

    @app.post("/examens/<nom>/deposer")
    def deposer(nom):
        p = projet(nom)
        f = request.files.get("scan")
        classe, langue = (request.form.get("classe") or "").strip(), request.form.get("langue")
        if not f or not f.filename:
            return redirect(_vers(f"/examens/{nom}", "Choisissez le PDF des copies scannées."))
        try:
            p.deposer(classe, langue, f.read())
        except ValueError as e:
            return redirect(_vers(f"/examens/{nom}", e))
        return lancer(nom, f"Lire les copies de {classe}", lambda log: p.traiter(classe, log=log), apres_lecture(nom))

    @app.post("/examens/<nom>/lire/<classe>")
    def relire(nom, classe):
        p = projet(nom)
        if not (p.scans / f"{classe}.pdf").exists():
            abort(404)
        return lancer(nom, f"Lire les copies de {classe}", lambda log: p.traiter(classe, log=log), apres_lecture(nom))

    @app.post("/examens/<nom>/corriger")
    def corriger(nom):
        p = projet(nom)
        dossiers = p.dossiers_lus()
        if not dossiers:
            return redirect(_vers(f"/examens/{nom}", "Aucune classe lue pour l'instant."))
        try:
            charger(dossiers, p.stockage())
        except SystemExit as e:
            return redirect(_vers(f"/examens/{nom}", e))
        etat["ouvert"] = nom
        return redirect("/")

    @app.post("/examens/<nom>/courtes")
    def courtes(nom):
        p = projet(nom)
        return lancer(nom, "Lire les réponses courtes et les noms", lambda log: p.lire_courtes(log=log), apres_lecture(nom))

    @app.post("/examens/<nom>/valider/<langue>")
    def valider(nom, langue):
        p = projet(nom)
        try:
            m = p.valider_lecture(langue)
        except ValueError as e:
            return redirect(_vers(f"/examens/{nom}", e))
        return lancer(nom, f"Sujet {langue.upper()} validé ({m['justes']}/{m['n']} lectures justes) : relecture des "
                           "réponses courtes", lambda log: p.lire_courtes(log=log), apres_lecture(nom))

    # ---------------------------------------------------------------- réglages, extensions, aide
    REG = "__reglages__"

    @app.route("/reglages")
    def reglages_page():
        from . import extensions, reglages as R
        t = taches.courante if taches.courante and taches.courante["projet"] == REG else None
        return render_template("reglages.html", parametres=R.lire(), cartes=extensions.etat(), tache=t,
                               message=request.args.get("m"))

    @app.post("/reglages/parametres")
    def reglages_parametres():
        from . import reglages as R
        R.ecrire(arrondi_demi_point="1" in request.form.getlist("arrondi"))    # case décochée : seul le champ caché
        return redirect(_vers("/reglages", "Réglages enregistrés."))

    @app.post("/reglages/extension")
    def reglages_extension():
        from . import extensions
        ident, action = request.form.get("id", ""), request.form.get("action", "")
        noms = {"installer": "Installer", "demarrer": "Démarrer", "telecharger": "Télécharger", "supprimer": "Supprimer"}
        return lancer(REG, f"{noms.get(action, action)} : {ident}", lambda log: extensions.agir(ident, action, log),
                      retour="/reglages")

    # ---------------------------------------------------------------- apprentissage
    APP = "__apprentissage__"

    @app.route("/apprentissage")
    def apprentissage_page():
        from . import apprentissage
        t = taches.courante if taches.courante and taches.courante["projet"] == APP else None
        return render_template("apprentissage.html", A=apprentissage.etat(racine), memoire=memoire() if memoire else None,
                               tache=t, message=request.args.get("m"))

    @app.post("/apprentissage/<quoi>/<action>")
    def apprentissage_action(quoi, action):
        from . import apprentissage as A
        if quoi not in ("chiffres", "ecriture") or action not in ("affiner", "adopter", "revenir", "ecarter"):
            abort(404)
        lecteur = {"chiffres": "lecteur de chiffres", "ecriture": "lecteur d'écriture"}[quoi]
        titre = {"affiner": "Affiner le", "adopter": "Adopter le nouveau", "revenir": "Revenir au précédent",
                 "ecarter": "Écarter le nouveau"}[action] + " " + lecteur
        fn = {"affiner": lambda log: (A.affiner_chiffres if quoi == "chiffres" else A.affiner_ecriture)(racine, log=log),
              "adopter": lambda log: A.adopter(quoi, log), "revenir": lambda log: A.revenir(quoi, log),
              "ecarter": lambda log: A.ecarter(quoi, log)}[action]
        return lancer(APP, titre, fn, retour="/apprentissage")

    # ---------------------------------------------------------------- contrôle des noms
    @app.post("/examens/<nom>/verif-noms")
    def verif_noms(nom):
        """Ouvre l'examen dans l'outil de correction, sur la page de contrôle des noms."""
        p = projet(nom)
        try:
            charger(p.dossiers_lus(), p.stockage())
        except SystemExit as e:
            return redirect(_vers(f"/examens/{nom}", e))
        etat["ouvert"] = nom
        return redirect("/verif-noms")

    @app.post("/examens/<nom>/noms-verifies")
    def noms_verifies(nom):
        projet(nom).noms_verifies()
        return redirect(f"/examens/{nom}#notes")

    @app.route("/aide")
    def aide():
        doc = Path(__file__).resolve().parent.parent / "docs"
        if not (doc / "Thessalia_mode_emploi.pdf").exists():
            abort(404)
        return send_from_directory(doc, "Thessalia_mode_emploi.pdf")

    @app.post("/examens/<nom>/preparer")
    def preparer(nom):
        p = projet(nom)
        return lancer(nom, "Préparer la correction (modèles locaux)", lambda log: p.preparer(log=log),
                      apres_lecture(nom))

    @app.post("/examens/<nom>/liste")
    def deposer_liste(nom):
        p = projet(nom)
        f = request.files.get("liste")
        if not f or not f.filename:
            return redirect(_vers(f"/examens/{nom}", "Choisissez la liste des élèves (.xlsx)."))
        try:
            n = p.deposer_liste(f.read())
        except ValueError as e:
            return redirect(_vers(f"/examens/{nom}", e))
        return redirect(_vers(f"/examens/{nom}", f"Liste des élèves enregistrée : {n} élèves."))

    @app.post("/examens/<nom>/notes")
    def exporter(nom):
        p = projet(nom)
        return lancer(nom, "Exporter les notes", lambda log: p.exporter_notes(log=log))

    @app.route("/examens/<nom>/notes.xlsx")
    def notes_xlsx(nom):
        p = projet(nom)
        if not p.notes_xlsx.exists():
            abort(404)
        return send_from_directory(p.notes_xlsx.parent.resolve(), p.notes_xlsx.name, as_attachment=True,
                                   download_name=f"notes_{nom}.xlsx")

    @app.route("/tache")
    def tache():
        t = taches.courante
        return jsonify(None if t is None else {k: t[k] for k in ("projet", "titre", "etat", "journal", "progression")})
