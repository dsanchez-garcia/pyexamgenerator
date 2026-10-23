"""Configuración de corrección (`grading_settings.json`, ARC-10): grupos, temas, regla PIR y columnas."""

import json
import os

import pytest

from pyexamgenerator.grading import settings
from pyexamgenerator.grading.settings import GradingSettings, Group


def _write(data):
    path = settings.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_without_a_file_the_values_are_those_of_the_uca():
    current = settings.current_settings()

    assert current == GradingSettings()
    assert current.group_names == ["GIM", "GITI-GIE-GIEI"]
    assert [g.name for g in current.groups_longest_first] == ["GITI-GIE-GIEI", "GIM"]
    assert current.groups[1] == Group("GITI-GIE-GIEI", "GGG", ("GITI", "GIE"))
    assert current.named_topic_names == ["LPRL", "RSP"]
    assert (current.pir_min_quiz_grade, current.pir_bonus_points) == (7.5, 1.0)
    assert settings.moodle_columns("id") == ("Número de ID", "Nmero de ID")
    assert settings.moodle_columns("grade") == ("Calificación/10,00", "Calificacin/10,00")


def test_the_default_file_reads_back_as_the_defaults():
    path = settings.write_default_settings()

    assert path == settings.settings_path()
    assert settings.load_settings(path) == GradingSettings()
    assert json.loads(path.read_text(encoding="utf-8"))["pir"] == {"nota_minima_cuestionario": 7.5, "puntos": 1.0}


def test_write_default_settings_keeps_an_existing_file():
    path = _write({"pir": {"puntos": 0.5}})

    settings.write_default_settings()

    assert json.loads(path.read_text(encoding="utf-8")) == {"pir": {"puntos": 0.5}}


def test_only_the_keys_in_the_file_change():
    _write(
        {
            "grupos": [{"nombre": "A1", "codigo": "AA", "en_nombre_de_fichero": ["A1"]}],
            "temas_con_nombre": {"PRL": r"\bprevencion\b"},
            "pir": {"nota_minima_cuestionario": 5},
            "columnas_moodle": {"id": ["ID number"]},
        }
    )

    current = settings.current_settings()

    assert current.group_names == ["A1"]
    assert current.named_topics == (("PRL", r"\bprevencion\b"),)
    assert (current.pir_min_quiz_grade, current.pir_bonus_points) == (5.0, 1.0)
    assert settings.moodle_columns("id") == ("ID number",)
    assert settings.moodle_columns("first_name") == ("Nombre",)


def test_a_group_without_code_takes_the_letters_of_its_name():
    _write({"grupos": [{"nombre": "Grupo 1"}]})

    assert settings.current_settings().groups == (Group("Grupo 1", "GRUPO", ("Grupo 1",)),)


def test_the_settings_are_read_again_when_the_file_changes():
    path = _write({"pir": {"puntos": 0.5}})
    assert settings.current_settings().pir_bonus_points == 0.5

    path.write_text(json.dumps({"pir": {"puntos": 2}}), encoding="utf-8")
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000_000))

    assert settings.current_settings().pir_bonus_points == 2.0


@pytest.mark.parametrize(
    "data, message",
    [
        ("{no es json", "JSON"),
        ({"grupo": []}, "claves desconocidas: grupo"),
        ({"grupos": [{"nombre": "A1", "codigo": "a-1"}]}, "codigo"),
        ({"grupos": [{"nombre": "G-A"}, {"nombre": "ga"}]}, "repetidos"),
        ({"grupos": [{"nombre": "--"}]}, "letras o cifras"),
        ({"temas_con_nombre": {"Tema 7": "x"}}, "Tema 7"),
        ({"temas_con_nombre": {"T07": "x"}}, "T07"),
        ({"temas_con_nombre": {"PRL": "(sin cerrar"}}, "PRL"),
        ({"pir": {"puntos": "uno"}}, "pir.puntos"),
        ({"columnas_moodle": {"dni": ["DNI"]}}, "columnas_moodle"),
        ({"columnas_moodle": {"id": []}}, "columnas_moodle.id"),
    ],
)
def test_invalid_settings_say_what_is_wrong(data, message):
    path = settings.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match=message) as excinfo:
        settings.load_settings()
    assert str(path) in str(excinfo.value)
