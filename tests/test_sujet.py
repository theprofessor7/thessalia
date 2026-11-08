"""Source unique d'un sujet (docs/FORMAT_SUJET.md) : contrôle strict et corrigé produit."""
import pytest

from thessalia.sujet.corrige import confronter, fichiers
from thessalia.sujet.modele import examen_texte
from thessalia.sujet.source import ErreurSujet

SUJET = """\
format: thessalia-sujet/1
examen:
  id: ESSAI
  langues: [fr, en]
  titre: {fr: Essai, en: Test}
  points: 2
exercices:
  - titre: Listes
    questions:
      - type: blancs
        points: 0.75
        enonce: {fr: 'Donnez les deux lignes :', en: 'Give both lines:'}
        lignes:
          - '[[liste:long]]'
          - '[[n:court]]'
        blancs:
          liste: {attendu: '[14, 16, 10]', points: 0.5,
                  tolerances: [espaces_virgules, {liste_incomplete: {manque_max: 1, points: 0.25}}]}
          n: {attendu: '3', nature: nombre, points: 0.25}
      - type: blancs
        points: 0.5
        enonce: {fr: 'Affichage : [[v]]', en: 'Output: [[v]]'}
        blancs:
          v: {attendu: {fr: 'Bonjour, Alice !', en: 'Hello, Alice!'}, tolerances: [guillemets, espace_ponctuation]}
      - type: qcm
        points: 0.25
        enonce: Quelle valeur ?
        choix: ['`12.50`', '`True`']
        bonne: a
      - type: vrai_faux
        points: 0.5
        enonce: {fr: 'Vrai ou faux ?', en: 'True or false?'}
        affirmations:
          - {texte: A, reponse: V}
          - {texte: B, reponse: F}
"""


def _erreurs(texte):
    with pytest.raises(ErreurSujet) as e:
        examen_texte(texte)
    return "\n".join(e.value.erreurs)


def test_sujet_valide_et_corrige():
    ex = examen_texte(SUJET)
    assert [q.num for q in ex.questions()] == [1, 2, 3, 4] and ex.points == 2
    key, vocab, bareme = fichiers(ex, "fr", "ESSAI_FR", "essai.yaml")
    assert key["short_answers"] == {"q1.1": "[14, 16, 10]", "q1.2": "3", "q2": "Bonjour, Alice !"}
    assert set(key["short_accept"]["q1.1"]) == {"[14,16,10]"}
    assert set(key["short_partiel"]["q1.1"]) == {"[16, 10]", "[14, 10]", "[14, 16]", "[16,10]", "[14,10]", "[14,16]"}
    assert set(key["short_accept"]["q2"]) == {"Bonjour, Alice!", '"Bonjour, Alice !"', "'Bonjour, Alice !'",
                                              '"Bonjour, Alice!"', "'Bonjour, Alice!'"}
    assert key["points_champs"] == {"q1.1": 0.5, "q1.2": 0.25}
    assert key["answers"] == {"q3": ["a"], "q4.1": ["V"], "q4.2": ["F"]}
    assert vocab["fields"]["q1.2"] == {"kind": "number"} and bareme is None
    en, _, _ = fichiers(ex, "en", "ESSAI_EN", "essai.yaml", traduction_de="ESSAI_FR")
    assert en["short_answers"]["q2"] == "Hello, Alice!" and en["answers"]["q4.1"] == ["T"]
    assert en["traduction_de"] == "ESSAI_FR"


def test_lecture_sans_conversion():
    ex = examen_texte(SUJET.replace("attendu: '3'", "attendu: 3.50"))      # sans guillemets : reste « 3.50 »
    assert ex.questions()[0].donnees["blancs"][1].attendu == {"fr": "3.50", "en": "3.50"}


@pytest.mark.parametrize("avant, apres, attendu", [
    ("attendu: '[14, 16, 10]'", "attendu: [14, 16, 10]", "lue comme une liste ; écrivez-la entre guillemets simples : '[14, 16, 10]'"),
    ("attendu: '3'", "attendu: {n}", "lue comme une structure"),
    ("nature: nombre", "natur: nombre", "clé inconnue « natur » (vouliez-vous « nature » ?)"),
    ("titre: {fr: Essai, en: Test}", "titre: {fr: Essai}", "texte manquant en en"),
    ("nature: nombre, points: 0.25}", "nature: nombre, points: 0.3}", "les points ne tombent pas juste (0,8 au lieu de 0,75)"),
    ("bonne: a", "bonne: [a, b]", "exactement une bonne réponse"),
    ("'[[n:court]]'", "'[[m:court]]'", "le blanc « n » est défini mais jamais placé"),
    ("Quelle valeur ?", "Quelle valeur : celle-ci ?", "« : » suivi d'une espace"),
    ("enonce: Quelle valeur ?", "enonce: Le signe # coupe", "YAML prend « # » pour un commentaire"),
    ("  points: 2\n", "  points: 2\n  points: 3\n", "écrite deux fois"),
    ("tolerances: [guillemets, espace_ponctuation]", "tolerances: [guillemet]", "tolérance inconnue"),
    ("{fr: 'Vrai ou faux ?', en: 'True or false?'}", "{fr: Vrai ou faux ?, en: True or false?}",
     "mettez chaque texte entre guillemets"),
    ("{fr: 'Affichage : [[v]]', en: 'Output: [[v]]'}", "{fr: 'Affichage : [[v]]', en: 'Output: ...'}",
     "les blancs ne sont pas les mêmes"),
])
def test_refus_lisibles(avant, apres, attendu):
    assert avant in SUJET
    assert attendu in _erreurs(SUJET.replace(avant, apres, 1))


def test_confronter_au_gabarit():
    ex = examen_texte(SUJET)
    gab = {"questions": [{"num": 1, "points": 0.75}, {"num": 2, "points": 0.5}, {"num": 3, "points": 0.5}],
           "pages": [{"fields": [{"id": "q1.1", "type": "short_text"}, {"id": "q1.2", "type": "short_text"},
                                 {"id": "q2", "type": "mcq"}, {"id": "q3", "type": "mcq"},
                                 {"id": "q4.1", "type": "truefalse"}, {"id": "q4.2", "type": "truefalse"},
                                 {"id": "q5", "type": "mcq"}]}]}
    err = "\n".join(confronter(ex, gab))
    assert "q2 est « mcq »" in err and "question 3 : 0,25 pt dans la source, 0,5 pt" in err and "q5" in err
