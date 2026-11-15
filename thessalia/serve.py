"""Application Thessalia (`python -m thessalia app`, lancée par Thessalia.bat / Thessalia.command) : pages des
examens (web_examens) et outil de correction de l'examen ouvert.

Petit serveur Flask qui n'écoute que cette machine (127.0.0.1) : tableau de bord, vue par question, vue par copie,
notes en direct. Chaque clic est enregistré dans la base de l'examen (`examens/<nom>/decisions.sqlite`, hors
dépôt). Les copies, vignettes et décisions ne quittent jamais la machine.
"""
from __future__ import annotations

import csv
import io
import webbrowser
from pathlib import Path

from .correction import Classe, Decisions, DB_PATH, Memory, group_of, lectures_tapees, resume_memoire, retenu


def _classes(paths):
    """Dossiers de résultats d'une classe (contiennent results.json), à partir des chemins donnés."""
    out = []
    for p in map(Path, paths):
        if (p / "results.json").exists():
            out.append(p)
        else:
            out += sorted(d for d in p.iterdir() if (d / "results.json").exists())
    return out


GROUP_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "NA", "NB"]


def _gkey(g):
    return (GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER), g)


def _qkey(fid):
    return [int(x) if x.isdigit() else 0 for x in fid.replace("q", "").split(".")]


