"""Transcription du code manuscrit par un service en ligne (OPTION : clé de l'utilisateur, plafond de dépense).

`python -m thessalia transcrire sorties/booster --champ q12 [--limite 20]` envoie les cadres de code (jamais
l'identité : principe 3) à un modèle qui lit les images, et range la transcription dans
`<classe>/code_lectures.json`. L'outil de correction l'affiche sous l'image ; l'enseignant note toujours.

Indépendant du fournisseur (décision de l'enseignant, 23 octobre) : deux adaptateurs légers.
  claude   API Anthropic (bibliothèque `anthropic`, extra `lecteur-claude`)
  openai   format « compatible OpenAI » (bibliothèque `openai`, extra `lecteur-openai`) : ChatGPT, Azure OpenAI /
           Foundry, DeepSeek, Mistral, modèles locaux (Ollama…) ; il suffit de régler `adresse`
Réglages : `data/lecteur.json` (créé au premier lancement, hors dépôt). Clé : variable d'environnement
(`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, ou celle nommée par `cle_variable`), sinon le fichier `data/lecteur.cle`
(hors dépôt). Sans clé, rien n'est envoyé.

Dépense : chaque appel est compté (jetons réels renvoyés par le service × prix des réglages) dans
`data/lecteur_depenses.json` ; au-delà de `plafond_dollars` (cumulé), plus rien n'est envoyé. Le plafond du
compte chez le fournisseur reste la protection principale : le régler aussi.
"""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

import cv2

from .common import load_json

REGLAGES = Path("data/lecteur.json")
CLE_FICHIER = Path("data/lecteur.cle")
DEPENSES = Path("data/lecteur_depenses.json")
LECTURES = "code_lectures.json"

DEFAUT = {
    "fournisseur": "claude",            # claude | openai
    "modele": "claude-opus-5-5",
    "adresse": None,                    # openai seulement : ex. https://<nom>.openai.azure.com/openai/v1/
    "cle_variable": None,               # nom de la variable d'environnement de la clé (défaut selon le fournisseur)
    "plafond_dollars": 10.0,            # dépense cumulée maximale (tous lancements confondus)
    "prix_entree_par_million": 4.0,     # $ par million de jetons envoyés (Claude Opus 5.5 au 22 octobre 2026)
    "prix_sortie_par_million": 20.0,    # $ par million de jetons reçus
    "largeur_max": 1400,                # px : l'image est réduite au-delà (moins de jetons)
}

CONSIGNE = """Tu lis un cadre de réponse d'un examen de Python, écrit à la main par un étudiant sur papier quadrillé.
Énoncé de la question : {enonce}

Transcris EXACTEMENT le code écrit, ligne par ligne :
- garde les fautes de l'étudiant (syntaxe, noms, guillemets, deux-points oubliés) : ne corrige RIEN, ne complète rien ;
- reproduis l'indentation telle qu'elle est écrite (4 espaces par niveau) ;
- ignore ce qui est barré ;
- un passage illisible : écris [?] à sa place ;
- si le cadre est vide, réponds seulement : (vide).
Réponds uniquement avec le code, sans commentaire ni explication."""


class Plafond(Exception):
    pass


def reglages():
    if not REGLAGES.exists():
        REGLAGES.parent.mkdir(parents=True, exist_ok=True)
        REGLAGES.write_text(json.dumps(DEFAUT, indent=2, ensure_ascii=False), encoding="utf-8")
    r = dict(DEFAUT)
    r.update(load_json(REGLAGES))
    return r


def _cle(r):
    import os
    var = r.get("cle_variable") or ("ANTHROPIC_API_KEY" if r["fournisseur"] == "claude" else "OPENAI_API_KEY")
    if os.environ.get(var):
        return os.environ[var]
    if CLE_FICHIER.exists() and CLE_FICHIER.read_text(encoding="utf-8").strip():
        return CLE_FICHIER.read_text(encoding="utf-8").strip()
    raise SystemExit(f"Pas de clé : définir la variable {var} ou écrire la clé dans {CLE_FICHIER} (hors dépôt). "
                     f"La transcription est une option ; l'outil de correction marche sans.")


def depense():
    return load_json(DEPENSES) if DEPENSES.exists() else {"total_dollars": 0.0, "appels": 0}


def _compter(r, entree, sortie):
    d = depense()
    cout = entree / 1e6 * r["prix_entree_par_million"] + sortie / 1e6 * r["prix_sortie_par_million"]
    d["total_dollars"] = round(d["total_dollars"] + cout, 4)
    d["appels"] += 1
    DEPENSES.parent.mkdir(parents=True, exist_ok=True)
    DEPENSES.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return cout


