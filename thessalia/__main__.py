"""Point d'entrée : python -m thessalia <commande> ...

    template   PDF vierge -> gabarit JSON
    process    scans -> résultats (JSON, CSV, overlays, vignettes)
    ocr        Niveau 2 : lecture des réponses courtes (après process)
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
        proc = Processor(a.template, a.blank, a.dpi, cfg, a.key, not a.no_overlays, not a.no_crops)
        copies = proc.run(a.scans, a.out)
        n_rev = sum(len(c["review"]) for c in copies)
        print(f"{len(copies)} copie(s) traitée(s), {n_rev} point(s) à revoir -> {a.out}")
    elif a.cmd == "ocr":
        from .ocr_run import run

        run(a.results_dir, a.vocab, a.backend, a.truth, {"model": a.model} if a.model else None,
            batch=max(1, a.batch))
    elif a.cmd == "simulate":
        from .simulate import main as smain

        smain(a)
    elif a.cmd == "evaluate":
        from .evaluate import main as emain

        emain(a.results_dir, a.truth)


if __name__ == "__main__":
    sys.exit(main())
