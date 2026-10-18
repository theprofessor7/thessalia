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
from .evaluate_ocr import evaluate, proposals, report, same
from .ocr import get_backend
from .ocr_prep import extra_word, struck_word
from .vocab import parse_number, propose_digits, snap

EXTRA_WORD = "écriture séparée en plus du mot reconnu (deux mots, rature ?) : à vérifier"
STRUCK = "mot barré à côté d'une autre écriture : à vérifier"
FORM = "parenthèses ou guillemets lus autour de la réponse : forme à vérifier (notée 50 %)"
FORM_CHARS = set("()\"'")


def form_marks(raw: str, value) -> bool:
    """La lecture brute porte des parenthèses ou guillemets que la valeur retenue n'a pas (`print("...")`
    accepté `print`) : depuis la règle de notation du 18 octobre, cet écart de forme change la note."""
    return bool(FORM_CHARS & set(raw or "")) and not (FORM_CHARS & set(str(value or "")))


def run(results_dir, vocab_path, backend="trocr", truth=None, backend_kw=None, log=print, batch=4,
        digits=True):
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

    # 3) rapprochement + écriture ; pour les nombres, le lecteur de chiffres fournit la proposition
    #    (jamais d'acceptation : il ne change pas le statut)
    reader = None
    if digits:
        from .digits import DigitReader
        reader = DigitReader()
        log(f"lecteur de chiffres : {reader.path}")
    # entiers acceptés seulement avec un TrOCR affiné localement (mesuré avec data/models/trocr_commun) :
    # avec le modèle d'origine, des nombres faux sortaient avec les deux lectures d'accord
    model = str(getattr(eng, "model_name", "") or "")
    accept_numbers = reader is not None and eng.name == "trocr" and not model.startswith("microsoft/")
    if accept_numbers:
        log("nombres entiers (2 chiffres ou plus, deux lectures d'accord, TrOCR >= 0,99) : acceptés")
    ocr_by_key, text_only, proposed, flagged = {}, {}, {}, set()
    for (rp, fid, info), key in zip(todo, keys):
        c = [(t, s) for t, s in cache[key]["candidates"]]
        spec = vocab.get(fid, {"kind": "text"})
        r = snap(c, spec)
        text_only[key] = r["value"]
        img = cv2.imread(str(results_dir / info["clean"]), cv2.IMREAD_GRAYSCALE)
        if reader is not None and spec.get("kind") == "number":
            txt, conf = reader.read(img)
            num = parse_number(txt) if txt else None
            if num is not None:
                propose_digits(r, spec, num, conf, accept_numbers=accept_numbers)
        # un seul mot accepté alors que la vignette en montre deux (« Grand Petit » lu « Grand ») : en revue
        if r["status"] == "ok":
            if " " not in str(r["value"]) and extra_word(img):
                r.update(status="review", reason=EXTRA_WORD)
            # le moteur a lu le mot barré au lieu de la réponse (`input` barré puis `for`) : en revue
            elif struck_word(img):
                r.update(status="review", reason=STRUCK)
            elif form_marks(c[0][0] if c else "", r["value"]):
                r.update(status="review", reason=FORM)
            if r["status"] == "review":
                flagged.add(key)
        proposed[key] = r["value"]
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
        st, by_q, errors = evaluate(ocr_by_key, load_json(truth), vocab, flagged=flagged)
        txt = report(eng.name, st, by_q, errors)
        truth_d = load_json(truth)
        n_ok = [(k, info["ocr"]["value"]) for (rp, fid, info), k in zip(todo, keys)
                if vocab.get(fid, {}).get("kind") == "number" and info["ocr"]["status"] == "ok"
                and k in truth_d and not truth_d[k].endswith("?")]
        bad = [(k, v, truth_d[k]) for k, v in n_ok if not same(str(v), truth_d[k], "number")]
        txt += f"\n  nombres acceptés auto : {len(n_ok)}, dont justes {len(n_ok) - len(bad)}"
        txt += "".join(f"\n    ERREUR NOMBRE {b}" for b in bad)
        n, a = proposals(text_only, truth_d, vocab)
        txt += f"\n  champs numériques (point et virgule distingués) : proposition juste {a}/{n} avec le moteur de texte seul"
        if reader is not None:
            txt += f", {proposals(proposed, truth_d, vocab)[1]}/{n} avec le lecteur de chiffres"
        (results_dir / f"ocr_eval_{tag}.txt").write_text(txt, encoding="utf-8")
        log(txt)
