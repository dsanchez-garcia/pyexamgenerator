"""Emparejamiento seguro de un nombre escrito con la matrícula (GRD-6).

Ningún umbral de parecido distingue una errata de otra persona («Mario» frente a «María» puntúan
0,94): solo se asigna el mismo nombre en cualquier orden o el único alumno que contiene todas las
palabras; lo demás devuelve el candidato más parecido para revisarlo.
"""

import pytest

from pyexamgenerator.grading._names import AMBIGUOUS, CONTAINED, EXACT, NONE, match_name, name_words

ENROLLED = ["María García López", "Pedro Sánchez Ruiz", "Laura Martín Pérez", "Ana María Gil Ruiz"]


def test_name_words_ignore_order_accents_case_and_punctuation():
    assert name_words("GARCÍA LÓPEZ, María") == name_words("maria garcia lopez") == ("garcia", "lopez", "maria")


@pytest.mark.parametrize("written, expected", [
    ("María García López", 0),
    ("GARCIA LOPEZ, MARIA", 0),        # «Apellidos, Nombre» from the mail client
    ("garcía lópez maría", 0),
    ("Pedro Sánchez Ruiz", 1),
])
def test_same_name_in_any_order_is_assigned(written, expected):
    match = match_name(written, ENROLLED)

    assert (match.position, match.kind, match.score) == (expected, EXACT, 1.0)


@pytest.mark.parametrize("written, expected", [("María García", 0), ("Ana Gil Ruiz", 3), ("Laura Pérez", 2)])
def test_fewer_words_are_assigned_to_the_only_student_containing_them(written, expected):
    match = match_name(written, ENROLLED)

    assert (match.position, match.kind) == (expected, CONTAINED)


@pytest.mark.parametrize("written, candidate", [
    ("Mario García López", 0),         # another person, 0.94 against María
    ("Pablo Sánchez Ruiz", 1),         # sibling
    ("Laura Martín Gómez", 2),         # same first name and first surname
    ("Maria Garcia Lopes", 0),         # a typo: also not assigned automatically
])
def test_similar_names_are_not_assigned_but_reported_with_a_candidate(written, candidate):
    match = match_name(written, ENROLLED)

    assert match.position is None and match.kind == NONE
    assert match.candidate == candidate and 0.6 < match.score < 1.0


def test_names_fitting_several_students_are_not_assigned():
    enrolled = ["María García López", "María García Pérez"]

    assert match_name("María García", enrolled)[:2] == (None, AMBIGUOUS)
    assert match_name("María García López", enrolled + ["María García López"])[:2] == (None, AMBIGUOUS)


def test_one_word_is_never_enough():
    assert match_name("María", ["María García López"]).position is None


@pytest.mark.parametrize("written", ["", "   ", None, float("nan")])
def test_empty_names(written):
    assert match_name(written, ENROLLED) == (None, NONE, None, 0.0)


def test_no_enrolled_students():
    assert match_name("María García", []) == (None, NONE, None, 0.0)
