"""Préparation d'une classe la veille de la correction, sans Claude : `python -m thessalia preparer sorties/<classe>`.

Enchaîne, sur ce PC (Ollama, aucun envoi), un modèle à la fois (16 Go suffisent) :
  1. `transcrire --local`  : code manuscrit lu par Qwen3-VL 8B (~1 min par cadre) ;
  2. `precocher`           : critères pré-cochés par les tests (corrigé du barème), réparateur Qwen3 14B contrôlé ;
  3. `second-lecteur`      : réponses courtes en revue relues par Qwen3-VL 4B (~30 s par réponse).
Chaque étape reprend où elle s'était arrêtée : relancer la même commande après une coupure.
Une centaine de copies tient en une nuit. Ensuite : `serve`, puis `code-bilan` après la correction.

Modèles absents (PC d'un collègue) : vérifiés AVANT de commencer ; l'outil marche sans eux, en moins aidé.
  - pas de lecteur du code : pas de transcription (pré-cochage seulement sur les transcriptions déjà là) ;
  - pas de réparateur : pré-cochage par les règles seules (mesuré : moins de critères, toujours 0 à tort) ;
  - pas de second lecteur : réponses courtes en revue comme avant.
Les modèles ne sont pas fournis avec Thessalia (3 à 9 Go chacun) : `ollama pull <modèle>` une fois, ou copie du
dossier des modèles d'Ollama depuis un partage interne (PC sans internet).
"""
from __future__ import annotations

import time


def run(dossiers, vision="qwen3-vl:8b-instruct", reparateur="qwen3:14b", second="qwen3-vl:4b-instruct",
        sans_code=False, sans_courtes=False, essai=False):
    """essai=True : réponses courtes « en revue » d'après la base d'essai (copie d'une classe déjà corrigée)."""
    from .code_tests import run as precocher
    from .lecteur_code import modeles_ollama, run_local
    from .second_lecteur import run as relire

    dispo = modeles_ollama()
    if dispo is None:
        print("Ollama ne répond pas (pas installé ou pas lancé : https://ollama.com). Sans modèle local, seul le "
              "pré-cochage par les règles tourne, sur les transcriptions déjà présentes.")
        dispo = []
    manque = [m for m, utile in ((vision, not sans_code), (reparateur, not sans_code), (second, not sans_courtes))
              if utile and m not in dispo]
    for m in manque:
        print(f"  modèle absent : {m}  →  pour l'installer : ollama pull {m}")
    t0 = time.time()
    etapes = []
    if not sans_code:
        if vision in dispo:
            etapes.append(("transcription du code", lambda: run_local(dossiers, None, None, vision)))
        else:
            print("  → transcription du code sautée")
        rep = reparateur if reparateur in dispo else None
        if rep is None:
            print("  → pré-cochage par les règles seules (sans réparateur)")
        etapes.append(("pré-cochage par les tests", lambda: precocher(dossiers, rep)))
    if not sans_courtes:
        if second in dispo:
            etapes.append(("second lecteur des réponses courtes", lambda: relire(dossiers, second, essai=essai)))
        else:
            print("  → second lecteur sauté")
    for i, (nom, f) in enumerate(etapes, 1):
        print(f"\n=== {i}/{len(etapes)} {nom} ({(time.time() - t0) / 60:.0f} min écoulées)", flush=True)
        try:
            f()
        except SystemExit as e:          # une étape impossible n'empêche pas les suivantes
            print(f"  étape arrêtée : {e}")
    print(f"\nPréparation terminée en {(time.time() - t0) / 60:.0f} min. Ensuite : python -m thessalia serve "
          + " ".join(map(str, dossiers)))
