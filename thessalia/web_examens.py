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


class Pause(BaseException):
    """Pause demandée par l'enseignant : levée au prochain message de la tâche. BaseException, pour traverser les
    `except Exception` des modules (une copie qui échoue ne doit pas avaler la pause)."""


class Taches:
    """Une seule tâche longue à la fois (lire des scans prend de la mémoire).

    Pause / reprise, pour les tâches qui reprennent où elles s'étaient arrêtées (`reprenable`) : la pause arrête la
    tâche proprement au prochain point d'étape (la copie ou le cadre en cours se termine), la reprise la relance et
    elle saute ce qui est déjà fait (lectures en cache, transcriptions enregistrées, affinage sauvegardé)."""

    def __init__(self):
        self.courante = None
        self._verrou = threading.Lock()

    def lancer(self, projet, titre, fn, apres=None, reprenable=False):
        with self._verrou:
            if self.courante and self.courante["etat"] == "en cours":
                raise RuntimeError(f"une tâche tourne déjà : {self.courante['titre']}")
            ancien = self.courante if self.courante and self.courante["titre"] == titre else None
            t = {"projet": projet, "titre": titre, "etat": "en cours", "journal": [], "debut": time.time(), "fin": None,
                 "progression": ancien["progression"] if ancien else None, "reprenable": reprenable,
                 "pause": False, "relancer": (fn, apres)}
            self.courante = t

        def log(*a):
            t["journal"].append(" ".join(str(x) for x in a))
            del t["journal"][:-400]
            if t["pause"]:
                raise Pause()

        def progression(pc, texte=""):    # jauge de la page ; None : étape sans avancement chiffré (jauge qui défile)
            t["progression"] = None if pc is None else {"pc": max(0, min(100, int(pc))), "texte": texte}
            if t["pause"]:
                raise Pause()
        log.progression = progression

        class Sortie:                     # print des modules (preparer, excel…) → journal, ligne par ligne
            def __init__(self):
                self.reste = ""           # print("a", b) écrit en plusieurs morceaux : une seule ligne au journal

            def write(self, s):
                *lignes, self.reste = (self.reste + s.replace("\r", "\n")).split("\n")
                for ligne in lignes:
                    if ligne.strip():
                        log(ligne)
                return len(s)

            def flush(self):
                pass

            def vider(self):
                if self.reste.strip():
                    log(self.reste)
                self.reste = ""

            # ce que les bibliothèques demandent à une console (transformers, barres de progression) : sans ces
            # méthodes, la lecture des réponses courtes s'arrêtait net (« 'Sortie' object has no attribute 'isatty' »)
            encoding, errors = "utf-8", "replace"

            def isatty(self):
                return False

            def writable(self):
                return True

        def corps():
            try:
                sortie = Sortie()
                try:
                    with contextlib.redirect_stdout(sortie):
                        fn(log)
                finally:
                    sortie.vider()
                t["etat"] = "terminé"
                if apres:
                    apres()
            except Pause:
                t["etat"] = "en pause"
                t["journal"].append("En pause. « Reprendre » repart d'ici : ce qui est déjà fait n'est pas refait.")
                if apres:
                    apres()           # ce qui est déjà lu est visible dans l'outil de correction
            except SystemExit as e:
                t["etat"] = "erreur"
                log(str(e))
            except Exception as e:      # erreur imprévue : affichée telle quelle, jamais avalée
                t["etat"] = "erreur"
                log(f"{type(e).__name__} : {e}")
            t["fin"] = time.time()
        threading.Thread(target=corps, daemon=True).start()
        return t

    def pause(self):
        t = self.courante
        if not t or t["etat"] != "en cours" or not t["reprenable"]:
            raise RuntimeError("aucune tâche à mettre en pause")
        t["pause"] = True
        t["journal"].append("Pause demandée : la tâche s'arrête à la fin de l'étape en cours…")

    def reprendre(self):
        t = self.courante
        if not t or t["etat"] != "en pause":
            raise RuntimeError("aucune tâche en pause")
        fn, apres = t["relancer"]
        return self.lancer(t["projet"], t["titre"], fn, apres, reprenable=True)


def _vers(chemin, message, etape=None):
    return f"{chemin}?m={quote(str(message))}" + (f"#etape-{etape}" if etape else "")


# étape de la page d'examen où une tâche ramène (d'après son titre)
ETAPE_DES_TACHES = (("Produire", 2), ("Lire les copies", 3), ("Lire les réponses courtes", 4), ("Sujet ", 4),
                    ("Lecture approfondie", 4), ("Exporter", 6))


