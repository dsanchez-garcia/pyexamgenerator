"""Tests del análisis de la respuesta de Gemini en `QuestionGenerator` (sin llamadas a la API)."""

import pytest

from pyexamgenerator.question_generator import QuestionGenerator


@pytest.fixture
def generator():
    gen = QuestionGenerator(api_key="dummy", model_name="models/test")
    gen.rejected_questions_list = []
    return gen


def test_analyze_response_parses_python_literal(generator):
    response = (
        "{'Pregunta': '¿Qué es la PRL?', 'Opciones': ['Uno', 'Dos', 'Tres', 'Cuatro'], "
        "'Respuesta correcta': 'b', 'Texto relevante': 'Fragmento'}"
    )
    questions = generator._analyze_gemini_response(response, "Tema 01")

    assert len(questions) == 1
    question = questions[0]
    assert question["Pregunta"] == "¿Qué es la PRL?"
    assert [question[f"Respuesta {letter}"] for letter in "ABCD"] == ["Uno", "Dos", "Tres", "Cuatro"]
    assert question["Respuesta correcta"] == "B"
    assert question["Estado"] == "Pendiente de revisar"


def test_analyze_response_accepts_json_literals(generator):
    response = (
        '{"Pregunta": "P1", "Opciones": ["a", "b", "c", "d"], "Respuesta correcta": "A", '
        '"Texto relevante": null, "Revisada": false}'
    )
    questions = generator._analyze_gemini_response(response, "Tema 01")

    assert len(questions) == 1
    assert questions[0]["Pregunta"] == "P1"


def test_analyze_response_never_executes_code(generator, tmp_path):
    """SEC-1: una respuesta manipulada no debe ejecutar código (antes se usaba eval)."""
    marker = tmp_path / "pwned.txt"
    payload = "__import__('pathlib').Path(r'%s').write_text('x')" % marker
    response = "{'Pregunta': %s, 'Opciones': ['a', 'b', 'c', 'd'], 'Respuesta correcta': 'A'}" % payload

    questions = generator._analyze_gemini_response(response, "Tema 01")

    assert questions == []
    assert not marker.exists()


def test_analyze_response_keeps_valid_questions_when_one_is_malformed(generator):
    response = "\n\n".join(
        [
            "{'Pregunta': 'Válida 1', 'Opciones': ['a', 'b', 'c', 'd'], 'Respuesta correcta': 'A'}",
            # Solo dos opciones y respuesta correcta numérica: antes lanzaba IndexError/AttributeError.
            "{'Pregunta': 'Corta', 'Opciones': ['a', 'b'], 'Respuesta correcta': 2}",
            "{'Pregunta': 'Válida 2', 'Opciones': ['a', 'b', 'c', 'd'], 'Respuesta correcta': 'c'}",
        ]
    )
    questions = generator._analyze_gemini_response(response, "Tema 01")

    assert [q["Pregunta"] for q in questions] == ["Válida 1", "Corta", "Válida 2"]
    short = questions[1]
    assert short["Respuesta C"] == "" and short["Respuesta D"] == ""
    assert short["Respuesta correcta"] == "2"


def test_api_key_defaults_to_environment_variable(monkeypatch):
    """REPO-4: el ejemplo del README `QuestionGenerator(model_name=...)` lanzaba TypeError."""
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-entorno")

    generator = QuestionGenerator(model_name="models/test")

    assert generator.model_name == "models/test"
    assert generator.client.api_key == "clave-de-entorno"


def test_model_name_is_required():
    with pytest.raises(ValueError, match="model_name"):
        QuestionGenerator(api_key="dummy")
