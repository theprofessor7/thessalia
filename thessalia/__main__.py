"""Point d'entrée : python -m thessalia <commande> ...

    template   PDF vierge -> gabarit JSON
    process    scans -> résultats (JSON, CSV, overlays, vignettes)
    ocr        Niveau 2 : lecture des réponses courtes (après process)
    digits-train  Niveau 2 : affiner le lecteur de chiffres sur un lot dont la vérité est validée
    trocr-train   Niveau 2 : affiner TrOCR sur des lots validés (long, ~6 Go de mémoire)
    truth-page    Niveau 2 : page HTML locale pour valider la vérité terrain des réponses courtes
    notes      notes partielles : QCM + réponses courtes, par classe (et fichier commun d'un groupe)
    simulate   génère des copies remplies + scannées synthétiques (tests)
    evaluate   compare des résultats à une vérité terrain
"""
import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="thessalia")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="PDF vierge -> gabarit JSON")
    t.add_argument("pdf")
    t.add_argument("-o", "--out", required=True)
    t.add_argument("--exam-id")
    t.add_argument("--merge")

    p = sub.add_parser("process", help="scans -> résultats")
    p.add_argument("scans", nargs="+", help="PDF, images ou dossiers")
    p.add_argument("-t", "--template", required=True)
    p.add_argument("-b", "--blank", required=True, help="PDF vierge du sujet")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("-k", "--key", help="corrigé JSON (optionnel)")
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--no-overlays", action="store_true")
    p.add_argument("--no-crops", action="store_true")
    p.add_argument("--full-policy", choices=["auto", "checked", "cancelled", "review"])
    p.add_argument("--bridge-line", action="store_true",
                   help="Niveau 2 (expérimental) : recoller les tracés coupés par le soulignement")

    s = sub.add_parser("simulate", help="copies synthétiques pour tester")
    s.add_argument("-t", "--template", required=True)
    s.add_argument("-b", "--blank", required=True)
    s.add_argument("-o", "--out", required=True)
    s.add_argument("-n", "--copies", type=int, default=5)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--hard", action="store_true", help="déformations et marques plus difficiles")

    o = sub.add_parser("ocr", help="Niveau 2 : lecture des réponses courtes d'un dossier de résultats")
    o.add_argument("results_dir")
    o.add_argument("-v", "--vocab", required=True, help="vocabulaires par champ (*.vocab.json)")
    o.add_argument("--backend", default="trocr", help="trocr (défaut), tesseract, rapidocr")
    o.add_argument("--model", help="modèle TrOCR (ex. microsoft/trocr-large-handwritten)")
    o.add_argument("--truth", help="vérité terrain pour évaluer (format cNN_qX.Y)")
    o.add_argument("--batch", type=int, default=4,
                   help="vignettes lues à la fois (défaut 4 ; plus petit = moins de mémoire)")

    o.add_argument("--no-digits", action="store_true",
                   help="ne pas utiliser le lecteur de chiffres pour proposer les nombres")

    d = sub.add_parser("digits-train", help="Niveau 2 : affiner le lecteur de chiffres sur un lot validé")
    d.add_argument("results_dir", nargs="?")
    d.add_argument("-v", "--vocab")
    d.add_argument("--truth", help="vérité terrain VALIDÉE (format cNN_qX.Y)")
    d.add_argument("-o", "--out", help="modèle affiné (défaut : data/models/digits.npz, hors dépôt)")
    d.add_argument("--base-only", action="store_true", help="réentraîner le modèle MNIST fourni avec le paquet")
    d.add_argument("--also", nargs=3, action="append", default=[], metavar=("DOSSIER", "VOCAB", "VERITE"),
                   help="autre lot validé à ajouter (répétable) : dossier de résultats, vocabulaire, vérité")

    tt = sub.add_parser("trocr-train", help="Niveau 2 : affiner TrOCR sur des lots validés (long, ~6 Go de mémoire)")
    tt.add_argument("results_dir")
    tt.add_argument("-v", "--vocab", required=True)
    tt.add_argument("--truth", required=True, help="vérité terrain VALIDÉE (format cNN_qX.Y)")
    tt.add_argument("--also", nargs=3, action="append", default=[], metavar=("DOSSIER", "VOCAB", "VERITE"),
                    help="autre lot validé à ajouter (répétable) : dossier de résultats, vocabulaire, vérité")
    tt.add_argument("-o", "--out", default="data/models/trocr", help="modèle affiné (hors dépôt, ~1,3 Go)")
    tt.add_argument("--passes", type=int, default=3)
    tt.add_argument("--limit", type=int, help="essai court : n'utiliser que N vignettes tirées au hasard")
    tt.add_argument("--from", dest="from_model", help="repartir de ce modèle déjà affiné (ex. data/models/trocr_commun)")
    tt.add_argument("--replay", type=int, help="ne reprendre que N vignettes tirées au hasard dans les lots --also")

    v = sub.add_parser("truth-page", help="Niveau 2 : page HTML locale pour valider la vérité terrain")
    v.add_argument("results_dir")
    v.add_argument("-t", "--template", help="gabarit JSON (affiche la consigne de chaque blanc)")
    v.add_argument("--truth", help="vérité existante à relire (sinon : propositions de `ocr`)")
    v.add_argument("-o", "--out", help="défaut : <results_dir>/validation.html")

    n = sub.add_parser("notes", help="notes partielles : QCM + réponses courtes")
    n.add_argument("results_dirs", nargs="+", help="dossiers de résultats (une classe chacun)")
    n.add_argument("-t", "--template", required=True)
    n.add_argument("-k", "--key", required=True, help="corrigé JSON (short_answers, short_accept, short_reject)")
    n.add_argument("-v", "--vocab", required=True, help="vocabulaire (nature de chaque blanc)")
    n.add_argument("-o", "--out", help="fichier commun du groupe (ex. sorties/notes/B.csv)")

    e = sub.add_parser("evaluate", help="résultats vs vérité terrain")
    e.add_argument("results_dir")
    e.add_argument("truth")

    a = ap.parse_args(argv)
    if a.cmd == "template":
        from .template_builder import main as tmain

        args = [a.pdf, "-o", a.out] + (["--exam-id", a.exam_id] if a.exam_id else []) + \
               (["--merge", a.merge] if a.merge else [])
        tmain(args)
    elif a.cmd == "process":
        from .omr import OMRConfig
        from .pipeline import Processor
        from .common import load_json

        cfg = OMRConfig.from_dict(load_json(a.template).get("omr"))
        if a.full_policy:
            cfg.full_policy = a.full_policy
        proc = Processor(a.template, a.blank, a.dpi, cfg, a.key, not a.no_overlays, not a.no_crops,
                         bridge_line=a.bridge_line)
        copies = proc.run(a.scans, a.out)
        n_rev = sum(len(c["review"]) for c in copies)
        print(f"{len(copies)} copie(s) traitée(s), {n_rev} point(s) à revoir -> {a.out}")
    elif a.cmd == "ocr":
        from .ocr_run import run

        run(a.results_dir, a.vocab, a.backend, a.truth, {"model": a.model} if a.model else None,
            batch=max(1, a.batch), digits=not a.no_digits)
    elif a.cmd == "digits-train":
        from . import digits_train

        if a.base_only:
            digits_train.train_base()
        elif not (a.results_dir and a.vocab and a.truth):
            ap.error("digits-train : results_dir, --vocab et --truth sont requis (ou --base-only)")
        else:
            digits_train.run(a.results_dir, a.vocab, a.truth, also=a.also, **({"out": a.out} if a.out else {}))
    elif a.cmd == "trocr-train":
        from . import trocr_train

        trocr_train.run([(a.results_dir, a.vocab, a.truth), *a.also], out=a.out, passes=a.passes, limit=a.limit,
                        base=a.from_model or trocr_train.BASE, replay=a.replay)
    elif a.cmd == "truth-page":
        from .truth_page import build

        build(a.results_dir, a.template, a.truth, a.out)
    elif a.cmd == "notes":
        from .notes import run as nrun

        nrun(a.results_dirs, a.template, a.key, a.vocab, a.out)
    elif a.cmd == "simulate":
        from .simulate import main as smain

        smain(a)
    elif a.cmd == "evaluate":
        from .evaluate import main as emain

        emain(a.results_dir, a.truth)


if __name__ == "__main__":
    sys.exit(main())
