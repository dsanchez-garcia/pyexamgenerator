"""Reglas comunes de `grading` para texto, columnas y notas (ARC-4).

Antes cada módulo tenía su copia de estos helpers con reglas ligeramente distintas; ahora están en
`pyexamgenerator.grading._text`.
"""

import math

import pandas as pd
import pytest

from pyexamgenerator.grading._text import clean_text, find_column, normalize_key, normalize_text, parse_decimal
from pyexamgenerator.grading.comparison import ResultComparator
from pyexamgenerator.grading.final_grade import FinalGradeCalculator


@pytest.mark.parametrize(
    "value, expected",
    [
        ("  Dirección de Correo ", "direcciondecorreo"),
        ("Apellido(s)", "apellidos"),
        ("Nº", "n"),
        (float("nan"), ""),
        (None, ""),
        (12345678, "12345678"),
    ],
)
def test_normalize_key(value, expected):
    assert normalize_key(value) == expected


def test_normalize_text_keeps_punctuation():
    assert normalize_text("  Calificación/10,00 ") == "calificacion/10,00"
    assert normalize_text(float("nan")) == ""


def test_find_column_tolerates_accents_case_and_mojibake_candidates():
    columns = ["Nombre", "Apellido(s)", "Nmero de ID", "Dirección de correo"]

    assert find_column(columns, ["Número de ID", "Nmero de ID"]) == "Nmero de ID"
    assert find_column(columns, ["apellidos"]) == "Apellido(s)"
    assert find_column(columns, ["DIRECCION DE CORREO"]) == "Dirección de correo"
    assert find_column(columns, ["Email", None, ""]) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        ("7,50", 7.5),
        (" -0,25 ", -0.25),
        ("10", 10.0),
        (8, 8.0),
        (6.5, 6.5),
        ("+3.0", 3.0),
        ("", None),
        ("-", None),
        (None, None),
        (float("nan"), None),
        ("Ausente", None),
        ("nan", None),
        ("inf", None),
        ("1e3", None),
        (True, None),
    ],
)
def test_parse_decimal(value, expected):
    assert parse_decimal(value) == expected


def test_parse_decimal_rejects_non_finite_numbers():
    assert parse_decimal(math.inf) is None


def test_clean_text():
    assert clean_text("  Ana ") == "Ana"
    assert clean_text(float("nan")) == ""
    assert clean_text(None) == ""


def _write(path, records):
    pd.DataFrame(records).to_excel(path, index=False)


_NOTE_ROW = {
    "Número de ID": None,
    "Nombre": None,
    "Apellido(s)": None,
    "Calificación/10,00": None,
    "Observaciones": "Revisado el 3 de febrero",
}


def test_rows_without_id_or_name_are_not_a_student_in_the_final_grade(tmp_path):
    """Una fila sin ID ni nombre (p. ej. una nota al pie) salía como un alumno sin nombre con un 0."""
    source = tmp_path / "teoria.xlsx"
    _write(
        source,
        [
            {
                "Número de ID": "1",
                "Nombre": "Ana",
                "Apellido(s)": "Gil",
                "Calificación/10,00": "8,00",
                "Observaciones": "",
            },
            _NOTE_ROW,
        ],
    )

    df = FinalGradeCalculator().compute_by_files([{"path": str(source), "weight": 1.0}])

    assert df["Nombre"].tolist() == ["Ana"]


def test_rows_without_id_or_name_are_not_compared_as_a_student(tmp_path):
    """La misma fila se comparaba como un alumno («eliminado» si solo estaba en un fichero)."""
    old, new = tmp_path / "old.xlsx", tmp_path / "new.xlsx"
    _write(
        old,
        [
            {
                "Número de ID": "1",
                "Nombre": "Ana",
                "Apellido(s)": "Gil",
                "Calificación/10,00": "8,00",
                "Observaciones": "",
            },
            _NOTE_ROW,
        ],
    )
    _write(
        new,
        [
            {
                "Número de ID": "1",
                "Nombre": "Ana",
                "Apellido(s)": "Gil",
                "Calificación/10,00": "9,00",
                "Observaciones": "",
            },
        ],
    )

    result = ResultComparator().compare(str(old), str(new), overwrite=True)

    assert result.summary["removed"] == 0
    assert result.summary["common"] == 1
    assert result.only_in_existing_df.empty
