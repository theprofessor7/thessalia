"""Niveau 2 — affinage de TrOCR sur des lots dont la vérité est validée (commande `trocr-train`,
nécessite l'extra [trocr]).

    python -m thessalia trocr-train sorties/<lot> -v keys/<x>.vocab.json --truth data/truth/<x>.json \
        [--also DOSSIER VOCAB VERITE]... [-o data/models/trocr] [--passes 3] [--limit 160]
        [--from data/models/<précédent> --replay 400]

Le modèle affiné est écrit dans data/models/ (local, hors dépôt : ~1,3 Go) après CHAQUE passe ; une
commande interrompue (veille, mémoire) reprend après la dernière passe enregistrée. Il se mesure ensuite
sur un lot qu'il n'a JAMAIS vu :

    python -m thessalia ocr sorties/<autre lot> -v … --model data/models/trocr --truth data/truth/<autre>.json

Mesuré le 5 octobre 2026 (754 vignettes EN, 3 passes, test sur supA 1) : lecture brute exacte 91 -> 211
sur 325. À savoir avant de s'en servir :
- le modèle apprend le vocabulaire des sujets qu'il a vus et remplace les mots inconnus par des mots
  connus (« Zéro » lu « Zero », « Bonjour Alice » lu « Error ») : entraîner sur TOUS les lots validés,
  tous sujets confondus, plutôt qu'un modèle par sujet ;
- sa confiance ne sépare pas le juste du faux (erreurs à 1,00) : la décision reste au rapprochement ;
- une étiquette fausse apprend une erreur : la vérité doit être validée par l'enseignant ;
- ~6 Go de mémoire, ~20 min par passe pour 750 vignettes sur CPU : fermer les applications lourdes.
  `--limit` permet un essai court sur un échantillon avant de lancer plusieurs heures.

Affinage classe par classe (`--from`, `--replay`) : repartir du modèle précédent plutôt que du modèle
d'origine, avec toute la nouvelle classe (lot principal) et seulement N vignettes tirées au hasard dans
les lots déjà appris (`--also`), pour qu'il ne les oublie pas. Durée à peu près constante d'une classe à
l'autre, au lieu d'un réentraînement complet qui s'allonge à chaque lot ajouté ; en refaire un complet
de temps en temps (une nuit) pour vérifier qu'on n'a rien perdu.
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import cv2

from .common import load_json
from .ocr import _pad

BASE = "microsoft/trocr-base-handwritten"
OUT = Path("data/models/trocr")
BATCH, ACCUM = 2, 2  # gradients cumulés sur 2 lots de 2 : même apprentissage qu'un lot de 4
# Étiquettes SANS le jeton de début <s> : TrOCR ne le produit pas (il écrit « texte </s> » après son jeton
# de départ). Jusqu'au 11 octobre 2026 les étiquettes le gardaient : l'affinage commençait par apprendre à
# l'écrire (modèle d'origine : log P d'une lecture juste -0,7 sans <s>, -41 avec). Noté dans etat.json :
# un modèle affiné avec l'ancien format ne se reprend pas avec le nouveau.
LABELS = "sans <s>"


def labelled_items(results_dir, vocab, truth):
    """Vignettes nettoyées d'un lot avec leur transcription validée (ni vides, ni incertaines)."""
    results_dir = Path(results_dir)
    for rp in sorted(results_dir.glob("copy_*/result.json")):
        doc = load_json(rp)
        c = int(doc["copy_id"].split("_")[1])
        for fid, info in doc.get("fields", {}).items():
            t = truth.get(f"c{c:02d}_{fid}", "")
            if fid in vocab and t and not t.endswith("?") and info.get("clean"):
                yield str(results_dir / info["clean"]), t


