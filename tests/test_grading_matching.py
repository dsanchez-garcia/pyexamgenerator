"""Emparejamiento de alumnos por nombre en `grading` (GRD-9, GRD-12)."""

import pandas as pd
import pytest

from pyexamgenerator.grading.attendance import AbsenceJustificationManager
from pyexamgenerator.grading.integrations import OcrGradeIntegrator


def test_justification_keys_do_not_depend_on_where_the_full_name_is_split():
    """GRD-9: 'María José García' partido en el primer espacio no coincidía con la matrícula
    ('María José' + 'García'), así que la justificación solo se aplicaba si coincidía el ID."""
    from_summary = AbsenceJustificationManager._student_lookup_keys(None, "María", "José García")
    from_enrollment = AbsenceJustificationManager._student_lookup_keys(None, "María José", "García")

    assert set(from_summary) & set(from_enrollment)


def test_justification_keys_still_distinguish_different_students():
    keys_a = AbsenceJustificationManager._student_lookup_keys(None, "Ana", "Gil")
    keys_b = AbsenceJustificationManager._student_lookup_keys(None, "Ana", "Ruiz")

    assert not set(keys_a) & set(keys_b)


def test_ocr_integration_matches_by_full_name_with_apellidos_column(tmp_path):
    """GRD-12: con la columna 'Apellidos' (sin '(s)') se comparaban apellidos vacíos y la nota OCR
    de 'Ana Ruiz' acababa en la fila de 'Ana Gil'."""
    general = pd.DataFrame(
        [
            {"Número de ID": "", "Apellidos": "Gil", "Nombre": "Ana", "Calificación/10,00": "5,00"},
            {"Número de ID": "", "Apellidos": "Ruiz", "Nombre": "Ana", "Calificación/10,00": "4,00"},
        ]
    )
    ocr = pd.DataFrame(
        [{"Imagen": "hoja.jpg", "Tipo_Examen": "A", "Nombre": "Ana", "Apellidos": "Ruiz",
          "ID_Oficial": "", "Calificacion/10,00": "9,00"}]
    )
    general_path, ocr_path = tmp_path / "teoria.xlsx", tmp_path / "ocr.xlsx"
    general.to_excel(general_path, index=False)
    ocr.to_excel(ocr_path, index=False)

    integrator = OcrGradeIntegrator(general_xlsx_path=str(general_path), ocr_xlsx_path=str(ocr_path))
    result = integrator.integrate(str(tmp_path / "integrada.xlsx"))

    grades = {row["Apellidos"]: float(row["Calificación/10,00"]) for _, row in result.iterrows()}
    assert grades == {"Gil": pytest.approx(5.0), "Ruiz": pytest.approx(9.0)}
    assert integrator.last_integration_summary["rows_matched"] == 1
    assert integrator.last_integration_summary["rows_appended_unmatched"] == 0


def test_name_match_requires_first_and_last_name():
    general_row = pd.Series({"Nombre": "Ana", "Apellido(s)": ""})
    ocr_row = pd.Series({"Nombre": "Ana", "Apellido(s)": ""})

    assert not OcrGradeIntegrator._name_match(general_row, ocr_row)
