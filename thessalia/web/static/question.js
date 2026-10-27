"use strict";
// Vue par question : réponses à décider groupées par proposition identique, réponses décidées repliées.
const D = JSON.parse(document.getElementById("donnees").textContent);
document.getElementById("attendu").textContent = D.attendu || "—";
document.getElementById("consigne").textContent = D.consigne || "";

const toutValider = document.getElementById("tout-valider");
toutValider.onclick = async () => {
  const cartes = [...document.querySelectorAll("#a-decider .carte.a-decider")];
  if (!cartes.length) return;
  if (!confirm("Valider les " + cartes.length + " propositions affichées telles quelles ?")) return;
  toutValider.disabled = true;
  for (const c of cartes) if (c.classList.contains("a-decider")) await c.valider();
  toutValider.disabled = false;
};

// prochaine question du groupe qui a encore des réponses à décider (après celle-ci, puis en reprenant au début)
const suivante = document.getElementById("suivante");
(() => {
  const qs = D.questions, i = qs.findIndex(q => q.champ === D.champ);
  const q = [...qs.slice(i + 1), ...qs.slice(0, i)].find(q => q.a_decider > 0);
  if (q) {
    suivante.href = "/g/" + D.groupe + "/q/" + q.champ;
    suivante.textContent = "Suivante à traiter → " + q.champ + " (" + q.a_decider + ")";
    suivante.hidden = false;
  } else {
    suivante.href = "/g/" + D.groupe + "/copies";
    suivante.textContent = "Groupe terminé → copies et notes";
    suivante.hidden = false;
  }
})();

// Mode banc d'essai : boutons « filtres » H / C / L (plusieurs à la fois) et « désaccords seulement ».
// Une carte est en désaccord quand les correcteurs affichés n'ont pas tous les mêmes critères (ou vide).
const BANC = {actifs: new Set(), desaccords: false};
function cleSource(v) { return v ? (v.verdict === "vide" ? "vide" : [...v.choix].sort().join("+")) : null; }
function majBanc() {
  if (!D.banc) return;
  for (const [k] of SOURCES_BANC) document.body.classList.toggle("voir-" + k, BANC.actifs.has(k));
  let n = 0;
  for (const c of document.querySelectorAll(".carte")) {
    if (!c.banc) continue;
    const cles = new Set([...BANC.actifs].map(k => cleSource(c.banc[k])).filter(x => x !== null));
    const diff = cles.size > 1;
    n += diff;
    c.classList.toggle("desaccord", diff);
    c.style.display = BANC.desaccords && !diff ? "none" : "";
  }
  const info = document.getElementById("banc-info");
  if (info) info.textContent = BANC.actifs.size > 1 ? n + " cadres en désaccord entre les correcteurs affichés" : "";
}
if (D.banc) {
  try { const s = JSON.parse(localStorage.getItem("banc") || "{}"); (s.actifs || []).forEach(k => BANC.actifs.add(k)); BANC.desaccords = !!s.desaccords; } catch (e) {}
  const garder = () => { try { localStorage.setItem("banc", JSON.stringify({actifs: [...BANC.actifs], desaccords: BANC.desaccords})); } catch (e) {} };
  const barre = el("div", {className: "banc-barre"}, el("span", {className: "gris", textContent: "Banc d'essai — voir les choix de :"}));
  for (const [k, l, t] of SOURCES_BANC) {
    const b = el("button", {className: "banc-btn src-" + k + (BANC.actifs.has(k) ? " actif" : ""), textContent: l + " · " + t});
    b.onclick = () => { BANC.actifs.has(k) ? BANC.actifs.delete(k) : BANC.actifs.add(k); b.classList.toggle("actif"); garder(); majBanc(); };
    barre.append(b);
  }
  const f = el("label", {className: "gris"}, el("input", {type: "checkbox", checked: BANC.desaccords}), " désaccords seulement");
  f.querySelector("input").onchange = ev => { BANC.desaccords = ev.target.checked; garder(); majBanc(); };
  barre.append(f, el("span", {id: "banc-info", className: "gris"}));
  document.getElementById("a-decider").before(barre);
}

function progres() {
  majBanc();
  const n = D.items.length, a = D.items.filter(i => !i.decide).length;
  suivante.classList.toggle("principal", !a);
  toutValider.textContent = a ? "Valider toutes les propositions (" + a + ")" : "Tout est validé";
  toutValider.disabled = !a;
  document.getElementById("progres").textContent = a ? a + " à décider sur " + n : "tout est décidé ✓";
  document.querySelector("#decidees summary").textContent = (n - a) + " réponses décidées (acceptées, vérité, deux lecteurs ou vous)";
}