def etapes_examen(e, tache, ouvert, notes, trocr, approfondie=None):
    """Assistant de la page d'examen : état de chaque étape et celle où ouvrir la page.
    Une étape n'est grisée que si un VRAI prérequis manque (pas de dépôt sans PDF produits, pas de correction ni
    d'export sans classe lue) ; une étape faite reste toujours accessible (le parcours n'est pas linéaire : une
    classe se dépose pendant qu'une autre se corrige)."""
    lues = e["lues"]
    sans_classe = None if lues else "déposez et lisez d'abord une classe (étape 3)"
    etapes = [
        {"n": 1, "titre": "Source du sujet", "faite": not e["erreurs"], "bloque": None},
        {"n": 2, "titre": "Sujets et corrigés", "faite": bool(e["produit"]),
         "bloque": "corrigez d'abord la source (étape 1)" if e["erreurs"] else None},
        {"n": 3, "titre": "Copies scannées", "faite": lues > 0,
         "bloque": None if e["produit"] or e["classes"] else "produisez d'abord les PDF (étape 2)"},
        {"n": 4, "titre": "Lectures automatiques", "facultatif": True,
         # une lecture approfondie interrompue (Thessalia fermé, pause) garde l'étape « à faire » : on y revient
         "faite": bool(lues) and e["courtes"] == lues and not (approfondie or {}).get("interrompue"),
         "bloque": sans_classe},
        {"n": 5, "titre": "Correction", "faite": bool(ouvert), "bloque": sans_classe},
        {"n": 6, "titre": "Notes", "faite": bool(notes), "bloque": sans_classe},
    ]
    courante = None
    if tache:
        courante = next((n for debut, n in ETAPE_DES_TACHES if tache["titre"].startswith(debut)), None)
    if courante is None:
        # première étape à faire ; les lectures automatiques ne retiennent pas sans lecteur installé
        courante = next((x["n"] for x in etapes if not x["faite"] and not x["bloque"]
                         and not (x["n"] == 4 and not trocr)), 6)
    return etapes, courante


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
        e, out = resume(p), outils()
        appr = p.approfondie()
        if appr:
            appr["en_tache"] = bool(t and t["titre"].startswith("Lecture approfondie") and t["etat"] in ("en cours", "en pause"))
            appr["interrompue"] = appr["etat"] == "en cours" and not appr["en_tache"]
        etapes, courante = etapes_examen(e, t, etat["ouvert"] == nom, notes.exists(), out["trocr"], appr)
        return render_template("examen.html", e=e, approfondie=appr, pdfs=[f.name for f in p.pdfs()], tache=t, etapes=etapes,
                               courante=courante,
                               ouvert=etat["ouvert"] == nom, message=request.args.get("m"), outils=out,
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

    def lancer(nom, titre, fn, apres=None, retour=None, reprenable=False):
        retour = retour or f"/examens/{nom}"
        try:
            taches.lancer(nom, titre, fn, apres, reprenable)
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
        return lancer(nom, "Lire les réponses courtes et les noms", lambda log: p.lire_courtes(log=log), apres_lecture(nom),
                      reprenable=True)

    @app.post("/examens/<nom>/valider/<langue>")
    def valider(nom, langue):
        p = projet(nom)
        try:
            m = p.valider_lecture(langue)
        except ValueError as e:
            return redirect(_vers(f"/examens/{nom}", e))
        return lancer(nom, f"Sujet {langue.upper()} validé ({m['justes']}/{m['n']} lectures justes) : relecture des "
                           "réponses courtes", lambda log: p.lire_courtes(log=log), apres_lecture(nom), reprenable=True)

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
                      retour="/reglages", reprenable=action == "telecharger")

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
        return lancer(APP, titre, fn, retour="/apprentissage", reprenable=quoi == "ecriture" and action == "affiner")

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
        return redirect(f"/examens/{nom}#etape-6")

    @app.route("/aide")
    def aide():
        doc = Path(__file__).resolve().parent.parent / "docs"
        if not (doc / "Thessalia_mode_emploi.pdf").exists():
            abort(404)
        return send_from_directory(doc, "Thessalia_mode_emploi.pdf")

    @app.post("/examens/<nom>/preparer")
    def preparer(nom):
        p = projet(nom)
        return lancer(nom, "Lecture approfondie (code, relecture)", lambda log: p.preparer(log=log),
                      apres_lecture(nom), reprenable=True)

    @app.post("/examens/<nom>/liste")
    def deposer_liste(nom):
        p = projet(nom)
        f = request.files.get("liste")
        if not f or not f.filename:
            return redirect(_vers(f"/examens/{nom}", "Choisissez la liste des élèves (.xlsx).", 6))
        try:
            n = p.deposer_liste(f.read())
        except ValueError as e:
            return redirect(_vers(f"/examens/{nom}", e, 6))
        return redirect(_vers(f"/examens/{nom}", f"Liste des élèves enregistrée : {n} élèves.", 6))

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
        return jsonify(None if t is None else {k: t[k] for k in ("projet", "titre", "etat", "journal", "progression",
                                                                 "reprenable", "pause")})

    @app.post("/tache/pause")
    def tache_pause():
        try:
            taches.pause()
        except RuntimeError:
            pass
        return redirect(request.referrer or "/examens")

    @app.post("/tache/reprendre")
    def tache_reprendre():
        try:
            taches.reprendre()
        except RuntimeError as e:
            return redirect(_vers(request.referrer or "/examens", e))
        return redirect(request.referrer or "/examens")
