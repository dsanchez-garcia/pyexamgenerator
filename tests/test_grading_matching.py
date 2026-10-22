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
        [
            {
                "Imagen": "hoja.jpg",
                "Tipo_Examen": "A",
                "Nombre": "Ana",
                "Apellidos": "Ruiz",
                "ID_Oficial": "",
                "Calificacion/10,00": "9,00",
            }
        ]
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


def _integrate(tmp_path, general_rows, ocr_rows):
    general_path, ocr_path = tmp_path / "teoria.xlsx", tmp_path / "ocr.xlsx"
    pd.DataFrame(general_rows).to_excel(general_path, index=False)
    pd.DataFrame(ocr_rows).to_excel(ocr_path, index=False)
    integrator = OcrGradeIntegrator(general_xlsx_path=str(general_path), ocr_xlsx_path=str(ocr_path))
    return integrator, integrator.integrate(str(tmp_path / "integrada.xlsx"))


def test_ocr_grade_replacing_a_moodle_grade_is_reported(tmp_path):
    """GRD-12: la nota OCR sustituía en silencio la nota de Moodle que ya tenía el alumno (hizo
    también el cuestionario en Moodle, o la hoja se asignó a otra persona)."""
    quiz = "Cuestionario:Examen GIM_Tipo 1A (Real)"
    students = [("111", "Ana", "Gil"), ("222", "Leo", "Ruiz"), ("333", "Eva", "Sanz")]
    general = [
        {"Número de ID": i, "Nombre": n, "Apellido(s)": a, quiz: grade}
        for (i, n, a), grade in zip(students, ["7,00", "-", "6,00"])
    ]
    ocr = [
        {
            "Imagen": f"hoja_{n}.jpg",
            "Tipo_Examen": "1A",
            "Número de ID": i,
            "Nombre": n,
            "Apellido(s)": a,
            "Calificacion/10,00": grade,
        }
        for (i, n, a), grade in zip(students, ["5,00", "6,00", "6,00"])
    ]

    integrator, result = _integrate(tmp_path, general, ocr)

    grades = dict(zip(result["Nombre"], result["Calificación/10,00"]))
    assert grades == {"Ana": pytest.approx(5.0), "Leo": pytest.approx(6.0), "Eva": pytest.approx(6.0)}
    incidents = integrator.last_integration_incidents_df
    assert list(incidents["Tipo"]) == ["OVERWRITTEN_GRADE"]
    assert incidents["Imagen"].iloc[0] == "hoja_Ana.jpg"
    assert incidents["Severidad"].iloc[0] == "media"
    assert "7,00 -> 5,00" in incidents["Detalle"].iloc[0]
    assert integrator.last_integration_summary["grades_overwritten"] == 1


def test_overwritten_grades_give_one_incident_per_sheet(tmp_path):
    """GRD-12 (formato general): una hoja que cambia la nota total y las de cada pregunta da una
    sola incidencia, no una por columna."""
    general = [
        {
            "Número de ID": "111",
            "Nombre": "Ana",
            "Apellido(s)": "Gil",
            "Calificación/10,00": "4,00",
            "P. 1 /5,00": "2,00",
            "P. 2 /5,00": "2,00",
        }
    ]
    ocr = [
        {
            "Imagen": "hoja.jpg",
            "Tipo_Examen": "A",
            "Número de ID": "111",
            "Nombre": "Ana",
            "Apellido(s)": "Gil",
            "Calificacion/10,00": "9,00",
            "P. 1 /5,00": "5,00",
            "P. 2 /5,00": "4,00",
        }
    ]

    integrator, result = _integrate(tmp_path, general, ocr)

    assert float(result["Calificación/10,00"].iloc[0]) == pytest.approx(9.0)
    incidents = integrator.last_integration_incidents_df
    assert list(incidents["Tipo"]) == ["OVERWRITTEN_GRADE"]
    assert integrator.last_integration_summary["grades_overwritten"] == 1


def test_same_grade_again_is_not_an_incident(tmp_path):
    general = [{"Número de ID": "111", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "6,00"}]
    ocr = [
        {
            "Imagen": "hoja.jpg",
            "Tipo_Examen": "A",
            "Número de ID": "111",
            "Nombre": "Ana",
            "Apellido(s)": "Gil",
            "Calificacion/10,00": "6",
        }
    ]

    integrator, _result = _integrate(tmp_path, general, ocr)

    assert integrator.last_integration_incidents_df.empty
    assert integrator.last_integration_summary["grades_overwritten"] == 0
