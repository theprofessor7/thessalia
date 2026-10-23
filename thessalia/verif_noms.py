"""Vérification des identités : le nom écrit sur chaque copie à côté de l'élève attribué.

`python -m thessalia verif-noms sorties/booster sorties/supA_1_v3 [-o sorties/notes/verif_identites.html]`

Second contrôle, sans service externe : l'enseignant (ou un collègue) parcourt la page et clique les lignes
où la vignette ne correspond pas. Les copies à risque passent en tête, avec la raison :
  - nom proche   l'élève attribué a un nom très proche d'un autre élève du groupe (DUBOIS / DUBOST) ;
  - proche d'un absent   l'élève attribué est à deux rangs ou moins d'un absent dans la liste du groupe,
                ou son nom commence par les deux mêmes lettres : une erreur de clic sur une ligne voisine
                laisse un présent « absent » (MERLIN / MESNIL : trois rangs, même début « ME ») ;
  - autre groupe   l'élève attribué n'est pas du groupe de la classe où la copie a été scannée.
Mesuré le 23 octobre 2026 sur 314 copies : les 3 erreurs d'attribution trouvées à la main sont toutes en tête.

La page contient des noms et des vignettes d'élèves : elle reste dans `sorties/` (hors dépôt), jamais partagée.
Le terminal n'affiche que des nombres.
"""
from __future__ import annotations

import html
import os
from difflib import SequenceMatcher
from pathlib import Path

from .correction import group_of
from .identite import _norm, lire_attributions, lire_liste

SEUIL_PROCHE = 0.75     # ressemblance de NOM au-delà de laquelle deux élèves d'un groupe sont « proches »
RANGS_ABSENT = 2        # distance (dans la liste triée du groupe) à un absent


def _nom(eleve):
    parts = eleve.split(" ")
    k = next((i for i, w in enumerate(parts) if not w.isupper()), len(parts))
    return " ".join(parts[:k]) or eleve


def risques(attributions, liste, seuil=SEUIL_PROCHE, rangs=RANGS_ABSENT):
    """attributions : [(classe, copie, élève)] ; liste : {groupe: [élèves]} -> {(classe, copie): [raisons]}."""
    groupe_de = {e: g for g, es in liste.items() for e in es}
    pris = {e for _, _, e in attributions}
    out = {}
    for cl, cid, e in attributions:
        raisons = []
        g = groupe_de.get(e)
        if g is None:
            raisons.append("élève absent de la liste")
        else:
            eleves = sorted(liste[g])
            proches = [x for x in eleves if x != e
                       and SequenceMatcher(None, _norm(_nom(e)), _norm(_nom(x))).ratio() >= seuil]
            if proches:
                raisons.append("nom proche de " + ", ".join(proches))
            i = eleves.index(e)
            debut = _norm(_nom(e))[:2]
            absents = [x for j, x in enumerate(eleves) if x not in pris
                       and (abs(j - i) <= rangs or _norm(_nom(x))[:2] == debut)]
            if absents:
                raisons.append("proche d'un absent : " + ", ".join(absents))
            if g != group_of(cl):
                raisons.append(f"élève du groupe {g}, copie scannée en {group_of(cl)}")
        out[(cl, cid)] = raisons
    return out


def _classes(dossiers):
    from .serve import _classes as cl
    return cl(dossiers)


def run(dossiers, sortie="sorties/notes/verif_identites.html", liste=None):
    liste = lire_liste(liste)
    out = Path(sortie)
    out.parent.mkdir(parents=True, exist_ok=True)
    attributions, dirs = [], {}
    for d in _classes(dossiers):
        dirs[d.name] = d
        for cid, e in sorted(lire_attributions(d.name).items()):
            attributions.append((d.name, cid, e))
    r = risques(attributions, liste)
    ordre = sorted(attributions, key=lambda a: (not r[(a[0], a[1])], a[0], a[1]))

    def img(cl, cid, z, cls=""):
        p = dirs[cl] / cid / "crops" / f"identity.{z}.png"
        if not p.exists():
            return '<span class="manque">(pas de vignette)</span>'
        return f'<img loading="lazy" class="{cls}" src="{html.escape(os.path.relpath(p, out.parent).replace(os.sep, "/"))}">'

    def page1(cl, cid):
        p = dirs[cl] / cid / "pages" / "p01_overlay.jpg"
        if not p.exists():
            return ""
        return f'<a href="{html.escape(os.path.relpath(p, out.parent).replace(os.sep, "/"))}" target="_blank">page 1</a>'

    rows = []
    for cl, cid, e in ordre:
        rs = r[(cl, cid)]
        rows.append(
            f'<tr class="{"risque" if rs else ""}" data-k="{cl} {cid} ({html.escape(e)})">'
            f'<td class="cl">{cl}<br>{cid.replace("copy_", "n° ")}<br>{page1(cl, cid)}</td>'
            f'<td>{img(cl, cid, "nom")}</td><td>{img(cl, cid, "prenom")}</td><td>{img(cl, cid, "numero", "petit")}</td>'
            f'<td><div class="el">{html.escape(e)}</div>'
            + "".join(f'<div class="raison">⚠ {html.escape(x)}</div>' for x in rs) + "</td></tr>")
    n_risque = sum(1 for a in attributions if r[(a[0], a[1])])
    out.write_text(f"""<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Vérification des identités</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px;background:#fff;color:#222}}
table{{border-collapse:collapse}}td{{border-bottom:1px solid #ddd;padding:4px 8px;vertical-align:middle}}
img{{height:56px}}img.petit{{height:40px}}.cl{{font-size:12px;color:#666;white-space:nowrap}}
.el{{font-size:18px;font-weight:600}}.raison{{font-size:13px;color:#a05a00}}
tr{{cursor:pointer}}tr.risque td:first-child{{border-left:4px solid #e0a000}}tr.faux{{background:#fdd}}
.manque{{color:#a00}}#bilan{{position:sticky;top:0;background:#ffe;border:1px solid #cc9;padding:8px;margin-bottom:8px}}</style>
<div id="bilan"><b>{len(attributions)} copies, dont {n_risque} à risque (en tête, ⚠).</b>
Lire chaque ligne : le nom écrit doit être celui de l'élève attribué. Une case vide : ouvrir « page 1 »
(certains écrivent leur nom dans l'en-tête). Cliquer une ligne fausse (re-cliquer pour annuler).
<div>Signalées : <span id="liste">aucune</span></div></div>
<table>{"".join(rows)}</table>
<script>const L=document.getElementById('liste');
document.querySelectorAll('tr').forEach(t=>t.onclick=ev=>{{if(ev.target.tagName==='A')return;t.classList.toggle('faux');
const s=[...document.querySelectorAll('tr.faux')].map(x=>x.dataset.k);L.textContent=s.length?s.join(' ; '):'aucune';}});</script>
</html>""", encoding="utf-8")
    print(f"{len(attributions)} copies, dont {n_risque} à risque en tête de page -> {out}")
    return out
