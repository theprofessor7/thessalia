"""Transcription du code manuscrit par un service en ligne (OPTION : clé de l'utilisateur, plafond de dépense).

`python -m thessalia transcrire examens/<nom>/classes/<classe> --champ q12 [--limite 20]` envoie les cadres
de code (jamais l'identité : principe 3) à un modèle qui lit les images, et range la transcription dans
`<classe>/code_lectures.json`. L'outil de correction l'affiche sous l'image ; l'enseignant note toujours.

MODE LOCAL (gratuit, rien ne sort de la machine ; étape de la lecture approfondie, cf. `preparer`) : lit les
cadres avec un modèle de vision servi par Ollama sur ce PC (sans clé, sans dépense ; ~65 s par cadre sans GPU,
une centaine de copies tient en une nuit). Tous les champs du barème par défaut ; cadres presque vides
(encre < CODE_VIDE) sautés ; reprend après arrêt. Mesuré sur le BIS le 27 octobre (Qwen3-VL 8B) : 75 % de
ressemblance avec la transcription de session. L'ÉNONCÉ n'est pas donné au modèle local : il contient le
programme imprimé et le 8B répondait alors « (vide) ». Un champ `"nature": "texte"` du barème (explication en
phrase, q11.a) est lu comme du texte, pas comme du code. Ensuite : `code_tests` (critères par les tests).

Indépendant du fournisseur (décision de l'enseignant, 23 octobre) : deux adaptateurs légers.
  claude   API Anthropic (bibliothèque `anthropic`, extra `lecteur-claude`)
  openai   format « compatible OpenAI » (bibliothèque `openai`, extra `lecteur-openai`) : ChatGPT, Azure OpenAI /
           Foundry, DeepSeek, Mistral, modèles locaux (Ollama…) ; il suffit de régler `adresse`
Réglages : page « Réglages » de l'application, section « Service en ligne » (service, modèle, prix, plafond, clé),
enregistrés dans `data/lecteur.json` et `data/lecteur.cle` (hors dépôt) ; la variable d'environnement
(`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, ou celle nommée par `cle_variable`) prime sur le fichier. Sans clé, rien
n'est envoyé. Lancement : étape 4 d'un examen, « Transcrire le code par … », après une confirmation chiffrée
(`estimer`) ; ou `python -m thessalia transcrire` (tous les champs de code par défaut).

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

# Services proposés dans Réglages. Seul Claude a été mesuré (transcriptions de session) : les autres s'affichent
# « non mesuré », et leur modèle et leurs prix sont à saisir (ils changent souvent : on n'en invente pas).
SERVICES = {
    "claude": {"nom": "Claude (Anthropic)", "fournisseur": "claude", "adresse": None, "biblio": "anthropic",
               "paquet": "anthropic>=0.70", "modele": "claude-opus-5-5", "prix": (4.0, 20.0), "mesure": True,
               "console": "https://console.anthropic.com"},
    "chatgpt": {"nom": "ChatGPT (OpenAI)", "fournisseur": "openai", "adresse": None, "biblio": "openai",
                "paquet": "openai>=1.40", "modele": "", "prix": (0.0, 0.0), "mesure": False,
                "console": "https://platform.openai.com"},
    "mistral": {"nom": "Mistral", "fournisseur": "openai", "adresse": "https://api.mistral.ai/v1", "biblio": "openai",
                "paquet": "openai>=1.40", "modele": "", "prix": (0.0, 0.0), "mesure": False,
                "console": "https://console.mistral.ai"},
    "autre": {"nom": "Autre (compatible OpenAI)", "fournisseur": "openai", "adresse": "", "biblio": "openai",
              "paquet": "openai>=1.40", "modele": "", "prix": (0.0, 0.0), "mesure": False, "console": None},
}

DEFAUT = {
    "service": "claude",                # clé de SERVICES (choisi dans Réglages)
    "fournisseur": "claude",            # claude | openai (adaptateur, déduit du service)
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


OLLAMA = "http://localhost:11434"
CONSIGNE_LOCALE = CONSIGNE.replace("Énoncé de la question : {enonce}\n", "")
CONSIGNE_TEXTE = """Tu lis un cadre de réponse d'un examen, écrit à la main par un étudiant sur papier quadrillé.
L'étudiant y répond par une phrase en français (une explication), parfois avec un peu de code.
Transcris EXACTEMENT ce qui est écrit :
- garde ses fautes (orthographe, syntaxe) : ne corrige RIEN, ne complète rien ;
- ignore ce qui est barré ;
- un passage illisible : écris [?] à sa place ;
- si le cadre est vide, réponds seulement : (vide).
Réponds uniquement avec le texte transcrit, sans commentaire ni explication."""


def reglages():
    if not REGLAGES.exists():
        REGLAGES.parent.mkdir(parents=True, exist_ok=True)
        REGLAGES.write_text(json.dumps(DEFAUT, indent=2, ensure_ascii=False), encoding="utf-8")
    r = dict(DEFAUT)
    lu = load_json(REGLAGES)
    r.update(lu)
    if "service" not in lu:             # réglages d'avant le choix du service
        r["service"] = "claude" if r["fournisseur"] == "claude" else "autre"
    return r


def _variable(r):
    return r.get("cle_variable") or ("ANTHROPIC_API_KEY" if r["fournisseur"] == "claude" else "OPENAI_API_KEY")


def _cle_et_origine(r):
    import os
    var = _variable(r)
    if os.environ.get(var, "").strip():
        return os.environ[var].strip(), f"variable d'environnement {var}"
    if CLE_FICHIER.exists() and CLE_FICHIER.read_text(encoding="utf-8").strip():
        return CLE_FICHIER.read_text(encoding="utf-8").strip(), "enregistrée sur ce PC"
    return None, None


def _cle(r):
    cle, _ = _cle_et_origine(r)
    if cle:
        return cle
    raise SystemExit(f"Pas de clé : la coller dans Réglages (Service en ligne), ou définir la variable {_variable(r)}. "
                     f"La transcription est une option ; l'outil de correction marche sans.")


# ---------------------------------------------------------------- configuration depuis l'application (Réglages)
def _nombre(v, defaut):
    try:
        return max(0.0, float(str(v).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return defaut


def enregistrer(service=None, modele=None, adresse=None, plafond=None, prix_entree=None, prix_sortie=None):
    """Réglages du service en ligne. Un autre service choisi : ses valeurs par défaut remplacent modèle, adresse et
    prix (ceux d'un service non mesuré restent à saisir) ; le plafond est gardé."""
    r = reglages()
    if service in SERVICES and service != r["service"]:
        s = SERVICES[service]
        r.update(service=service, fournisseur=s["fournisseur"], modele=s["modele"], adresse=s["adresse"],
                 prix_entree_par_million=s["prix"][0], prix_sortie_par_million=s["prix"][1], cle_variable=None)
    else:
        if modele is not None:
            r["modele"] = modele.strip()
        if adresse is not None and r["service"] == "autre":
            r["adresse"] = adresse.strip()
        r["prix_entree_par_million"] = _nombre(prix_entree, r["prix_entree_par_million"])
        r["prix_sortie_par_million"] = _nombre(prix_sortie, r["prix_sortie_par_million"])
    r["plafond_dollars"] = _nombre(plafond, r["plafond_dollars"])
    REGLAGES.parent.mkdir(parents=True, exist_ok=True)
    REGLAGES.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    return r


def enregistrer_cle(texte):
    cle = (texte or "").strip()
    if len(cle) < 8 or any(c.isspace() for c in cle):
        raise ValueError("clé vide ou incomplète : la copier en entier, sans espace")
    CLE_FICHIER.parent.mkdir(parents=True, exist_ok=True)
    CLE_FICHIER.write_text(cle, encoding="utf-8")


def supprimer_cle():
    CLE_FICHIER.unlink(missing_ok=True)


def etat_en_ligne():
    """Ce que montrent Réglages et l'étape 4 : service, clé (masquée), prêt ou ce qui manque, dépense."""
    from importlib import invalidate_caches
    from importlib.util import find_spec
    invalidate_caches()
    r = reglages()
    s = SERVICES.get(r["service"], SERVICES["autre"])
    cle, origine = _cle_et_origine(r)
    biblio = find_spec(s["biblio"]) is not None
    manque = []
    if not biblio:
        manque.append("bibliothèque à installer")
    if not cle:
        manque.append("clé à coller")
    if not r["modele"]:
        manque.append("modèle à indiquer")
    if r["service"] == "autre" and not r.get("adresse"):
        manque.append("adresse du service à indiquer")
    if not (r["prix_entree_par_million"] > 0 and r["prix_sortie_par_million"] > 0):
        manque.append("prix à indiquer (sans eux, le plafond ne protège pas)")
    d = depense()
    return {"reglages": r, "cle_service": r["service"], "service": s, "services": SERVICES, "biblio": biblio,
            "origine": origine, "cle": ("…" + cle[-4:]) if cle else None,
            "cle_fichier": origine == "enregistrée sur ce PC", "manque": manque, "pret": not manque,
            "depense": d["total_dollars"], "appels": d["appels"],
            "reste": round(max(0.0, r["plafond_dollars"] - d["total_dollars"]), 2)}


def verifier_cle():
    """(acceptée, message) : la clé est-elle acceptée par le service ? Appel gratuit (liste des modèles)."""
    r = reglages()
    try:
        cle = _cle(r)
        if r["fournisseur"] == "claude":
            import anthropic
            noms = [m.id for m in anthropic.Anthropic(api_key=cle, timeout=30).models.list(limit=100)]
        else:
            import openai
            client = openai.OpenAI(api_key=cle, base_url=r.get("adresse") or None, timeout=30)
            noms = [m.id for m in client.models.list()]
    except SystemExit as e:
        return False, str(e)
    except ImportError:
        return False, "bibliothèque du service pas encore installée (bouton « Installer »)"
    except Exception as e:
        nom = type(e).__name__
        if "Authentication" in nom or "PermissionDenied" in nom:
            return False, "clé refusée par le service (copiée en entier ? bon service choisi ?)"
        if "Connection" in nom or "Timeout" in nom:
            return False, "service injoignable (connexion internet ? adresse du service ?)"
        return False, f"{nom} : {e}"[:300]
    if r["modele"] and noms and r["modele"] not in noms:
        return True, (f"clé acceptée, mais le modèle « {r['modele']} » n'est pas dans la liste du service : "
                      f"vérifier son nom")
    return True, "clé acceptée par le service"


def installer_biblio(log=print):
    import os
    import sys
    from .extensions import _executer
    s = SERVICES.get(reglages()["service"], SERVICES["autre"])
    env = dict(os.environ)
    tmp = Path(sys.prefix) / "tmp"           # comptes Windows de l'école : pas de « $ » dans TEMP (cf. installer.py)
    tmp.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
    log(f"Installation de la bibliothèque {s['biblio']}…")
    if _executer([sys.executable, "-m", "pip", "install", s["paquet"]], log, env):
        raise SystemExit("l'installation a échoué (connexion internet ? message ci-dessus)")
    log(f"Bibliothèque {s['biblio']} installée.")


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


def modeles_ollama():
    """Modèles installés dans Ollama sur ce PC, ou None si Ollama ne répond pas (pas installé, pas lancé)."""
    import urllib.request
    try:
        return [m["name"] for m in json.load(urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10))["models"]]
    except Exception:
        return None


