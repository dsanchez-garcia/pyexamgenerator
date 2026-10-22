"""Carpeta de configuración del usuario (ARC-12): prompts personalizados, plantilla de exámenes y
fichero alternativo de la clave, nunca en la carpeta desde la que se abre la aplicación.

`tests/conftest.py` lleva la carpeta de configuración a `tmp_path` en todos los tests.
"""

import json
from pathlib import Path

import pytest

from pyexamgenerator import user_config


@pytest.mark.parametrize("platform, environ, expected", [
    ("win32", {"APPDATA": r"C:\Users\ana\AppData\Roaming"}, Path(r"C:\Users\ana\AppData\Roaming") / "pyexamgenerator"),
    ("win32", {}, Path("/home/ana") / "AppData" / "Roaming" / "pyexamgenerator"),
    ("darwin", {}, Path("/home/ana") / "Library" / "Application Support" / "pyexamgenerator"),
    ("linux", {"XDG_CONFIG_HOME": "/home/ana/cfg"}, Path("/home/ana/cfg") / "pyexamgenerator"),
    ("linux", {}, Path("/home/ana") / ".config" / "pyexamgenerator"),
])
def test_config_dir_by_platform(platform, environ, expected):
    assert user_config._config_dir_for(platform, environ, "/home/ana") == expected


def test_json_files_round_trip(tmp_path):
    assert user_config.read_json("ajustes.json") is None

    path = user_config.write_json("ajustes.json", {"Historia": "Genera preguntas de historia."})

    assert path == tmp_path / "configuracion_usuario" / "ajustes.json"
    assert user_config.read_json("ajustes.json") == {"Historia": "Genera preguntas de historia."}


def _write(path, data):
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_old_files_in_the_current_folder_are_moved(tmp_path):
    folder = tmp_path / "trabajo"
    folder.mkdir()
    _write(folder / "custom_prompts.json", {"Historia": "texto antiguo", "Química": "química"})
    _write(folder / "exam_generation_template.json", {"subject": "Física"})
    user_config.write_json("custom_prompts.json", {"Historia": "texto actual", "Biología": "biología"})
    user_config.write_json("exam_generation_template.json", {"subject": "Otra"})

    assert [p.name for p in user_config.find_legacy_files(str(folder))] == [
        "custom_prompts.json", "exam_generation_template.json"]
    moved = user_config.move_legacy_files(str(folder))

    assert moved == (1, 1, True)
    assert user_config.read_json("custom_prompts.json") == {
        "Historia": "texto actual", "Biología": "biología", "Química": "química"}
    assert user_config.read_json("exam_generation_template.json") == {"subject": "Física"}
    assert user_config.find_legacy_files(str(folder)) == []


def test_a_broken_old_file_moves_nothing(tmp_path):
    folder = tmp_path / "trabajo"
    folder.mkdir()
    _write(folder / "custom_prompts.json", {"Química": "química"})
    _write(folder / "exam_generation_template.json", "{no es JSON")

    with pytest.raises(ValueError):
        user_config.move_legacy_files(str(folder))

    assert (folder / "custom_prompts.json").exists() and (folder / "exam_generation_template.json").exists()
    assert user_config.read_json("custom_prompts.json") is None


def test_the_configuration_folder_itself_has_no_old_files():
    user_config.write_json("custom_prompts.json", {"Historia": "texto"})

    assert user_config.find_legacy_files(str(user_config.config_dir())) == []
