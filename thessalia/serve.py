"""Outil de correction local : `python -m thessalia serve sorties/booster [autres dossiers…]`.

Petit serveur Flask qui n'écoute que cette machine (127.0.0.1) : tableau de bord, vue par question (comme
Gradescope), vue par copie, notes en direct, export CSV. Chaque clic est enregistré dans
`data/correction.sqlite` (hors dépôt) : plus de fichier à exporter ni à recopier.
Les copies, vignettes et décisions ne quittent jamais la machine.
"""
from __future__ import annotations

import csv
import io
import json
import webbrowser
from pathlib import Path

from .correction import Classe, Decisions, DB_PATH, Memory, group_of
from .notes import RATE


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


def create_app(paths, db_path=DB_PATH, apprendre=True):
    """apprendre=False (mode essai) : aucune étiquette d'apprentissage écrite (data/truth/<classe>.appris.json)."""
    from flask import Flask, abort, jsonify, render_template, request, send_from_directory, Response

    web = Path(__file__).parent / "web"
    app = Flask(__name__, template_folder=str(web / "templates"), static_folder=str(web / "static"))
    app.json.ensure_ascii = False
    decisions, exams, memory = Decisions(db_path), {}, Memory()
    classes = {d.name: Classe(d, exams, decisions, memory=memory) for d in _classes(paths)}
    if not classes:
        raise SystemExit("Aucune classe trouvée (dossiers contenant results.json).")
    for c in classes.values():  # vérité d'apprentissage à jour dès le démarrage (classes déjà travaillées)
        if apprendre and decisions.of(c.name):
            c.save_labels()
    groups = {}
    for c in classes.values():
        groups.setdefault(c.group, []).append(c)

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
                         "completes": sum(r["etat"] == "complète" for r in n)})
        return rows

    def items_of(cs, fid):
        out = []
        for c in cs:
            pool = (c.qcm_items() if fid in _qcm_fids(c)
                    else c.code_items() if fid in c.exam.bareme.get("champs", {}) else c.short_items())
            out += [i for i in pool if i["champ"] == fid]
        return out

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
                   "consigne": consigne, "questions": qs}
        i = ids.index(fid)
        return render_template("question.html", data=payload, groupe=g, champ=fid, code=code,
                               prec=ids[i - 1] if i else None, suiv=ids[i + 1] if i + 1 < len(ids) else None)

    @app.route("/suivi")
    def suivi_page():
        rows, erreurs = [], []
        for g in sorted(groups, key=_gkey):
            for c in groups[g]:
                st, err = c.suivi()
                rows.append(st)
                erreurs += err
        return render_template("suivi.html", lignes=rows, erreurs=erreurs)

    @app.route("/revoir")
    def revoir_page():
        """Page temporaire : quelques réponses désignées (?cles=classe/cNN_qX.Y,…) à trancher par l'enseignant."""
        wanted = [x.strip() for x in request.args.get("cles", "").split(",") if "/" in x]
        items = []
        for w in wanted:
            name, cle = w.split("/", 1)
            c = classes.get(name)
            if c:
                items += [i for i in c.all_items() if i["cle"] == cle]
        return render_template("revoir.html", data={"items": items}, titre=request.args.get("titre", "Réponses à revoir"))

    def identification(g):
        """Copies du groupe avec leur élève confirmé ou proposé (répartition d'ensemble sur ce qui reste)."""
        from .identite import LECTURES, classer, lire_attributions, lire_convoques, lire_liste, repartir
        cs = group(g)
        # session à part (BIS) : les convoqués, quel que soit leur groupe ; sinon la liste du groupe
        convoques = sorted({e for c in cs for e in lire_convoques(c.name, c.lists_dir)})
        eleves = convoques or lire_liste().get(g, [])
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
                rows.append({"classe": c.name, "copie": cid, "num": int(cid.split("_")[-1]),
                             "nom": f"{cid}/crops/identity.nom.png", "prenom": f"{cid}/crops/identity.prenom.png",
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
            liste = lire_liste()
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
        if apprendre:
            c.save_labels()  # data/truth/<classe>.appris.json à jour : rien à exporter à la main
        cid = next((x for x in c.copy_ids if f"c{int(x.split('_')[-1]):02d}_" == d["cle"][:4]), None)
        item = next((i for i in c.all_items() if i["cle"] == d["cle"]), None)
        note = next((r for r in c.notes() if r["copie"] == cid), None)
        return jsonify({"item": item, "note": note})

    @app.post("/api/code-transcription")
    def api_code_transcription():
        """Transcription d'un cadre de code corrigée : enregistrée, tests relancés, critères pré-cochés à jour."""
        d = request.get_json(force=True)
        c = classes.get(d.get("classe")) or abort(404)
        texte = (d.get("texte") or "").rstrip()
        if not texte.strip():
            return jsonify({"erreur": "transcription vide : écrire (vide) si rien n'est écrit"}), 400
        c.corriger_transcription(d["cle"], texte)
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

    app.jinja_env.globals.update(rate=RATE)
    return app


ESSAI_DB = Path("data/correction_essai.sqlite")


def run(paths, port=8765, open_browser=True, db_path=DB_PATH, essai=False):
    """essai=True : base de décisions à part (data/correction_essai.sqlite), aucune étiquette d'apprentissage :
    pour essayer l'outil sur une classe déjà corrigée sans toucher à ses décisions."""
    if essai:
        db_path = ESSAI_DB
    app = create_app(paths, db_path, apprendre=not essai)
    url = f"http://127.0.0.1:{port}/"
    print(f"Outil de correction{' (ESSAI : décisions à part, rien appris)' if essai else ''} : {url}  "
          f"(Ctrl+C pour arrêter ; décisions dans {db_path})")
    if open_browser:
        webbrowser.open(url)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
