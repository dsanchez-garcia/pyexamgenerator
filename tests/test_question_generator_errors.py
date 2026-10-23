"""Errores de la API de Gemini: reintentos con espera creciente y mensajes útiles (ARC-11, PKG-8)."""

from types import SimpleNamespace

import pymupdf
import pytest
from google.genai import errors

from pyexamgenerator import GeminiRequestError, QuotaExceededError, ServiceOverloadedError
from pyexamgenerator.question_generator import QuestionGenerator


def _api_error(code, status, retry_delay=None):
    details = []
    if retry_delay:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay})
    error_class = errors.ClientError if code < 500 else errors.ServerError
    return error_class(
        code, {"error": {"code": code, "message": f"Error {code}", "status": status, "details": details}}
    )


@pytest.fixture
def waits(monkeypatch):
    recorded = []
    monkeypatch.setattr("pyexamgenerator.question_generator.time.sleep", recorded.append)
    return recorded


def _generator(outcomes, models=()):
    """A QuestionGenerator whose Gemini client returns (text) or raises (exception) ``outcomes``."""
    generator = QuestionGenerator(api_key="dummy", model_name="models/gemini-de-prueba")
    calls = []

    def generate_content(model, contents):
        calls.append(model)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)

    generator.client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=generate_content,
            list=lambda: [SimpleNamespace(name=name) for name in models],
        )
    )
    return generator, calls


def test_overloaded_servers_are_retried_with_increasing_waits(waits):
    """ARC-11: un 503 detenía la generación al primer intento."""
    generator, calls = _generator([_api_error(503, "UNAVAILABLE"), _api_error(503, "UNAVAILABLE"), "respuesta"])

    assert generator._generate_content("prompt").text == "respuesta"
    assert waits == [2, 4]
    assert len(calls) == 3


def test_quota_error_that_persists_after_the_retries(waits):
    generator, calls = _generator([_api_error(429, "RESOURCE_EXHAUSTED") for _ in range(4)])

    with pytest.raises(QuotaExceededError, match="3 veces") as raised:
        generator._generate_content("prompt")

    assert waits == [2, 4, 8]
    assert len(calls) == 4
    assert "gemini-" not in str(raised.value)  # PKG-8: no model names that Google may retire


def test_wait_suggested_by_the_api_is_respected(waits):
    """ARC-11: con un límite por minuto, la API indica cuánto esperar (RetryInfo)."""
    generator, _calls = _generator([_api_error(429, "RESOURCE_EXHAUSTED", retry_delay="30s"), "respuesta"])

    assert generator._generate_content("prompt").text == "respuesta"
    assert waits == [30]


def test_quota_used_up_for_hours_is_not_retried(waits):
    generator, calls = _generator([_api_error(429, "RESOURCE_EXHAUSTED", retry_delay="3600s")])

    with pytest.raises(QuotaExceededError):
        generator._generate_content("prompt")

    assert waits == [] and len(calls) == 1


def test_retired_model_fails_at_once_and_lists_the_available_ones(waits):
    """PKG-8: un modelo retirado (404) se reintentaba en todos los fragmentos; ahora se avisa con
    los modelos disponibles."""
    generator, calls = _generator(
        [_api_error(404, "NOT_FOUND")], models=["models/gemini-nuevo-flash", "models/text-embedding-004"]
    )

    with pytest.raises(GeminiRequestError) as raised:
        generator._generate_content("prompt")

    message = str(raised.value)
    assert "models/gemini-de-prueba" in message and "models/gemini-nuevo-flash" in message
    assert "embedding" not in message
    assert waits == [] and len(calls) == 1


def test_invalid_key_fails_at_once(waits):
    generator, _calls = _generator([_api_error(403, "PERMISSION_DENIED")])

    with pytest.raises(GeminiRequestError, match="GEMINI_API_KEY"):
        generator._generate_content("prompt")

    assert waits == []


def test_other_errors_are_not_retried(waits):
    generator, _calls = _generator([ValueError("respuesta inesperada")])

    with pytest.raises(ValueError, match="respuesta inesperada"):
        generator._generate_content("prompt")

    assert waits == []


def test_overloaded_message_does_not_recommend_a_specific_model():
    message = str(QuestionGenerator._persistent_error(503, 3))

    assert isinstance(QuestionGenerator._persistent_error(503, 3), ServiceOverloadedError)
    assert "gemini-" not in message and "Flash" in message


def test_generation_stops_at_the_first_retired_model_error(tmp_path, waits):
    """Con un modelo retirado, cada fragmento y cada intento repetían la llamada fallida y el
    resultado era «no se generaron preguntas» sin explicar por qué."""
    pdf_paths = []
    for name in ("Tema 1.pdf", "Tema 2.pdf"):
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "La ley de prevencion de riesgos laborales.")
        document.save(str(tmp_path / name))
        document.close()
        pdf_paths.append(str(tmp_path / name))
    generator, calls = _generator([_api_error(404, "NOT_FOUND")])

    with pytest.raises(GeminiRequestError):
        generator.generate_multiple_choice_questions(
            pdf_paths=pdf_paths,
            prompt_type="PRL",
            num_questions_per_chunk_target=2,
            output_dir=str(tmp_path),
            max_generation_attempts_per_chunk=3,
        )

    assert len(calls) == 1
