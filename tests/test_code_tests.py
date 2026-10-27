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
