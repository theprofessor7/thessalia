"""Point d'entrée : python -m thessalia <commande> ...

    app          l'application (navigateur) : examens, copies, lectures, correction, notes ; c'est elle que lancent
                 Thessalia.bat / Thessalia.command
    importer     créer un examen à partir d'un sujet produit par un autre générateur (aussi depuis l'accueil)
    verif-zones  contrôle d'un fichier de zones (générateur d'un collègue) contre le PDF : rapport à coller
    transcrire   option payante, sur clé : lire le code manuscrit par un service en ligne (plafond de dépense) ;
                 la lecture approfondie locale (Ollama) se lance depuis l'application
    simulate     copies remplies et scannées synthétiques (tests)
    evaluate     lecture des cases d'un lot simulé, comparée à sa vérité (tests ; 0 « FAUSSES » exigé)
"""
import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="thessalia")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_ = sub.add_parser("app", help="application : examens, du sujet à la correction (navigateur)")
    ap_.add_argument("--examens", default="examens", help="dossier des examens (défaut : examens/)")
    ap_.add_argument("--port", type=int, default=8765)
    ap_.add_argument("--no-browser", action="store_true")

    im = sub.add_parser("importer", help="examen à partir d'un sujet produit par un autre générateur")
    im.add_argument("nom", help="nom du dossier de l'examen (lettres, chiffres, _ - .)")
    im.add_argument("--titre", help="titre affiché (défaut : le nom)")
    im.add_argument("--langue", nargs=4, action="append", required=True,
                    metavar=("LANGUE", "SUJET_PDF", "CORRIGE_KEY", "VOCAB"),
                    help="une langue du sujet : fr sujet.pdf sujet.key.json sujet.vocab.json (répétable)")
    im.add_argument("--zones", nargs=2, action="append", default=[], metavar=("LANGUE", "ZONES"),
                    help="fichier de zones du générateur, contrôlé contre le PDF (recommandé)")
    im.add_argument("--gabarit", nargs=2, action="append", default=[], metavar=("LANGUE", "GABARIT"),
                    help="gabarit déjà construit sur ce PDF (sinon lu dans le PDF)")
    im.add_argument("--autre", action="append", default=[], help="barème du code .bareme.json, tests .tests.py…")
    im.add_argument("--examens", default="examens", help="dossier des examens (défaut : examens/)")

    vz = sub.add_parser("verif-zones", help="contrôle d'un fichier de zones (.json du générateur) contre le PDF du sujet")
    vz.add_argument("pdf", help="PDF vierge du sujet")
    vz.add_argument("zones", help="fichier de zones .json")
    vz.add_argument("-o", "--sortie", help="écrire le rapport (Markdown) dans ce fichier au lieu de l'afficher")
    vz.add_argument("--tolerance", type=float, default=0.3, help="écart toléré en mm (défaut 0,3)")

    tr = sub.add_parser("transcrire", help="code manuscrit lu par un service en ligne (option payante, plafonnée) "
                                           "ou --local (Ollama, gratuit)")
    tr.add_argument("dossiers", nargs="+", help="dossiers de classes (examens/<nom>/classes/<classe>)")
    tr.add_argument("--champ", action="append", help="champ(s) de code : q12, q18… (en local : tous par défaut)")
    tr.add_argument("--local", nargs="?", const="qwen3-vl:8b-instruct", metavar="MODELE",
                    help="modèle de vision local via Ollama (gratuit, rien ne sort du PC) ; défaut qwen3-vl:8b-instruct")
    tr.add_argument("--refaire", action="store_true", help="local : relire aussi les cadres déjà transcrits par la machine")
    tr.add_argument("--limite", type=int, help="nombre maximal de cadres envoyés ce lancement")

    s = sub.add_parser("simulate", help="copies synthétiques pour tester")
    s.add_argument("-t", "--template", required=True)
    s.add_argument("-b", "--blank", required=True)
    s.add_argument("-o", "--out", required=True)
    s.add_argument("-n", "--copies", type=int, default=5)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--hard", action="store_true", help="déformations et marques plus difficiles")

    e = sub.add_parser("evaluate", help="lecture d'un lot simulé (scans.pdf) comparée à sa vérité (truth.json)")
    e.add_argument("lot", help="dossier écrit par simulate")
    e.add_argument("-t", "--template", required=True, help="gabarit du sujet")
    e.add_argument("-b", "--blank", required=True, help="PDF vierge du sujet")

    a = ap.parse_args(argv)
    if a.cmd == "app":
        from .serve import run_app
        return run_app(a.examens, port=a.port, open_browser=not a.no_browser)
    if a.cmd == "importer":
        from .projet import importer_fichiers
        langues = {lg.lower(): {"pdf": pdf, "key": key, "vocab": vocab} for lg, pdf, key, vocab in a.langue}
        for opt, cle in ((a.zones, "zones"), (a.gabarit, "gabarit")):
            for lg, f in opt:
                if lg.lower() not in langues:
                    ap.error(f"--{cle} {lg} : langue absente des --langue")
                langues[lg.lower()][cle] = f
        try:
            p, resume = importer_fichiers(a.nom, a.titre or a.nom, langues, racine=a.examens, autres=a.autre)
        except ValueError as err:
            print(f"Import refusé : {err}")
            return 1
        print(f"Examen importé : {p.dir}\n{resume}")
        return 0
    if a.cmd == "verif-zones":
        from .verif_zones import run as vzrun
        return vzrun(a.pdf, a.zones, a.sortie, a.tolerance)
    if a.cmd == "transcrire":
        from .lecteur_code import run as trun
        return trun(a.dossiers, a.champ, a.limite, a.local, a.refaire)
    if a.cmd == "simulate":
        from .simulate import main as smain
        return smain(a)
    if a.cmd == "evaluate":
        from pathlib import Path

        from .evaluate import main as emain
        from .pipeline import Processor
        lot = Path(a.lot)
        copies = Processor(a.template, a.blank).run([str(lot / "scans.pdf")], str(lot / "lu"))
        print(f"{len(copies)} copie(s) lue(s) -> {lot / 'lu'}")
        return emain(lot / "lu", lot / "truth.json")


if __name__ == "__main__":
    sys.exit(main())
