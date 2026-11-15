"""Lecture des réponses courtes d'une classe (« Lire les réponses courtes » de l'application) : les vignettes
nettoyées par la lecture des copies passent au lecteur d'écriture (TrOCR, local), puis sont rapprochées du
vocabulaire du sujet.

Écrit pour chaque copie `fields[id]["ocr"]` dans result.json, et au niveau de la classe :
    short_answers.csv   une ligne par copie, une colonne par blanc (valeur ou vide)
    ocr_review.csv      les réponses à valider par un humain, avec propositions

Sujet nouveau : tant que le corrigé ne porte pas `"lecture_validee": true`, AUCUNE réponse n'est acceptée
d'office (toutes en revue, vides exceptées). Mesuré le 23 octobre 2026 sur le sujet B (BIS, 7 copies) avec
trocr_v3 + accord de trocr_v2, affinés sur le sujet A : 3 réponses fausses acceptées sur 80 (« Impair » lu
« ERREUR » par les deux modèles en q14.2). L'accord de deux modèles ne protège pas d'un biais commun. Le drapeau
se pose à la main, après une mesure sur des copies du sujet corrigées par l'enseignant.
"""
from __future__ import annotations

import csv
import hashlib
import re
import time
from pathlib import Path

import cv2

from .common import load_json, save_json
from .ocr import TrOCRBackend
from .ocr_prep import extra_word, struck_word
from .vocab import parse_number, propose_digits, snap

EXTRA_WORD = "écriture séparée en plus du mot reconnu (deux mots, rature ?) : à vérifier"
STRUCK = "mot barré à côté d'une autre écriture : à vérifier"
FORM = "parenthèses ou guillemets lus autour de la réponse : forme à vérifier (notée 50 %)"
NOUVEAU = "sujet pas encore validé (corrigé sans « lecture_validee ») : aucune réponse acceptée d'office"


def lecture_validee(vocab_path, keys_dir=None) -> bool:
    """Le corrigé du sujet du vocabulaire porte-t-il `"lecture_validee": true` ? (absent = non : sujet nouveau)"""
    eid = load_json(vocab_path).get("exam_id")
    for k in sorted(Path(keys_dir or Path(vocab_path).parent).glob("*.key.json")):
        key = load_json(k)
        if key.get("exam_id") == eid:
            return key.get("lecture_validee") is True
    return False
FORM_CHARS = set("()\"'")


def form_marks(raw: str, value) -> bool:
    """La lecture brute porte des parenthèses ou guillemets que la valeur retenue n'a pas (`print("...")`
    accepté `print`) : depuis la règle de notation du 18 octobre, cet écart de forme change la note."""
    return bool(FORM_CHARS & set(raw or "")) and not (FORM_CHARS & set(str(value or "")))


