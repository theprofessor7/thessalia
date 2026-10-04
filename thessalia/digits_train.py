"""Niveau 2 — entraînement du lecteur de chiffres (commande `digits-train`, nécessite l'extra [trocr]).

    python -m thessalia digits-train sorties/<lot> -v keys/<x>.vocab.json --truth data/truth/<x>.json

1. Modèle de base : petit réseau entraîné sur MNIST (téléchargé une fois, ~11 Mo, dans ~/.cache/thessalia).
2. Affinage sur les chiffres du lot : les réponses numériques dont le découpage a la forme de la vérité
   donnent des chiffres étiquetés (l'écriture des étudiants : « 1 » à la française, « 7 » barré…).
3. Mesure en validation croisée PAR COPIE : chaque copie est lue par un modèle qui n'a jamais vu son
   écriture. C'est ce chiffre qui compte, pas le score sur les copies d'entraînement.
4. Le modèle affiné sur tout le lot est écrit dans data/models/digits.npz (HORS dépôt : il est dérivé
   de copies d'étudiants). `--base-only` régénère le modèle MNIST fourni avec le paquet.

La vérité doit être validée par l'enseignant : une étiquette fausse apprend une erreur au modèle.
"""
from __future__ import annotations

import gzip
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from .common import load_json
from .digits import LOCAL, PACKAGED, DigitReader, segment, shape, to_mnist
from .evaluate_ocr import same
from .vocab import parse_number

MNIST_URL = "https://ossci-datasets.s3.amazonaws.com/mnist/"
CACHE = Path.home() / ".cache" / "thessalia"


def _idx(name, offset):
    p = CACHE / name
    if not p.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MNIST_URL + name, p)
    return np.frombuffer(gzip.open(p).read(), np.uint8, offset=offset)


def _torch():
    try:
        import torch
    except ImportError:
        raise SystemExit("digits-train nécessite PyTorch : pip install -e \".[trocr]\"")
    return torch


def _net(torch):
    nn, F = torch.nn, torch.nn.functional

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.c1, self.c2 = nn.Conv2d(1, 32, 3, padding=1), nn.Conv2d(32, 64, 3, padding=1)
            self.c3 = nn.Conv2d(64, 64, 3, padding=1)
            self.f1, self.f2 = nn.Linear(64 * 7 * 7, 128), nn.Linear(128, 10)
            self.drop = nn.Dropout(0.3)

        def forward(self, x):
            x = F.max_pool2d(F.relu(self.c1(x)), 2)
            x = F.max_pool2d(F.relu(self.c3(F.relu(self.c2(x)))), 2)
            return self.f2(self.drop(F.relu(self.f1(x.flatten(1)))))

    return Net()


def _augment(torch, x):
    """Rotation, cisaillement, échelle, épaisseur du trait."""
    F = torch.nn.functional
    n = x.shape[0]
    ang, sh, sc = (torch.rand(n) - 0.5) * 0.5, (torch.rand(n) - 0.5) * 0.6, 0.85 + torch.rand(n) * 0.35
    th = torch.zeros(n, 2, 3)
    th[:, 0, 0], th[:, 0, 1] = torch.cos(ang) * sc, (-torch.sin(ang) + sh) * sc
    th[:, 1, 0], th[:, 1, 1] = torch.sin(ang) * sc, torch.cos(ang) * sc
    th[:, :, 2] = (torch.rand(n, 2) - 0.5) * 0.15
    x = F.grid_sample(x, F.affine_grid(th, x.shape, align_corners=False), align_corners=False)
    r = torch.rand(n, 1, 1, 1)
    thick = F.max_pool2d(x, 3, 1, 1)
    thin = F.pad(-F.max_pool2d(-x, 2, 1, 0), (0, 1, 0, 1))
    return torch.where(r < 0.3, thick, torch.where(r > 0.8, thin, x))


def _mnist(torch):
    x = torch.tensor(_idx("train-images-idx3-ubyte.gz", 16).reshape(-1, 1, 28, 28) / 255.0, dtype=torch.float32)
    y = torch.tensor(_idx("train-labels-idx1-ubyte.gz", 8).astype(np.int64))
    return x, y


def _save(net, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{k: v.numpy().astype(np.float16) for k, v in net.state_dict().items()})


def _load(torch, path):
    net = _net(torch)
    net.load_state_dict({k: torch.tensor(v.astype(np.float32)) for k, v in np.load(path).items()})
    return net


