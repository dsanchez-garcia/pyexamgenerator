"""Regresiones del emparejamiento de alumnos por 'Número de ID' (GRD-3, GRD-4)."""

import numpy as np
import pandas as pd
import pytest

from pyexamgenerator.grading._ids import normalize_id
from pyexamgenerator.grading.attendance import AbsenceJustificationManager
from pyexamgenerator.grading.comparison import ResultComparator
from pyexamgenerator.grading.data import EnrollmentMerger
from pyexamgenerator.grading.final_grade import FinalGradeCalculator
from pyexamgenerator.grading.integrations import MoodleGradeIntegrator


@pytest.mark.parametrize(
    "value, expected",
    [
        (12345678, "12345678"),
        (12345678.0, "12345678"),
        ("12345678.0", "12345678"),
        ("001234", "001234"),
        (" X1234567 ", "X1234567"),
        (np.nan, ""),
        (None, ""),
        ("nan", ""),
        ("", ""),
    ],
)
def test_normalize_id(value, expected):
    assert normalize_id(value) == expected


def _write(path, rows):
    pd.DataFrame(rows).to_excel(path, index=False)
    return str(path)


def test_final_grade_matches_ids_read_as_float(tmp_path):
    """GRD-3: un hueco en la columna de ID hace que pandas lea '12345678.0' y partía al alumno."""
    theory = _write(
        tmp_path / "teoria.xlsx",
        [
            {"Número de ID": 12345678, "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 8},
            {"Número de ID": None, "Nombre": "Sin", "Apellido(s)": "Id", "Nota": 5},
        ],
    )
    practice = _write(
        tmp_path / "practicas.xlsx",
        [{"Número de ID": "12345678", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 6}],
    )

    df = FinalGradeCalculator().compute_by_files(
        [{"path": theory, "weight": 1.0, "grade_col": "Nota"}, {"path": practice, "weight": 1.0, "grade_col": "Nota"}]
    )

    ana = df[df["Nombre"] == "Ana"]
    assert len(ana) == 1
    assert ana["Número de ID"].iloc[0] == "12345678"
    assert ana["Nota_Final"].iloc[0] == pytest.approx(7.0)


def test_comparator_matches_ids_read_as_float(tmp_path):
    """GRD-3: la comparación tampoco debe ver altas/bajas por '12345678' frente a '12345678.0'."""
    old = _write(
        tmp_path / "antes.xlsx",
        [
            {"Número de ID": 12345678, "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 5},
            {"Número de ID": None, "Nombre": "Leo", "Apellido(s)": "Ruiz", "Nota": 4},
        ],
    )
    new = _write(
        tmp_path / "despues.xlsx",
        [{"Número de ID": "12345678", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 7}],
    )

    result = ResultComparator().compare(old, new, value_cols=["Nota"])

    assert len(result.changes_df) == 1
    assert result.only_in_new_df.empty
    assert result.only_in_existing_df["Nombre"].tolist() == ["Leo"]


def test_moodle_deduplicate_keeps_students_without_id(tmp_path):
    """GRD-4: deduplicar por ID fusionaba en una sola fila a todos los alumnos sin ID."""
    source = _write(
        tmp_path / "moodle.xlsx",
        [
            {"Número de ID": "111", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "5,00"},
            {"Número de ID": "111", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "7,00"},
            {"Número de ID": "", "Nombre": "Leo", "Apellido(s)": "Ruiz", "Calificación/10,00": "6,00"},
            {"Número de ID": "", "Nombre": "Eva", "Apellido(s)": "Sanz", "Calificación/10,00": "8,00"},
        ],
    )

    result = MoodleGradeIntegrator(xlsx_files=[source]).integrate_grades(deduplicate_by_id=True)

    assert sorted(result["Nombre"]) == ["Ana", "Eva", "Leo"]
    ana = result[result["Nombre"] == "Ana"]
    assert float(ana["Calificación/10,00"].iloc[0]) == pytest.approx(7.0)


def test_enrollment_merger_matches_ids_read_as_float(tmp_path):
    """GRD-3: la matrícula fusionada no debe duplicar a un alumno por '12345678' vs '12345678.0'."""
    gim = _write(
        tmp_path / "matricula_GIM.xlsx",
        [
            {"Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": 12345678, "Consulta": "P1"},
            {"Apellido(s)": "Id", "Nombre": "Sin", "Número de ID": None, "Consulta": "P2"},
        ],
    )
    giti = _write(
        tmp_path / "matricula_GITI.xlsx",
        [{"Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": "12345678", "Consulta": "Sin contestar"}],
    )

    merged = EnrollmentMerger([gim, giti]).merge()

    ana = merged[merged["Nombre"] == "Ana"]
    assert len(ana) == 1
    assert ana["Número de ID"].iloc[0] == "12345678"
    assert len(merged) == 2


def test_attendance_lookup_keys_ignore_missing_ids():
    """GRD-3: un ID vacío se convertía en la clave 'id:nan', compartida por todos los alumnos sin ID,
    de modo que la justificación de uno se aplicaba a los demás."""
    keys_without_id = AbsenceJustificationManager._student_lookup_keys(np.nan, "Ana", "Gil")
    assert not any(key.startswith("id:") for key in keys_without_id)
    assert keys_without_id == ["name:ana_gil"]

    keys_float_id = AbsenceJustificationManager._student_lookup_keys(12345678.0, "Ana", "Gil")
    assert keys_float_id[0] == "id:12345678"
