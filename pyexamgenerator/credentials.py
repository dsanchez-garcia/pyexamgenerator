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

"""Where the Gemini API key is kept (SEC-3).

The key in use (:func:`get_api_key`) is the ``GEMINI_API_KEY`` environment variable or, if it is not
set, the key saved with :func:`save_api_key`. The key is saved encrypted in the system credential
store through ``keyring`` (Windows Credential Manager, macOS Keychain, Secret Service on Linux).
Where there is no store (a Linux server, WSL), it goes unencrypted to a file in the user's
configuration folder that only they can read.

Older versions wrote the key unencrypted to ``config.json`` in the folder the application was started
from: :func:`find_legacy_api_key` finds it so the application can offer to move it.
"""

import json
import os
import sys
from pathlib import Path
from typing import NamedTuple, Optional, Tuple

import keyring

ENV_VAR = "GEMINI_API_KEY"
PLACEHOLDER = "TU_CLAVE_API"  # shown in the GUI's empty key field: never a key
_SERVICE = "pyexamgenerator"
_ACCOUNT = "gemini_api_key"
_KEY_FILE_NAME = "credentials.json"
_LEGACY_FILE_NAME = "config.json"


class SavedKey(NamedTuple):
    """Where :func:`save_api_key` left the key."""

    encrypted: bool  # True: system credential store; False: file in the user's configuration folder
    location: str  # name of the store, or path of the file


def _clean(key: object) -> Optional[str]:
    text = "" if key is None else str(key).strip()
    return text if text and text != PLACEHOLDER else None


def _config_dir() -> Path:
    """The user's configuration folder for the application (never the current folder)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "pyexamgenerator"


def _key_file() -> Path:
    return _config_dir() / _KEY_FILE_NAME


def _store_name() -> str:
    if sys.platform == "win32":
        return "Administrador de credenciales de Windows"
    if sys.platform == "darwin":
        return "Llavero de macOS"
    return "almacén de claves del sistema"


def _read_key_file() -> Optional[str]:
    try:
        data = json.loads(_key_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _clean(data.get(_ACCOUNT)) if isinstance(data, dict) else None


def _write_key_file(key: str) -> Path:
    path = _key_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Readable only by the user (on Windows the folder already belongs to the user).
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({_ACCOUNT: key}, handle)
    os.chmod(path, 0o600)  # also when the file already existed
    return path


def get_saved_api_key() -> Optional[str]:
    """The key saved with :func:`save_api_key` (system store first, then the user's file), or None."""
    try:
        key = _clean(keyring.get_password(_SERVICE, _ACCOUNT))
    except Exception:  # noqa: BLE001 - no usable store (no backend, locked keyring, no D-Bus…)
        key = None
    return key or _read_key_file()


def get_api_key() -> Optional[str]:
    """The key to use: the ``GEMINI_API_KEY`` environment variable, else the saved key, else None."""
    return _clean(os.environ.get(ENV_VAR)) or get_saved_api_key()


def save_api_key(key: str) -> SavedKey:
    """Saves ``key`` encrypted in the system credential store, or in the user's file if there is none.

    Raises:
        ValueError: If ``key`` is empty or the GUI's placeholder.
    """
    clean = _clean(key)
    if not clean:
        raise ValueError("La clave de API está vacía.")
    try:
        keyring.set_password(_SERVICE, _ACCOUNT, clean)
    except Exception:  # noqa: BLE001 - no usable store: the user's file instead (reported to the caller)
        return SavedKey(encrypted=False, location=str(_write_key_file(clean)))
    _key_file().unlink(missing_ok=True)  # an unencrypted copy from a machine without a store
    return SavedKey(encrypted=True, location=_store_name())


def delete_api_key() -> bool:
    """Deletes the saved key from the store and from the user's file. True if there was one."""
    deleted = False
    try:
        keyring.delete_password(_SERVICE, _ACCOUNT)
        deleted = True
    except Exception:  # noqa: BLE001 - not saved in the store, or no usable store
        pass
    path = _key_file()
    if path.exists():
        path.unlink()
        deleted = True
    return deleted


def find_legacy_api_key(folder: Optional[str] = None) -> Optional[Tuple[Path, str]]:
    """``(path, key)`` of a key saved unencrypted by older versions in ``config.json`` of ``folder``.

    ``folder`` defaults to the current folder, where those versions wrote it. None if there is none.
    """
    path = Path(folder or os.getcwd()) / _LEGACY_FILE_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    key = _clean(data.get("api_key")) if isinstance(data, dict) else None
    return (path, key) if key else None


def remove_legacy_api_key(path: Path) -> None:
    """Removes the key from an old ``config.json``; the file goes away if the key was all it held."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("api_key", None)
    if data:
        path.write_text(json.dumps(data), encoding="utf-8")
    else:
        path.unlink()
