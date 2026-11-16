"""Lecture approfondie des classes d'un examen, sans Claude (bouton de la page de l'examen, cf. `Projet.preparer`).

Enchaîne, sur ce PC (Ollama, aucun envoi), un modèle à la fois (16 Go suffisent) :
  1. transcription    : code manuscrit lu par Qwen3-VL 8B (~1 min par cadre) ;
  2. pré-cochage      : critères pré-cochés par les tests (corrigé du barème), réparateur Qwen3 14B contrôlé ;
  3. second lecteur   : réponses courtes en revue relues par Qwen3-VL 4B (~30 s par réponse).
Chaque étape reprend où elle s'était arrêtée : relancer après une coupure. Une centaine de copies tient en une nuit.

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
        sans_code=False, sans_courtes=False, sans_reparateur=False):
    """sans_reparateur + sans_courtes : lecture rapide (transcription du code et pré-cochage par les règles)."""
    from .code_tests import run as precocher
    from .lecteur_code import modeles_ollama, run_local
    from .second_lecteur import run as relire

    dispo = modeles_ollama()
    if dispo is None:
        print("Ollama ne répond pas (pas installé ou pas lancé : https://ollama.com). Sans modèle local, seul le "
              "pré-cochage par les règles tourne, sur les transcriptions déjà présentes.")
        dispo = []
    manque = [m for m, utile in ((vision, not sans_code), (reparateur, not (sans_code or sans_reparateur)),
                                 (second, not sans_courtes))
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
        rep = reparateur if reparateur in dispo and not sans_reparateur else None
        if rep is None:
            print("  → pré-cochage par les règles seules (sans réparateur"
                  + (" : lecture rapide)" if sans_reparateur else ")"))
        etapes.append(("pré-cochage par les tests", lambda: precocher(dossiers, rep)))
    if not sans_courtes:
        if second in dispo:
            etapes.append(("second lecteur des réponses courtes", lambda: relire(dossiers, second)))
        else:
            print("  → second lecteur sauté")
    from . import avancement
    for i, (nom, f) in enumerate(etapes, 1):
        print(f"\n=== {i}/{len(etapes)} {nom} ({(time.time() - t0) / 60:.0f} min écoulées)", flush=True)
        avancement.etape(f"étape {i}/{len(etapes)} · ")
        avancement.attendre(f"{nom} : démarrage…")
        try:
            f()
        except SystemExit as e:          # une étape impossible n'empêche pas les suivantes
            print(f"  étape arrêtée : {e}")
    print(f"\nLecture approfondie terminée en {(time.time() - t0) / 60:.0f} min.")
