"""Pré-cochage du code par exécution : réparation tolérée, contrôle du réparateur, tests du sujet B."""
from thessalia.code_tests import charger_tests, garde, precocher_cadre, reparer


def test_reparation_des_fautes_tolerees():
    code = 'Age = int(input("age"))\nIf Age =< 2\n    Print("Gratuit")'
    assert reparer(code) == 'Age = int(input("age"))\nif Age <= 2:\n    print("Gratuit")'
    assert "for x in" in reparer("for x in range(3):\n    print(x x 2)")      # x de boucle gardé, x produit → *
    assert "x * 2" in reparer("for x in range(3):\n    print(x x 2)")


def test_garde_refuse_les_changements_de_logique():
    assert garde("s = int(a * b).", "s = int(a) * int(b)")                     # int( ajouté
    assert garde('if "a" = "b"', "if a == b:")                                  # guillemets enlevés
    assert garde("if a on b", "if a or b:")                                     # opérateur deviné
    assert garde('x = impot("n")\nif x =! 3\n  print(x)', 'x = input("n")\nif x != 3:\n  print(x)') is None
    assert garde('print("degres Celsius :" , c)', 'print("degrés Celsius :", c)') is None


def test_garde_tolere_le_texte_des_invites():
    assert garde('m = int(input("entrez un entier m=))', 'm = int(input("entrez un entier m="))') is None
    assert garde('n = int(input("entrey une valeur"))', 'n = int(input("entrez une valeur"))') is None
    assert garde('n = int(input(quel est votre note ? =))', 'n = int(input("quel est votre note ?"))') is None
    assert garde('print("Ceci n\'est pas un entier =)', 'print("Ceci n\'est pas un entier =")') is None
    assert garde('if note < 0:\n    print(note invalide)', 'if note < 0:\n    print("note invalide")') is None
    assert garde('print(Insuffisant)', 'print("Insuffisant")') is None
    assert garde('x = 3\nprint(x)', 'x = 3\nprint("x")')                             # une variable : refusé
    assert garde('print(note invalide)', 'print("note non valide")')                 # mot changé : refusé
    assert garde('print(a + b)', 'print("a+b")')                                     # calcul : refusé
    assert garde('print("entrey une valeur")', 'print("entrez une valeur")')        # texte affiché : refusé
    assert garde('n = int(input("note")) + m', 'n = int(input("note")) + n')        # hors de l'invite
    assert garde('n = int(input(note))', 'n = int(input(int(note)))')               # du code ajouté


def test_precocher_cadre_sujet_b():
    tests = charger_tests("socle-python-2026-FR-B")
    assert tests and "q15" in tests
    juste = """age = int(input("age"))
if age < 0 or age > 120 :
    print("age invalide")
elif age < 3 :
    print("Gratuit")
elif age <= 12 :
    print("5 €")
elif age <= 17 :
    print("8 €")
elif age <= 59 :
    print("12 €")
else :
    print("7 €")"""
    r = precocher_cadre(juste, "q15", tests)
    assert r["tourne"] and all(r["criteres"].values())
    faux = juste.replace("age <= 17", "age < 17")                             # 17 ans mal placé
    r = precocher_cadre(faux, "q15", tests)
    assert not r["criteres"]["5"] and not r["criteres"]["6"] and r["criteres"]["4"]
    assert precocher_cadre("(vide)", "q15", tests) is None
    assert precocher_cadre("print(1)", "q11.a", tests) is None                  # pas de test : jugement


def test_marqueur_auto_n_est_pas_une_transcription():
    from thessalia.correction import _transcription_enseignant
    assert _transcription_enseignant({"texte": "auto: lecture session"}) is None
    assert _transcription_enseignant({"texte": "auto: vide (encre)"}) is None
    assert _transcription_enseignant({"texte": "print(1)"}) == "print(1)"
    assert _transcription_enseignant(None) is None


