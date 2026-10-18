"""Niveau 2 — page de validation de la vérité terrain des réponses courtes (commande `truth-page`).

    python -m thessalia truth-page sorties/<lot> [-t templates/<gabarit>.json] [--truth data/truth/<x>.json]

Écrit `sorties/<lot>/validation.html` : une page locale, sans serveur ni réseau, qui affiche les
réponses question par question (toutes les réponses à q2.1 côte à côte), pré-remplies avec la vérité
existante ou, à défaut, la proposition de `ocr`. L'enseignant corrige, valide (Entrée), puis exporte
un JSON au format de `--truth` (clé cNN_qX.Y ; "" = vide ; suffixe « ? » = non validée ou incertaine,
exclue des mesures).

Les QCM en revue (statut `review` de `process`) y sont aussi : extrait de la page, une case par option
pré-réglée sur la lecture de la machine. Ils s'exportent dans un second fichier, `<lot>.qcm_truth.json`
(clé cNN_qX ; options cochées « a,c » ; "" = aucune ; « ? » = non validée), lu par la commande `notes`.

La page contient des réponses d'étudiants : elle reste dans le dossier de sortie (hors dépôt) et
référence les vignettes par chemin relatif. L'avancement est gardé dans le navigateur (localStorage) ;
l'export / import JSON sert de sauvegarde.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2

from .common import load_json

OVERLAY_SCALE = 0.6  # échelle des overlays écrits par report.draw_overlay


def _qkey(fid):
    return [int(x) if x.isdigit() else x for x in fid.replace("q", "").split(".")]


def collect(results_dir, template=None, truth=None, qcm_truth=None):
    results_dir = Path(results_dir)
    copies = sorted(results_dir.glob("copy_*/result.json"))
    if not copies:
        raise SystemExit(f"Aucun résultat dans {results_dir} (lancer d'abord `process`).")
    prompts = {}
    if template:
        prompts = {f["id"]: f.get("prompt") or "" for p in load_json(template)["pages"] for f in p["fields"]
                   if f["type"] == "short_text"}
    truth = load_json(truth) if truth else {}
    items = []
    for rp in copies:
        doc = load_json(rp)
        c = int(doc["copy_id"].split("_")[1])
        for fid, info in doc.get("fields", {}).items():
            if info.get("type") != "short_text":
                continue
            key = f"c{c:02d}_{fid}"
            o = info.get("ocr") or {}
            blank = bool(info.get("blank")) and not info.get("suspect")
            prop = "" if blank else (o.get("value") or "")
            t = truth.get(key)
            items.append({
                "key": key, "copy": c, "fid": fid,
                "img": (info.get("crop") or "").replace("\\", "/"),
                "prop": prop, "status": "blank" if blank else o.get("status", ""),
                "sure": bool(o.get("sure")) and not blank,
                "sugg": [s for s in o.get("suggestions", []) if s and s != prop][:3],
                "value": prop if t is None else t.rstrip("?"),
                "unsure": bool(t is not None and t.endswith("?")),
                "from_truth": t is not None,
            })
    items.sort(key=lambda it: (_qkey(it["fid"]), it["copy"]))
    return {"lot": results_dir.name, "prompts": prompts, "items": items,
            "qcm": collect_qcm(results_dir, copies, qcm_truth)}


def _qcm_crop(results_dir: Path, copy_dir: Path, overlay: str, ans: dict, fid: str) -> str:
    """Bande de la page sur toute la largeur (libellés à droite des cases, énoncés V/F à gauche)."""
    img = cv2.imread(str(results_dir / overlay.replace("\\", "/")))
    if img is None:
        return ""
    ys = [y for o in ans["options"].values() for y in (o["box_px"][1], o["box_px"][3])]
    y0, y1 = int((min(ys) - 35) * OVERLAY_SCALE), int((max(ys) + 35) * OVERLAY_SCALE)
    out = copy_dir / "crops" / f"qcm_{fid}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img[max(0, y0):min(img.shape[0], y1), :], [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out.relative_to(results_dir).as_posix()


def collect_qcm(results_dir: Path, copies, qcm_truth=None):
    """QCM en revue : un élément par question, options pré-réglées sur la lecture de la machine."""
    truth = load_json(qcm_truth) if qcm_truth and Path(qcm_truth).exists() else {}
    items = []
    for rp in copies:
        doc = load_json(rp)
        c = int(doc["copy_id"].split("_")[1])
        reasons = {r["item"]: r for r in doc.get("review", [])}
        for fid, ans in doc.get("answers", {}).items():
            if ans.get("type") not in ("mcq", "truefalse") or ans.get("status") != "review":
                continue
            key, r, sel = f"c{c:02d}_{fid}", reasons.get(fid, {}), sorted(ans.get("selected", []))
            t = truth.get(key)
            items.append({
                "key": key, "copy": c, "fid": fid, "mode": ans.get("mode", "multi"),
                "img": _qcm_crop(results_dir, rp.parent, r["overlay"], ans, fid) if r.get("overlay") else "",
                "reason": r.get("reason") or ", ".join(ans.get("flags", [])),
                "options": [{"id": k, "label": o.get("label", k), "state": o["state"]}
                            for k, o in ans["options"].items()],
                "prop": sel,
                "value": sel if t is None else [x for x in t.rstrip("?").split(",") if x],
                "unsure": bool(t is not None and t.endswith("?")),
            })
    items.sort(key=lambda it: (_qkey(it["fid"]), it["copy"]))
    return items


def build(results_dir, template=None, truth=None, out=None, log=print, qcm_truth=None):
    if qcm_truth is None:  # vérité QCM déjà exportée pour ce lot : on la reprend
        guess = Path("data/truth") / f"{Path(results_dir).name}.qcm_truth.json"
        qcm_truth = guess if guess.exists() else None
    data = collect(results_dir, template, truth, qcm_truth)
    out = Path(out) if out else Path(results_dir) / "validation.html"
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(PAGE.replace("__DATA__", payload).replace("__LOT__", data["lot"]), encoding="utf-8")
    log(f"{len(data['items'])} réponses, {len(data['qcm'])} QCM en revue -> {out} (à ouvrir dans un navigateur ; ne pas diffuser : réponses d'étudiants)")
    return out


PAGE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Validation — __LOT__</title>
<style>
  :root { --bg:#f6f5f2; --card:#fff; --ink:#1d1d1b; --mute:#6b6a66; --line:#d9d6cf; --ok:#2f7d4f; --okbg:#e9f4ec;
          --warn:#b26a00; --warnbg:#fdf1dc; --accent:#2b5fab; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.4 system-ui, "Segoe UI", sans-serif; }
  header { position:sticky; top:0; z-index:5; background:var(--card); border-bottom:1px solid var(--line);
           padding:10px 16px; display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center; }
  header h1 { font-size:16px; margin:0 8px 0 0; }
  header label { color:var(--mute); }
  select, button, input[type=text] { font:inherit; }
  select, button { padding:5px 9px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--ink); }
  button { cursor:pointer; } button:hover { border-color:var(--accent); }
  button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
  #progress { margin-left:auto; font-variant-numeric:tabular-nums; color:var(--mute); }
  #bar { flex-basis:100%; height:4px; background:var(--line); border-radius:2px; overflow:hidden; }
  #bar div { height:100%; background:var(--ok); width:0; }
  main { padding:8px 16px 60px; }
  section h2 { font-size:15px; margin:22px 0 8px; display:flex; gap:12px; align-items:baseline; flex-wrap:wrap; }
  section h2 .prompt { font-weight:400; color:var(--mute); font-family:ui-monospace, Consolas, monospace; }
  section h2 button { font-size:12px; margin-left:auto; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(250px, 1fr)); gap:8px; }
  .grid.wide { grid-template-columns:repeat(auto-fill, minmax(420px, 1fr)); }
  .card { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--line); border-radius:6px; padding:6px 8px; }
  .card.ok { border-left-color:var(--ok); background:var(--okbg); }
  .card.unsure { border-left-color:var(--warn); background:var(--warnbg); }
  .card .top { display:flex; justify-content:space-between; color:var(--mute); font-size:12px; }
  .card img { display:block; max-width:100%; height:auto; margin:4px 0; background:#fff; border:1px solid var(--line); }
  .card .row { display:flex; gap:4px; }
  .card input[type=text] { flex:1; min-width:0; padding:5px 7px; border:1px solid var(--line); border-radius:5px;
                           font-family:ui-monospace, Consolas, monospace; font-size:15px; }
  .card input[type=text]:focus { outline:2px solid var(--accent); border-color:var(--accent); }
  .card .row button { padding:4px 8px; }
  .card .hint { font-size:12px; color:var(--mute); margin-top:3px; min-height:17px; }
  .card .hint a { color:var(--accent); cursor:pointer; text-decoration:underline; margin-right:6px; font-family:ui-monospace, Consolas, monospace; }
  .empty { color:var(--mute); padding:30px 0; }
  .block { grid-column:1 / -1; display:flex; gap:10px; align-items:center; margin-top:6px; padding:4px 0 2px;
           border-bottom:1px solid var(--line); font-family:ui-monospace, Consolas, monospace; color:var(--mute); }
  .block button { font-size:12px; }
  .card.qcm:focus { outline:2px solid var(--accent); }
  .card .reason { font-size:12px; color:var(--warn); }
  .opts { display:flex; flex-wrap:wrap; gap:4px; margin:4px 0; }
  .opts label { display:flex; gap:4px; align-items:center; padding:3px 7px; border:1px solid var(--line); border-radius:5px;
                background:var(--card); cursor:pointer; font-family:ui-monospace, Consolas, monospace; }
  .opts label.on { border-color:var(--accent); background:#e6eefb; font-weight:600; }
  .opts label.amb { border-style:dashed; border-color:var(--warn); }
  .opts input { margin:0; }
  kbd { border:1px solid var(--line); border-radius:3px; padding:0 4px; background:var(--bg); font-size:12px; }
</style>
</head>
<body>
<header>
  <h1>Validation — __LOT__</h1>
  <label>Question <select id="fq"></select></label>
  <label>Afficher <select id="ff">
    <option value="todo">à valider</option>
    <option value="sure">nombres très sûrs à valider</option>
    <option value="all">toutes</option>
    <option value="unsure">incertaines</option>
    <option value="diff">écart avec la proposition</option>
    <option value="ok">validées</option>
    <option value="auto">acceptées par la machine (contrôle rapide)</option>
  </select></label>
  <span><kbd>Entrée</kbd> valider et passer à la suivante · <kbd>Ctrl</kbd>+<kbd>I</kbd> incertaine · QCM : cochez ce que l'étudiant a coché</span>
  <span id="progress"></span>
  <button id="imp">Importer…</button><input type="file" id="file" accept=".json" hidden>
  <button id="exp" class="primary">Exporter le JSON</button>
  <div id="bar"><div></div></div>
</header>
<main id="main"></main>
<script id="data" type="application/json">__DATA__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("data").textContent);
const STORE = "thessalia-verite:" + DATA.lot;
// état d'une réponse : v = texte, ok = validée par l'enseignant, unsure = illisible / incertaine
let state = {};
// une réponse reprise d'une vérité déjà validée (sans « ? ») est déjà validée : seul le reste est à faire.
// Acceptée par la machine (statut ok de `ocr`) : validée d'office (auto), visible dans « contrôle rapide ».
// Tant que l'enseignant n'y touche pas, elle n'est PAS exportée dans la vérité : `notes` la reprend de la
// lecture, et l'affinage comme les mesures ne la prennent pas pour une réponse vérifiée.
const isAuto = it => it.status === "ok" && !it.from_truth;
for (const it of DATA.items)
  state[it.key] = {v: it.value, ok: (it.from_truth && !it.unsure) || isAuto(it), unsure: it.unsure, auto: isAuto(it)};
// QCM en revue : sel = options cochées par l'étudiant (pré-réglées sur la lecture de la machine)
const QCM = DATA.qcm || [];
let qstate = {};
for (const it of QCM) qstate[it.key] = {sel: it.value.slice(), ok: false, unsure: it.unsure};
try {
  const saved = JSON.parse(localStorage.getItem(STORE) || "{}");
  for (const k in saved) if (state[k]) {
    const s = saved[k], it = DATA.items.find(x => x.key === k);
    // avancement d'avant les validations d'office : une acceptée jamais touchée reste validée d'office
    if (state[k].auto && s.auto === undefined && !s.ok && s.v === it.value) continue;
    state[k] = s;
  }
  const qsaved = JSON.parse(localStorage.getItem(STORE + ":qcm") || "{}");
  for (const k in qsaved) if (qstate[k]) qstate[k] = qsaved[k];
} catch (e) { /* stockage indisponible : l'export reste la sauvegarde */ }
function save() {
  try { localStorage.setItem(STORE, JSON.stringify(state)); localStorage.setItem(STORE + ":qcm", JSON.stringify(qstate)); } catch (e) {}
}

const main = document.getElementById("main"), fq = document.getElementById("fq"), ff = document.getElementById("ff");
const questions = [...new Set(DATA.items.map(it => it.fid))];
const qcmQuestions = [...new Set(QCM.map(it => it.fid))];
fq.append(new Option("toutes", ""));
for (const q of qcmQuestions) fq.append(new Option(q + " (QCM)", q));
for (const q of questions) fq.append(new Option(q, q));

function el(tag, props, ...kids) {
  const e = Object.assign(document.createElement(tag), props || {});
  e.append(...kids);
  return e;
}
function shown(it) {
  const s = state[it.key];
  if (fq.value && it.fid !== fq.value) return false;
  switch (ff.value) {
    case "todo": return !s.ok;
    case "sure": return it.sure && !s.ok;
    case "unsure": return s.unsure;
    case "diff": return s.v !== it.prop;
    case "ok": return s.ok;
    case "auto": return isAuto(it);
    default: return true;
  }
}
function qshown(it) {
  const s = qstate[it.key];
  if (fq.value && it.fid !== fq.value) return false;
  switch (ff.value) {
    case "todo": case "sure": return !s.ok;
    case "unsure": return s.unsure;
    case "diff": return s.sel.join(",") !== it.prop.join(",");
    case "ok": return s.ok;
    case "auto": return false;
    default: return true;
  }
}
function paint(card, it) {
  const s = state[it.key];
  card.className = "card" + (s.unsure ? " unsure" : s.ok ? " ok" : "");
}
function progress() {
  const n = DATA.items.length + QCM.length;
  const ok = DATA.items.filter(it => state[it.key].ok).length + QCM.filter(it => qstate[it.key].ok).length;
  const un = DATA.items.filter(it => state[it.key].unsure).length + QCM.filter(it => qstate[it.key].unsure).length;
  document.getElementById("progress").textContent = ok + " / " + n + " validées · " + un + " incertaines"
    + (QCM.length ? " · dont " + QCM.length + " QCM" : "");
  document.querySelector("#bar div").style.width = (100 * ok / Math.max(n, 1)) + "%";
}
function validate(card, it, input) {
  const s = state[it.key];
  s.v = input.value.trim(); s.ok = true; s.auto = false;
  save(); paint(card, it); progress();
}
function makeCard(it) {
  const s = state[it.key];
  const input = el("input", {type: "text", value: s.v, placeholder: "(vide)", spellcheck: false, autocomplete: "off"});
  const card = el("div", {});
  card.dataset.key = it.key;
  const statut = ({ok: "acceptée par ocr", review: "en revue", blank: "détectée vide"}[it.status] || "non lue")
    + (it.sure ? " (très sûr : deux lectures d'accord)" : "");
  const hint = el("div", {className: "hint"});
  hint.append("proposé : " + (it.prop === "" ? "(vide)" : it.prop) + " — " + statut + (it.from_truth ? "" : " ; pas de vérité existante"));
  if (it.sugg.length) {
    hint.append(el("br"), "autres : ");
    for (const sg of it.sugg) hint.append(el("a", {textContent: sg, onclick: () => { input.value = sg; input.focus(); }}));
  }
  const bOk = el("button", {textContent: "✓", title: "Valider (Entrée)"});
  const bUn = el("button", {textContent: "?", title: "Incertaine / illisible (Ctrl+I)"});
  const next = () => {
    const all = [...main.querySelectorAll(".card input[type=text], .card.qcm")];
    const nx = all[all.indexOf(input) + 1];
    if (nx) nx.focus();
  };
  bOk.onclick = () => { s.unsure = false; validate(card, it, input); next(); };
  const toggleUnsure = () => { s.unsure = !s.unsure; s.v = input.value.trim(); s.ok = true; s.auto = false; save(); paint(card, it); progress(); };
  bUn.onclick = toggleUnsure;
  input.addEventListener("keydown", ev => {
    if (ev.key === "Enter") { ev.preventDefault(); s.unsure = false; validate(card, it, input); next(); }
    else if (ev.key.toLowerCase() === "i" && ev.ctrlKey) { ev.preventDefault(); toggleUnsure(); }
  });
  input.addEventListener("input", () => { s.v = input.value.trim(); s.ok = false; s.auto = false; save(); paint(card, it); progress(); });
  card.append(
    el("div", {className: "top"}, el("span", {textContent: "copie " + it.copy}), el("span", {textContent: it.key})),
    it.img ? el("img", {src: it.img, loading: "lazy", alt: "vignette " + it.key}) : el("div", {className: "hint", textContent: "(pas de vignette)"}),
    el("div", {className: "row"}, input, bOk, bUn), hint);
  paint(card, it);
  return card;
}
function makeQcmCard(it) {
  const s = qstate[it.key];
  const card = el("div", {tabIndex: 0});
  card.dataset.key = it.key;
  const opts = el("div", {className: "opts"});
  const paintQ = () => {
    card.className = "card qcm" + (s.unsure ? " unsure" : s.ok ? " ok" : "");
    for (const lb of opts.querySelectorAll("label")) {
      const on = s.sel.includes(lb.dataset.id);
      lb.classList.toggle("on", on);
      lb.querySelector("input").checked = on;
    }
  };
  for (const o of it.options) {
    const box = el("input", {type: "checkbox", tabIndex: -1});
    const lb = el("label", {className: o.state === "ambiguous" ? "amb" : "", title: "lecture machine : " + o.state},
                  box, o.id === o.label ? o.id : o.id + " " + o.label);
    lb.dataset.id = o.id;
    box.onchange = () => {
      if (box.checked) s.sel = it.mode === "single" ? [o.id] : [...new Set([...s.sel, o.id])].sort();
      else s.sel = s.sel.filter(x => x !== o.id);
      s.ok = false; save(); paintQ(); progress();
    };
    opts.append(lb);
  }
  const next = () => {
    const all = [...main.querySelectorAll(".card input[type=text], .card.qcm")];
    const nx = all[all.indexOf(card) + 1];
    if (nx) nx.focus();
  };
  const ok = () => { s.unsure = false; s.ok = true; save(); paintQ(); progress(); next(); };
  const toggleUnsure = () => { s.unsure = !s.unsure; s.ok = true; save(); paintQ(); progress(); };
  card.addEventListener("keydown", ev => {
    if (ev.target !== card) return;
    if (ev.key === "Enter") { ev.preventDefault(); ok(); }
    else if (ev.key.toLowerCase() === "i" && ev.ctrlKey) { ev.preventDefault(); toggleUnsure(); }
  });
  const bOk = el("button", {textContent: "✓", title: "Valider (Entrée)", onclick: ok});
  const bUn = el("button", {textContent: "?", title: "Incertaine / illisible (Ctrl+I)", onclick: toggleUnsure});
  card.append(
    el("div", {className: "top"}, el("span", {textContent: "copie " + it.copy}), el("span", {textContent: it.key})),
    el("div", {className: "reason", textContent: "en revue : " + it.reason}),
    it.img ? el("img", {src: it.img, loading: "lazy", alt: "extrait " + it.key}) : el("div", {className: "hint", textContent: "(pas d'image)"}),
    opts,
    el("div", {className: "row"}, el("span", {className: "hint", style: "flex:1",
       textContent: "lecture machine : " + (it.prop.length ? it.prop.join(", ") : "aucune case")}), bOk, bUn));
  paintQ();
  return card;
}
function render() {
  main.textContent = "";
  let total = 0;
  const nAuto = DATA.items.filter(it => state[it.key].auto).length;
  if (nAuto && ff.value !== "auto") {
    const b = el("button", {textContent: "contrôle rapide", onclick: () => { ff.value = "auto"; render(); }});
    main.append(el("p", {className: "hint"}, nAuto + " réponses acceptées par la machine sont déjà validées (non exportées "
      + "dans la vérité tant que vous n'y touchez pas). ", b));
  }
  for (const q of qcmQuestions) {
    const its = QCM.filter(it => it.fid === q && qshown(it));
    if (!its.length) continue;
    total += its.length;
    const grid = el("div", {className: "grid wide"});
    for (const it of its) grid.append(makeQcmCard(it));
    main.append(el("section", {}, el("h2", {}, el("span", {textContent: q + " — QCM en revue"}),
      el("span", {className: "prompt", textContent: "cochez exactement ce que l'étudiant a coché"})), grid));
  }
  for (const q of questions) {
    const its = DATA.items.filter(it => it.fid === q && shown(it));
    if (!its.length) continue;
    total += its.length;
    // réponses identiques côte à côte : une erreur de lecture saute aux yeux dans la rangée
    its.sort((a, b) => state[a.key].v.localeCompare(state[b.key].v) || a.copy - b.copy);
    const grid = el("div", {className: "grid" + (q.startsWith("q7.") ? " wide" : "")});
    // blocs de propositions identiques : un coup d'œil sur les vignettes du bloc, puis un seul clic
    for (let i = 0; i < its.length;) {
      let j = i;
      while (j < its.length && state[its[j].key].v === state[its[i].key].v) j++;
      const block = its.slice(i, j), cards = block.map(makeCard);
      if (block.length >= 2) {
        const v = state[block[0].key].v;
        const b = el("button", {textContent: "Valider ce bloc (" + block.length + ")"});
        b.onclick = () => {
          cards.forEach((c, k) => { if (!state[block[k].key].unsure) validate(c, block[k], c.querySelector("input[type=text]")); });
          b.disabled = true; b.textContent = "bloc validé";
        };
        grid.append(el("div", {className: "block"},
          el("span", {textContent: "« " + (v === "" ? "(vide)" : v) + " » × " + block.length}), b));
      }
      grid.append(...cards);
      i = j;
    }
    const all = el("button", {textContent: "Valider les " + its.length + " affichées"});
    all.onclick = () => {
      for (const c of grid.querySelectorAll(".card")) {
        const it = its.find(x => x.key === c.dataset.key);
        if (!state[it.key].unsure) validate(c, it, c.querySelector("input[type=text]"));
      }
    };
    main.append(el("section", {}, el("h2", {}, el("span", {textContent: q}),
      el("span", {className: "prompt", textContent: DATA.prompts[q] || ""}), all), grid));
  }
  if (!total) main.append(el("p", {className: "empty", textContent: "Rien à afficher avec ce filtre."}));
  progress();
}
fq.onchange = render; ff.onchange = render;

document.getElementById("exp").onclick = () => {
  // format de --truth : validée -> texte ; non validée ou incertaine -> texte + « ? » (exclue des mesures)
  const out = {};
  for (const it of DATA.items) {
    const s = state[it.key];
    if (s.auto) continue;  // acceptée par la machine, non vérifiée : pas dans la vérité (notes la reprend de la lecture)
    out[it.key] = s.v + (s.ok && !s.unsure ? "" : "?");
  }
  const todo = DATA.items.filter(it => !state[it.key].ok).length + QCM.filter(it => !qstate[it.key].ok).length;
  if (todo && !confirm(todo + " réponses ne sont pas validées : elles seront exportées avec « ? » (non notées). Continuer ?")) return;
  const dl = (obj, name) => {
    const a = el("a", {href: URL.createObjectURL(new Blob([JSON.stringify(obj, null, 1)], {type: "application/json"})), download: name});
    document.body.append(a); a.click(); a.remove();
  };
  dl(out, DATA.lot + ".short_truth.json");
  if (QCM.length) {  // second fichier : les QCM (le navigateur peut demander d'autoriser plusieurs téléchargements)
    const q = {};
    for (const it of QCM) { const s = qstate[it.key]; q[it.key] = s.sel.join(",") + (s.ok && !s.unsure ? "" : "?"); }
    setTimeout(() => dl(q, DATA.lot + ".qcm_truth.json"), 400);
  }
};
document.getElementById("imp").onclick = () => document.getElementById("file").click();
document.getElementById("file").onchange = async ev => {
  const f = ev.target.files[0];
  if (!f) return;
  let obj;
  try { obj = JSON.parse(await f.text()); } catch (e) { alert("Fichier JSON illisible."); return; }
  let n = 0;
  for (const k in obj) if (qstate[k] && typeof obj[k] === "string") {
    const un = obj[k].endsWith("?");
    qstate[k] = {sel: obj[k].replace(/\?$/, "").split(",").filter(x => x), ok: !un, unsure: false};
    n++;
  }
  for (const k in obj) if (state[k] && typeof obj[k] === "string") {
    const un = obj[k].endsWith("?");
    state[k] = {v: un ? obj[k].slice(0, -1) : obj[k], ok: !un, unsure: false, auto: false};
    n++;
  }
  save(); render();
  alert(n + " réponses importées (celles marquées « ? » restent à valider).");
  ev.target.value = "";
};
render();
</script>
</body>
</html>
"""