class _Local:
    """Modèle de vision servi par Ollama sur cette machine (format compatible OpenAI, sans bibliothèque)."""

    def __init__(self, modele):
        import urllib.request
        self.urllib, self.modele = urllib.request, modele
        try:
            noms = [m["name"] for m in json.load(urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10))["models"]]
        except Exception:
            raise SystemExit(f"Ollama ne répond pas sur {OLLAMA} : l'installer (https://ollama.com) et le lancer.")
        if modele not in noms:
            raise SystemExit(f"Modèle « {modele} » absent d'Ollama : `ollama pull {modele}` "
                             f"(installés : {', '.join(noms) or 'aucun'}).")

    def lire(self, png_b64, consigne):
        corps = {"model": self.modele, "temperature": 0, "max_tokens": 700, "keep_alive": "10m",
                 "messages": [{"role": "user", "content": [
                     {"type": "text", "text": consigne},
                     {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png_b64}}]}]}
        req = self.urllib.Request(OLLAMA + "/v1/chat/completions", data=json.dumps(corps).encode(),
                                  headers={"Content-Type": "application/json"})
        rep = json.load(self.urllib.urlopen(req, timeout=3600))
        return rep["choices"][0]["message"]["content"] or ""

    def decharger(self):
        try:
            self.urllib.urlopen(self.urllib.Request(OLLAMA + "/api/generate", data=json.dumps(
                {"model": self.modele, "keep_alive": 0}).encode()), timeout=30)
        except Exception:
            pass


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
def run(dossiers, champs=None, limite=None, local=None, refaire=False):
    if local:
        return run_local(dossiers, champs, limite, local, refaire)
    return run_en_ligne(dossiers, champs, limite)      # sans --champ : tous les champs de code du barème


