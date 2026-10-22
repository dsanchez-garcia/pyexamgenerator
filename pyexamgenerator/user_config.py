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

"""The user's configuration folder (ARC-12).

Custom prompts, the exam-tab template and, where the system has no credential store, the API key
(:mod:`pyexamgenerator.credentials`) are kept in one folder per user, not in the folder the
application is started from (they got lost, or copied, when it was started from another folder):

- Windows: ``%APPDATA%\\pyexamgenerator``
- macOS: ``~/Library/Application Support/pyexamgenerator``
- Linux and others: ``$XDG_CONFIG_HOME/pyexamgenerator`` (``~/.config/pyexamgenerator`` by default)

Older versions wrote ``custom_prompts.json`` and ``exam_generation_template.json`` in the current
folder: :func:`find_legacy_files` and :func:`move_legacy_files` let the application move them.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, NamedTuple, Optional

PROMPTS_FILE = "custom_prompts.json"
EXAM_TEMPLATE_FILE = "exam_generation_template.json"
_LEGACY_FILES = (PROMPTS_FILE, EXAM_TEMPLATE_FILE)


def _config_dir_for(platform: str, environ: Mapping[str, str], home: str) -> Path:
    if platform == "win32":
        base = environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return Path(base) / "pyexamgenerator"


def config_dir() -> Path:
    """The user's configuration folder of the application (it may not exist yet)."""
    return _config_dir_for(sys.platform, os.environ, os.path.expanduser("~"))


def config_path(name: str) -> Path:
    """Path of the configuration file ``name`` in :func:`config_dir`."""
    return config_dir() / name


def _read_object(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))  # a JSONDecodeError is a ValueError
    if not isinstance(data, dict):
        raise ValueError(f"{path} no contiene un objeto JSON.")
    return data


def read_json(name: str) -> Optional[Dict[str, Any]]:
    """Contents of the configuration file ``name``, or None if it does not exist.

    Raises:
        ValueError: If the file is not a JSON object.
    """
    path = config_path(name)
    return _read_object(path) if path.exists() else None


def write_json(name: str, data: Mapping[str, Any]) -> Path:
    """Writes the configuration file ``name`` (creating the folder) and returns its path."""
    path = config_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    return path


def _same_folder(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def find_legacy_files(folder: Optional[str] = None) -> List[Path]:
    """Configuration files left by older versions in ``folder`` (the current folder by default)."""
    base = Path(folder or os.getcwd())
    if _same_folder(base, config_dir()):
        return []
    return [base / name for name in _LEGACY_FILES if (base / name).is_file()]


class MovedFiles(NamedTuple):
    """What :func:`move_legacy_files` did."""

    prompts_added: int  # old prompts added to the configuration folder
    prompts_kept: int  # old prompts not added: another one with that name was already there
    template_moved: bool  # the old exam template replaced the one in the configuration folder


def move_legacy_files(folder: Optional[str] = None) -> MovedFiles:
    """Moves the files of :func:`find_legacy_files` to :func:`config_dir` and deletes them.

    Prompts are merged with the ones already in the configuration folder (on the same name, those
    are kept); the exam template replaces the one there, because it is the one the application used
    when started from ``folder``.

    Raises:
        ValueError: If one of the files is not a JSON object. Nothing is moved or deleted then.
    """
    legacy = {path.name: path for path in find_legacy_files(folder)}
    contents = {name: _read_object(path) for name, path in legacy.items()}  # all read before writing
    added = kept = 0
    if PROMPTS_FILE in contents:
        prompts = read_json(PROMPTS_FILE) or {}
        for name, text in contents[PROMPTS_FILE].items():
            if name not in prompts:
                prompts[name] = text
                added += 1
            elif prompts[name] != text:
                kept += 1
        write_json(PROMPTS_FILE, prompts)
    if EXAM_TEMPLATE_FILE in contents:
        write_json(EXAM_TEMPLATE_FILE, contents[EXAM_TEMPLATE_FILE])
    for path in legacy.values():
        path.unlink()
    return MovedFiles(added, kept, EXAM_TEMPLATE_FILE in contents)
