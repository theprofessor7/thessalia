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


def create_app(paths, db_path=DB_PATH):
    from flask import Flask, abort, jsonify, render_template, request, send_from_directory, Response

    web = Path(__file__).parent / "web"
    app = Flask(__name__, template_folder=str(web / "templates"), static_folder=str(web / "static"))
    app.json.ensure_ascii = False
    decisions, exams, memory = Decisions(db_path), {}, Memory()
    classes = {d.name: Classe(d, exams, decisions, memory=memory) for d in _classes(paths)}
    if not classes:
        raise SystemExit("Aucune classe trouvée (dossiers contenant results.json).")
    for c in classes.values():  # vérité d'apprentissage à jour dès le démarrage (classes déjà travaillées)
        if decisions.of(c.name):
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
            pool = c.qcm_items() if fid in _qcm_fids(c) else c.short_items()
            out += [i for i in pool if i["champ"] == fid]
        return out

    def _qcm_fids(c):
        return {f["id"] for f in c.exam.fields.values() if f["type"] in ("mcq", "truefalse")}

    def questions(cs):
        """Champs du groupe avec le nombre de réponses à décider (QCM en revue compris)."""
        todo, total = {}, {}
        for c in cs:
            for i in c.short_items() + c.qcm_items():
                total[i["champ"]] = total.get(i["champ"], 0) + 1
                todo[i["champ"]] = todo.get(i["champ"], 0) + (not i["decide"])
        return [{"champ": f, "a_decider": todo[f], "total": total[f]} for f in sorted(total, key=_qkey)]

    @app.route("/")
    def home():
        data = [{"groupe": g, "classes": summary(groups[g])} for g in sorted(groups, key=_gkey)]
        return render_template("accueil.html", groupes=data)

    @app.route("/g/<g>")
    def group_page(g):
        cs = group(g)
        return render_template("groupe.html", groupe=g, classes=summary(cs), questions=questions(cs))

    @app.route("/g/<g>/q/<fid>")
    def question_page(g, fid):
        cs = group(g)
        qs = questions(cs)
        ids = [q["champ"] for q in qs]
        if fid not in ids:
            abort(404)
        ex = cs[0].exam
        payload = {"groupe": g, "champ": fid, "items": items_of(cs, fid),
                   "attendu": ex.key.get("short_answers", {}).get(fid) or ", ".join(ex.key.get("answers", {}).get(fid, [])),
                   "consigne": ex.prompts.get(fid, ""), "questions": qs}
        i = ids.index(fid)
        return render_template("question.html", data=payload, groupe=g, champ=fid,
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
                items += [i for i in c.short_items() + c.qcm_items() if i["cle"] == cle]
        return render_template("revoir.html", data={"items": items}, titre=request.args.get("titre", "Réponses à revoir"))

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
        items = [it for it in c.short_items() + c.qcm_items() if it["copie"] == cid]
        for it in items:  # position de la réponse sur la page (overlay à l'échelle 0,6)
            f = c.exam.fields.get(it["champ"], {})
            it["page"] = f.get("page")
            if it.get("qcm"):
                boxes = [o["box_px"] for o in doc["answers"][it["champ"]]["options"].values()]
                it["box"] = [min(b[0] for b in boxes) - 10, min(b[1] for b in boxes) - 10,
                             max(b[2] for b in boxes) + 10, max(b[3] for b in boxes) + 10]
        note = next(r for r in c.notes() if r["copie"] == cid)
        payload = {"classe": classe, "copie": cid, "groupe": c.group, "pages": pages, "items": items, "note": note,
                   "attendus": c.exam.key.get("short_answers", {}), "echelle": 0.6}
        return render_template("copie.html", data=payload, classe=classe, copie=cid, groupe=c.group,
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
        c.save_labels()  # data/truth/<classe>.appris.json à jour : rien à exporter à la main
        cid = next((x for x in c.copy_ids if f"c{int(x.split('_')[-1]):02d}_" == d["cle"][:4]), None)
        item = next((i for i in c.short_items() + c.qcm_items() if i["cle"] == d["cle"]), None)
        note = next((r for r in c.notes() if r["copie"] == cid), None)
        return jsonify({"item": item, "note": note})

    @app.route("/g/<g>/notes.csv")
    def export(g):
        rows = [r for c in group(g) for r in c.notes()]
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["classe", "copie", "étudiant", "QCM", "réponses courtes", "total", "sur", "en attente", "état"])
        fmt = lambda x: f"{x:.3f}".rstrip("0").rstrip(".").replace(".", ",")
        for r in rows:
            w.writerow([r["classe"], r["copie"], r["etudiant"], fmt(r["qcm"]), fmt(r["courtes"]), fmt(r["total"]),
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


def run(paths, port=8765, open_browser=True, db_path=DB_PATH):
    app = create_app(paths, db_path)
    url = f"http://127.0.0.1:{port}/"
    print(f"Outil de correction : {url}  (Ctrl+C pour arrêter ; décisions dans {db_path})")
    if open_browser:
        webbrowser.open(url)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