def _keep_awake():
    """Windows : pas de mise en veille tant que la commande tourne (rien de permanent)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)


def run(lots, out=OUT, passes=3, limit=None, base=BASE, lr=2e-5, seed=0, log=print, replay=None, new=1):
    """lots : [(dossier de résultats, vocabulaire, vérité validée), …] ; le premier est le lot principal.

    base : modèle de départ (d'origine, ou un modèle déjà affiné) ; replay : ne garder que N vignettes
    tirées au hasard dans les lots autres que les `new` premiers (appris en entier).
    """
    try:
        import torch
        from PIL import Image
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    except ImportError:
        raise SystemExit("trocr-train nécessite l'extra [trocr] : pip install -e \".[trocr]\"")
    out = Path(out)
    if Path(base).resolve() == out.resolve():
        raise SystemExit("Le modèle de départ (--from) et la destination (-o) doivent être différents.")
    train, old = [], []
    for k, (rd, vp, tp) in enumerate(lots):
        its = list(labelled_items(rd, load_json(vp)["fields"], load_json(tp)))
        log(f"{Path(rd).name} : {len(its)} vignettes étiquetées")
        (train if k < new or replay is None else old).extend(its)
    if replay is not None:
        random.Random(seed).shuffle(old)
        log(f"rappel : {min(replay, len(old))} vignettes tirées sur {len(old)} des lots déjà appris")
        train += old[:replay]
    if not train:
        raise SystemExit("Aucune vignette avec vérité validée dans ces lots.")
    random.Random(seed).shuffle(train)
    if limit:
        train = train[:limit]
    n_lots = (len(train) + BATCH - 1) // BATCH

    state_path, first = out / "etat.json", 0
    if state_path.exists():
        st = load_json(state_path)
        if (st.get("entrainement") != len(train) or st.get("lots") != [str(Path(l[0])) for l in lots]
                or st.get("base") != str(base) or st.get("rappel") != replay):
            raise SystemExit(f"{out} contient un modèle affiné sur d'autres données : choisir un autre "
                             f"dossier avec -o, ou supprimer celui-ci.")
        if st.get("etiquettes") != LABELS:
            raise SystemExit(f"{out} a été affiné avec l'ancien format d'étiquettes (jeton de début) : il ne "
                             f"se reprend pas. Choisir un autre dossier avec -o, ou supprimer celui-ci.")
        first = st["passes_faites"]
        if first >= passes:
            log(f"{out} : les {passes} passes sont déjà faites.")
            return out
        log(f"reprise : {first} passe(s) déjà faite(s), modèle relu dans {out}")
    _keep_awake()
    torch.manual_seed(seed)
    proc = TrOCRProcessor.from_pretrained(str(base))
    model = VisionEncoderDecoderModel.from_pretrained(str(out) if first else str(base))
    tok = proc.tokenizer
    start = getattr(model.generation_config, "decoder_start_token_id", None)
    model.config.pad_token_id = tok.pad_token_id
    model.config.decoder_start_token_id = start if start is not None else tok.eos_token_id
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)

    def pil(path):  # même préparation que le moteur de lecture (`ocr.TrOCRBackend`)
        return Image.fromarray(cv2.cvtColor(_pad(cv2.imread(path, cv2.IMREAD_GRAYSCALE), 12), cv2.COLOR_GRAY2RGB))

    log(f"affinage de {base} : {len(train)} vignettes, passes {first + 1} à {passes}, {n_lots} lots par passe")
    t0, done = time.time(), 0
    for ep in range(first, passes):
        random.Random(seed + ep).shuffle(train)
        model.train()
        opt.zero_grad()
        tot = 0.0
        for n, i in enumerate(range(0, len(train), BATCH), 1):
            b = train[i:i + BATCH]
            px = proc(images=[pil(p) for p, _ in b], return_tensors="pt").pixel_values
            lab = tok([t for _, t in b], padding=True, return_tensors="pt").input_ids
            if tok.bos_token_id is not None and bool((lab[:, 0] == tok.bos_token_id).all()):
                lab = lab[:, 1:].clone()  # voir LABELS
            lab[lab == tok.pad_token_id] = -100
            loss = model(pixel_values=px, labels=lab).loss
            (loss / ACCUM).backward()
            tot += float(loss.detach())
            if n % ACCUM == 0 or n == n_lots:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                opt.zero_grad()
            done += 1
            if n % 40 == 0:
                dt = (time.time() - t0) / done
                left = ((passes - ep - 1) * n_lots + n_lots - n) * dt / 60
                log(f"  passe {ep + 1} lot {n}/{n_lots} : {dt:.1f} s/lot, reste ~{left:.0f} min")
        out.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(out)
        proc.save_pretrained(out)
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump({"base": str(base), "rappel": replay, "passes_faites": ep + 1, "passes_prevues": passes, "entrainement": len(train),
                       "lots": [str(Path(l[0])) for l in lots], "etiquettes": LABELS}, fh, ensure_ascii=False,
                      indent=1)
        log(f"passe {ep + 1}/{passes} : perte moyenne {tot / n_lots:.3f} -> {out} enregistré")
    log(f"-> {out} (hors dépôt). Mesurer sur un lot jamais vu : ocr <lot> -v … --model {out} --truth …")
    return out