def _duree(secondes):
    """« 45 min », « 2 h 10 » : durée restante lisible."""
    m = max(1, round(secondes / 60))
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60:02d}"


def run_local(dossiers, champs, limite, modele, refaire=False):
    """Transcription par un modèle local (Ollama). `refaire` : relit aussi les cadres déjà transcrits par la
    machine (une transcription corrigée par l'enseignant est dans ses décisions et prime toujours)."""
    from .correction import CODE_VIDE, Classe, Decisions
    from .serve import _classes

    from . import avancement
    lec = _Local(modele)
    exams, faits, t0 = {}, 0, time.time()
    plans = []
    for d in _classes(dossiers):
        c = Classe(d, exams, Decisions())
        bar = c.exam.bareme.get("champs", {})
        sortie = d / LECTURES
        deja = load_json(sortie) if sortie.exists() else {}
        enc = c._encre()
        a_faire = []
        for cid in c.copy_ids:
            for fid in (champs or bar):
                cle = f"c{int(cid.split('_')[-1]):02d}_{fid}"
                info = c.doc(cid).get("fields", {}).get(fid) or {}
                e = enc.get(cid, {}).get(fid)
                if fid not in bar or not info.get("crop") or (e is not None and e < CODE_VIDE):
                    continue
                if cle in deja and not refaire:
                    continue
                a_faire.append((fid, cle, info))
        plans.append((d, bar, sortie, deja, a_faire, sum(1 for k in deja if k.startswith("c"))))
    # une seule jauge pour toutes les classes (elle ne repart pas de zéro à chaque classe)
    total = sum(len(p[4]) for p in plans)
    if total:
        avancement.attendre(f"transcription du code : {total} cadres, premier cadre en cours (chargement du modèle)…")
    try:
        for d, bar, sortie, deja, a_faire, avant in plans:
            print(f"{d.name} : {len(a_faire)} cadres à lire avec {modele} (local)"
                  + (f", {avant} déjà transcrits" if avant else ""), flush=True)
            for n, (fid, cle, info) in enumerate(a_faire, 1):
                if limite is not None and faits >= limite:
                    print(f"Limite atteinte ({limite} cadres).")
                    return
                png = _image_png(d / info["crop"].replace("\\", "/"), 1000)
                if png is None:
                    continue
                consigne = CONSIGNE_TEXTE if bar[fid].get("nature") == "texte" else CONSIGNE_LOCALE
                t1 = time.time()
                try:
                    texte = lec.lire(png, consigne)
                except Exception as e:      # une erreur n'arrête pas le lot ; elle est consignée
                    print(f"  {cle} : ÉCHEC ({type(e).__name__} : {e})", flush=True)
                    continue
                deja[cle] = {"code": _nettoyer(texte), "fournisseur": "local", "modele": modele,
                             "secondes": round(time.time() - t1)}
                sortie.write_text(json.dumps(deja, indent=1, ensure_ascii=False), encoding="utf-8")
                faits += 1
                v = (time.time() - t0) / faits
                avancement.signaler(faits, total, f"transcription du code : {faits}/{total} cadres ({d.name}) · "
                                    f"reste environ {_duree(v * (total - faits))}")
                print(f"  {n}/{len(a_faire)} {cle} ({time.time() - t1:.0f} s ; "
                      f"reste ~{v * (len(a_faire) - n) / 60:.0f} min)", flush=True)
    finally:
        lec.decharger()
    print(f"{faits} cadres transcrits en local.")