def run(results_dir, vocab_path, model=None, log=print, batch=4, digits=True, digits_model=None):
    """model : lecteur d'écriture affiné et adopté (page Apprentissage), sinon le modèle d'origine."""
    results_dir = Path(results_dir)
    vocab = load_json(vocab_path)["fields"]
    valide = lecture_validee(vocab_path)
    if not valide:
        log("SUJET NON VALIDÉ : aucune réponse acceptée d'office, toutes en revue "
            "(après mesure sur des copies corrigées : bouton « Sujet validé » de l'application, ou "
            "\"lecture_validee\": true dans le corrigé)")
    copies = sorted(results_dir.glob("copy_*/result.json"))
    if not copies:
        raise SystemExit(f"Aucune copie lue dans {results_dir}.")

    # 1) collecte des vignettes à lire
    todo, docs = [], {}
    for rp in copies:
        doc = load_json(rp)
        docs[rp] = doc
        for fid, info in doc.get("fields", {}).items():
            if info.get("type") != "short_text":
                continue
            if info.get("blank") and not info.get("suspect"):
                info["ocr"] = {"value": "", "status": "blank"}
            elif info.get("blank"):
                info["ocr"] = {"value": None, "status": "review",
                               "reason": "zone vide mais écriture à proximité (réponse écrite trop haut ?)",
                               "suggestions": []}
            else:
                todo.append((rp, fid, info))
    log(f"{len(todo)} vignettes à lire avec « trocr » ({len(copies)} copies)")

    # 2) reconnaissance, par petits lots ; chaque lot lu est enregistré aussitôt dans un fichier
    #    de lectures : une commande interrompue reprend où elle s'était arrêtée
    eng = TrOCRBackend(**({"model": model} if model else {}))
    tag = eng.name + ("_" + re.sub(r"[^\w.-]+", "_", eng.model_name) if getattr(eng, "model_name", None) else "")
    cache_path = results_dir / f"ocr_lectures_{tag}.json"
    cache = load_json(cache_path) if cache_path.exists() else {}
    keys, sums = [], []
    for rp, fid, info in todo:
        keys.append(f"c{int(docs[rp]['copy_id'].split('_')[1]):02d}_{fid}")
        # empreinte de la vignette : une lecture enregistrée ne sert que si l'image n'a pas changé
        sums.append(hashlib.md5((results_dir / info["clean"]).read_bytes()).hexdigest())
    rest = [i for i, (k, h) in enumerate(zip(keys, sums)) if cache.get(k, {}).get("md5") != h]
    if len(rest) < len(todo):
        log(f"  {len(todo) - len(rest)} lectures déjà enregistrées ({cache_path.name}), {len(rest)} restantes")
    t0, last = time.time(), time.time()
    for n, j in enumerate(range(0, len(rest), batch)):
        idx = rest[j:j + batch]
        imgs = [cv2.imread(str(results_dir / todo[i][2]["clean"]), cv2.IMREAD_GRAYSCALE) for i in idx]
        for i, c in zip(idx, eng.recognize(imgs, [{"prompt": todo[i][1]} for i in idx])):
            cache[keys[i]] = {"md5": sums[i], "candidates": [[t, float(s)] for t, s in c]}
        save_json(cache, cache_path)
        done = j + len(idx)
        if getattr(log, "progression", None):
            dt = time.time() - t0
            log.progression(100 * done // len(rest), f"{done}/{len(rest)} réponses lues · reste environ "
                            f"{max(1, round((len(rest) - done) * dt / done / 60))} min")
        if time.time() - last >= 15 or done == len(rest):
            last, dt = time.time(), time.time() - t0
            log(f"  {done}/{len(rest)} vignettes lues, {dt / done:.1f} s/vignette, "
                f"reste ~{(len(rest) - done) * dt / done / 60:.0f} min")

    # 3) rapprochement + écriture ; pour les nombres, le lecteur de chiffres fournit la proposition. Aucun nombre
    #    n'est accepté seul : la règle d'acceptation (vocab.propose_digits, accept_numbers) a été mesurée avec des
    #    TrOCR affinés à la main en octobre ; un lecteur adopté depuis la page Apprentissage n'est mesuré que sur
    #    ses lectures exactes, pas sur les nombres qu'il accepterait (principe : zéro erreur silencieuse)
    reader = None
    if digits:
        from .digits import DigitReader
        reader = DigitReader(digits_model)
        log(f"lecteur de chiffres : {reader.path}")
    for (rp, fid, info), key in zip(todo, keys):
        c = [(t, s) for t, s in cache[key]["candidates"]]
        spec = vocab.get(fid, {"kind": "text"})
        r = snap(c, spec)
        img = cv2.imread(str(results_dir / info["clean"]), cv2.IMREAD_GRAYSCALE)
        if reader is not None and spec.get("kind") == "number":
            txt, conf = reader.read(img)
            num = parse_number(txt) if txt else None
            if num is not None:
                propose_digits(r, spec, num, conf)
        # un seul mot accepté alors que la vignette en montre deux (« Grand Petit » lu « Grand ») : en revue
        if r["status"] == "ok":
            if " " not in str(r["value"]) and extra_word(img):
                r.update(status="review", reason=EXTRA_WORD)
            # le moteur a lu le mot barré au lieu de la réponse (`input` barré puis `for`) : en revue
            elif struck_word(img):
                r.update(status="review", reason=STRUCK)
            elif form_marks(c[0][0] if c else "", r["value"]):
                r.update(status="review", reason=FORM)
            if r["status"] == "ok" and not valide:
                r.update(status="review", reason=NOUVEAU)
        r["engine"] = eng.name
        r["candidates"] = [[t, round(float(s), 3)] for t, s in c]
        info["ocr"] = r
    for rp, doc in docs.items():
        save_json(doc, rp)

    field_ids = sorted({fid for d in docs.values() for fid, i in d["fields"].items() if i.get("type") == "short_text"},
                       key=lambda s: [int(x) if x.isdigit() else x for x in s.replace("q", "").split(".")])
    with open(results_dir / "short_answers.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["copy"] + field_ids)
        for doc in docs.values():
            row = [doc["copy_id"]]
            for fid in field_ids:
                o = doc["fields"].get(fid, {}).get("ocr", {})
                row.append(o.get("value") if o.get("status") in ("ok", "blank") else f"?{o.get('value') or ''}")
            w.writerow(row)
    n_rev = 0
    with open(results_dir / "ocr_review.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["copy", "field", "proposition", "suggestions", "raison", "vignette"])
        for doc in docs.values():
            for fid in field_ids:
                info = doc["fields"].get(fid, {})
                o = info.get("ocr", {})
                if o.get("status") == "review":
                    n_rev += 1
                    w.writerow([doc["copy_id"], fid, o.get("value") or "", " | ".join(o.get("suggestions", [])),
                                o.get("reason", ""), info.get("clean") or info.get("crop", "")])
    log(f"-> short_answers.csv, ocr_review.csv ({n_rev} à valider)")

