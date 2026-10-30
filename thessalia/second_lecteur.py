"""Second lecteur LOCAL des réponses courtes : `python -m thessalia second-lecteur sorties/<classe> [--modele …]`.

Un modèle de vision servi par Ollama sur ce PC (Qwen3-VL 4B par défaut : gratuit, rien ne sort de la machine) relit
les réponses courtes EN REVUE. Le résultat va dans `<classe>/lectures_secondaires.json`, déjà lu par l'outil de
correction :
  - « second lecteur : « … » » est affiché sous la proposition (indice pour l'enseignant) ;
  - si la lecture est SÛRE, la réponse est décidée « deux lecteurs » (cf. `correction.short_items`).

Sûre = Qwen lit EXACTEMENT ce que TrOCR a lu (première lecture brute, après le nettoyage de la notation). Jamais
pour un nombre décimal (règle : un décimal part toujours en revue, l'enseignant le juge), ni pour une réponse vide,
ni quand un espace compte (sortie d'un programme, q7 : l'enseignant juge les espaces sur la vignette).
Mesuré sur le BIS le 26 octobre (247 réponses vérifiées, vignette brute, ~32 s par vignette) : TrOCR v2 et Qwen
d'accord sur 92 réponses, 3 fausses, qui étaient toutes des erreurs de saisie de l'enseignant (0 après
correction). Sujet A (supD_2, 28 octobre) : 135 décidées, 11 fausses, toutes sur q7 (espaces) ; 0 sans q7.
Reprend après arrêt ; `--refaire` relit tout ; `--essai` : réponses en revue d'après la base d'essai.
"""
from __future__ import annotations

import base64
import json
import re
import time

from .correction import SECOND, mise_en_forme

MODELE = "qwen3-vl:4b-instruct"
CONSIGNE = ("Cette image montre la réponse manuscrite d'un étudiant à un examen de Python, écrite sur une ligne. "
            "Transcris EXACTEMENT ce qui est écrit, caractère par caractère, sans corriger les fautes, sans rien "
            "ajouter (garde virgule ou point tels quels). Ignore le texte imprimé et ce qui dépasse des lignes voisines. "
            "Réponds uniquement par la transcription. Si rien n'est écrit, réponds (vide).")
DECIMAL = re.compile(r"\d\s*[.,]\s*\d")


def sur(c, it, brut, lecture):
    """La lecture du second lecteur confirme-t-elle la première lecture brute de TrOCR ?"""
    if brut is None or not lecture or lecture.strip().lower() in ("(vide)", "vide"):
        return False
    if DECIMAL.search(str(brut)) or DECIMAL.search(lecture):
        return False
    if mise_en_forme(it.get("attendu"), brut, lecture):          # espaces : jugés sur la vignette
        return False
    a, b = c.exam.clean(str(brut), it["champ"]), c.exam.clean(lecture, it["champ"])
    return bool(a) and a == b


def run(dossiers, modele=MODELE, refaire=False, limite=None, essai=False):
    from .correction import Classe, Decisions, Memory
    from .lecteur_code import _Local
    from .serve import ESSAI_DB, _classes

    lec = _Local(modele)
    exams, faits, t0 = {}, 0, time.time()
    try:
        for d in _classes(dossiers):
            c = Classe(d, exams, Decisions(ESSAI_DB) if essai else Decisions(), memory=Memory())
            p = d / SECOND
            deja = json.loads(p.read_text(encoding="utf-8")) if p.exists() and not refaire else {}
            todo = [it for it in c.short_items(use_memory=False)
                    if it["lecture"] == "review" and it["origine"] not in ("enseignant", "vérité")
                    and it["img"] and it["cle"] not in deja]
            print(f"{d.name} : {len(todo)} réponses en revue à relire avec {modele} (local)", flush=True)
            n_sur = 0
            for n, it in enumerate(todo, 1):
                if limite is not None and faits >= limite:
                    print(f"Limite atteinte ({limite} réponses).")
                    return
                img = d / it["img"]
                if not img.exists():
                    continue
                png = base64.b64encode(img.read_bytes()).decode()
                try:
                    lu = lec.lire(png, CONSIGNE).strip()
                except Exception as e:      # une erreur n'arrête pas le lot ; elle est consignée
                    print(f"  {it['cle']} : ÉCHEC ({type(e).__name__} : {e})", flush=True)
                    continue
                o = (c.doc(it["copie"]).get("fields", {}).get(it["champ"], {}).get("ocr") or {})
                brut = ((o.get("candidates") or [[None]])[0] or [None])[0]
                s = sur(c, it, brut, lu)
                n_sur += s
                deja[it["cle"]] = {"lecture": "" if lu.lower() in ("(vide)", "vide") else lu, "sur": s,
                                   "lecteur": modele, "trocr": brut}
                p.write_text(json.dumps(deja, ensure_ascii=False, indent=1), encoding="utf-8")
                faits += 1
                if n % 5 == 0 or n == len(todo):
                    v = (time.time() - t0) / faits
                    print(f"  {n}/{len(todo)} ({v:.0f} s par réponse, {n_sur} confirmées ; "
                          f"reste ~{v * (len(todo) - n) / 60:.0f} min)", flush=True)
            print(f"{d.name} : {n_sur} réponses confirmées par les deux lecteurs (décidées « deux lecteurs »)")
    finally:
        lec.decharger()
