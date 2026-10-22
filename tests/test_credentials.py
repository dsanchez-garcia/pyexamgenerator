"""Dónde se guarda la clave de API de Gemini (SEC-3): almacén de credenciales del sistema.

`tests/conftest.py` sustituye el almacén real por uno en memoria y lleva la carpeta de configuración
del usuario a `tmp_path`: ningún test lee ni escribe la clave real.
"""

import json
import os

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import NoKeyringError

from pyexamgenerator import credentials
from pyexamgenerator.question_generator import QuestionGenerator


class NoKeyring(KeyringBackend):
    """A system without credential store (a Linux server, WSL)."""

    priority = 1

    def get_password(self, service, username):
        raise NoKeyringError("sin almacén de credenciales")

    def set_password(self, service, username, password):
        raise NoKeyringError("sin almacén de credenciales")

    def delete_password(self, service, username):
        raise NoKeyringError("sin almacén de credenciales")


@pytest.fixture(autouse=True)
def no_environment_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_saved_key_goes_to_the_credential_store(memory_keyring):
    saved = credentials.save_api_key("  clave-guardada  ")

    assert saved.encrypted
    assert memory_keyring.passwords == {("pyexamgenerator", "gemini_api_key"): "clave-guardada"}
    assert credentials.get_saved_api_key() == "clave-guardada"
    assert not credentials._key_file().exists()


@pytest.mark.parametrize("key", ["", "   ", "TU_CLAVE_API", None])
def test_empty_key_or_placeholder_is_not_saved(memory_keyring, key):
    with pytest.raises(ValueError):
        credentials.save_api_key(key)

    assert memory_keyring.passwords == {}


def test_environment_variable_comes_before_the_saved_key(monkeypatch):
    credentials.save_api_key("clave-guardada")
    assert credentials.get_api_key() == "clave-guardada"

    monkeypatch.setenv("GEMINI_API_KEY", " clave-de-entorno ")
    assert credentials.get_api_key() == "clave-de-entorno"


def test_without_a_credential_store_the_key_goes_to_the_user_folder(tmp_path):
    keyring.set_keyring(NoKeyring())

    saved = credentials.save_api_key("clave-sin-almacen")

    path = credentials._key_file()
    assert not saved.encrypted
    assert saved.location == str(path)
    assert path.parent == tmp_path / "configuracion_usuario"
    assert json.loads(path.read_text(encoding="utf-8")) == {"gemini_api_key": "clave-sin-almacen"}
    assert credentials.get_saved_api_key() == "clave-sin-almacen"
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_saving_in_the_store_removes_an_unencrypted_copy(memory_keyring):
    keyring.set_keyring(NoKeyring())
    credentials.save_api_key("clave-en-fichero")
    keyring.set_keyring(memory_keyring)

    credentials.save_api_key("clave-en-almacen")

    assert not credentials._key_file().exists()
    assert credentials.get_saved_api_key() == "clave-en-almacen"


def test_delete_api_key():
    credentials.save_api_key("clave")

    assert credentials.delete_api_key() is True
    assert credentials.get_saved_api_key() is None
    assert credentials.delete_api_key() is False


def test_key_saved_by_older_versions_is_found_and_removed(tmp_path):
    legacy = tmp_path / "config.json"
    legacy.write_text(json.dumps({"api_key": " clave-antigua "}), encoding="utf-8")

    assert credentials.find_legacy_api_key(str(tmp_path)) == (legacy, "clave-antigua")
    credentials.remove_legacy_api_key(legacy)
    assert not legacy.exists()


def test_removing_a_legacy_key_keeps_other_settings(tmp_path):
    legacy = tmp_path / "config.json"
    legacy.write_text(json.dumps({"api_key": "clave-antigua", "otro_ajuste": 1}), encoding="utf-8")

    credentials.remove_legacy_api_key(legacy)

    assert json.loads(legacy.read_text(encoding="utf-8")) == {"otro_ajuste": 1}


@pytest.mark.parametrize("content", ['{"api_key": "TU_CLAVE_API"}', '{"api_key": ""}', "no es JSON", "[]"])
def test_no_legacy_key_in_placeholder_or_broken_files(tmp_path, content):
    (tmp_path / "config.json").write_text(content, encoding="utf-8")

    assert credentials.find_legacy_api_key(str(tmp_path)) is None


def test_question_generator_uses_the_saved_key():
    """SEC-3: la librería solo leía GEMINI_API_KEY, así que la clave guardada desde la aplicación no
    servía en scripts y notebooks."""
    credentials.save_api_key("clave-guardada")

    assert QuestionGenerator(model_name="models/test").client.api_key == "clave-guardada"
    assert QuestionGenerator(api_key="explicita", model_name="models/test").client.api_key == "explicita"
