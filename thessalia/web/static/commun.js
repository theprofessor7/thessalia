"use strict";
// Fonctions communes aux vues par question et par copie.
const LIBELLE = {juste: "✓ juste", forme: "½ forme", faux: "✗ faux", vide: "∅ vide", illisible: "? illisible"};
const TOUCHE = {"1": "juste", "2": "forme", "3": "faux", "4": "vide", "5": "illisible"};

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

// Pinceau (idée de l'enseignant, 23 octobre 2026) : une lecture prise sur une carte (🖌 ou touche P) s'applique
// aux vignettes cliquées, ou survolées bouton de la souris enfoncé ; Échap le repose. Même enregistrement qu'un
// clic sur une autre lecture (verdict recalculé) ; chaque carte reste visible et annulable (↺).
const PINCEAU = {valeur: null, appui: false, faites: new Set()};
function afficherPinceau() {
  let b = document.getElementById("bandeau-pinceau");
  if (!b) { b = el("div", {id: "bandeau-pinceau"}); document.body.append(b); }
  document.body.classList.toggle("pinceau-actif", PINCEAU.valeur != null);
  b.hidden = PINCEAU.valeur == null;
  b.textContent = PINCEAU.valeur == null ? "" : "🖌 pinceau : « " + PINCEAU.valeur
    + " » · cliquez ou glissez (bouton enfoncé) sur les vignettes · Échap pour reposer";
}
function prendrePinceau(v) { PINCEAU.valeur = v; PINCEAU.faites.clear(); afficherPinceau(); }
function poserPinceau() { PINCEAU.valeur = null; PINCEAU.appui = false; PINCEAU.faites.clear(); afficherPinceau(); }
document.addEventListener("keydown", ev => { if (ev.key === "Escape" && PINCEAU.valeur != null) poserPinceau(); });
document.addEventListener("mouseup", () => { PINCEAU.appui = false; PINCEAU.faites.clear(); });

