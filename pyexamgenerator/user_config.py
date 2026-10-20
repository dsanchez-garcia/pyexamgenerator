# pyexamgenerator: A tool for generating exams from PDF files using AI.
# Copyright (C) 2024 Daniel Sánchez-García

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Per-user configuration files of the application.

The settings are kept in a per-user folder, so they are found whatever folder the
application is launched from and they are not left in the (often cloud-synced)
working folders:

* Windows: ``%APPDATA%\\pyexamgenerator``
* macOS and Linux: ``~/.config/pyexamgenerator``

The AI configuration (selected provider, and API key and model of each provider) is
the ``config.json`` file of that folder, readable only by the user where the system
supports it. Previous versions saved it in the ``config.json`` of the working folder:
that file is still read while the per-user one does not exist, and its content is
copied to the per-user file the next time the configuration is saved (the old file is
neither modified nor deleted).

Nothing in this module depends on Tkinter.
"""

import contextlib
import json
import os
import tempfile
from typing import Any, Dict, Optional, Tuple

from .ai_providers import DEFAULT_PROVIDER, PROVIDERS, is_valid_api_key, resolve_provider

#: Name of the per-user settings folder.
APP_DIR_NAME = "pyexamgenerator"

#: Name of the AI configuration file.
AI_CONFIG_FILENAME = "config.json"


def get_user_config_dir() -> str:
    """
    Returns the per-user settings folder (without creating it).

    ``%APPDATA%\\pyexamgenerator`` on Windows and ``~/.config/pyexamgenerator`` elsewhere.
    """
    appdata = os.getenv("APPDATA")
    base = appdata if appdata else os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, APP_DIR_NAME)


def ensure_user_config_dir() -> str:
    """
    Creates the per-user settings folder if needed and returns its path.

    Raises:
        OSError: If the folder cannot be created.
    """
    path = get_user_config_dir()
    os.makedirs(path, exist_ok=True)
    return path


def get_ai_config_path() -> str:
    """Returns the path of the per-user AI configuration file, where it is saved."""
    return os.path.join(get_user_config_dir(), AI_CONFIG_FILENAME)


def get_legacy_ai_config_path() -> str:
    """Returns the path of the ``config.json`` of the working folder, used by previous versions."""
    return os.path.abspath(AI_CONFIG_FILENAME)


def read_ai_config_file() -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Reads the AI configuration file as saved, without validating its settings.

    The per-user file is read first; while it does not exist (or cannot be read), the
    legacy ``config.json`` of the working folder is read instead.

    Returns:
        Tuple[Dict[str, Any], Optional[str]]: The content of the first readable file that
        holds a JSON object, and its path; ``({}, None)`` if there is none.
    """
    for path in (get_ai_config_path(), get_legacy_ai_config_path()):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(config, dict):
            return config, path
    return {}, None


def parse_ai_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts the settings used by the application from the content of a configuration file.

    Only the known providers, the valid keys and the non-empty model names are kept. The
    legacy format ``{"api_key": "..."}`` is read as the Gemini key.

    Args:
        config (Dict[str, Any]): Content of the file, as returned by :func:`read_ai_config_file`.

    Returns:
        Dict[str, Any]: ``{"provider": str, "api_keys": {...}, "models": {...}}``.
    """
    api_keys = dict(config["api_keys"]) if isinstance(config.get("api_keys"), dict) else {}
    if config.get("api_key") and not api_keys.get("gemini"):
        api_keys["gemini"] = config["api_key"]
    models = config["models"] if isinstance(config.get("models"), dict) else {}
    try:
        provider = resolve_provider(config.get("provider"))
    except ValueError:
        provider = DEFAULT_PROVIDER
    return {
        "provider": provider,
        "api_keys": {k: v for k, v in api_keys.items() if k in PROVIDERS and is_valid_api_key(v)},
        "models": {k: v for k, v in models.items() if k in PROVIDERS and isinstance(v, str) and v.strip()},
    }


def merge_ai_config(existing: Dict[str, Any], ai_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns the content to save: ``existing`` updated with the settings of ``ai_config``.

    The rest of ``existing`` is kept, such as the keys and models of providers unknown to
    this version (e.g. written by a newer one) or any other setting. The Gemini key is also
    written in the legacy ``api_key`` field, the format of previous versions.

    Args:
        existing (Dict[str, Any]): Current content of the configuration file.
        ai_config (Dict[str, Any]): Settings to save, as returned by :func:`parse_ai_config`.

    Returns:
        Dict[str, Any]: The new content (the arguments are not modified).
    """
    merged = dict(existing)
    api_keys = dict(existing["api_keys"]) if isinstance(existing.get("api_keys"), dict) else {}
    models = dict(existing["models"]) if isinstance(existing.get("models"), dict) else {}
    api_keys.update(ai_config.get("api_keys", {}))
    models.update(ai_config.get("models", {}))
    merged.update({
        "provider": ai_config.get("provider", DEFAULT_PROVIDER),
        "api_keys": api_keys,
        "models": models,
    })
    gemini_key = ai_config.get("api_keys", {}).get("gemini")
    if gemini_key:
        merged["api_key"] = gemini_key
    return merged


def save_ai_config(ai_config: Dict[str, Any]) -> str:
    """
    Saves the AI settings in the per-user configuration file.

    The settings are merged into the current content of the file (see
    :func:`merge_ai_config`). While the per-user file does not exist, the current content
    is that of the legacy ``config.json`` of the working folder, which is thus migrated;
    the legacy file is neither modified nor deleted. The file is replaced atomically and
    made readable only by the user where the system supports it (``chmod 600``).

    Args:
        ai_config (Dict[str, Any]): Settings to save, as returned by :func:`parse_ai_config`.

    Returns:
        str: Path of the saved file.

    Raises:
        OSError: If the file cannot be written.
    """
    existing, _ = read_ai_config_file()
    path = os.path.join(ensure_user_config_dir(), AI_CONFIG_FILENAME)
    _write_private_json(path, merge_ai_config(existing, ai_config))
    return path


def _write_private_json(path: str, data: Dict[str, Any]) -> None:
    """Writes ``data`` as JSON to ``path`` through a temporary file, readable only by the user."""
    # mkstemp crea el temporal con permisos 0o600 (en Windows protege la propia carpeta del usuario),
    # así que la clave no es legible por otros usuarios en ningún momento, y un fallo a mitad de la
    # escritura no deja un config.json cortado.
    fd, tmp_path = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        raise
    try:
        os.chmod(path, 0o600)
    except (OSError, NotImplementedError):
        pass  # Sistemas de archivos sin permisos POSIX.
