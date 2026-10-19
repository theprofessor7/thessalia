"use strict";
// Fonctions communes aux vues par question et par copie.
const LIBELLE = {juste: "✓ juste", forme: "½ forme", faux: "✗ faux", vide: "∅ vide"};
const TOUCHE = {"1": "juste", "2": "forme", "3": "faux", "4": "vide"};

function el(tag, props, ...kids) {
  const e = Object.assign(document.createElement(tag), props || {});
  for (const k of kids) if (k !== null && k !== undefined) e.append(k);
  return e;
}

async function decider(corps) {
  const r = await fetch("/api/decision", {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify(corps)});
  if (!r.ok) { alert("Décision non enregistrée (" + r.status + ")."); throw new Error(r.status); }
  return r.json();
}

function fmt(x) { return (Math.round(x * 100) / 100).toString().replace(".", ","); }

// Carte d'une réponse : vignette, lecture, boutons de verdict (ou cases d'un QCM).
// surDecision(reponse_du_serveur) est appelé après chaque enregistrement.
function carte(it, surDecision, opts = {}) {
  const c = el("div", {className: "carte", tabIndex: 0});
  c.dataset.cle = it.classe + "/" + it.cle;
  const peindre = () => {
    c.classList.toggle("decide", !!it.decide);
    c.classList.toggle("a-decider", !it.decide);
  };
  const envoyer = async corps => {
    const rep = await decider(Object.assign({classe: it.classe, cle: it.cle}, corps));
    if (rep.item) Object.assign(it, rep.item);
    redessiner();
    surDecision(rep, c);
  };
  const redessiner = () => {
    c.textContent = "";
    const titre = el("div", {className: "haut"},
      opts.lienCopie === false ? el("span", {textContent: it.champ}) :
        el("a", {href: "/c/" + it.classe + "/" + it.copie, textContent: it.classe + " · copie " + it.num, tabIndex: -1}),
      el("span", {className: "origine " + (it.origine || "").replace(/\s|\?/g, ""),
                  textContent: it.origine + (it.historique && (it.origine === "mémoire" || it.origine === "proposé")
                    ? (it.origine === "mémoire" ? " (" : " · vous : " + it.historique.verdict + " ") + it.historique.n + "/" + it.historique.total + (it.origine === "mémoire" ? ")" : "")
                    : ""),
                  title: it.historique ? "dans les autres classes, vous avez jugé cette lecture « " + it.historique.verdict + " » "
                    + it.historique.n + " fois sur " + it.historique.total : ""}));
    c.append(titre);
    if (it.img) c.append(el("img", {src: "/img/" + it.classe + "/" + it.img, loading: "lazy", alt: it.cle}));
    else c.append(el("div", {className: "manque", textContent: "pas d'image (page absente du scan ?) : voir la copie papier"}));
    if (it.qcm) {
      if (it.raison) c.append(el("div", {className: "raison", textContent: "doute : " + it.raison}));
      const cases = el("div", {className: "options"});
      for (const o of it.options) {
        const on = it.choix.includes(o.id), bon = (it.attendu || []).includes(o.id);
        const b = el("button", {className: "option" + (on ? " on" : "") + (o.state === "ambiguous" ? " amb" : ""),
                                tabIndex: -1, title: "lecture machine : " + o.state + (bon ? " · bonne réponse" : "")},
                     o.id === o.label ? o.id : o.id + " " + o.label,
                     bon ? el("span", {className: "bon", textContent: " ✓"}) : null);
        b.onclick = () => {
          let ch = it.choix.slice();
          if (ch.includes(o.id)) ch = ch.filter(x => x !== o.id);
          else ch = it.mode === "single" ? [o.id] : [...ch, o.id].sort();
          it.choix = ch; it.decide = false; redessiner(); c.focus();
        };
        cases.append(b);
      }
      c.append(cases);
      c.append(el("div", {className: "attendu-carte"}, "attendu : ",
        el("code", {textContent: (it.attendu || []).join(", ") || "aucune case"}), el("span", {className: "gris", textContent: "  (✓ vert sur les bonnes cases)"})));
      if (it.options.some(o => o.state === "ambiguous"))
        c.append(el("div", {className: "legende", textContent: "orange : case douteuse, comptée seulement si vous la cochez"}));
      const ok = el("button", {className: "verdict principal", textContent: it.decide ? "✓ validé" : "✓ valider ces cases", tabIndex: -1});
      ok.onclick = () => envoyer({options: it.choix});
      c.append(el("div", {className: "verdicts"}, ok,
        el("span", {className: "gris", textContent: "machine : " + (it.proposition.join(", ") || "aucune case")})));
      c.valider = () => envoyer({options: it.choix});
    } else {
      const lu = it.texte != null ? it.texte : it.proposition;
      c.append(el("div", {className: "lu"}, it.texte != null ? "écrit : " : "lu : ",
        el("code", {textContent: lu === null || lu === undefined ? "?" : (lu === "" ? "(vide)" : lu)}),
        it.second != null ? el("span", {className: "gris", textContent: "  second lecteur : « " + it.second + " »"}) : null));
      if (it.attendu != null) c.append(el("div", {className: "attendu-carte"}, "attendu : ", el("code", {textContent: it.attendu})));
      const ligne = el("div", {className: "verdicts"});
      if (!it.decide && it.verdict) {
        const ok = el("button", {className: "verdict principal", textContent: "✓ valider", title: "confirmer le verdict proposé (Entrée)", tabIndex: -1});
        ok.onclick = () => envoyer({verdict: it.verdict});
        ligne.append(ok);
      }
      // vide et faux valent 0 tous les deux, mais ce sont deux constats différents : deux boutons distincts
      for (const v of ["juste", "forme", "faux", "vide"]) {
        const actif = it.verdict === v;
        const b = el("button", {className: "verdict " + v + (actif ? (it.decide ? " choisi" : " propose") : ""),
                                textContent: LIBELLE[v], tabIndex: -1,
                                title: {juste: "1", forme: "2", faux: "3", vide: "4 : rien d'écrit"}[v]});
        b.onclick = () => envoyer({verdict: v});
        ligne.append(b);
      }
      const stylo = el("button", {className: "verdict texte", textContent: "✎", title: "taper ce qui est écrit (T)", tabIndex: -1});
      stylo.onclick = () => saisir();
      ligne.append(stylo);
      if (it.origine === "enseignant") {
        const annul = el("button", {className: "verdict annuler", textContent: "↺", title: "annuler ma décision (Suppr)", tabIndex: -1});
        annul.onclick = () => envoyer({annuler: true});
        ligne.append(annul);
      }
      c.append(ligne);
      c.append(el("div", {className: "points gris", textContent: it.points == null ? "" : fmt(it.points) + " / " + fmt(it.max) + " pt"}));
      c.valider = () => it.verdict ? envoyer({verdict: it.verdict}) : saisir();
    }
    peindre();
  };
  const saisir = () => {
    const champ = el("input", {type: "text", value: it.texte != null ? it.texte : (it.proposition || ""),
                               placeholder: "ce que l'étudiant a écrit", spellcheck: false});
    const zone = el("div", {className: "saisie"}, champ, el("span", {className: "gris", textContent: " Entrée : enregistrer · Échap : annuler"}));
    c.append(zone); champ.focus(); champ.select();
    champ.onkeydown = ev => {
      ev.stopPropagation();
      if (ev.key === "Enter") { ev.preventDefault(); envoyer({texte: champ.value.trim()}); }
      else if (ev.key === "Escape") { zone.remove(); c.focus(); }
    };
  };
  c.addEventListener("keydown", ev => {
    if (ev.target !== c) return;
    if (ev.key === "Enter") { ev.preventDefault(); c.valider(); }
    else if (!it.qcm && TOUCHE[ev.key]) { ev.preventDefault(); envoyer({verdict: TOUCHE[ev.key]}); }
    else if (!it.qcm && (ev.key === "t" || ev.key === "T")) { ev.preventDefault(); saisir(); }
    else if (ev.key === "Delete" && it.origine === "enseignant") { ev.preventDefault(); envoyer({annuler: true}); }
    else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") { ev.preventDefault(); bouger(c, ev.key === "ArrowDown" ? 1 : -1); }
  });
  redessiner();
  return c;
}

// retour arrière du navigateur : la page vient du cache, on la recharge pour voir les décisions récentes
window.addEventListener("pageshow", ev => { if (ev.persisted) location.reload(); });

function bouger(depuis, sens) {
  const toutes = [...document.querySelectorAll(".carte")].filter(x => x.offsetParent !== null);
  const i = toutes.indexOf(depuis);
  const n = toutes[i + sens];
  if (n) { n.focus(); n.scrollIntoView({block: "nearest"}); }
}

function suivanteADecider(depuis) {
  const toutes = [...document.querySelectorAll(".carte")].filter(x => x.offsetParent !== null);
  const i = toutes.indexOf(depuis);
  const n = toutes.slice(i + 1).find(x => x.classList.contains("a-decider")) || toutes[i + 1];
  if (n) { n.focus(); n.scrollIntoView({block: "nearest", behavior: "smooth"}); }
}
