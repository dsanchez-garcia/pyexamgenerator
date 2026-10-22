"""Configuración común de los tests."""

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError


class MemoryKeyring(KeyringBackend):
    """Replaces the system credential store in every test: the tests never read or write the real one
    (on the developer's computer it holds their real Gemini key, SEC-3)."""

    priority = 1

    def __init__(self):
        super().__init__()
        self.passwords = {}

    def get_password(self, service, username):
        return self.passwords.get((service, username))

    def set_password(self, service, username, password):
        self.passwords[(service, username)] = password

    def delete_password(self, service, username):
        if self.passwords.pop((service, username), None) is None:
            raise PasswordDeleteError(username)


@pytest.fixture(autouse=True)
def memory_keyring(monkeypatch, tmp_path):
    """An empty credential store per test, and the user's configuration folder inside ``tmp_path``."""
    from pyexamgenerator import credentials

    store = MemoryKeyring()
    keyring.set_keyring(store)
    monkeypatch.setattr(credentials, "_config_dir", lambda: tmp_path / "configuracion_usuario")
    return store


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
