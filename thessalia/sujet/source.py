"""Lecture stricte d'un fichier de sujet YAML (docs/FORMAT_SUJET.md, § 2).

Le YAML est lu SANS conversion automatique : toute valeur est un texte, tel qu'il est écrit (`12.50` reste
`12.50`, `True` reste `True`). Chaque valeur garde son numéro de ligne, pour que les erreurs disent où corriger.
Une clé écrite deux fois et une tabulation sont refusées ici ; le reste est contrôlé par `modele`.
"""
from __future__ import annotations

from pathlib import Path

import yaml


class ErreurSujet(Exception):
    """Fichier refusé ; `erreurs` : messages lisibles, avec leur ligne."""

    def __init__(self, erreurs):
        self.erreurs = list(erreurs)
        super().__init__("\n".join(self.erreurs))


class Texte(str):
    ligne: int = 0
    guillemets: bool = False   # écrit entre guillemets doubles (interprète \n)
    commentaire: str = ""      # « # … » juste après un texte sans guillemets : YAML l'a coupé là


class Table(dict):
    ligne: int = 0
    source: str = ""           # le texte tel qu'écrit (pour proposer la correction d'une réponse mal écrite)
    lignes: dict              # ligne de chaque clé


class Liste(list):
    ligne: int = 0
    source: str = ""


def charger(chemin) -> Table:
    texte = Path(chemin).read_text(encoding="utf-8")
    return charger_texte(texte)


def charger_texte(texte: str) -> Table:
    erreurs = [f"ligne {i} : tabulation ; utilisez des espaces pour l'indentation"
               for i, l in enumerate(texte.splitlines(), 1) if "\t" in l]
    if erreurs:
        raise ErreurSujet(erreurs)
    try:
        noeud = yaml.compose(texte, Loader=yaml.BaseLoader)
    except yaml.YAMLError as e:
        m = getattr(e, "problem_mark", None)
        pb = str(getattr(e, "problem", e))
        aide = {"mapping values are not allowed here":
                "un texte contient « : » suivi d'une espace (fréquent en français : « Complétez : ») ; "
                "mettez tout le texte entre guillemets",
                "found character '\t' that cannot start any token": "tabulation ; utilisez des espaces"}
        conseil = next((v for k, v in aide.items() if k in pb), None)
        if conseil is None and ("expected ',' or '}'" in pb or "expected ',' or ']'" in pb):
            conseil = ("entre accolades { } ou crochets [ ], mettez chaque texte entre guillemets "
                       "(une virgule, un « ? » ou un « : » y coupent le texte)")
        if conseil is None and "expected <block end>" in pb:
            conseil = "indentation incohérente, ou texte commençant par un caractère spécial ([ { ' \" * & ! | > %) : entre guillemets"
        raise ErreurSujet([f"ligne {m.line + 1 if m else '?'} : " + (conseil or f"YAML illisible ({pb})")]) from None
    if noeud is None:
        raise ErreurSujet(["fichier vide"])
    erreurs = []
    racine = _convertir(noeud, texte, erreurs)
    if erreurs:
        raise ErreurSujet(erreurs)
    if not isinstance(racine, Table):
        raise ErreurSujet(["ligne 1 : le fichier doit commencer par des clés (format:, examen:, exercices:)"])
    return racine


def _convertir(n, texte, erreurs):
    ligne = n.start_mark.line + 1
    if isinstance(n, yaml.ScalarNode):
        t = Texte(n.value)
        t.ligne, t.guillemets = ligne, n.style == '"'
        if n.style is None:
            reste = texte[n.end_mark.index:].split("\n", 1)[0]
            if reste.lstrip().startswith("#"):
                t.commentaire = reste.strip()
        return t
    source = texte[n.start_mark.index:n.end_mark.index]
    if isinstance(n, yaml.SequenceNode):
        out = Liste(_convertir(x, texte, erreurs) for x in n.value)
        out.ligne, out.source = ligne, source
        return out
    out = Table()
    out.ligne, out.source, out.lignes = ligne, source, {}
    for k, v in n.value:
        cle = k.value if isinstance(k, yaml.ScalarNode) else str(k)
        if cle in out:
            erreurs.append(f"ligne {k.start_mark.line + 1} : clé « {cle} » écrite deux fois "
                           f"(la première est ligne {out.lignes[cle]})")
            continue
        out[cle] = _convertir(v, texte, erreurs)
        out.lignes[cle] = k.start_mark.line + 1
    return out