function cleBloc(it) {
  // se groupent : les vides, et les cadres dont TOUS les critères sont vérifiés par les tests (un bloc à confirmer)
  if (it.code) return it.verdict === "vide" && !it.decide ? "code:vide"
    : !it.decide && !D.banc && it.tests && it.tests.complet ? "code:complet" : "code:" + it.cle;
  return it.qcm ? "qcm:" + it.choix.join(",") : (it.verdict || "?") + "|" + (it.proposition == null ? "?" : it.proposition);
}

function dessiner() {
  const zone = document.getElementById("a-decider"), dec = document.getElementById("liste-decidees");
  zone.textContent = ""; dec.textContent = "";
  const blocs = new Map();
  for (const it of D.items.filter(i => !i.decide)) {
    const k = cleBloc(it);
    if (!blocs.has(k)) blocs.set(k, []);
    blocs.get(k).push(it);
  }
  const ordre = [...blocs.values()].sort((a, b) => b.length - a.length);
  if (!ordre.length) zone.append(el("p", {className: "vide-ok", textContent: "Rien à décider pour cette question."}));
  for (const its of ordre) {
    const ex = its[0];
    const grille = el("div", {className: "grille" + (D.champ.startsWith("q7") || ex.qcm ? " large" : ex.code ? " code" : "")});
    const cartes = its.map(it => carte(it, (rep, c, clavier) => { progres(); if (clavier) suivanteADecider(c); }));
    grille.append(...cartes);
    const titre = ex.code ? (ex.verdict === "vide" ? "presque rien d'écrit → vide ?"
                             : cleBloc(ex) === "code:complet" ? "tous les critères vérifiés par les tests → note pleine ?"
                             : ex.origine === "tests" ? "pré-coché par les tests, à compléter" : "à noter")
      : ex.qcm ? "cases lues : " + (ex.choix.join(", ") || "aucune")
      : "lu « " + (ex.proposition == null ? "?" : ex.proposition === "" ? "(vide)" : ex.proposition) + " » → " + (LIBELLE[ex.verdict] || "?");
    const tete = el("div", {className: "bloc"}, el("span", {textContent: titre + " · " + its.length}));
    if (its.length > 1 && !ex.qcm && (ex.verdict || cleBloc(ex) === "code:complet")) {
      const b = el("button", {className: "bouton", textContent: "Confirmer le bloc (" + its.length + ")"});
      b.onclick = async () => {
        b.disabled = true;
        for (const c of cartes) if (c.classList.contains("a-decider")) await c.valider();
        b.textContent = "bloc confirmé";
      };
      tete.append(b);
    }
    // lecture exacte pour tout le bloc : autant d'exemples d'apprentissage en un clic
    if (its.length > 1 && !ex.qcm && ex.proposition != null) {
      const l = el("button", {className: "bouton", textContent: "bien lu pour le bloc (" + its.length + ")",
                              title: "la machine a lu exactement ce qui est écrit, pour toutes les réponses du bloc"});
      l.onclick = async () => {
        l.disabled = true;
        for (const c of cartes) if (c.bienLu) await c.bienLu();
        l.textContent = "bloc bien lu";
      };
      tete.append(l);
    }
    // faux négatif en série : la machine a mal lu la même chose (« 2427 ») alors que tous ont écrit le corrigé
    if (its.length > 1 && !ex.qcm && ex.attendu != null) {
      const a = el("button", {className: "bouton attendu-bloc", textContent: "= attendu pour le bloc (" + its.length + ")"});
      a.onclick = async () => {
        a.disabled = true;
        for (const c of cartes) if (c.attendu) await c.attendu();
        a.textContent = "bloc = attendu";
      };
      tete.append(a);
    }
    // zones « vides mais encre à proximité » : la machine ne propose rien, l'enseignant constate le vide.
    // Mesuré sur le Booster : 90 des 540 « vide » saisis à la main l'étaient ainsi, carte par carte.
    // Seulement sur un bloc SANS lecture : un bloc où quelque chose a été lu ne se vide pas d'un clic.
    if (its.length > 1 && !ex.qcm && !ex.code && (ex.proposition == null || ex.proposition === "")
        && ex.verdict !== "vide") {
      const v = el("button", {className: "bouton", textContent: "vide pour le bloc (" + its.length + ")",
                              title: "rien n'est écrit dans aucune de ces zones : 0 point, « vide »"});
      v.onclick = async () => {
        v.disabled = true;
        for (const c of cartes) if (c.classList.contains("a-decider") && c.vide) await c.vide();
        v.textContent = "bloc vide";
      };
      tete.append(v);
    }
    zone.append(tete, grille);
  }
  for (const it of D.items.filter(i => i.decide)) dec.append(carte(it, () => progres()));
  progres();
  const premiere = zone.querySelector(".carte");
  if (premiere) premiere.focus();
}
dessiner();
