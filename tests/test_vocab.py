from thessalia.vocab import normalize, parse_number, snap

TYPES = {"kind": "enum", "values": ["int", "float", "str", "bool", "list", "tuple", "dict"]}
NUM = {"kind": "number", "values": ["ERROR"]}


def test_normalize():
    assert normalize("<class 'int'>") == "int"
    assert normalize("print( )") == "print"
    assert normalize('"42"', "number") == "42"


def test_snap_handwriting_confusions():
    assert snap([("iht", 0.6)], TYPES)["value"] == "int"
    assert snap([("flaot", 0.6)], TYPES)["value"] == "float"
    assert snap([("ERR0R", 0.7)], NUM)["value"] == "ERROR"


def test_wrong_answer_is_not_corrected():
    # « bool » écrit pour "42" doit rester « bool » : le vocabulaire contient les mauvaises réponses
    assert snap([("bool", 0.9)], TYPES)["value"] == "bool"


def test_free_number_is_reviewed():
    assert parse_number("1O24") == "1024"
    # un nombre libre n'est jamais accepté seul, même lu avec une confiance élevée…
    r = snap([("44", 0.99)], NUM)
    assert r["status"] == "review" and r["value"] == "44"
    # … sauf si le vocabulaire du champ fixe un seuil (opt-in)
    assert snap([("44", 0.99)], {**NUM, "min_conf": 0.98})["status"] == "ok"
    assert snap([("44", 0.95)], {**NUM, "min_conf": 0.98})["status"] == "review"
    assert snap([("ERROR", 0.6)], NUM)["status"] == "ok"


def test_comma_is_not_a_point():
    # « 2,5 » est une faute courante en Python : la virgule est conservée, jamais convertie en point
    assert parse_number("2,5") == "2,5" and parse_number("2.5") == "2.5"
    r = snap([("2,5", 0.99)], {**NUM, "min_conf": 0.5})
    # un nombre décimal n'est jamais accepté seul ; la virgule lue est conservée, le point proposé aussi
    assert r["status"] == "review" and r["value"] == "2,5" and r["suggestions"][:2] == ["2,5", "2.5"]
    assert snap([("3", 0.99)], {**NUM, "min_conf": 0.5})["status"] == "ok"


def test_secondary_reading_alone_is_not_accepted():
    # la lecture principale n'a rien du mot retenu : seule une variante du moteur « trouve » le vocabulaire
    r = snap([('" what .', 0.53), ('" What .', 0.42), ('" List .', 0.42)], TYPES)
    assert r["status"] == "review" and r["value"] == "list" and "secondaire" in r["reason"]
    r = snap([("bool", 0.9), ("Error", 0.5)], {"kind": "enum", "values": ["Grand", "Petit", "ERREUR"]})
    assert r["status"] == "review"
    # lecture principale proche du mot retenu : la lecture secondaire peut emporter l'acceptation
    assert snap([("flat .", 0.86), ("feat .", 0.42), ("# float .", 0.36)], TYPES)["status"] == "ok"


def test_text_always_reviewed():
    r = snap([("Hello Alice", 0.99)], {"kind": "text", "values": ["Hello Alice"]})
    assert r["status"] == "review"


def test_trailing_dot_is_ignored():
    # les moteurs entraînés sur des phrases ajoutent un point final (« int . », « 15 . »)
    assert normalize("int .") == "int"
    assert normalize("str.") == "str"
    assert parse_number("15 .") == "15"
    assert parse_number("2. 5 .") == "2.5"
    assert snap([("float .", 0.9)], TYPES)["status"] == "ok"
    # le texte libre garde sa ponctuation
    assert normalize("A-B-C.", "text") == "A-B-C."
