"""Notes finales dans un classeur Excel (.xlsx), sans dépendance.

`python -m thessalia excel sorties/booster sorties/supA_1_v3 [-o sorties/notes/notes.xlsx]`

Feuilles :
  Notes     une ligne par copie identifiée : groupe (celui de la liste), élève, classe où il a composé,
            QCM, réponses courtes, code, total sur 20, réponses encore en attente,
            note arrondie au demi-point supérieur (15,083 → 15,5 ; 15 reste 15)
  Absents   élèves de la liste sans copie
  À vérifier  copies sans élève attribué, ou avec des réponses en attente (jamais une note silencieusement fausse)
Si le fichier de sortie existe déjà, il est d'abord copié en `<nom>.avant-AAAAMMJJ-HHMM.xlsx` (jamais écrasé sans trace).
Le fichier contient des noms d'élèves : il va dans `sorties/` (hors dépôt), jamais dans un partage public.
"""
from __future__ import annotations

import zipfile
import math
import shutil
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


NOTE_MAX = 20     # un barème peut dépasser 20 (Midterm 2026 : q10 à 1 pt, total 20,25) : la note finale est plafonnée


def note_finale(note, arrondi=True):
    """Note du classeur : au demi-point supérieur (règle de l'enseignant, réglable par examen) ou exacte ; max 20."""
    if note is None:
        return None
    return arrondi_demi(note) if arrondi else min(round(note, 2), NOTE_MAX)


def arrondi_demi(note):
    """Arrondi au demi-point supérieur, plafonné à 20. Le passage par 3 décimales évite qu'un 15,0000001 devienne 15,5."""
    if note is None:
        return None
    return min(math.ceil(round(note, 3) * 2) / 2, NOTE_MAX)


def sauvegarder(path, maintenant=None):
    """Copie datée d'un fichier existant avant qu'on le remplace ; renvoie le chemin de la copie (None si rien)."""
    path = Path(path)
    if not path.exists():
        return None
    t = (maintenant or datetime.now()).strftime("%Y%m%d-%H%M")
    copie, i = path.with_name(f"{path.stem}.avant-{t}{path.suffix}"), 2
    while copie.exists():
        copie, i = path.with_name(f"{path.stem}.avant-{t}-{i}{path.suffix}"), i + 1
    shutil.copy2(path, copie)
    return copie


def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref, v, style=0):
    st = f' s="{style}"' if style else ""
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        v = "oui" if v else "non"
    if isinstance(v, (int, float)):
        return f'<c r="{ref}"{st}><v>{round(v, 3)}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{st}><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'


def _feuille(lignes, largeurs):
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(largeurs))
    rows = []
    for r, ligne in enumerate(lignes, 1):
        cells = "".join(_cell(f"{_col(c)}{r}", v, 1 if r == 1 else 0) for c, v in enumerate(ligne))
        rows.append(f'<row r="{r}">{cells}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews>'
            f'<cols>{cols}</cols><sheetData>{"".join(rows)}</sheetData></worksheet>')


