"""Configuración común de los tests."""

import pytest


class OfflineGeminiClient:
    """Replaces ``google.genai.Client`` in every test: the tests never use the real API (TST-8).

    It only records the key it receives. A test that needs answers from Gemini assigns its own fake
    to ``QuestionGenerator.client`` (see ``tests/test_question_generator_flow.py``).
    """

    def __init__(self, api_key=None, **kwargs):
        self.api_key = api_key
        self.models = self

    def generate_content(self, *args, **kwargs):
        raise AssertionError("Los tests no deben llamar a la API de Gemini: simula la respuesta.")

    def list(self, *args, **kwargs):
        raise AssertionError("Los tests no deben llamar a la API de Gemini: simula la respuesta.")


@pytest.fixture(autouse=True)
def offline_gemini_client(monkeypatch):
    try:
        from google import genai
    except ImportError:  # google-genai is a required dependency; nothing to replace without it
        return None
    monkeypatch.setattr(genai, "Client", OfflineGeminiClient)
    return OfflineGeminiClient