def _image_png(path, largeur_max):
    im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    if im.shape[1] > largeur_max:
        k = largeur_max / im.shape[1]
        im = cv2.resize(im, (largeur_max, int(im.shape[0] * k)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", im)
    return base64.standard_b64encode(buf.tobytes()).decode("ascii") if ok else None


# ---------------------------------------------------------------- adaptateurs : (texte, jetons entrée, jetons sortie)
class _Claude:
    def __init__(self, r):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=_cle(r))
        self.modele = r["modele"]

    def lire(self, png_b64, consigne):
        # secours côté serveur en cas de refus du modèle (« fallbacks: default »)
        rep = self.client.beta.messages.create(
            model=self.modele, max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64}},
                {"type": "text", "text": consigne}]}])
        if rep.stop_reason == "refusal":
            raise RuntimeError("le modèle a refusé de transcrire ce cadre")
        texte = "".join(b.text for b in rep.content if b.type == "text")
        return texte, rep.usage.input_tokens, rep.usage.output_tokens


class _OpenAI:
    def __init__(self, r):
        import openai
        self.client = openai.OpenAI(api_key=_cle(r), base_url=r.get("adresse") or None)
        self.modele = r["modele"]

    def lire(self, png_b64, consigne):
        rep = self.client.chat.completions.create(
            model=self.modele, max_tokens=4000,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png_b64}},
                {"type": "text", "text": consigne}]}])
        u = rep.usage
        return rep.choices[0].message.content or "", getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0)


def lecteur(r):
    if r["fournisseur"] == "claude":
        return _Claude(r)
    if r["fournisseur"] == "openai":
        return _OpenAI(r)
    raise SystemExit(f"Fournisseur inconnu « {r['fournisseur']} » dans {REGLAGES} (claude ou openai).")


def _nettoyer(texte):
    t = texte.strip()
    m = re.search(r"```(?:python)?\n(.*?)```", t, re.S)
    return (m.group(1) if m else t).rstrip()


# ---------------------------------------------------------------- commande
def run(dossiers, champs, limite=None):
    from .correction import Classe, Decisions
    from .serve import _classes

    r = reglages()
    total = depense()["total_dollars"]
    if total >= r["plafond_dollars"]:
        raise SystemExit(f"Plafond atteint : {total:.2f} $ dépensés sur {r['plafond_dollars']:.2f} $ "
                         f"(relever plafond_dollars dans {REGLAGES} si vous le décidez).")
    lec = lecteur(r)
    exams, faits, cout_lancement = {}, 0, 0.0
    for d in _classes(dossiers):
        c = Classe(d, exams, Decisions())
        bar = c.exam.bareme.get("champs", {})
        sortie = d / LECTURES
        deja = load_json(sortie) if sortie.exists() else {}
        for cid in c.copy_ids:
            doc = c.doc(cid)
            for fid in champs:
                if fid not in bar:
                    continue
                cle = f"c{int(cid.split('_')[-1]):02d}_{fid}"
                info = doc.get("fields", {}).get(fid) or {}
                if cle in deja or not info.get("crop"):
                    continue
                if limite is not None and faits >= limite:
                    print(f"Limite atteinte ({limite} cadres). Dépense de ce lancement : {cout_lancement:.3f} $.")
                    return
                if depense()["total_dollars"] >= r["plafond_dollars"]:
                    print(f"PLAFOND ATTEINT ({r['plafond_dollars']:.2f} $) : arrêt. Ce lancement : {cout_lancement:.3f} $.")
                    return
                png = _image_png(d / info["crop"].replace("\\", "/"), r["largeur_max"])
                if png is None:
                    continue
                num = c.exam.fields.get(fid, {}).get("question")
                enonce = next((q.get("prompt", "") for q in c.exam.template["questions"] if q["num"] == num), "")
                try:
                    texte, ent, sor = lec.lire(png, CONSIGNE.format(enonce=enonce))
                except Exception as e:      # une erreur du service n'arrête pas le lot ; elle est consignée
                    print(f"  {d.name} {cle} : ÉCHEC ({type(e).__name__} : {e})")
                    time.sleep(2)
                    continue
                cout = _compter(r, ent, sor)
                cout_lancement += cout
                deja[cle] = {"code": _nettoyer(texte), "fournisseur": r["fournisseur"], "modele": r["modele"],
                             "jetons": [ent, sor], "cout": round(cout, 5)}
                sortie.write_text(json.dumps(deja, indent=1, ensure_ascii=False), encoding="utf-8")
                faits += 1
        if faits:
            print(f"  {d.name} : {sum(1 for k in deja if k.split('_', 1)[1] in champs)} cadres transcrits")
    print(f"{faits} cadres transcrits, {cout_lancement:.3f} $ ce lancement, "
          f"{depense()['total_dollars']:.2f} $ cumulés sur {r['plafond_dollars']:.2f} $ autorisés.")