def create_app(paths, db_path=DB_PATH, examens=None, compte=None):
    """examens : dossier des examens (application) ; « Corriger les copies lues » d'un examen y charge ses classes.
    paths : classes chargées d'emblée (tests)."""
    from flask import Flask, abort, jsonify, render_template, request, send_from_directory, Response, redirect, url_for

    web = Path(__file__).parent / "web"
    app = Flask(__name__, template_folder=str(web / "templates"), static_folder=str(web / "static"))
    app.json.ensure_ascii = False
    decisions, exams, memory = Decisions(db_path), {}, Memory()
    classes, groups = {}, {}

    def charger(dossiers, stockage=None):
        """(Re)charge les classes corrigées, en place : les pages s'en servent aussitôt (application des examens :
        « Corriger » ouvre les classes d'un examen). `stockage` : base des décisions, vérité et attributions propres
        à l'examen ; sans lui, celles de data/. Deux classes de même nom dans deux examens ne partagent ainsi
        jamais leurs décisions."""
        st = stockage or {}
        decisions.ouvrir(st.get("db", db_path))
        dirs = {k: st[k] for k in ("truth_dir", "lists_dir") if k in st}
        exams.clear()       # corrigés relus : un examen a pu être reproduit entre-temps
        nouv = ({d.name: Classe(d, exams, decisions, memory=memory, **dirs) for d in _classes(dossiers)}
                if dossiers else {})
        classes.clear()
        classes.update(nouv)
        groups.clear()
        for c in classes.values():  # vérité d'apprentissage à jour dès le chargement (classes déjà travaillées)
            if decisions.of(c.name):
                c.save_labels()
            groups.setdefault(c.group, []).append(c)
        memory.dirty = True

    charger(paths)
    if not classes and examens is None:
        raise SystemExit("Aucune classe trouvée (dossiers contenant results.json).")

    @app.before_request
    def refresh_memory():
        # mémoire des verdicts recalculée à l'ouverture d'une page après de nouvelles décisions (pas à chaque clic)
        if memory.dirty and request.method == "GET" and not request.path.startswith(("/img/", "/static/")):
            memory.rebuild(classes.values())

    def group(g):
        if g not in groups:
            abort(404)
        return groups[g]

    def summary(cs):
        rows = []
        for c in cs:
            s, q, n = c.short_items(), c.qcm_items(), c.notes()
            rows.append({"classe": c.name, "copies": len(c.copy_ids),
                         "a_decider": sum(not i["decide"] for i in s + q), "total": len(s) + len(q),
                         "completes": sum(r["en_attente"] == 0 for r in n)})
        return rows

    def items_of(cs, fid):
        out = []
        for c in cs:
            pool = (c.qcm_items() if fid in _qcm_fids(c)
                    else c.code_items() if fid in c.exam.bareme.get("champs", {}) else c.short_items())
            out += [i for i in pool if i["champ"] == fid]
        return out

    def saisies(c, fid, n=6):
        """Lectures tapées pour ce champ dans toutes les classes ouvertes du même sujet (pas seulement le
        groupe) : proposées en un clic sur les cartes. Le corrigé a déjà son bouton « = attendu »."""
        if fid not in c.exam.points:
            return []
        mid = c.memory_id(fid)
        meme = [o for o in classes.values() if fid in o.exam.points and o.memory_id(fid) == mid]
        att = c.exam.key.get("short_answers", {}).get(fid)
        cnt = lectures_tapees(meme, fid)
        return [{"texte": t, "n": k} for t, k in cnt.most_common()
                if att is None or c.exam.clean(t, fid) != c.exam.clean(att, fid)][:n]

    def _qcm_fids(c):
        return {f["id"] for f in c.exam.fields.values() if f["type"] in ("mcq", "truefalse")}

    def questions(cs):
        """Champs du groupe avec le nombre de réponses à décider (QCM en revue compris)."""
        todo, total = {}, {}
        for c in cs:
            for i in c.all_items():
                total[i["champ"]] = total.get(i["champ"], 0) + 1
                todo[i["champ"]] = todo.get(i["champ"], 0) + (not i["decide"])
        return [{"champ": f, "a_decider": todo[f], "total": total[f]} for f in sorted(total, key=_qkey)]

    def a_la_main(g=None):
        return [x for gg in sorted(groups, key=_gkey) if g in (None, gg) for c in groups[gg] for x in c.a_la_main()]

    @app.context_processor
    def nb_a_la_main():
        # compteur du bouton de l'en-tête : copies à reprendre sur le papier dont des réponses attendent encore
        return {"nb_a_la_main": sum(bool(x["restants"]) for x in a_la_main())}

    @app.route("/")
    def home():
        if not classes and examens is not None:
            from flask import redirect
            return redirect("/examens")
        data = [{"groupe": g, "classes": summary(groups[g]), "a_la_main": a_la_main(g)} for g in sorted(groups, key=_gkey)]
        return render_template("accueil.html", groupes=data)

    @app.route("/a-la-main")
    def a_la_main_page():
        g = request.args.get("g")
        return render_template("a_la_main.html", copies=a_la_main(g), groupe=g)

    @app.route("/g/<g>")
    def group_page(g):
        cs = group(g)
        return render_template("groupe.html", groupe=g, classes=summary(cs), questions=questions(cs), a_la_main=a_la_main(g))

    @app.route("/g/<g>/q/<fid>")
    def question_page(g, fid):
        cs = group(g)
        qs = questions(cs)
        ids = [q["champ"] for q in qs]
        if fid not in ids:
            abort(404)
        ex = cs[0].exam
        code = fid in ex.bareme.get("champs", {})
        consigne = ex.prompts.get(fid, "")
        if code:   # énoncé de la question (gabarit) ; le barème tient lieu de corrigé
            num = ex.fields.get(fid, {}).get("question")
            consigne = next((q.get("prompt", "") for q in ex.template["questions"] if q["num"] == num), "")
        payload = {"groupe": g, "champ": fid, "items": items_of(cs, fid), "code": code,
                   "attendu": "barème ci-dessous" if code else
                   ex.key.get("short_answers", {}).get(fid) or ", ".join(ex.key.get("answers", {}).get(fid, [])),
                   "consigne": consigne, "questions": qs, "saisies": [] if code else saisies(cs[0], fid)}
        champ_g = ex.fields.get(fid, {})
        q = next((q for q in ex.template["questions"] if q["num"] == champ_g.get("question")), {})
        pts = ex.bareme.get("champs", {}).get(fid, {}).get("points") if code else ex.points.get(fid)
        tete = {"exercice": (q.get("exercise") or {}).get("title"), "question": q.get("num"),
                "points": None if pts is None else f"{pts:g}".replace(".", ",")}
        i = ids.index(fid)
        return render_template("question.html", data=payload, groupe=g, champ=fid, code=code, tete=tete,
                               prec=ids[i - 1] if i else None, suiv=ids[i + 1] if i + 1 < len(ids) else None)

    @app.route("/g/<g>/q/<fid>/enonce.png")
    def enonce_image(g, fid):
        """Question découpée dans le PDF du sujet, zone surlignée (cf. enonce). 404 : l'outil garde le texte."""
        from .correction import stockage_examen
        from .enonce import image_question, pdf_du_sujet
        c = group(g)[0]
        st = stockage_examen(c.dir)
        dossiers = [st["templates_dir"].parent, st["templates_dir"]] if st else [Path("templates")]
        cache = (st["templates_dir"].parent / "enonces") if st else (c.dir / "enonces")
        try:
            p = image_question(pdf_du_sujet(c.exam.template, dossiers), c.exam.template, fid,
                               cache / f"{c.exam_id}_{fid}.png")
        except Exception:      # PDF illisible, page absente… : l'énoncé reste en texte
            p = None
        if not p:
            abort(404)
        return send_from_directory(p.parent.resolve(), p.name, max_age=0)

    @app.route("/suivi")
    def suivi_page():
        rows, erreurs = [], []
        for g in sorted(groups, key=_gkey):
            for c in groups[g]:
                st, err = c.suivi()
                rows.append(st)
                erreurs += err
        return render_template("suivi.html", lignes=rows, erreurs=erreurs)

    def identification(g):
        """Copies du groupe avec leur élève confirmé ou proposé (répartition d'ensemble sur ce qui reste)."""
        from .identite import LECTURES, classer, lire_attributions, lire_convoques, lire_liste, repartir
        cs = group(g)
        # session à part (BIS) : les convoqués, quel que soit leur groupe ; sinon la liste du groupe
        convoques = sorted({e for c in cs for e in lire_convoques(c.name, c.lists_dir)})
        eleves = convoques or lire_liste(lists_dir=cs[0].lists_dir).get(g, []) if cs else []
        att = {c.name: lire_attributions(c.name, c.lists_dir) for c in cs}
        # un élève peut avoir composé avec un autre groupe : pris dans TOUTES les classes
        pris = {e for o in classes.values() for e in lire_attributions(o.name, o.lists_dir).values()}
        libres = [e for e in eleves if e not in pris]
        rows, scores = [], {}
        for c in cs:
            lus = c._json(c.dir / LECTURES)
            for cid in c.copy_ids:
                rang = classer(lus.get(cid, {}), eleves) if lus.get(cid) else []
                if rang and not att[c.name].get(cid):
                    scores[(c.name, cid)] = dict(rang)
                vig = {z: f"{cid}/crops/identity.{z}.png" for z in ("nom", "prenom")}
                vig = {z: p if (c.dir / p).exists() else None for z, p in vig.items()}
                rows.append({"classe": c.name, "copie": cid, "num": int(cid.split("_")[-1]), **vig,
                             "hors_format": cid in c.hors_format,
                             "confirme": att[c.name].get(cid),
                             "propositions": [{"eleve": e, "score": sc} for e, sc in rang[:3]]})
        # proposition pré-remplie : répartition d'ensemble sur les copies non confirmées et les élèves libres
        rep = repartir({k: {e: v[e] for e in libres} for k, v in scores.items()}, libres)
        for r in rows:
            e = rep.get((r["classe"], r["copie"]))
            if e:
                r["repartition"] = e
                if all(p["eleve"] != e for p in r["propositions"]):
                    r["propositions"].insert(0, {"eleve": e, "score": scores[(r["classe"], r["copie"])][e]})
        return rows, eleves, pris

    @app.route("/g/<g>/noms")
    def noms_page(g):
        """Identification : chaque copie du groupe, vignettes Nom/Prénom, élève proposé ou confirmé."""
        rows, eleves, pris = identification(g)
        data = {"groupe": g, "eleves": eleves, "copies": rows, "lus": any(r["propositions"] for r in rows)}
        return render_template("noms.html", data=data, groupe=g,
                               absents=[e for e in eleves if e not in pris], n_conf=sum(bool(r["confirme"]) for r in rows))

    @app.route("/g/<g>/repartition")
    def repartition(g):
        """Propositions recalculées après une confirmation (moins de copies et d'élèves en jeu : meilleures).
        Simulé sur NB le 22 octobre : 32 justes sur 37 au moment de les voir, contre 27 figées au chargement."""
        rows, eleves, pris = identification(g)
        return jsonify({"repartition": {r["classe"] + "/" + r["copie"]: r.get("repartition") for r in rows
                                        if not r["confirme"]},
                        "absents": [e for e in eleves if e not in pris]})

    @app.post("/api/identite")
    def api_identite():
        from .identite import ecrire_attribution, lire_attributions, lire_convoques, lire_liste
        d = request.get_json(force=True)
        c = classes.get(d.get("classe")) or abort(404)
        cid, e = d.get("copie"), (d.get("etudiant") or "").strip()
        if cid not in c.copy_ids:
            abort(404)
        if e:
            liste = lire_liste(lists_dir=c.lists_dir)
            if e not in (lire_convoques(c.name, c.lists_dir) or liste.get(c.group, [])):
                autre = next((g for g, v in liste.items() if e in v), None)
                if autre is None:
                    return jsonify({"erreur": f"« {e} » n'est sur aucune liste (vérifier l'orthographe : NOM Prénom)"}), 409
                if not d.get("autre_groupe"):   # élève qui a composé avec un autre groupe : confirmation demandée
                    return jsonify({"erreur": f"« {e} » est sur la liste du groupe {autre}, pas {c.group}",
                                    "autre_groupe": autre}), 409
            for o in classes.values():   # un élève n'a qu'une copie, tous groupes confondus
                for oc, oe in lire_attributions(o.name, o.lists_dir).items():
                    if oe == e and (o.name, oc) != (c.name, cid):
                        return jsonify({"erreur": f"déjà attribué à {o.name} · copie {int(oc.split('_')[-1])}"}), 409
        ecrire_attribution(c.name, c.copy_ids, cid, e, c.lists_dir)
        return jsonify({"ok": True, "etudiant": e})

    @app.route("/g/<g>/copies")
    def copies_page(g):
        cs = group(g)
        rows = [r for c in cs for r in c.notes()]
        return render_template("copies.html", groupe=g, notes=rows)

    @app.route("/c/<classe>/<cid>")
    def copy_page(classe, cid):
        c = classes.get(classe) or abort(404)
        if cid not in c.copy_ids:
            abort(404)
        i = c.copy_ids.index(cid)
        doc = c.doc(cid)
        nav = {"prec": c.copy_ids[i - 1] if i else None,
               "suiv": c.copy_ids[i + 1] if i + 1 < len(c.copy_ids) else None}
        if cid in c.hors_format:
            note = next(r for r in c.notes() if r["copie"] == cid)
            return render_template("copie_hors_format.html", classe=classe, copie=cid, groupe=c.group, note=note,
                                   annexes=doc.get("annexes", []), etudiant=c.students().get(cid),
                                   message=request.args.get("m"), **nav)
        pages = []
        for num, p in sorted(doc.get("pages", {}).items(), key=lambda kv: int(kv[0])):
            if p.get("overlay"):
                pages.append({"page": int(num), "img": p["overlay"].replace("\\", "/")})
        items = [it for it in c.all_items() if it["copie"] == cid]
        for it in items:  # position de la réponse sur la page (overlay à l'échelle 0,6)
            f = c.exam.fields.get(it["champ"], {})
            it["page"] = f.get("page")
            if it.get("qcm") and it["champ"] in doc.get("answers", {}):  # QCM d'une page absente : pas de cadre
                boxes = [o["box_px"] for o in doc["answers"][it["champ"]]["options"].values()]
                it["box"] = [min(b[0] for b in boxes) - 10, min(b[1] for b in boxes) - 10,
                             max(b[2] for b in boxes) + 10, max(b[3] for b in boxes) + 10]
        note = next(r for r in c.notes() if r["copie"] == cid)
        payload = {"classe": classe, "copie": cid, "groupe": c.group, "pages": pages, "items": items, "note": note,
                   "attendus": c.exam.key.get("short_answers", {}), "echelle": 0.6}
        main = next((x for x in c.a_la_main() if x["copie"] == cid), None)
        return render_template("copie.html", data=payload, classe=classe, copie=cid, groupe=c.group, a_la_main=main,
                               prec=c.copy_ids[i - 1] if i else None,
                               suiv=c.copy_ids[i + 1] if i + 1 < len(c.copy_ids) else None)

    @app.post("/c/<classe>/<cid>/note-hors-format")
    def note_hors_format(classe, cid):
        """Note saisie à la main d'une copie hors format (points de l'examen, virgule acceptée ; vide = effacer)."""
        c = classes.get(classe) or abort(404)
        brut = (request.form.get("note") or "").strip()
        vers = lambda m: redirect(url_for("copy_page", classe=classe, cid=cid, m=m))
        try:
            note = float(brut.replace(",", ".")) if brut else None
        except ValueError:
            return vers(f"Note refusée : « {brut} » n'est pas un nombre.")
        try:
            c.noter_hors_format(cid, note)
        except ValueError as e:
            return vers(f"Note refusée : {e}.")
        return vers("Note enregistrée." if brut else "Note effacée.")

    @app.route("/verif-noms")
    def verif_noms_page():
        """Contrôle avant l'export : le nom écrit sur chaque copie à côté de l'élève attribué, copies à risque
        en tête (nom proche d'un autre élève, voisin d'un absent, autre groupe ; cf. verif_noms)."""
        from .identite import lire_attributions, lire_convoques, lire_liste
        from .verif_noms import risques
        attributions, sans = [], []
        for c in classes.values():
            att = lire_attributions(c.name, c.lists_dir)
            attributions += [(c.name, cid, e) for cid, e in sorted(att.items())]
            sans += [{"classe": c.name, "copie": cid, "groupe": c.group} for cid in c.copy_ids if cid not in att]
        liste = lire_liste(lists_dir=next(iter(classes.values())).lists_dir) if classes else {}
        r = risques(attributions, liste, convoques={c.name: lire_convoques(c.name, c.lists_dir) for c in classes.values()})
        lignes = [{"classe": cl, "copie": cid, "num": int(cid.split("_")[-1]), "groupe": group_of(cl), "eleve": e,
                   "raisons": r[(cl, cid)],
                   "img": {z: f"{cid}/crops/identity.{z}.png" for z in ("nom", "prenom")
                           if (classes[cl].dir / cid / "crops" / f"identity.{z}.png").exists()}}
                  for cl, cid, e in attributions]
        lignes.sort(key=lambda x: (not x["raisons"], x["classe"], x["num"]))
        return render_template("verif_noms.html", lignes=lignes, sans=sans,
                               n_risque=sum(bool(x["raisons"]) for x in lignes))

    @app.route("/img/<classe>/<path:p>")
    def image(classe, p):
        c = classes.get(classe) or abort(404)
        return send_from_directory(c.dir.resolve(), p)

    @app.post("/api/decision")
    def api_decision():
        d = request.get_json(force=True)
        c = classes.get(d.get("classe")) or abort(404)
        memory.dirty = True
        if d.get("annuler"):
            c.undo(d["cle"])
        else:
            texte = d.get("texte")
            c.decide(d["cle"], d.get("verdict"), texte, d.get("options"))  # ce qui manque est conservé
        c.save_labels()  # examens/<nom>/verite/<classe>.appris.json à jour : rien à exporter à la main
        cid = next((x for x in c.copy_ids if f"c{int(x.split('_')[-1]):02d}_" == d["cle"][:4]), None)
        item = next((i for i in c.all_items() if i["cle"] == d["cle"]), None)
        note = next((r for r in c.notes() if r["copie"] == cid), None)
        rep = {"item": item, "note": note}
        if item and not d.get("annuler") and not item.get("qcm") and not item.get("code"):
            rep["retenu"] = retenu(list(classes.values()), c, d["cle"])
            # lecture tapée par l'enseignant : exemple pour affiner le lecteur (page Apprentissage)
            rep["exemple"] = d.get("texte") is not None
        return jsonify(rep)

    @app.post("/api/code-transcription")
    def api_code_transcription():
        """Transcription d'un cadre de code corrigée : enregistrée, tests relancés, critères pré-cochés à jour."""
        d = request.get_json(force=True)
        c = classes.get(d.get("classe")) or abort(404)
        texte = (d.get("texte") or "").rstrip()
        if not texte.strip():
            return jsonify({"erreur": "transcription vide : écrire (vide) si rien n'est écrit"}), 400
        c.corriger_transcription(d["cle"], texte)
        c.save_labels()   # <classe>.code_appris.json : vérité pour faire progresser la chaîne locale
        item = next((i for i in c.code_items() if i["cle"] == d["cle"]), None)
        return jsonify({"item": item})

    @app.route("/g/<g>/notes.csv")
    def export(g):
        rows = [r for c in group(g) for r in c.notes()]
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["classe", "copie", "étudiant", "QCM", "réponses courtes", "code", "total", "sur", "en attente", "état"])
        fmt = lambda x: f"{x:.3f}".rstrip("0").rstrip(".").replace(".", ",")
        for r in rows:
            w.writerow([r["classe"], r["copie"], r["etudiant"], fmt(r["qcm"]), fmt(r["courtes"]), fmt(r["code"]), fmt(r["total"]),
                        fmt(r["max"]), r["en_attente"], r["etat"]])
        return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=notes_{g}.csv"})

    @app.after_request
    def no_cache(resp):
        # les pages changent à chaque décision : jamais de version en cache (retour arrière compris)
        if resp.mimetype in ("text/html", "application/json"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    app.jinja_env.globals.update(mode_examens=examens is not None, avec_compte=False)
    if compte is not None:         # application : identifiant et mot de passe avant toute page (thessalia.compte)
        from .compte import proteger
        proteger(app, compte)
    if examens is not None:
        from .web_examens import enregistrer
        def memoire():
            if memory.dirty:
                memory.rebuild(classes.values())
            return resume_memoire(memory) if classes else None
        enregistrer(app, Path(examens), charger, memoire)
    return app




def port_occupe(port) -> bool:
    """Un autre serveur écoute-t-il déjà sur 127.0.0.1:port ? Sous Windows, un second Thessalia pourrait s'y
    installer sans erreur (SO_REUSEADDR) et l'ancien continuerait de répondre, avec son ancien code (9 nov.)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _refuser_si_occupe(port):
    if port_occupe(port):
        raise SystemExit(f"Thessalia tourne déjà (adresse http://127.0.0.1:{port}/ occupée) : une autre fenêtre noire "
                         "est ouverte. La fermer, puis relancer ; ou utiliser l'onglet déjà ouvert.")


def run_app(examens="examens", port=8765, open_browser=True, db_path=DB_PATH):
    """Application : pages Examens (sujet source, PDF, dépôt des scans, lecture) + outil de correction."""
    from .compte import Compte
    _refuser_si_occupe(port)
    Path(examens).mkdir(parents=True, exist_ok=True)
    app = create_app([], db_path, examens=examens, compte=Compte())
    url = f"http://127.0.0.1:{port}/examens"
    print(f"Thessalia : {url}  (Ctrl+C pour arrêter ; examens et décisions dans {Path(examens).resolve()})")
    if open_browser:
        webbrowser.open(url)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
