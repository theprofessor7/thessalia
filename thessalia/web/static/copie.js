"use strict";
// Vue par copie : pages de la copie avec chaque réponse encadrée de la couleur de son verdict,
// liste des réponses à droite, note recalculée à chaque décision.
const D = JSON.parse(document.getElementById("donnees").textContent);
const pages = document.getElementById("pages"), liste = document.getElementById("liste");
const cadres = {};   // cle -> [éléments cadre sur la page]

function couleur(it) {
  if (!it.decide) return "doute";
  if (it.qcm) return "qcm";
  return it.verdict === "juste" ? "juste" : it.verdict === "forme" ? "forme" : "faux";
}

function note(n) {
  const z = document.getElementById("note");
  z.textContent = "";
  z.append(el("div", {className: "grand"}, fmt(n.total), el("span", {textContent: " / " + fmt(n.max)})),
           el("div", {className: "gris", textContent: "QCM " + fmt(n.qcm) + " · réponses courtes " + fmt(n.courtes)}),
           el("div", {className: n.etat === "complète" ? "ok" : "attente",
                      textContent: n.etat === "complète" ? "note complète" : n.en_attente + " à décider (note si l'on accepte tout : " + fmt(n.provisoire) + ")"}),
           el("div", {className: "gris", textContent: D.note.etudiant}));
}

function peindreCadres(it) {
  for (const b of cadres[it.cle] || []) b.className = "cadre " + couleur(it);
}

function dessinerPages() {
  for (const p of D.pages) {
    const boite = el("div", {className: "page"});
    const img = el("img", {src: "/img/" + D.classe + "/" + p.img, alt: "page " + p.page});
    boite.append(img, el("div", {className: "num", textContent: "page " + p.page}));
    img.onload = () => {
      const W = img.naturalWidth, H = img.naturalHeight;
      for (const it of D.items.filter(i => i.page === p.page && i.box)) {
        const [x0, y0, x1, y1] = it.box.map(v => v * D.echelle);
        const b = el("div", {className: "cadre " + couleur(it), title: it.champ});
        Object.assign(b.style, {left: (100 * x0 / W) + "%", top: (100 * y0 / H) + "%",
                                width: (100 * (x1 - x0) / W) + "%", height: (100 * (y1 - y0) / H) + "%"});
        b.onclick = () => {
          const c = liste.querySelector(`[data-cle="${CSS.escape(it.classe + "/" + it.cle)}"]`);
          if (c) { c.scrollIntoView({block: "center"}); c.focus(); }
        };
        (cadres[it.cle] = cadres[it.cle] || []).push(b);
        boite.append(b);
      }
    };
    pages.append(boite);
  }
}

function dessinerListe() {
  liste.textContent = "";
  const seul = document.getElementById("seulement").checked;
  const its = D.items.slice().sort((a, b) => (a.page || 0) - (b.page || 0) ||
    a.champ.localeCompare(b.champ, undefined, {numeric: true}));
  for (const it of its) {
    if (seul && it.decide) continue;
    const c = carte(it, (rep, carteEl, clavier) => {
      if (rep.note) note(rep.note);
      peindreCadres(it);
      if (clavier) suivanteADecider(carteEl);
    }, {lienCopie: false});
    c.addEventListener("focus", () => {
      for (const b of document.querySelectorAll(".cadre.actif")) b.classList.remove("actif");
      for (const b of cadres[it.cle] || []) { b.classList.add("actif"); b.scrollIntoView({block: "center", behavior: "smooth"}); }
    });
    liste.append(c);
  }
  const p = liste.querySelector(".carte.a-decider") || liste.querySelector(".carte");
  if (p) p.focus({preventScroll: true});
}

document.getElementById("seulement").onchange = dessinerListe;
document.addEventListener("keydown", ev => {
  if (ev.target.tagName === "INPUT") return;
  if (ev.key === "n" || ev.key === "N") { const a = document.getElementById("suiv"); if (a) location = a.href; }
  if (ev.key === "p" || ev.key === "P") { const a = document.getElementById("prec"); if (a) location = a.href; }
});
note(D.note);
dessinerPages();
dessinerListe();
