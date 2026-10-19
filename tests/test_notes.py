from thessalia.notes import ATTENTE, FAUX, FORME, JUSTE, VIDE, judge


def test_exact_and_teacher_equivalences():
    assert judge("int", "int", "enum") == JUSTE
    assert judge("Error", "ERREUR", "number") == JUSTE      # décision du 14 octobre, toute casse
    assert judge("erreur", "ERREUR", "number") == JUSTE
    assert judge("Zero", "Zéro", "enum") == JUSTE
    assert judge("Bonjour  Alice ", "Bonjour Alice", "text") == JUSTE


def test_decimal_comma_is_wrong():
    assert judge("2,5", "2.5", "number") == FAUX
    assert judge("2.5", "2.5", "number") == JUSTE
    assert judge("43", "42", "number") == FAUX


def test_form_only_is_half_except_exact_output():
    # règle globale du 18 octobre : écart de forme = 50 %, sauf en q7 (affichage exact) où il est faux
    assert judge("grand", "Grand", "enum") == FORME
    assert judge("print()", "print", "enum") == FORME
    assert judge('"427"', "427", "number") == FORME
    assert judge('print("...")', "print", "enum") == FORME   # appel complet au lieu du nom
    assert judge("X Y", "XY", "text") == FAUX
    assert judge("X_Y", "XY", "text") == FAUX
    assert judge("Total: 8", "Total : 8", "text") == FAUX
    assert judge("2.50", "2.5", "number") == FAUX


def test_teacher_decisions_and_missing():
    assert judge("print()", "print", "enum", accept=["print()"]) == JUSTE
    assert judge("Int", "int", "enum", reject=["Int"]) == FAUX
    assert judge("Int", "int", "enum") == FORME
    assert judge("", "int", "enum") == VIDE
    assert judge(None, "int", "enum") == ATTENTE
    assert judge("float", "int", "enum") == FAUX


def test_form_marks_send_to_review():
    from thessalia.ocr_run import form_marks
    assert form_marks("print()", "print")          # accepter `print` noterait 100 % au lieu de 50 %
    assert form_marks('"427"', "427")
    assert not form_marks("print", "print")
    assert not form_marks('"427"', '"427"')


def test_computation_ending_with_the_right_value():
    assert judge("2^10 = 1024", "1024", "number") == JUSTE   # décision du 19 octobre
    assert judge("2^10=1024", "1024", "number") == JUSTE
    assert judge("2^10 = 1152", "1024", "number") == FAUX
    assert judge("x = 2,5", "2.5", "number") == FAUX          # la virgule reste fausse
    assert judge("2^10", "1024", "number") == FAUX