def train_base(out=PACKAGED, epochs=4, log=print):
    torch = _torch()
    F = torch.nn.functional
    torch.manual_seed(0)
    x, y = _mnist(torch)
    net = _net(torch)
    opt = torch.optim.Adam(net.parameters(), 1e-3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=epochs * (len(x) // 128 + 1))
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(x))
        for i in range(0, len(x), 128):
            b = perm[i:i + 128]
            loss = F.cross_entropy(net(_augment(torch, x[b])), y[b], label_smoothing=0.05)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
        log(f"  époque {ep + 1}/{epochs}")
    _save(net.eval(), out)
    log(f"-> {out}")


def _finetune(torch, base, xo, yo, xm, ym, seed, steps=400):
    F = torch.nn.functional
    torch.manual_seed(seed)
    net = _load(torch, base)
    opt = torch.optim.Adam(net.parameters(), 3e-4)
    net.train()
    for _ in range(steps):  # moitié chiffres du lot, moitié MNIST : on n'oublie pas les formes courantes
        a, b = torch.randint(len(xo), (64,)), torch.randint(len(xm), (64,))
        loss = F.cross_entropy(net(_augment(torch, torch.cat([xo[a], xm[b]]))), torch.cat([yo[a], ym[b]]),
                               label_smoothing=0.05)
        opt.zero_grad()
        loss.backward()
        opt.step()
    return net.eval()


def numeric_items(results_dir, truth, vocab):
    """Réponses numériques sûres d'un lot : (clé cNN_qX.Y, nombre vrai, vignette nettoyée)."""
    results_dir = Path(results_dir)
    for rp in sorted(results_dir.glob("copy_*/result.json")):
        doc = load_json(rp)
        c = int(doc["copy_id"].split("_")[1])
        for fid, info in doc.get("fields", {}).items():
            key = f"c{c:02d}_{fid}"
            t = truth.get(key, "")
            if vocab.get(fid, {}).get("kind") != "number" or not t or t.endswith("?") or not info.get("clean"):
                continue
            num = parse_number(t)
            if num is not None:
                yield key, num, cv2.imread(str(results_dir / info["clean"]), cv2.IMREAD_GRAYSCALE)


def run(results_dir, vocab_path, truth_path, out=LOCAL, folds=3, base=PACKAGED, log=print):
    torch = _torch()
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    vocab = load_json(vocab_path)["fields"]
    items = list(numeric_items(results_dir, load_json(truth_path), vocab))
    if not items:
        raise SystemExit("Aucune réponse numérique avec vérité dans ce lot.")
    segs = {k: segment(img) for k, _, img in items}
    glyphs = {}  # copie -> [(28×28, chiffre)] ; seulement quand le découpage a la forme de la vérité
    for k, t, _ in items:
        if shape(segs[k]) == "".join("d" if ch.isdigit() else ch for ch in t):
            for g, ch in zip(segs[k], t):
                if g["kind"] == "digit":
                    glyphs.setdefault(k[:3], []).append((to_mnist(g["mask"]), int(ch)))
    n_ok = sum(shape(segs[k]) == "".join("d" if ch.isdigit() else ch for ch in t) for k, t, _ in items)
    log(f"{len(items)} réponses numériques ; découpage conforme : {n_ok} ; "
        f"{sum(len(v) for v in glyphs.values())} chiffres étiquetés sur {len(glyphs)} copies")
    xm, ym = _mnist(torch)

    def tensors(copies):
        gl = [g for c in copies for g in glyphs.get(c, [])]
        return torch.tensor(np.stack([g[0] for g in gl]))[:, None], torch.tensor([g[1] for g in gl])

    def score(read, keys):
        return sum(1 for k, t, img in items if k in keys and (r := read(img, segs[k])[0]) is not None
                   and parse_number(r) is not None and same(parse_number(r), t, "number"))

    copies = sorted({k[:3] for k, _, _ in items})
    all_keys = {k for k, _, _ in items}
    log(f"modèle de base (MNIST) : {score(DigitReader(base).read, all_keys)}/{len(items)} nombres justes")
    if len(copies) >= folds:
        good = 0
        for f in range(folds):
            test = set(copies[f::folds])
            net = _finetune(torch, base, *tensors([c for c in copies if c not in test]), xm, ym, seed=f)
            tmp = CACHE / "digits_fold.npz"
            _save(net, tmp)
            good += score(DigitReader(tmp).read, {k for k in all_keys if k[:3] in test})
        log(f"modèle affiné, validation croisée par copie ({folds} plis) : {good}/{len(items)} nombres justes")
    _save(_finetune(torch, base, *tensors(copies), xm, ym, seed=0), out)
    log(f"-> {out} (affiné sur tout le lot ; hors dépôt)")