// Carte d'une réponse : vignette, lecture, boutons de verdict (ou cases d'un QCM).
// surDecision(reponse_du_serveur) est appelé après chaque enregistrement.
function carte(it, surDecision, opts = {}) {
  const c = el("div", {className: "carte", tabIndex: 0});
  c.dataset.cle = it.classe + "/" + it.cle;
  const peindre = () => {
    c.classList.toggle("decide", !!it.decide);
    c.classList.toggle("a-decider", !it.decide);
  };
  // clavier = true : on passe à la réponse suivante (Entrée, 1 à 4) ; un clic de souris ne fait pas défiler
  const envoyer = async (corps, clavier = false) => {
    const rep = await decider(Object.assign({classe: it.classe, cle: it.cle}, corps));
    if (rep.item) Object.assign(it, rep.item);
    redessiner();
    surDecision(rep, c, clavier);
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
    if (it.code) {
      // code noté au barème : chaque clic enregistre (critères cochés = options) ; la note est leur somme
      if (it.raison) c.append(el("div", {className: "raison", textContent: "doute : " + it.raison}));
      if (it.transcription) c.append(el("pre", {className: "transcription", textContent: it.transcription}));
      // l'élève a pu écrire sous le cadre : la page entière, affichée à la demande
      if (it.page) {
        const vue = el("img", {className: "page-entiere", alt: "page entière", hidden: true});
        const b = el("button", {className: "lecture", tabIndex: -1, textContent: "voir la page"});
        b.onclick = ev => {
          ev.stopPropagation();
          if (!vue.src) vue.src = "/img/" + it.classe + "/" + it.page;
          vue.hidden = !vue.hidden;
          b.textContent = vue.hidden ? "voir la page" : "masquer la page";
          c.focus();
        };
        c.append(el("div", {}, b), vue);
      }
      const coches = new Set(it.choix || []);
      const enregistrer = (corps, clavier = false) => envoyer(corps, clavier).then(() => c.focus());
      const basculer = id => {
        const s = new Set(coches);
        s.has(id) ? s.delete(id) : s.add(id);
        enregistrer({options: [...s].sort()});
      };
      const liste = el("div", {className: "criteres"});
      it.criteres.forEach((cr, i) => {
        const b = el("button", {className: "critere" + (coches.has(cr.id) && it.verdict !== "vide" ? " on" : ""), tabIndex: -1,
                                title: "touche " + (i + 1)},
                     el("kbd", {textContent: String(i + 1)}), " " + cr.libelle + " ",
                     el("span", {className: "gris", textContent: "(" + fmt(cr.points) + ")"}));
        b.onclick = () => basculer(cr.id);
        liste.append(b);
      });
      if (it.malus) {
        const b = el("button", {className: "critere malus" + (coches.has(it.malus.id) ? " on" : ""), tabIndex: -1, title: "touche M"},
                     el("kbd", {textContent: "M"}), " " + it.malus.libelle + " ",
                     el("span", {className: "gris", textContent: "(" + fmt(it.malus.points) + ")"}));
        b.onclick = () => basculer(it.malus.id);
        liste.append(b);
      }
      c.append(liste);
      const tous = it.criteres.map(cr => cr.id);
      const juste = el("button", {className: "verdict juste", textContent: "✓ tout juste", tabIndex: -1, title: "J"});
      juste.onclick = () => enregistrer({options: tous});
      const vide = el("button", {className: "verdict vide" + (it.verdict === "vide" ? (it.decide ? " choisi" : " propose") : ""),
                                 textContent: LIBELLE.vide, tabIndex: -1, title: "V : rien d'écrit (0)"});
      vide.onclick = () => enregistrer({verdict: "vide", options: []});
      const zero = el("button", {className: "verdict faux", textContent: "✗ rien de juste", tabIndex: -1, title: "0 : écrit mais aucun critère (0)"});
      zero.onclick = () => enregistrer({options: []});
      const ligne = el("div", {className: "verdicts"}, juste, zero, vide);
      if (!it.decide) {
        const ok = el("button", {className: "verdict principal", tabIndex: -1, title: "Entrée",
                                 textContent: it.verdict === "vide" ? "✓ confirmer vide" : "✓ valider (" + fmt(it.points || 0) + ")"});
        ok.onclick = () => c.valider();
        ligne.prepend(ok);
      }
      if (it.origine === "enseignant") {
        const annul = el("button", {className: "verdict annuler", textContent: "↺", title: "annuler ma décision (Suppr)", tabIndex: -1});
        annul.onclick = () => envoyer({annuler: true});
        ligne.append(annul);
      }
      c.append(ligne);
      c.append(el("div", {className: "points", textContent: fmt(it.points || 0) + " / " + fmt(it.max) + " pt"}));
      c.valider = (clavier = false) => it.verdict === "vide" ? envoyer({verdict: "vide", options: []}, clavier)
                                                               : envoyer({options: [...coches].sort()}, clavier);
      c.basculer = basculer;
      c.toutJuste = () => enregistrer({options: tous});
      c.vide = () => enregistrer({verdict: "vide", options: []});
      c.zero = () => enregistrer({options: []});
    } else if (it.qcm) {
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
          // le clic enregistre directement (plus besoin de « valider ») ; q1 à plusieurs cases : chaque clic
          // enregistre l'état courant, le dernier fait foi
          it.choix = ch; envoyer({options: ch}).then(() => c.focus());
        };
        cases.append(b);
      }
      c.append(cases);
      c.append(el("div", {className: "attendu-carte"}, "attendu : ",
        el("code", {textContent: (it.attendu || []).join(", ") || "aucune case"}), el("span", {className: "gris", textContent: "  (✓ vert sur les bonnes cases)"})));
      if (it.options.some(o => o.state === "ambiguous"))
        c.append(el("div", {className: "legende", textContent: "orange : case douteuse, comptée seulement si vous la cochez"}));
      const ok = el("button", {className: "verdict principal",
                               textContent: it.verdict === "illisible" ? "✓ valider ces cases" : it.decide ? "✓ validé" : "✓ valider ces cases", tabIndex: -1});
      ok.onclick = () => envoyer({options: it.choix});
      // copie inutilisable pour ce QCM (page absente, cases illisibles) : 0 point
      const ill = el("button", {className: "verdict illisible" + (it.verdict === "illisible" ? " choisi" : ""),
                                textContent: LIBELLE.illisible, tabIndex: -1,
                                title: it.verdict === "illisible" ? "5 : annuler « illisible »" : "5 : impossible à lire (0 point)"});
      // second clic : annule (retour à la lecture de la machine, à décider)
      ill.onclick = () => envoyer(it.verdict === "illisible" ? {annuler: true} : {verdict: "illisible", options: []});
      c.append(el("div", {className: "verdicts"}, ok, ill,
        el("span", {className: "gris", textContent: "machine : " + (it.proposition.join(", ") || "aucune case")})));
      c.valider = (clavier = false) => envoyer({options: it.choix}, clavier);
    } else {
      // lecture (ce qui est écrit) : distincte de la note. « bien lu » / « corriger » sont facultatifs et
      // servent à apprendre au lecteur ; la note ne change que si aucun verdict n'a été choisi à la main.
      const lu = it.texte != null ? it.texte : it.proposition;
      const verifiee = it.texte != null;
      const ligneLu = el("div", {className: "lu"}, verifiee ? "écrit : " : "lu : ",
        el("code", {textContent: lu === null || lu === undefined ? "?" : (lu === "" ? "(vide)" : lu)}),
        verifiee ? el("span", {className: "verifie", textContent: " ✓ lecture vérifiée"}) : null,
        it.second != null ? el("span", {className: "gris", textContent: "  second lecteur : « " + it.second + " »"}) : null);
      if (lu != null && lu !== "") {
        const pb = el("button", {className: "lecture pinceau-btn", textContent: "🖌", tabIndex: -1,
                                 title: "prendre « " + lu + " » au pinceau (P), puis cliquer ou glisser sur les autres vignettes"});
        pb.onclick = ev => { ev.stopPropagation(); prendrePinceau(lu); };
        ligneLu.append(" ", pb);
      }
      if (!verifiee && it.proposition != null) {
        const bien = el("button", {className: "lecture", textContent: "✓ bien lu", tabIndex: -1,
                                   title: "la machine a lu exactement ce qui est écrit (L) : sert à l'apprentissage"});
        bien.onclick = () => envoyer({texte: it.proposition});
        ligneLu.append(" ", bien);
      }
      // faux négatif : la machine a mal lu une réponse qui est exactement le corrigé → lecture = attendu, note juste
      if (it.attendu != null && !(it.verdict === "juste" && (verifiee || it.decide))) {
        const att = el("button", {className: "lecture attendu-btn", textContent: "= attendu", tabIndex: -1,
                                  title: "l'étudiant a écrit exactement « " + it.attendu + " » : la machine a mal lu (A)"});
        att.onclick = () => envoyer({texte: it.attendu, verdict: "juste"});
        ligneLu.append(" ", att);
      }
      // autres lectures de la machine : un clic (ou 6, 7, 8) les prend comme lecture, le verdict est recalculé
      const alts = (!verifiee && it.alternatives) ? it.alternatives : [];
      let ligneAlt = null;
      if (alts.length) {
        ligneAlt = el("div", {className: "alternatives gris"}, "ou : ");
        alts.forEach((a, i) => {
          const b = el("button", {className: "lecture alt", tabIndex: -1,
                                  title: "l'étudiant a écrit « " + a + " » (" + (6 + i) + ")"},
                       el("code", {textContent: a}), el("span", {className: "gris", textContent: " " + (6 + i)}));
          b.onclick = () => envoyer({texte: a});
          ligneAlt.append(b, " ");
        });
      }
      c.alternatives = alts;
      const corr = el("button", {className: "lecture", textContent: "✎ corriger la lecture", tabIndex: -1,
                                 title: "taper ce qui est réellement écrit (T) : sert à l'apprentissage"});
      corr.onclick = () => saisir();
      ligneLu.append(" ", corr);
      c.append(ligneLu);
      if (ligneAlt) c.append(ligneAlt);
      if (it.attendu != null) c.append(el("div", {className: "attendu-carte"}, "attendu : ", el("code", {textContent: it.attendu})));
      const ligne = el("div", {className: "verdicts"});
      if (!it.decide && it.verdict) {
        const ok = el("button", {className: "verdict principal", textContent: "✓ valider", title: "confirmer le verdict proposé (Entrée)", tabIndex: -1});
        ok.onclick = () => envoyer({verdict: it.verdict});
        ligne.append(ok);
      }
      // vide et faux valent 0 tous les deux, mais ce sont deux constats différents : deux boutons distincts
      for (const v of ["juste", "forme", "faux", "vide", "illisible"]) {
        const actif = it.verdict === v;
        const b = el("button", {className: "verdict " + v + (actif ? (it.decide ? " choisi" : " propose") : ""),
                                textContent: LIBELLE[v], tabIndex: -1,
                                title: {juste: "1", forme: "2", faux: "3", vide: "4 : rien d'écrit", illisible: "5 : impossible à lire (0 point)"}[v]});
        b.onclick = () => envoyer({verdict: v});
        ligne.append(b);
      }
      if (it.origine === "enseignant") {
        const annul = el("button", {className: "verdict annuler", textContent: "↺", title: "annuler ma décision (Suppr)", tabIndex: -1});
        annul.onclick = () => envoyer({annuler: true});
        ligne.append(annul);
      }
      c.append(ligne);
      c.append(el("div", {className: "points gris", textContent: it.points == null ? "" : fmt(it.points) + " / " + fmt(it.max) + " pt"}));
      c.valider = (clavier = false) => it.verdict ? envoyer({verdict: it.verdict}, clavier) : saisir();
      c.attendu = it.attendu != null ? () => envoyer({texte: it.attendu, verdict: "juste"}) : null;
      c.bienLu = it.proposition != null ? () => envoyer({texte: it.proposition}) : null;
      c.vide = () => envoyer({verdict: "vide"});
      c.lu = lu;
      c.peindreAvec = v => envoyer({texte: v});
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
    if (ev.key === "Enter") { ev.preventDefault(); c.valider(true); }
    else if (it.code) {
      const k = ev.key.toLowerCase(), n = parseInt(ev.key, 10);
      if (n >= 1 && n <= it.criteres.length) { ev.preventDefault(); c.basculer(it.criteres[n - 1].id); }
      else if (k === "m" && it.malus) { ev.preventDefault(); c.basculer(it.malus.id); }
      else if (k === "j") { ev.preventDefault(); c.toutJuste(); }
      else if (k === "v") { ev.preventDefault(); c.vide(); }
      else if (ev.key === "0") { ev.preventDefault(); c.zero(); }
      else if (ev.key === "Delete" && it.origine === "enseignant") { ev.preventDefault(); envoyer({annuler: true}); }
      else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") { ev.preventDefault(); bouger(c, ev.key === "ArrowDown" ? 1 : -1); }
    }
    else if (it.qcm && ev.key === "5") {
      ev.preventDefault();
      if (it.verdict === "illisible") envoyer({annuler: true}); else envoyer({verdict: "illisible", options: []}, true);
    }
    else if (!it.qcm && TOUCHE[ev.key]) { ev.preventDefault(); envoyer({verdict: TOUCHE[ev.key]}, true); }
    else if (!it.qcm && (ev.key === "t" || ev.key === "T")) { ev.preventDefault(); saisir(); }
    else if (!it.qcm && (ev.key === "p" || ev.key === "P") && c.lu != null && c.lu !== "") { ev.preventDefault(); prendrePinceau(c.lu); }
    else if (!it.qcm && (ev.key === "l" || ev.key === "L") && it.proposition != null) { ev.preventDefault(); envoyer({texte: it.proposition}); }
    else if (!it.qcm && ["6", "7", "8"].includes(ev.key) && (c.alternatives || [])[+ev.key - 6] != null) {
      ev.preventDefault(); envoyer({texte: c.alternatives[+ev.key - 6]});
    }
    else if (!it.qcm && (ev.key === "a" || ev.key === "A") && it.attendu != null) { ev.preventDefault(); envoyer({texte: it.attendu, verdict: "juste"}, true); }
    else if (ev.key === "Delete" && it.origine === "enseignant") { ev.preventDefault(); envoyer({annuler: true}); }
    else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") { ev.preventDefault(); bouger(c, ev.key === "ArrowDown" ? 1 : -1); }
  });
  const appliquerPinceau = () => {
    if (PINCEAU.valeur == null || it.qcm || it.code || !c.peindreAvec || PINCEAU.faites.has(c)) return;
    PINCEAU.faites.add(c);
    c.classList.add("peinte");
    setTimeout(() => c.classList.remove("peinte"), 600);
    c.peindreAvec(PINCEAU.valeur);
  };
  c.addEventListener("mousedown", ev => {
    if (PINCEAU.valeur == null || ev.button !== 0 || ev.target.closest("button, a, input")) return;
    ev.preventDefault();
    PINCEAU.appui = true;
    appliquerPinceau();
  });
  c.addEventListener("mouseenter", () => { if (PINCEAU.appui) appliquerPinceau(); });
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