def a_transcrire(dossiers, champs=None):
    """Par classe : (dossier, classe, barème, fichier, transcriptions déjà là, cadres à envoyer). Tous les champs de
    code du barème par défaut ; sautés : cadres déjà transcrits (sur ce PC ou en ligne), presque vides (encre <
    CODE_VIDE), absents."""
    from .correction import CODE_VIDE, Classe, Decisions
    from .serve import _classes

    exams, plans = {}, []
    for d in _classes(dossiers):
        c = Classe(d, exams, Decisions())
        bar = c.exam.bareme.get("champs", {})
        sortie = d / LECTURES
        deja = load_json(sortie) if sortie.exists() else {}
        enc = c._encre()
        items = []
        for cid in c.copy_ids:
            doc = c.doc(cid)
            for fid in (champs or bar):
                cle = f"c{int(cid.split('_')[-1]):02d}_{fid}"
                info = doc.get("fields", {}).get(fid) or {}
                e = enc.get(cid, {}).get(fid)
                if fid not in bar or cle in deja or not info.get("crop") or (e is not None and e < CODE_VIDE):
                    continue
                items.append((fid, cle, info))
        plans.append((d, c, bar, sortie, deja, items))
    return plans


# ordre de grandeur des jetons d'un cadre : image ≈ largeur × hauteur / 750 (règle d'Anthropic, reprise pour les
# autres faute de mieux), consigne et énoncé ≈ 500, réponse ≈ 300
JETONS_TEXTE, JETONS_REPONSE = 500, 300


