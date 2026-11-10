"""Apprentissage depuis l'application (page « Apprentissage ») : affiner les lecteurs sur les corrections de
l'enseignant, mesurer, puis adopter ou revenir en arrière.

Exemples d'entraînement : les lectures que l'enseignant a vérifiées dans l'outil de correction (texte tapé, ou
réponse jugée juste dont la lecture brute est exactement le corrigé, cf. `Classe.labels`), dans tous les examens.
Jamais une lecture acceptée par la machine sans revue : le modèle n'apprend pas de ses propres décisions.

Règle de mesure (CLAUDE.md) : un lecteur se mesure sur des copies qu'il n'a JAMAIS vues.
- Chiffres : validation croisée par copie (chaque copie est lue par un modèle affiné sans elle), comparée au
  modèle fourni, qui n'a jamais vu ces copies. Quelques minutes.
- Écriture (TrOCR) : affiné sur toutes les classes sauf une, mise de côté, sur laquelle le modèle d'origine et
  le modèle affiné sont mesurés (lecture brute exacte). Plusieurs heures, ~6 Go de mémoire : une nuit. C'est ce
  modèle mesuré qui est adopté ; la classe mise de côté servira au prochain affinage.

Adopter n'est proposé que si le modèle affiné fait mieux. Le modèle remplacé est gardé : « Revenir au
précédent » le remet en service. Tout reste dans data/models/ (hors dépôt).
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

MODELES = Path("data/models")
CHIFFRES = {"service": MODELES / "digits.npz", "candidat": MODELES / "digits_candidat.npz",
            "precedent": MODELES / "digits_precedent.npz"}
ECRITURE = {"service": MODELES / "ecriture", "candidat": MODELES / "ecriture_candidat",
            "precedent": MODELES / "ecriture_precedent"}
MIN_CHIFFRES = 20        # nombres validés nécessaires pour affiner le lecteur de chiffres
MIN_ECRITURE = 100       # vignettes validées (hors classe de test) pour affiner le lecteur d'écriture
MIN_TEST = 20            # vignettes validées dans la classe mise de côté pour la mesure
PASSES = 3


def _meta(chemin: Path) -> Path:
    """Fiche de mesure d'un modèle : à côté du fichier (chiffres) ou dedans (dossier TrOCR)."""
    return chemin / "mesure.json" if chemin.suffix == "" else chemin.with_suffix(".json")