def test_verite_du_code_sans_les_lots_auto(tmp_path):
    from types import SimpleNamespace
    from thessalia.correction import Classe, Decisions
    db = Decisions(tmp_path / "d.sqlite")
    db.set("X", "c01_q16", options=["1", "4"], texte="auto: lecture session")       # lot validé : exclu
    db.set("X", "c02_q16", options=["1", "2", "3", "4"])                             # jugé cadre par cadre
    db.set("X", "c03_q16", texte="annee = int(input())")                             # transcription T seule
    db.set("X", "c04_q16", verdict="vide")
    db.set("X", "c01_q3", texte="42")                                                # réponse courte : ignorée
    fake = SimpleNamespace(name="X", decisions=db, exam=SimpleNamespace(bareme={"champs": {"q16": {}}}))
    lab = Classe.code_labels(fake)
    assert lab["transcriptions"] == {"c03_q16": "annee = int(input())"}
    assert lab["criteres"] == {"c02_q16": {"choix": ["1", "2", "3", "4"], "verdict": None},
                               "c04_q16": {"choix": [], "verdict": "vide"}}


def test_second_lecteur_sur_seulement_si_lecture_identique():
    from types import SimpleNamespace
    from thessalia.second_lecteur import sur
    c = SimpleNamespace(exam=SimpleNamespace(clean=lambda a, f: a.strip().lower()))
    it = {"champ": "q3.1"}
    assert sur(c, it, "ERREUR", "Erreur ")
    assert not sur(c, it, "1024", "1029")
    assert not sur(c, it, "2.5", "2.5")              # décimal : toujours en revue
    assert not sur(c, it, "", "(vide)") and not sur(c, it, None, "3")
    q7 = {"champ": "q7.3", "attendu": "XY"}
    assert not sur(c, q7, "X Y", "X Y")                # espace : jugé sur la vignette
    assert not sur(c, {"champ": "q7.1", "attendu": "Bonjour Alice"}, "BonjourAlice", "BonjourAlice")
    assert sur(c, q7, "XY", "XY")


def test_tests_tires_du_corrige():
    from thessalia.code_tests import tests_du_bareme, precocher_cadre
    bar = {"champs": {"q16": {"corrige": 'a = int(input())\nif (a % 4 == 0 and a % 100 != 0) or a % 400 == 0:\n'
                                          '    print("Année bissextile")\nelse:\n    print("Année non bissextile")',
                              "criteres": [{"id": "1", "contient": ["int(input"]},
                                           {"id": "2", "essais": [["2024"], ["2023"], ["1900"]]},
                                           {"id": "3", "essais": [["2000"], ["2024"]], "contient": ["400"]},
                                           {"id": "4"}]}}}
    tests = tests_du_bareme(bar)
    eleve = 'n = int (input("année"))\nif n % 4 == 0 and n % 100 != 0 :\n    print(n, "est bisestile")\nelse :\n    print("pas bisestile")'
    r = precocher_cadre(eleve, "q16", tests)["criteres"]
    assert r == {"1": True, "2": True, "3": False}            # 2000 : « pas » au lieu de « bissextile » ; 4 sans test
    assert all(precocher_cadre(bar["champs"]["q16"]["corrige"], "q16", tests)["criteres"].values())


def test_nombre_cherche_dans_la_bonne_ligne():
    from thessalia.code_tests import _mode
    ref = {"etat": "ok", "saisies": 3, "sortie": "Plus grande valeur : -2\nValeurs paires : 2\n"}
    echo = {"etat": "ok", "saisies": 3, "sortie": "Valeur 1 : -5\nValeur 2 : -2\nPlus grande : 0\nPaires : 2\n"}
    juste = {"etat": "ok", "saisies": 3, "sortie": "max = -2\npaires 2\n"}
    assert not _mode("nombre:1", echo, ref, (set(), set()))        # « -2 » n'est qu'un écho de la saisie
    assert _mode("nombre:2", echo, ref, (set(), set()))
    assert _mode("nombre:1", juste, ref, (set(), set()))           # sans mot commun : n'importe quelle ligne
    moy = {"etat": "ok", "saisies": 1, "sortie": "Moyenne : 7.50\n"}
    assert not _mode("nombre:1", {"etat": "ok", "saisies": 1, "sortie": "Moyenne : 7.5\n"}, moy, (set(), set()))