def ecrire_xlsx(path, feuilles):
    """feuilles : [(nom, lignes (la première = en-tête), largeurs)]."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = len(feuilles)
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" '
                             'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(n)) + "</Types>")
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",
                   f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook {ns} xmlns:r="{rel}"><sheets>'
                   + "".join(f'<sheet name="{escape(nom[:31])}" sheetId="{i + 1}" r:id="rId{i + 1}"/>'
                             for i, (nom, _, _) in enumerate(feuilles)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i + 1}" Type="{rel}/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                             for i in range(n))
                   + f'<Relationship Id="rId{n + 1}" Type="{rel}/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml",
                   f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet {ns}>'
                   '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
                   '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
                   '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
                   '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
                   '<cellXfs count="2"><xf fontId="0"/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>')
        for i, (_, lignes, largeurs) in enumerate(feuilles):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", _feuille(lignes, largeurs))
    return path


def run(dossiers, sortie="sorties/notes/notes.xlsx", db=None, log=print, arrondi=True):
    """arrondi=False : note finale exacte (2 décimales) au lieu du demi-point supérieur ; plafonnée à 20 dans les deux cas."""
    from .correction import DB_PATH, Classe, Decisions, Memory, group_of
    from .identite import lire_convoques, lire_liste
    from .serve import GROUP_ORDER, _classes

    dec = Decisions(db or DB_PATH)
    exams, notes, verifier, memory = {}, [], [], Memory()
    # mémoire des verdicts : mêmes décisions automatiques que dans l'outil de correction
    classes = [Classe(d, exams, dec, memory=memory) for d in _classes(dossiers)]
    if not classes:
        raise SystemExit("aucune classe lue à exporter")
    if len({str(c.lists_dir) for c in classes}) > 1:
        raise SystemExit("classes de plusieurs examens : exporter chaque examen dans son propre classeur")
    liste = lire_liste(lists_dir=classes[0].lists_dir)
    groupe_de = {e: g for g, eleves in liste.items() for e in eleves}
    memory.rebuild(classes)
    for c in classes:
        attrib = c.students()
        for r in c.notes():
            eleve = r["etudiant"] if r["copie"] in attrib else None
            g = groupe_de.get(eleve) or group_of(c.name)
            hf = r.get("hors_format")
            ligne = [g, eleve or "", c.name, int(r["copie"].split("_")[-1])] \
                + (["", "", ""] if hf else [r["qcm"], r["courtes"], r["code"]]) \
                + [r["total"], r["max"], r["en_attente"], note_finale(r["total"], arrondi)]
            notes.append(ligne)
            if not eleve or r["en_attente"]:
                raison = ("copie sans élève" if not eleve else
                          "copie hors format : note à saisir dans l'outil (0 en attendant)" if hf else
                          "réponses en attente : note provisoire")
                verifier.append([g, eleve or "(non identifiée)", c.name, ligne[3], r["en_attente"], raison])
            elif hf:      # notée à la main : signalée pour mémoire, la note compte
                verifier.append([g, eleve, c.name, ligne[3], 0, "copie hors format, notée à la main"])
    rang = lambda g: GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER)
    notes.sort(key=lambda l: (rang(l[0]), l[1]))
    pris = {l[1] for l in notes if l[1]}
    # session à part (BIS) : seuls les convoqués peuvent être absents ; sinon toute la liste
    convoques = [set(lire_convoques(c.name, c.lists_dir)) for c in classes]
    if any(convoques):
        if not all(convoques):
            raise ValueError("mélange d'une session à part (fichier .convoques.txt) et d'une session normale : "
                             "exporter chaque session dans son propre classeur")
        attendus = set().union(*convoques)
    else:
        attendus = set(groupe_de)
    absents = sorted(([g, e] for g, es in liste.items() for e in es if e in attendus and e not in pris),
                     key=lambda l: (rang(l[0]), l[1]))
    copie = sauvegarder(sortie)
    if copie:
        log(f"Ancien fichier conservé : {copie}")
    p = ecrire_xlsx(sortie, [
        ("Notes", [["Groupe", "Élève", "Classe (composé)", "Copie", "QCM", "Réponses courtes", "Code", "Total",
                    "Sur", "En attente", "Note arrondie (max 20)" if arrondi else "Note finale (max 20)"]] + notes, [8, 32, 16, 7, 7, 10, 7, 8, 6, 10, 12]),
        ("Absents", [["Groupe", "Élève"]] + absents, [8, 32]),
        ("À vérifier", [["Groupe", "Élève", "Classe", "Copie", "En attente", "Raison"]] + verifier,
         [8, 32, 16, 7, 10, 40]),
    ])
    log(f"{len(notes)} copies, {len(absents)} absents, {len(verifier)} à vérifier -> {p}")
    if verifier:
        log("ATTENTION : des notes sont provisoires ou sans élève (feuille « À vérifier »).")
    return p