def lire_mesure(chemin: Path):
    p = _meta(Path(chemin))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ecrire_mesure(chemin: Path, mesure: dict):
    p = _meta(Path(chemin))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(mesure, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ exemples validés
def lots(racine="examens"):
    """Classes lues de tous les examens, avec leurs étiquettes validées :
    [{examen, classe, dossier, vocab, etiquettes, nombres, ecriture, date}]."""
    from .correction import Classe, Decisions
    from .projet import Projet, nom_valide
    out = []
    racine = Path(racine)
    for d in sorted(racine.iterdir()) if racine.is_dir() else []:
        if not d.is_dir() or not nom_valide(d.name):
            continue
        p = Projet(d)
        for c in p.classes():
            if not c["lue"] or not c["langue"]:
                continue
            dossier = p.classes_dir / c["classe"]
            try:
                vocab = p.fichiers(c["langue"])["vocab"]
                cl = Classe(dossier, {}, Decisions(p.stockage()["db"]))
                etiquettes = cl.labels()
            except (SystemExit, OSError, KeyError, ValueError):
                continue     # examen dont la source ne passe plus le contrôle : ses classes attendent
            champs = json.loads(Path(vocab).read_text(encoding="utf-8"))["fields"] if Path(vocab).exists() else {}
            nb = sum(1 for k in etiquettes if champs.get(k.split("_", 1)[1], {}).get("kind") == "number")
            ec = sum(1 for k in etiquettes if k.split("_", 1)[1] in champs)
            out.append({"examen": d.name, "classe": c["classe"], "dossier": dossier, "vocab": vocab,
                        "etiquettes": etiquettes, "nombres": nb, "ecriture": ec,
                        "date": (dossier / "results.json").stat().st_mtime})
    return out


def _torch_present():
    from importlib.util import find_spec
    return bool(find_spec("torch"))


# ------------------------------------------------------------------ état (page)
def etat(racine="examens"):
    ls = lots(racine)
    n_nb, n_ec = sum(l["nombres"] for l in ls), sum(l["ecriture"] for l in ls)
    test = classe_de_test(ls)
    reste = sum(l["ecriture"] for l in ls if l is not test) if test else 0

    def modele(cfg, fourni):
        s = cfg["service"]
        return {"service": lire_mesure(s) if s.exists() else None, "en_service": s.exists(), "fourni": fourni,
                "candidat": lire_mesure(cfg["candidat"]) if cfg["candidat"].exists() else None,
                "precedent": cfg["precedent"].exists()}

    chiffres = modele(CHIFFRES, "modèle fourni avec Thessalia")
    chiffres.update(exemples=n_nb, minimum=MIN_CHIFFRES, pret=n_nb >= MIN_CHIFFRES, torch=_torch_present())
    ecriture = modele(ECRITURE, "modèle d'origine (microsoft/trocr-base-handwritten)")
    ecriture.update(exemples=n_ec, minimum=MIN_ECRITURE, torch=_torch_present(),
                    test=None if test is None else f"{test['examen']} / {test['classe']}",
                    test_n=test["ecriture"] if test else 0, entrainement=reste,
                    pret=test is not None and reste >= MIN_ECRITURE)
    if ECRITURE["candidat"].exists() and not ecriture["candidat"]:
        ecriture["interrompu"] = True      # affinage commencé, pas encore mesuré : relancer reprend
    return {"lots": [{k: l[k] for k in ("examen", "classe", "nombres", "ecriture")} for l in ls],
            "chiffres": chiffres, "ecriture": ecriture}


def classe_de_test(ls):
    """Classe mise de côté pour mesurer le lecteur d'écriture : la plus récente qui a assez de vignettes."""
    ok = [l for l in ls if l["ecriture"] >= MIN_TEST]
    return max(ok, key=lambda l: l["date"]) if len(ok) >= 2 or (ok and len(ls) >= 2) else None


# ------------------------------------------------------------------ lecteur de chiffres
def affiner_chiffres(racine="examens", log=print):
    from .digits import PACKAGED, TUNED
    from .digits_train import run
    if not _torch_present():
        raise SystemExit("il faut d'abord le lecteur d'écriture (Réglages > Extensions) : il apporte PyTorch")
    ls = [l for l in lots(racine) if l["nombres"]]
    n = sum(l["nombres"] for l in ls)
    if n < MIN_CHIFFRES:
        raise SystemExit(f"{n} nombres validés : il en faut au moins {MIN_CHIFFRES} (corrigez d'abord des réponses "
                         "numériques dans l'outil)")
    log(f"{n} nombres validés dans {len(ls)} classe(s). Le premier affinage télécharge la base MNIST (11 Mo).")
    lots_ = [(l["dossier"], l["vocab"], l["etiquettes"]) for l in ls]
    reference = TUNED if TUNED.exists() else PACKAGED
    m = run(*lots_[0], out=CHIFFRES["candidat"], also=lots_[1:], log=log, reference=reference)
    if m.get("affine") is None:
        CHIFFRES["candidat"].unlink(missing_ok=True)
        raise SystemExit("pas assez de copies différentes pour une mesure honnête (validation croisée sur 3 copies au moins)")
    mesure = {"date": time.strftime("%Y-%m-%d %H:%M"), "n": m["n"], "reference": m["reference"], "affine": m["affine"],
              "classes": [f"{l['examen']} / {l['classe']}" for l in ls],
              "mieux": m["affine"] > m["reference"]}
    _ecrire_mesure(CHIFFRES["candidat"], mesure)
    log(f"Mesure sur des copies jamais vues : modèle en service {m['reference']}/{m['n']}, "
        f"affiné {m['affine']}/{m['n']}. " + ("Il fait mieux : vous pouvez l'adopter." if mesure["mieux"]
                                              else "Il ne fait pas mieux : le garder n'apporterait rien."))
    return mesure


# ------------------------------------------------------------------ lecteur d'écriture
def affiner_ecriture(racine="examens", log=print, passes=PASSES):
    from . import trocr_train
    if not _torch_present():
        raise SystemExit("il faut d'abord le lecteur d'écriture (Réglages > Extensions)")
    out = ECRITURE["candidat"]
    if out.exists() and lire_mesure(out):        # candidat déjà mesuré : un nouvel affinage repart de zéro
        shutil.rmtree(out)
    gel = out / "exemples.json"
    if gel.exists():
        # reprise après une pause ou une coupure : mêmes exemples qu'au départ, même si vous avez corrigé d'autres
        # copies entre-temps (sinon l'affinage repartirait de zéro) ; ils serviront au prochain affinage
        g = json.loads(gel.read_text(encoding="utf-8"))
        train = [dict(l, dossier=Path(l["dossier"])) for l in g["train"]]
        test = dict(g["test"], dossier=Path(g["test"]["dossier"]))
        n = sum(l["ecriture"] for l in train)
        log(f"Reprise de l'affinage : {n} lectures vérifiées, mesure sur {test['examen']} / {test['classe']}.")
    else:
        ls = lots(racine)
        test = classe_de_test(ls)
        if test is None:
            raise SystemExit(f"il faut au moins deux classes corrigées, dont une avec {MIN_TEST} lectures vérifiées, "
                             "pour mesurer sur une classe jamais vue")
        train = [l for l in ls if l is not test and l["ecriture"]]
        n = sum(l["ecriture"] for l in train)
        if n < MIN_ECRITURE:
            raise SystemExit(f"{n} lectures vérifiées hors classe de test : il en faut au moins {MIN_ECRITURE}")
        if out.exists():                          # ancien affinage interrompu sans exemples gelés : on recommence
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        cles = ("examen", "classe", "dossier", "vocab", "etiquettes", "ecriture")
        gel.write_text(json.dumps({"train": [{k: str(l[k]) if k in ("dossier", "vocab") else l[k] for k in cles}
                                             for l in train],
                                   "test": {k: str(test[k]) if k in ("dossier", "vocab") else test[k] for k in cles}},
                                  ensure_ascii=False), encoding="utf-8")
        log(f"Affinage sur {n} lectures vérifiées ({len(train)} classe(s)) ; mesure sur {test['examen']} / "
            f"{test['classe']} ({test['ecriture']} lectures), jamais vue. Quelques heures en arrière-plan ; "
            "« Pause » ou une coupure : la reprise repart d'où l'affinage s'était arrêté.")
    trocr_train.run([(l["dossier"], l["vocab"], l["etiquettes"]) for l in train], out=out, passes=passes, log=log)
    log("Mesure sur la classe mise de côté…")
    ref = ECRITURE["service"] if ECRITURE["service"].exists() else trocr_train.BASE
    a, b, t = _mesurer_ecriture(test, [str(ref), str(out)], log)
    mesure = {"date": time.strftime("%Y-%m-%d %H:%M"), "n": t, "reference": a, "affine": b,
              "test": f"{test['examen']} / {test['classe']}", "exemples": n,
              "classes": [f"{l['examen']} / {l['classe']}" for l in train], "mieux": b > a}
    _ecrire_mesure(out, mesure)
    log(f"Lecture exacte sur la classe jamais vue : modèle en service {a}/{t}, affiné {b}/{t}. "
        + ("Il fait mieux : vous pouvez l'adopter." if b > a else "Il ne fait pas mieux : le garder n'apporterait rien."))
    return mesure


def _vignettes_validees(lot):
    """(vignette nettoyée, transcription validée, genre du champ) : mêmes vignettes que l'affinage (`labelled_items`)."""
    from .common import load_json
    champs = json.loads(Path(lot["vocab"]).read_text(encoding="utf-8"))["fields"]
    for rp in sorted(Path(lot["dossier"]).glob("copy_*/result.json")):
        doc = load_json(rp)
        c = int(doc["copy_id"].split("_")[1])
        for fid, info in doc.get("fields", {}).items():
            t = lot["etiquettes"].get(f"c{c:02d}_{fid}", "")
            if fid in champs and t and not t.endswith("?") and info.get("clean"):
                yield str(Path(lot["dossier"]) / info["clean"]), t, champs[fid].get("kind", "text")


def _mesurer_ecriture(lot, modeles, log):
    """Lecture brute exacte (première proposition) de chaque modèle sur les vignettes validées du lot."""
    import cv2

    from .evaluate_ocr import same
    from .ocr import TrOCRBackend
    items = list(_vignettes_validees(lot))
    images = [cv2.imread(v, cv2.IMREAD_GRAYSCALE) for v, _, _ in items]
    scores = []
    for m in modeles:
        log(f"  lecture avec {Path(m).name}…")
        lus = TrOCRBackend(model=m).recognize(images)
        scores.append(sum(1 for c, (_, t, k) in zip(lus, items) if c and same(c[0][0], t, k)))
    return scores[0], scores[1], len(items)


# ------------------------------------------------------------------ adopter, revenir
def _deplacer(src: Path, dst: Path):
    """Déplace un modèle avec sa fiche de mesure ; ce qui était à la destination est remplacé."""
    if dst.exists():
        shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
    if dst.suffix:
        _meta(dst).unlink(missing_ok=True)
    if src.exists():
        src.rename(dst)
        if src.suffix and _meta(src).exists():
            _meta(src).rename(_meta(dst))


def adopter(quoi, log=print):
    cfg = {"chiffres": CHIFFRES, "ecriture": ECRITURE}[quoi]
    m = lire_mesure(cfg["candidat"]) if cfg["candidat"].exists() else None
    if not m:
        raise SystemExit("aucun modèle affiné et mesuré à adopter")
    if not m.get("mieux"):
        raise SystemExit("le modèle affiné ne fait pas mieux que celui en service : il n'est pas adopté")
    _deplacer(cfg["service"], cfg["precedent"])
    _deplacer(cfg["candidat"], cfg["service"])
    log("Nouveau lecteur en service (l'ancien est gardé : « Revenir au précédent »).")


def revenir(quoi, log=print):
    """Remet le modèle précédent en service (ou le modèle fourni s'il n'y en a pas) ; celui retiré devient le
    précédent : un second clic annule."""
    cfg = {"chiffres": CHIFFRES, "ecriture": ECRITURE}[quoi]
    if not cfg["service"].exists() and not cfg["precedent"].exists():
        raise SystemExit("rien à rétablir : le modèle fourni est déjà en service")
    s = cfg["service"]
    tmp = s.with_name(s.stem + "_echange" + s.suffix)
    _deplacer(cfg["service"], tmp)
    _deplacer(cfg["precedent"], cfg["service"])
    _deplacer(tmp, cfg["precedent"])
    log("Modèle précédent remis en service.")


def ecarter(quoi, log=print):
    cfg = {"chiffres": CHIFFRES, "ecriture": ECRITURE}[quoi]
    c = cfg["candidat"]
    if c.exists():
        shutil.rmtree(c) if c.is_dir() else (c.unlink(), _meta(c).unlink(missing_ok=True))
    log("Modèle affiné écarté.")


def modele_ecriture():
    """Modèle TrOCR à utiliser pour lire les réponses courtes : celui adopté, sinon None (modèle d'origine)."""
    return str(ECRITURE["service"]) if (ECRITURE["service"] / "config.json").exists() else None
