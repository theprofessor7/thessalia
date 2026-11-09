"""Construit le guide PDF : python docs/guide/construire.py  ->  docs/Thessalia_mode_emploi.pdf"""
from pathlib import Path

import typst

ICI = Path(__file__).resolve().parent
sortie = ICI.parent / "Thessalia_mode_emploi.pdf"
typst.compile(str(ICI / "mode_emploi.typ"), output=str(sortie), root=str(ICI))
print(f"-> {sortie}")