def estimer(dossiers):
    """Avant l'envoi : {cadres, cout (estimé), reste (plafond), cadres_possibles, service, modele}."""
    r = reglages()
    entree = sortie = n = 0
    for d, c, bar, f, deja, items in a_transcrire(dossiers):
        for fid, cle, info in items:
            im = cv2.imread(str(d / info["crop"].replace("\\", "/")), cv2.IMREAD_GRAYSCALE)
            if im is None:
                continue
            h, w = im.shape
            k = min(1.0, r["largeur_max"] / w)
            entree += w * k * h * k / 750 + JETONS_TEXTE
            sortie += JETONS_REPONSE
            n += 1
    cout = entree / 1e6 * r["prix_entree_par_million"] + sortie / 1e6 * r["prix_sortie_par_million"]
    reste = max(0.0, r["plafond_dollars"] - depense()["total_dollars"])
    par_cadre = cout / n if n else 0
    return {"cadres": n, "cout": round(cout, 2), "reste": round(reste, 2),
            "cadres_possibles": min(n, int(reste / par_cadre)) if par_cadre else n,
            "service": SERVICES.get(r["service"], SERVICES["autre"])["nom"], "modele": r["modele"]}


def run_en_ligne(dossiers, champs=None, limite=None):
    from . import avancement

    et = etat_en_ligne()
    if not et["pret"]:
        raise SystemExit("Service en ligne pas prêt (Réglages, « Service en ligne ») : " + ", ".join(et["manque"]) + ".")
    r = et["reglages"]
    if depense()["total_dollars"] >= r["plafond_dollars"]:
        raise SystemExit(f"Plafond atteint : {depense()['total_dollars']:.2f} $ dépensés sur "
                         f"{r['plafond_dollars']:.2f} $ (le relever dans Réglages si vous le décidez).")
    lec = lecteur(r)
    plans = a_transcrire(dossiers, champs)
    total = sum(len(p[-1]) for p in plans)
    faits, cout_lancement = 0, 0.0
    nom = et["service"]["nom"]
    if total:
        avancement.attendre(f"transcription du code par {nom} : {total} cadres…")
    for d, c, bar, sortie, deja, items in plans:
        print(f"{d.name} : {len(items)} cadres à envoyer à {nom} ({r['modele']})", flush=True)
        for fid, cle, info in items:
            if limite is not None and faits >= limite:
                print(f"Limite atteinte ({limite} cadres). Dépense de ce lancement : {cout_lancement:.3f} $.")
                return
            if depense()["total_dollars"] >= r["plafond_dollars"]:
                print(f"PLAFOND ATTEINT ({r['plafond_dollars']:.2f} $) : arrêt. Ce lancement : {cout_lancement:.3f} $.")
                return
            png = _image_png(d / info["crop"].replace("\\", "/"), r["largeur_max"])
            if png is None:
                continue
            if bar[fid].get("nature") == "texte":
                consigne = CONSIGNE_TEXTE
            else:
                num = c.exam.fields.get(fid, {}).get("question")
                enonce = next((q.get("prompt", "") for q in c.exam.template["questions"] if q["num"] == num), "")
                consigne = CONSIGNE.format(enonce=enonce)
            try:
                texte, ent, sor = lec.lire(png, consigne)
            except Exception as e:      # une erreur du service n'arrête pas le lot ; elle est consignée
                print(f"  {d.name} {cle} : ÉCHEC ({type(e).__name__} : {e})"[:300], flush=True)
                time.sleep(2)
                continue
            cout = _compter(r, ent, sor)
            cout_lancement += cout
            deja[cle] = {"code": _nettoyer(texte), "fournisseur": r["fournisseur"], "modele": r["modele"],
                         "jetons": [ent, sor], "cout": round(cout, 5)}
            sortie.write_text(json.dumps(deja, indent=1, ensure_ascii=False), encoding="utf-8")
            faits += 1
            avancement.signaler(faits, total, f"transcription du code : {faits}/{total} cadres ({d.name}) · "
                                              f"{cout_lancement:.2f} $")
    print(f"{faits} cadres transcrits, {cout_lancement:.3f} $ ce lancement, "
          f"{depense()['total_dollars']:.2f} $ cumulés sur {r['plafond_dollars']:.2f} $ autorisés.")
