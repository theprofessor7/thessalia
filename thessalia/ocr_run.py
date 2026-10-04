"""Niveau 2 — commande `ocr` : lit les vignettes nettoyées produites par `process`,
les passe au moteur choisi, rapproche du vocabulaire et enrichit les résultats.

    python -m thessalia ocr sorties/lot_TD1 -v keys/python_core_EN.vocab.json --backend trocr

Écrit pour chaque copie `fields[id]["ocr"]` dans result.json, et au niveau du lot :
    short_answers.csv   une ligne par copie, une colonne par blanc (valeur ou vide)
    ocr_review.csv      les réponses à valider par un humain, avec propositions
Avec --truth : évalue contre une vérité terrain (format cNN_qX.Y, voir evaluate_ocr).
"""
from __future__ import annotations

import csv
import hashlib
import re
import time
from pathlib import Path

import cv2

from .common import load_json, save_json
from .evaluate_ocr import evaluate, report
from .ocr import get_backend
from .vocab import snap


def run(results_dir, vocab_path, backend="trocr", truth=None, backend_kw=None, log=print, batch=4):
    results_dir = Path(results_dir)
    vocab = load_json(vocab_path)["fields"]
    copies = sorted(results_dir.glob("copy_*/result.json"))
    if not copies:
        raise SystemExit(f"Aucun résultat dans {results_dir} (lancer d'abord `process`).")

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
    log(f"{len(todo)} vignettes à lire avec « {backend} » ({len(copies)} copies)")

    # 2) reconnaissance, par petits lots ; chaque lot lu est enregistré aussitôt dans un fichier
    #    de lectures : une commande interrompue reprend où elle s'était arrêtée
    eng = get_backend(backend, **(backend_kw or {}))
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
        if time.time() - last >= 15 or done == len(rest):
            last, dt = time.time(), time.time() - t0
            log(f"  {done}/{len(rest)} vignettes lues, {dt / done:.1f} s/vignette, "
                f"reste ~{(len(rest) - done) * dt / done / 60:.0f} min")

    # 3) rapprochement + écriture
    ocr_by_key = {}
    for (rp, fid, info), key in zip(todo, keys):
        c = [(t, s) for t, s in cache[key]["candidates"]]
        spec = vocab.get(fid, {"kind": "text"})
        r = snap(c, spec)
        r["engine"] = eng.name
        r["candidates"] = [[t, round(float(s), 3)] for t, s in c]
        info["ocr"] = r
        ocr_by_key[key] = c
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

    if truth:
        st, by_q, errors = evaluate(ocr_by_key, load_json(truth), vocab)
        txt = report(eng.name, st, by_q, errors)
        (results_dir / f"ocr_eval_{tag}.txt").write_text(txt, encoding="utf-8")
        log(txt)
