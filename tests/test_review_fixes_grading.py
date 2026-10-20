"""Pruebas de regresión de la revisión del subpaquete `pyexamgenerator.grading` (GR-1 .. GR-23).

Cada prueba reproduce un fallo confirmado en la revisión y comprueba el comportamiento corregido.
Las que usan el OCR (cv2/rapidocr) se saltan si el extra `[grading]` no está instalado, y las de la
interfaz se saltan si no hay tkinter (no crean ninguna ventana: usan variables simuladas).
"""

import os
import types

import numpy as np
import pandas as pd
import pytest

from pyexamgenerator import grading
from pyexamgenerator.exam_generator import ExamGenerator
from pyexamgenerator.grading import (
    EnrollmentMerger,
    ExamGrader,
    OcrGradeIntegrator,
    SharedExamDataStore,
    TheoryBonusApplier,
)
from pyexamgenerator.grading._ids import is_empty_id, normalize_id
from pyexamgenerator.grading.api import ExamCorrectionAPI, ExcelGradingConfig
from pyexamgenerator.grading.attendance import AbsenceJustificationManager
from pyexamgenerator.grading.comparison import ResultComparator
from pyexamgenerator.grading.data import _detect_macro_group
from pyexamgenerator.grading.final_grade import FinalGradeCalculator
from pyexamgenerator.grading.session import GradingSession


# --- Helpers -----------------------------------------------------------------------------------

def _write(path, records):
    pd.DataFrame(records).to_excel(path, index=False)
    return str(path)


def _xml(correct_letters, penalty=-25):
    """Plantilla Moodle con letras a/b/c/d como texto de respuesta (formato por defecto)."""
    questions = []
    for number, correct in enumerate(correct_letters, start=1):
        answers = "".join(
            f'<answer fraction="{100 if letter == correct else penalty}"><text>{letter}</text></answer>'
            for letter in "abcd"
        )
        questions.append(
            f'<question type="multichoice"><name><text>Pregunta {number:02d}</text></name>{answers}</question>'
        )
    return f'<?xml version="1.0" encoding="UTF-8"?><quiz>{"".join(questions)}</quiz>'


def _write_xml(path, correct_letters):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_xml(correct_letters), encoding="utf-8")
    return str(path)


def _roster(path, students):
    """Matrícula canónica: students = [(apellidos, nombre, id, correo), ...]."""
    return _write(path, [
        {"Apellido(s)": last, "Nombre": first, "Número de ID": sid, "Dirección de correo": email}
        for last, first, sid, email in students
    ])


def _write_attendance(path, year, header, rows):
    """Exportación de asistencia de Moodle: 3 filas de informe y la cabecera en la fila 3."""
    session_col = f"10 feb {year} 10:00 Todos los estudiantes"
    full_header = [session_col if h == "SESION" else h for h in header]
    width = len(full_header)
    data = [["Informe"] + [""] * (width - 1), [""] * width, [""] * width, full_header] + rows
    pd.DataFrame(data).to_excel(path, index=False, header=False)
    return str(path)


def _write_schedule(path, year):
    return _write(path, [{
        "Fecha de Inicio": f"{year}-02-10 10:00", "Descripción": "Tema 2 Riesgos", "Título (EDITABLE)": "Clase GIM",
    }])


_QUIZ_COL = "Cuestionario:Cuestionario Tema 2 - GIM (Real)"


# --- Shared ID normalisation (GR-4 / GR-5 / GR-7) ----------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, ""), (np.nan, ""), (pd.NA, ""), ("", ""), ("  ", ""), ("nan", ""), ("NaN", ""), ("None", ""),
        ("<NA>", ""), (11111111, "11111111"), (11111111.0, "11111111"), (np.float64(4444.0), "4444"),
        (np.int64(7), "7"), ("11111111.0", "11111111"), ("001234", "001234"), (" 12345678A ", "12345678A"),
        (12.5, "12.5"),
    ],
)
def test_normalize_id(raw, expected):
    assert normalize_id(raw) == expected
    assert is_empty_id(raw) == (expected == "")


# --- GR-1: GUI column mapping ------------------------------------------------------------------

def test_gr1_enrollment_merger_uses_column_overrides_and_canonical_output(tmp_path):
    src = _write(tmp_path / "GIM.xlsx", [
        {"Surname": "Gil", "First name": "Ana", "ID number": 11111111, "Email address": "a@x"},
    ])
    merged = EnrollmentMerger(
        [src], first_name_col="First name", last_name_col="Surname", id_col="ID number", email_col="Email address",
    ).merge()

    assert len(merged) == 1
    row = merged.iloc[0]
    assert (row["Nombre"], row["Apellido(s)"], row["Número de ID"], row["Dirección de correo"]) == (
        "Ana", "Gil", "11111111", "a@x")


def test_gr1_exam_grader_missing_column_names_file_and_column(tmp_path):
    xml = _write_xml(tmp_path / "examen_1A.xml", "ab")
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x")])
    answers = _write(tmp_path / "ans.xlsx", [{"Nombre_Alumno_Generado": "Ana Gil", "Pregunta 01": "a"}])

    with pytest.raises(ValueError) as excinfo:
        ExamGrader(exam_xml_path=xml, answers_xlsx_path=answers, enrollment_xlsx_path=roster,
                   first_name_col="First name")
    assert "First name" in str(excinfo.value)
    assert "m.xlsx" in str(excinfo.value)


def test_gr1_attendance_quizzes_honour_column_overrides(tmp_path):
    attendance = _write_attendance(tmp_path / "asist.xlsx", 2026, ["Surname", "First name", "SESION"],
                                   [["Gil", "Ana", "P (2/2)"]])
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "ana@x")])
    quizzes = _write(tmp_path / "q.xlsx", [{"Surname": "Gil", "First name": "Ana", _QUIZ_COL: "9,00"}])
    justif = _write(tmp_path / "j.xlsx", [{"REMITENTE": "otro@x", "ASUNTO": "Duda", "MENSAJE": "Una consulta"}])

    result = AbsenceJustificationManager(
        attendance_xlsx_path=attendance, justifications_xlsx_path=justif, enrollment_xlsx_path=roster,
        schedule_xlsx_path=_write_schedule(tmp_path / "h.xlsx", 2026), quizzes_xlsx_path=quizzes,
        first_name_col="First name", last_name_col="Surname",
    ).analyze()

    row = result.attendance_quiz_df.iloc[0]
    assert (row["Nombre"], row["Apellido(s)"]) == ("Ana", "Gil")
    assert row["Tiene_Punto_Adicional_Teoria"] == "si"


# --- GR-2: XML with the full answer text -------------------------------------------------------

def test_gr2_xml_with_answer_text_is_keyed_by_position(tmp_path):
    bank = pd.DataFrame([
        {"Número de pregunta": 1, "Pregunta": "Q1?", "Respuesta A": "Rojo", "Respuesta B": "Azul",
         "Respuesta C": "Verde", "Respuesta D": "Negro", "Respuesta correcta": "a"},
        {"Número de pregunta": 2, "Pregunta": "Q2?", "Respuesta A": "Uno", "Respuesta B": "Dos",
         "Respuesta C": "Tres", "Respuesta D": "Cuatro", "Respuesta correcta": "b"},
    ])
    xml = str(tmp_path / "examen_texto_1A.xml")
    ExamGenerator().generate_moodle_xml(bank, xml, 2, exam="E", exam_type="1A", xml_use_answer_text=True)

    questions = SharedExamDataStore().load_questions_xml(xml)
    assert questions["Pregunta 01"]["a"] == 1.0 and questions["Pregunta 01"]["b"] == -0.25
    assert questions["Pregunta 02"]["b"] == 1.0

    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x")])
    answers = _write(tmp_path / "ans.xlsx", [{"Nombre_Alumno_Generado": "Ana Gil", "Pregunta 01": "a", "Pregunta 02": "b"}])
    result = ExamGrader(exam_xml_path=xml, answers_xlsx_path=answers, enrollment_xlsx_path=roster).grade_and_export(
        str(tmp_path / "out.xlsx"))
    assert result["Calificación/10,00"].tolist() == ["10,00"]


def test_gr2_letter_xml_in_any_order_still_keyed_by_letter(tmp_path):
    xml = tmp_path / "examen_1A.xml"
    xml.write_text(
        '<quiz><question type="multichoice"><name><text>Pregunta 01</text></name>'
        '<answer fraction="-25"><text>b</text></answer><answer fraction="100"><text>c</text></answer>'
        '<answer fraction="-25"><text>a</text></answer><answer fraction="-25"><text>d</text></answer>'
        '</question></quiz>', encoding="utf-8")
    questions = SharedExamDataStore().load_questions_xml(str(xml))
    assert questions["Pregunta 01"] == {"b": -0.25, "c": 1.0, "a": -0.25, "d": -0.25}


# --- GR-3: several XMLs in "Corregir desde respuestas" -----------------------------------------

def _two_type_setup(tmp_path, answers_records):
    x1a = _write_xml(tmp_path / "examen_1A.xml", "ab")
    x1b = _write_xml(tmp_path / "examen_1B.xml", "ba")
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x"), ("Paz", "Leo", "222", "l@x")])
    answers = _write(tmp_path / "ans.xlsx", answers_records)
    cfg = ExcelGradingConfig(exam_xml_path=x1a, exam_xml_paths=[x1a, x1b], answers_xlsx_path=answers,
                             enrollment_xlsx_path=roster, output_path="cal.xlsx", output_dir=str(tmp_path / "out"))
    return cfg


def test_gr3_each_row_graded_with_its_exam_type(tmp_path):
    cfg = _two_type_setup(tmp_path, [
        {"Nombre_Alumno_Generado": "Ana Gil", "Tipo_Examen": "1A", "Pregunta 01": "a", "Pregunta 02": "b"},
        {"Nombre_Alumno_Generado": "Leo Paz", "Tipo_Examen": "1B", "Pregunta 01": "b", "Pregunta 02": "a"},
    ])
    result = ExamCorrectionAPI().grade_from_excel(cfg)

    by_name = {row["Nombre"]: row for _, row in result.iterrows()}
    assert by_name["Ana"]["Calificación/10,00"] == "10,00"
    assert by_name["Leo"]["Calificación/10,00"] == "10,00"
    assert by_name["Leo"]["Tipo_Examen"] == "1B"


def test_gr3_several_xmls_without_type_column_is_an_error(tmp_path):
    cfg = _two_type_setup(tmp_path, [
        {"Nombre_Alumno_Generado": "Ana Gil", "Pregunta 01": "a", "Pregunta 02": "b"},
    ])
    with pytest.raises(ValueError, match="columna de tipo"):
        ExamCorrectionAPI().grade_from_excel(cfg)


def test_gr3_unknown_type_row_is_not_graded_and_reported(tmp_path):
    cfg = _two_type_setup(tmp_path, [
        {"Nombre_Alumno_Generado": "Ana Gil", "Tipo_Examen": "1A", "Pregunta 01": "a", "Pregunta 02": "b"},
        {"Nombre_Alumno_Generado": "Leo Paz", "Tipo_Examen": "1C", "Pregunta 01": "b", "Pregunta 02": "a"},
    ])
    api = ExamCorrectionAPI()
    result = api.grade_from_excel(cfg)

    assert result["Nombre"].tolist() == ["Ana"]
    incidents = api.results["excel_grading_incidents"]
    assert incidents["Tipo"].tolist() == ["TIPO_EXAMEN_DESCONOCIDO"]
    assert os.path.exists(api.results["excel_grading_incidents_path"])


# --- GR-4: numeric IDs read as floats ----------------------------------------------------------

def test_gr4_enrollment_merger_normalizes_float_and_blank_ids(tmp_path):
    src = _write(tmp_path / "GIM.xlsx", [
        {"Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": 11111111, "Dirección de correo": "a@x"},
        {"Apellido(s)": "Paz", "Nombre": "Leo", "Número de ID": np.nan, "Dirección de correo": "l@x"},
    ])
    merged = EnrollmentMerger([src]).merge()
    assert dict(zip(merged["Nombre"], merged["Número de ID"])) == {"Ana": "11111111", "Leo": ""}


def test_gr4_final_grade_joins_float_and_int_ids(tmp_path):
    teoria = _write(tmp_path / "teoria.xlsx", [
        {"Número de ID": 11111111, "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": 8.0},
        {"Número de ID": np.nan, "Nombre": "Leo", "Apellido(s)": "Paz", "Calificación/10,00": 6.0},
    ])
    practicas = _write(tmp_path / "practicas.xlsx", [
        {"Número de ID": 11111111, "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": 10.0},
    ])
    result = FinalGradeCalculator(id_col="Número de ID", first_name_col="Nombre", last_name_col="Apellido(s)") \
        .compute_by_files([{"path": teoria, "weight": 0.5, "label": "T"}, {"path": practicas, "weight": 0.5, "label": "P"}])

    ana = result[result["Nombre"] == "Ana"]
    assert len(ana) == 1
    assert ana["Número de ID"].iloc[0] == "11111111"
    assert ana["Nota_Final"].iloc[0] == pytest.approx(9.0)


def test_gr4_final_grade_row_without_id_joins_same_name_with_unique_id(tmp_path):
    teoria = _write(tmp_path / "teoria.xlsx", [
        {"Número de ID": "X1", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 8.0},
    ])
    practicas = _write(tmp_path / "practicas.xlsx", [{"Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 10.0}])
    result = FinalGradeCalculator().compute_by_files([
        {"path": teoria, "weight": 0.5, "label": "T"}, {"path": practicas, "weight": 0.5, "label": "P"}])
    assert len(result) == 1
    assert result["Nota_Final"].iloc[0] == pytest.approx(9.0)


def test_gr4_comparator_matches_float_and_int_ids(tmp_path):
    old = _write(tmp_path / "old.xlsx", [
        {"Número de ID": 1.0, "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": 8.0},
        {"Número de ID": 2.0, "Nombre": "Leo", "Apellido(s)": "Paz", "Calificación/10,00": 5.0},
        {"Número de ID": np.nan, "Nombre": "Mia", "Apellido(s)": "Sol", "Calificación/10,00": 7.0},
    ])
    new = _write(tmp_path / "new.xlsx", [
        {"Número de ID": 1, "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": 9.0},
        {"Número de ID": 2, "Nombre": "Leo", "Apellido(s)": "Paz", "Calificación/10,00": 5.0},
    ])
    result = ResultComparator(id_col="Número de ID").compare(old, new, overwrite=True, add_new_rows=True)

    assert result.summary["common"] == 2
    assert result.summary["added"] == 0
    assert result.summary["changed_cells"] == 1
    assert len(result.merged_df) == 3


def test_gr4_ocr_integration_keeps_moodle_id_unchanged(tmp_path):
    ocr = _write(tmp_path / "ocr.xlsx", [{
        "Imagen": "h1.jpg", "Tipo_Examen": "1A", "ID_Oficial": "11111111.0", "Calificacion/10,00": "7,50",
        "Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": "11111111.0", "Dirección de correo": "ana@x",
    }])
    theory = _write(tmp_path / "teoria.xlsx", [{
        "Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": 11111111, "Dirección de correo": "ana@x",
        "Calificación/10,00": "-",
    }])
    out = tmp_path / "ti.xlsx"
    OcrGradeIntegrator(general_xlsx_path=theory, ocr_xlsx_path=ocr).integrate(str(out))

    written = pd.read_excel(out, dtype=str)
    assert written["Número de ID"].iloc[0] == "11111111"
    assert float(pd.read_excel(out)["Calificación/10,00"].iloc[0]) == pytest.approx(7.5)


# --- GR-5 / GR-6 / GR-14: attendance + justifications ------------------------------------------

def _attendance_case(tmp_path, year):
    roster = _roster(tmp_path / "matriculados.xlsx", [
        ("Gil López", "María José", "", "mj@uca.es"), ("Paz", "Leo", "", "leo@uca.es"),
        ("Sol", "Mia", "", "mia@uca.es"), ("Mar", "Zoe", 4444, "zoe@uca.es"),
    ])
    quizzes = _write(tmp_path / "quizzes.xlsx", [
        {"Apellido(s)": last, "Nombre": first, _QUIZ_COL: "9,00"}
        for last, first in [("Gil López", "María José"), ("Paz", "Leo"), ("Sol", "Mia"), ("Mar", "Zoe")]
    ])
    justif = _write(tmp_path / "justif.xlsx", [
        {"REMITENTE": '"Maria Jose Gil Lopez" <mj@uca.es>', "ASUNTO": "Justificante falta",
         "MENSAJE": "Adjunto justificante médico de la falta"},
        {"REMITENTE": '"Leo Paz" <leo@uca.es>', "ASUNTO": "Justificante falta",
         "MENSAJE": "Adjunto justificante médico de la falta"},
    ])
    attendance = _write_attendance(tmp_path / f"asist{year}.xlsx", year, ["Apellido(s)", "Nombre", "Número de ID", "SESION"], [
        ["Gil López", "María José", "", "A (0/2)"], ["Paz", "Leo", "", "A (0/2)"],
        ["Sol", "Mia", "", "A (0/2)"], ["Mar", "Zoe", 4444, "P (2/2)"],
    ])
    return AbsenceJustificationManager(
        attendance_xlsx_path=attendance, justifications_xlsx_path=justif, enrollment_xlsx_path=roster,
        schedule_xlsx_path=_write_schedule(tmp_path / f"horario{year}.xlsx", year), quizzes_xlsx_path=quizzes,
    ).analyze()


def test_gr5_students_without_id_do_not_share_justifications(tmp_path):
    result = _attendance_case(tmp_path, 2026)

    assert result.summary_df["ID_Alumno"].tolist() == ["", ""]
    bonus = dict(zip(result.attendance_quiz_df["Nombre"], result.attendance_quiz_df["Tiene_Punto_Adicional_Teoria"]))
    assert bonus == {"María José": "si", "Leo": "si", "Mia": "no", "Zoe": "si"}
    assert "nan" not in result.attendance_quiz_df["ID_Alumno"].astype(str).tolist()


def test_gr5_theory_bonus_ignores_nan_ids():
    theory = pd.DataFrame([
        {"ID_Alumno": "nan", "Nombre": "Mia", "Apellido(s)": "Sol", "Calificación/10,00": "6,00"},
    ])
    attendance_quiz = pd.DataFrame([
        {"ID_Alumno": "nan", "Nombre": "Leo", "Apellido(s)": "Paz", "Tiene_Punto_Adicional_Teoria": "si", "Motivo_No_Punto": ""},
        {"ID_Alumno": "nan", "Nombre": "Mia", "Apellido(s)": "Sol", "Tiene_Punto_Adicional_Teoria": "no",
         "Motivo_No_Punto": "faltas_no_justificadas"},
    ])
    result = TheoryBonusApplier(theory, attendance_quiz).apply()
    assert float(result["Incremento_Aplicado"].iloc[0]) == 0.0
    assert float(result["Nota_Final_Teoria"].iloc[0]) == 6.0


def test_gr5_moodle_dedup_by_id_keeps_every_student_without_id(tmp_path):
    from pyexamgenerator.grading.integrations import MoodleGradeIntegrator

    f1 = _write(tmp_path / "PRL - 1A-calificaciones.xlsx", [
        {"Número de ID": "", "Nombre": "Leo", "Apellido(s)": "Paz", "Calificación/10,00": "5,00"},
        {"Número de ID": "", "Nombre": "Mia", "Apellido(s)": "Sol", "Calificación/10,00": "7,00"},
        {"Número de ID": 111, "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "6,00"},
    ])
    f2 = _write(tmp_path / "PRL - 1B-calificaciones.xlsx", [
        {"Número de ID": 111.0, "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "8,00"},
    ])
    result = MoodleGradeIntegrator(xlsx_files=[f1, f2]).integrate_grades(deduplicate_by_id=True)
    grades = dict(zip(result["Nombre"], result["Calificación/10,00"]))
    assert grades == {"Ana": 8.0, "Leo": 5.0, "Mia": 7.0}


def test_gr6_attendance_columns_of_any_year(tmp_path):
    result = _attendance_case(tmp_path, 2027)

    session_cols = [c for c in result.attendance_quiz_df.columns if str(c).endswith("__Asistencia")]
    assert session_cols == ["C01_1002_T02_GIM__Asistencia"]
    assert result.warnings == []


def test_gr6_attendance_without_session_columns_warns_instead_of_crashing(tmp_path):
    attendance = _write_attendance(tmp_path / "asist.xlsx", 2027, ["Apellido(s)", "Nombre", "Notas"],
                                   [["Gil", "Ana", "x"]])
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "ana@x")])
    justif = _write(tmp_path / "j.xlsx", [{"REMITENTE": "ana@x", "ASUNTO": "Justificante", "MENSAJE": "falta"}])
    quizzes = _write(tmp_path / "q.xlsx", [{"Apellido(s)": "Gil", "Nombre": "Ana", _QUIZ_COL: "9,00"}])

    result = AbsenceJustificationManager(
        attendance_xlsx_path=attendance, justifications_xlsx_path=justif, enrollment_xlsx_path=roster,
        quizzes_xlsx_path=quizzes,
    ).analyze()

    assert len(result.warnings) == 1 and "columna de sesión" in result.warnings[0]
    assert result.attendance_quiz_df["Tiene_Punto_Adicional_Teoria"].tolist() == ["no"]


def test_gr14_compound_first_names_keep_their_justification(tmp_path):
    attendance = _write_attendance(tmp_path / "asist.xlsx", 2026, ["Apellido(s)", "Nombre", "SESION"], [
        ["Gil López", "María José", "A (0/2)"], ["Paz", "Leo", "A (0/2)"],
    ])
    quizzes = _write(tmp_path / "q.xlsx", [
        {"Apellido(s)": "Gil López", "Nombre": "María José", _QUIZ_COL: "9,00"},
        {"Apellido(s)": "Paz", "Nombre": "Leo", _QUIZ_COL: "9,00"},
    ])
    roster = _roster(tmp_path / "m.xlsx", [
        ("Gil López", "María José", "11111111A", "mj@uca.es"), ("Paz", "Leo", "22222222B", "leo@uca.es")])
    justif = _write(tmp_path / "j.xlsx", [
        {"REMITENTE": '"Maria Jose Gil Lopez" <mj@uca.es>', "ASUNTO": "Justificante",
         "MENSAJE": "Adjunto justificante médico de la falta"},
        {"REMITENTE": '"Leo Paz" <leo@uca.es>', "ASUNTO": "Justificante",
         "MENSAJE": "Adjunto justificante médico de la falta"},
    ])
    for mode in ("extremo", "normal"):
        result = AbsenceJustificationManager(
            attendance_xlsx_path=attendance, justifications_xlsx_path=justif, enrollment_xlsx_path=roster,
            schedule_xlsx_path=_write_schedule(tmp_path / "h.xlsx", 2026), quizzes_xlsx_path=quizzes,
            justification_mode=mode,
        ).analyze()
        bonus = dict(zip(result.attendance_quiz_df["Nombre"], result.attendance_quiz_df["Tiene_Punto_Adicional_Teoria"]))
        assert bonus == {"María José": "si", "Leo": "si"}, mode


# --- GR-8: compare + overwrite with different value types (pandas 3) ----------------------------

@pytest.mark.parametrize(
    "old_value, new_value",
    [(8.0, "9,50"), (np.nan, "asiste"), ("-", 7.5)],
)
def test_gr8_overwrite_accepts_values_of_another_type(tmp_path, old_value, new_value):
    old = _write(tmp_path / "old.xlsx", [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Valor": old_value}])
    new = _write(tmp_path / "new.xlsx", [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Valor": new_value}])

    result = ResultComparator().compare(old, new, overwrite=True)
    assert result.merged_df["Valor"].iloc[0] == new_value
    ResultComparator.export_merged(result, str(tmp_path / "merged.xlsx"))


# --- GR-9 / GR-10: final grade by file ---------------------------------------------------------

def test_gr9_gui_column_names_do_not_disable_autodetection(tmp_path):
    t2 = _write(tmp_path / "t2.xlsx", [{"DNI": "X1", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 8.0}])
    p2 = _write(tmp_path / "p2.xlsx", [{"DNI": "X1", "Nombre": "Ana", "Apellidos": "Gil", "Nota": 10.0}])
    result = FinalGradeCalculator(id_col="Número de ID", first_name_col="Nombre", last_name_col="Apellido(s)") \
        .compute_by_files([{"path": t2, "weight": 0.5, "label": "T"}, {"path": p2, "weight": 0.5, "label": "P"}])

    assert len(result) == 1
    assert result["Número de ID"].iloc[0] == "X1"
    assert result["Nota_Final"].iloc[0] == pytest.approx(9.0)


def test_gr10_files_with_the_same_name_keep_separate_grades(tmp_path):
    (tmp_path / "parcial1").mkdir()
    (tmp_path / "parcial2").mkdir()
    record = {"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil"}
    p1 = _write(tmp_path / "parcial1" / "calificaciones_examen_teoria.xlsx", [{**record, "Calificación/10,00": "2,00"}])
    p2 = _write(tmp_path / "parcial2" / "calificaciones_examen_teoria.xlsx", [{**record, "Calificación/10,00": "10,00"}])

    result = FinalGradeCalculator().compute_by_files([{"path": p1, "weight": 0.5}, {"path": p2, "weight": 0.5}])

    assert result["Nota_Final"].iloc[0] == pytest.approx(6.0)
    grade_cols = [c for c in result.columns if c.startswith("Nota_") and c != "Nota_Final"]
    assert grade_cols == ["Nota_parcial1_calificaciones_examen_teoria", "Nota_parcial2_calificaciones_examen_teoria"]


# --- GR-13: never overwrite a source enrollment file -------------------------------------------

def test_gr13_merger_refuses_to_overwrite_a_source_file(tmp_path):
    src = _write(tmp_path / "matriculados.xlsx", [{
        "Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": "111", "Dirección de correo": "a@x",
        "Grupo": "MC1", "Observaciones": "repetidora", "Teléfono": "600000000",
    }])
    with pytest.raises(ValueError, match="origen"):
        EnrollmentMerger([src]).export(src)
    assert "Observaciones" in pd.read_excel(src).columns


# --- GR-15 / GR-18: grading from an answers xlsx -----------------------------------------------

def test_gr15_reuses_ocr_answers_file_and_reports_unmatched_rows(tmp_path):
    xml = _write_xml(tmp_path / "examen_1A.xml", "ab")
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x"), ("Paz", "Leo", "222", "l@x")])
    answers = _write(tmp_path / "respuestas.xlsx", [
        {"Imagen": "C:/scans/h1.jpg", "Tipo_Examen": "1A", "Nombre_OCR": "Ana Gil", "Nombre_Oficial": "Ana Gil",
         "ID_Oficial": "111", "Pregunta 01": "a", "Pregunta 02": "b"},
        {"Imagen": "C:/scans/h2.jpg", "Tipo_Examen": "1A", "Nombre_OCR": "", "Nombre_Oficial": "",
         "ID_Oficial": 222.0, "Pregunta 01": "a", "Pregunta 02": "a"},
        {"Imagen": "C:/scans/h3.jpg", "Tipo_Examen": "1A", "Nombre_OCR": "Zzz Qqq", "Nombre_Oficial": "",
         "ID_Oficial": "", "Pregunta 01": "a", "Pregunta 02": "b"},
    ])
    api = ExamCorrectionAPI()
    result = api.grade_from_excel(ExcelGradingConfig(
        exam_xml_path=xml, answers_xlsx_path=answers, enrollment_xlsx_path=roster,
        output_path="cal.xlsx", output_dir=str(tmp_path / "out")))

    assert result["Nombre"].tolist() == ["Ana", "Leo"]
    assert result["Número de ID"].tolist() == ["111", "222"]
    incidents = api.results["excel_grading_incidents"]
    assert incidents["Tipo"].tolist() == ["ALUMNO_NO_ENCONTRADO"]
    assert incidents["Nombre_Leido"].tolist() == ["Zzz Qqq"]
    assert (tmp_path / "out" / "incidencias_respuestas.xlsx").exists()


def test_gr15_no_graded_rows_is_an_error(tmp_path):
    xml = _write_xml(tmp_path / "examen_1A.xml", "ab")
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x")])
    answers = _write(tmp_path / "ans.xlsx", [{"Imagen": "C:/scans/h1.jpg", "Pregunta 01": "a"}])
    grader = ExamGrader(exam_xml_path=xml, answers_xlsx_path=answers, enrollment_xlsx_path=roster)
    with pytest.raises(ValueError, match="ninguna fila"):
        grader.grade_and_export(str(tmp_path / "out.xlsx"))
    assert not (tmp_path / "out.xlsx").exists()


def test_gr18_attempt_times_are_not_invented(tmp_path):
    xml = _write_xml(tmp_path / "examen_1A.xml", "a")
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x"), ("Paz", "Leo", "222", "l@x")])
    answers = _write(tmp_path / "ans.xlsx", [
        {"Nombre_Alumno_Generado": "Ana Gil", "Comenzado": "3 de mayo de 2027 09:00", "Pregunta 01": "a"},
        {"Nombre_Alumno_Generado": "Leo Paz", "Comenzado": np.nan, "Pregunta 01": "a"},
    ])
    result = ExamGrader(exam_xml_path=xml, answers_xlsx_path=answers, enrollment_xlsx_path=roster) \
        .grade_and_export(str(tmp_path / "out.xlsx"))

    by_name = {row["Nombre"]: row for _, row in result.iterrows()}
    assert by_name["Ana"]["Comenzado"] == "3 de mayo de 2027 09:00"
    assert by_name["Leo"]["Comenzado"] == ""
    assert set(result["Finalizado"]) == {""} and set(result["Duración"]) == {""}


# --- GR-16: two different XMLs for the same exam type ------------------------------------------

def test_gr16_same_type_from_two_different_xmls_is_an_error(tmp_path):
    gim = _write_xml(tmp_path / "GIM" / "examen_PRL_P1_2026_1A.xml", "ab")
    giti = _write_xml(tmp_path / "GITI" / "examen_PRL_P1_2026_1A.xml", "cd")
    with pytest.raises(ValueError) as excinfo:
        SharedExamDataStore().load_questions_by_exam_type([gim, giti])
    assert "1A" in str(excinfo.value) and "GIM" in str(excinfo.value) and "GITI" in str(excinfo.value)

    copy = _write_xml(tmp_path / "copia" / "examen_PRL_P1_2026_1A.xml", "ab")
    loaded = SharedExamDataStore().load_questions_by_exam_type([gim, copy])
    assert list(loaded) == ["1A"]


# --- GR-19: macro group detected by whole words ------------------------------------------------

@pytest.mark.parametrize(
    "path, expected",
    [
        ("C:/m/Higiene_Industrial_GIM.xlsx", "GIM"),
        ("GITI-GIE-GIEI.xlsx", "GITI-GIE-GIEI"),
        ("matriculados_GIM.xlsx", "GIM"),
        ("MatriculadosGIM.xlsx", "GIM"),
        ("PRL GIEI 2026.xlsx", "GITI-GIE-GIEI"),
        ("Higiene.xlsx", "Higiene"),
    ],
)
def test_gr19_macro_group_matches_whole_words(path, expected):
    assert _detect_macro_group(path) == expected


# --- GR-22: loading a session never prefers the pickle -----------------------------------------

class _MaliciousPickle:
    def __init__(self, marker):
        self.marker = marker

    def __reduce__(self):
        return (os.mkdir, (self.marker,))


def test_gr22_session_loads_json_and_never_unpickles_when_not_allowed(tmp_path):
    session = GradingSession(name="b")
    session.set_grading_inputs(xmls="b.xml")
    pkl_path, json_path = session.save(str(tmp_path / "sesion"))
    marker = str(tmp_path / "pickle_was_executed")
    import pickle
    with open(pkl_path, "wb") as handle:
        pickle.dump(_MaliciousPickle(marker), handle)

    assert GradingSession.load(str(tmp_path / "sesion")).grading_inputs == {"xmls": "b.xml"}
    assert GradingSession.load(pkl_path, allow_pickle=False).grading_inputs == {"xmls": "b.xml"}
    assert not os.path.exists(marker)

    os.remove(json_path)
    with pytest.raises(ValueError, match="seguridad"):
        GradingSession.load(pkl_path, allow_pickle=False)
    assert not os.path.exists(marker)


# --- OCR grading (GR-7 / GR-11 / GR-12): need the [grading] extra -------------------------------

@pytest.fixture
def ocr_grader_factory(tmp_path, monkeypatch):
    """Construye un ImageExamGrader real sin ejecutar OCR: process_image devuelve hojas preparadas."""
    if not grading.HAS_OCR:
        pytest.skip("OCR extra no disponible")
    pytest.importorskip("cv2")
    from pyexamgenerator.grading import extraction

    class _NoOCR:
        def __call__(self, *args, **kwargs):
            return None

    monkeypatch.setattr(extraction, "RapidOCR", _NoOCR)

    def factory(xml_letters_by_type, roster_path, sheets):
        xml_paths = [_write_xml(tmp_path / f"examen_{t}.xml", letters) for t, letters in xml_letters_by_type.items()]
        grader = extraction.ImageExamGrader(xml_paths=xml_paths, enrollment_path=roster_path)

        def fake_process_image(image_path):
            if image_path not in sheets:
                raise FileNotFoundError(f"Could not read image: {image_path}")
            build = sheets[image_path]
            return build(grader.extractor) if callable(build) else build

        grader.extractor.process_image = fake_process_image
        return extraction, grader

    return factory


def _sheet(extraction, image, exam_type, answers, name=None, official=(None, None, None), audit_rows=None):
    official_name, official_id, index = official
    first, last = (name.split(" ", 1) if name else (None, None))
    return extraction.SheetResult(
        image=image, exam_type=exam_type, first_name_raw=first, last_name_raw=last, student_name_ocr=name,
        student_name_official=official_name, student_id_official=official_id, answers=answers,
        audit_rows=audit_rows or [], enrollment_index=index,
    )


def test_gr7_ocr_grade_goes_to_the_matched_student_without_id(tmp_path, ocr_grader_factory):
    # Matrícula fusionada escrita en disco (como en el pipeline): Leo y Mia sin "Número de ID".
    src = _roster(tmp_path / "GIM.xlsx", [("Gil", "Ana", "111", "ana@x"), ("Paz", "Leo", "", "leo@x"),
                                          ("Sol", "Mia", "", "mia@x")])
    matric = str(tmp_path / "_intermedios" / "matriculados.xlsx")
    EnrollmentMerger([src]).export(matric)

    def mia_sheet(extractor):
        match = extractor._match_official_student_row("Mia Sol", "Mia", "Sol")
        return _sheet(extraction, "hoja_mia.jpg", "1A", {"Pregunta 01": "a", "Pregunta 02": "a"},
                      name="Mia Sol", official=match)

    extraction, grader = ocr_grader_factory({"1A": "aa"}, matric, {"hoja_mia.jpg": mia_sheet})
    assert grader.extractor._match_official_student("Mia Sol", "Mia", "Sol") == ("Mia Sol", None)
    assert grader._enrollment_row_from_id("nan") is None

    _, grades, _ = grader.grade_from_images(["hoja_mia.jpg"], "respuestas.xlsx", "calificaciones.xlsx",
                                            output_dir=str(tmp_path / "out"), output_incidents="incidencias.xlsx",
                                            prompt_missing_type=False)
    row = grades.iloc[0]
    assert (row["Nombre"], row["Apellido(s)"], row["Número de ID"]) == ("Mia", "Sol", "")
    incidents = pd.read_excel(tmp_path / "out" / "incidencias.xlsx")
    assert "MISSING_ID" in incidents["Tipo"].tolist()

    # La integración posterior asigna la nota a Mia (por nombre), no a otro alumno sin ID.
    theory = _write(tmp_path / "teoria.xlsx", [
        {"Apellido(s)": last, "Nombre": first, "Número de ID": sid, "Calificación/10,00": "-"}
        for last, first, sid in [("Gil", "Ana", "111"), ("Paz", "Leo", ""), ("Sol", "Mia", "")]
    ])
    integrated = OcrGradeIntegrator(general_xlsx_path=theory, ocr_xlsx_path=str(tmp_path / "out" / "calificaciones.xlsx")) \
        .integrate(str(tmp_path / "teoria_integrada.xlsx"))
    grades_by_name = dict(zip(integrated["Nombre"], integrated["Calificación/10,00"]))
    assert grades_by_name["Mia"] == pytest.approx(10.0)
    assert pd.isna(grades_by_name["Leo"])


def test_gr11_unresolved_type_or_unreadable_image_does_not_abort_the_batch(tmp_path, ocr_grader_factory):
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x")])
    sheets = {}
    extraction, grader = ocr_grader_factory({"1A": "ab", "1B": "ba"}, roster, sheets)
    sheets["s1.jpg"] = _sheet(extraction, "s1.jpg", "1A", {"Pregunta 01": "a", "Pregunta 02": "b"},
                              name="Ana Gil", official=("Ana Gil", "111", 0))
    sheets["s2.jpg"] = _sheet(extraction, "s2.jpg", None, {"Pregunta 01": "b", "Pregunta 02": "a"})

    out = tmp_path / "out"
    answers, grades, _ = grader.grade_from_images(
        ["s1.jpg", "s2.jpg", "ilegible.jpg"], "respuestas.xlsx", "calificaciones.xlsx", output_dir=str(out),
        output_incidents="incidencias.xlsx", prompt_missing_type=False)

    assert grades["Imagen"].tolist() == ["s1.jpg"]
    assert answers["Tipo_Examen_Usado"].tolist() == ["1A", ""]
    assert {"respuestas.xlsx", "calificaciones.xlsx", "incidencias.xlsx"} <= set(os.listdir(out))
    incidents = pd.read_excel(out / "incidencias.xlsx")
    by_type = dict(zip(incidents["Tipo"], incidents["Imagen"]))
    assert by_type["EXAM_TYPE_UNRESOLVED"] == "s2.jpg"
    assert by_type["IMAGE_READ_ERROR"] == "ilegible.jpg"
    assert "1B" in incidents.loc[incidents["Tipo"] == "EXAM_TYPE_UNRESOLVED", "Detalle"].iloc[0]


def test_gr11_no_readable_image_raises_after_writing_incidents(tmp_path, ocr_grader_factory):
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x")])
    _, grader = ocr_grader_factory({"1A": "ab"}, roster, {})

    with pytest.raises(ValueError, match="ninguna"):
        grader.grade_from_images(["x.jpg", "y.jpg"], "r.xlsx", "c.xlsx", output_dir=str(tmp_path / "out"),
                                 output_incidents="incidencias.xlsx", prompt_missing_type=False)
    incidents = pd.read_excel(tmp_path / "out" / "incidencias.xlsx")
    assert incidents["Tipo"].tolist() == ["IMAGE_READ_ERROR", "IMAGE_READ_ERROR"]


def test_gr12_incidents_flag_doubtful_answers_without_output_audit(tmp_path, ocr_grader_factory):
    roster = _roster(tmp_path / "m.xlsx", [("Gil", "Ana", "111", "a@x")])

    def audit(question, selected, score_a, score_b):
        return {"Imagen": "s1.jpg", "Pregunta": question, "Score_a": score_a, "Score_b": score_b, "Score_c": 0.0,
                "Score_d": 0.0, "Score_nc": 0.0, "Seleccionada": selected,
                "Decision": "aggressive" if selected != "-" else "blank", "AutoRecovered": "si"}

    sheets = {}
    extraction, grader = ocr_grader_factory({"1A": "ab"}, roster, sheets)
    sheets["s1.jpg"] = _sheet(
        extraction, "s1.jpg", "1A", {"Pregunta 01": "a", "Pregunta 02": "-"}, name="Ana Gil",
        official=("Ana Gil", "111", 0),
        audit_rows=[audit("Pregunta 01", "a", 0.12, 0.11), audit("Pregunta 02", "-", 0.02, 0.01)])

    _, _, audit_df = grader.grade_from_images(["s1.jpg"], "r.xlsx", "c.xlsx", output_dir=str(tmp_path / "out"),
                                              output_incidents="incidencias.xlsx", prompt_missing_type=False)
    assert audit_df is None  # no se pidió el fichero de auditoría
    incident_types = set(pd.read_excel(tmp_path / "out" / "incidencias.xlsx")["Tipo"])
    assert {"LOW_CONFIDENCE_MARKS", "UNRESOLVED_ANSWERS"} <= incident_types


# --- GUI helpers (GR-1 / GR-13 / GR-17 / GR-21 / GR-22 / GR-23): need tkinter ------------------

class _Var:
    """Sustituto mínimo de tk.StringVar/BooleanVar (get/set) para no crear ventanas."""

    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


@pytest.fixture
def fake_app():
    pytest.importorskip("tkinter")
    import inspect
    import re
    from pyexamgenerator import main_app

    names = set(re.findall(r"self\.(grad_\w+_var)\b", inspect.getsource(main_app.ExamApp)))
    app = types.SimpleNamespace(**{name: _Var("") for name in names})
    for method in ("_grad_columns", "_grad_session_inputs", "_grad_parse_final_files", "_grad_parse_weights",
                   "_grad_try_begin_job", "_grad_end_job", "_grad_merged_enrollment", "_grad_enrollment_list"):
        setattr(app, method, types.MethodType(getattr(main_app.ExamApp, method), app))
    app._grad_parse_weight_value = main_app.ExamApp._grad_parse_weight_value
    return main_app, app


def test_gr1_gr13_gui_merged_roster_uses_mapping_and_keeps_teacher_file(tmp_path, fake_app):
    main_app, app = fake_app
    out = tmp_path / "out"
    out.mkdir()
    teacher_file = _write(out / "matriculados.xlsx", [
        {"Surname": "Gil", "First name": "Ana", "ID number": 111, "Email address": "a@x", "Observaciones": "x"}])
    cols = {"first_name_col": "First name", "last_name_col": "Surname", "id_col": "ID number",
            "email_col": "Email address"}

    merged_path = app._grad_merged_enrollment(str(out), [teacher_file], cols)

    assert os.path.basename(merged_path) == "matriculados_fusionados.xlsx"
    assert "Observaciones" in pd.read_excel(teacher_file).columns
    merged = pd.read_excel(merged_path, dtype=str)
    assert merged[["Nombre", "Apellido(s)", "Número de ID"]].values.tolist() == [["Ana", "Gil", "111"]]


def test_gr17_weights_accept_percent_and_report_bad_entries(fake_app, monkeypatch):
    main_app, app = fake_app
    app.grad_final_files_var.set("C:/teoria.xlsx|60% ; C:/practicas.xlsx|0,4")
    assert [s["weight"] for s in app._grad_parse_final_files()] == [pytest.approx(0.6), pytest.approx(0.4)]

    errors = []
    monkeypatch.setattr(main_app.messagebox, "showerror", lambda *args, **kwargs: errors.append(args))
    app.grad_out_var.set("/tmp/salida")
    app.grad_final_mode_var.set("by_file")
    app.grad_final_files_var.set("C:/teoria.xlsx|sesenta")
    main_app.ExamApp.run_final_grade(app)  # no debe lanzar excepción: muestra un error
    assert len(errors) == 1 and "sesenta" in errors[0][1]


def test_gr21_only_one_grading_job_at_a_time(fake_app, monkeypatch):
    main_app, app = fake_app
    warnings = []
    monkeypatch.setattr(main_app.messagebox, "showwarning", lambda *args, **kwargs: warnings.append(args))

    assert app._grad_try_begin_job() is True
    assert app._grad_try_begin_job() is False
    assert len(warnings) == 1
    app._grad_end_job()
    assert app._grad_try_begin_job() is True


def test_gr22_gr23_gui_load_session_uses_json_and_clears_stale_fields(tmp_path, fake_app, monkeypatch):
    main_app, app = fake_app
    shown = []
    monkeypatch.setattr(main_app.messagebox, "showinfo", lambda *args, **kwargs: shown.append(("info",) + args))
    monkeypatch.setattr(main_app.messagebox, "showerror", lambda *args, **kwargs: shown.append(("error",) + args))

    # Valores de la sesión anterior (examen A).
    app.grad_images_var.set("A/h1.jpg;A/h2.jpg")
    app.grad_final_files_var.set("A/teoria.xlsx|1")
    app.grad_final_cap_var.set(True)

    # Sesión B guardada desde la GUI: sin imágenes, con nota final por ficheros.
    app_b = types.SimpleNamespace(**{name: _Var(var.get()) for name, var in vars(app).items() if isinstance(var, _Var)})
    app_b._grad_columns = types.MethodType(main_app.ExamApp._grad_columns, app_b)
    app_b.grad_images_var.set("")
    app_b.grad_xmls_var.set("B/examen_1A.xml")
    app_b.grad_final_files_var.set("B/teoria.xlsx|0.6 ; B/practicas.xlsx|0.4")
    app_b.grad_final_cap_var.set(False)
    session = GradingSession(name="b")
    session.set_grading_inputs(**main_app.ExamApp._grad_session_inputs(app_b))
    pkl_path, _ = session.save(str(tmp_path / "sesion_b"))

    app.grad_session_path_var.set(pkl_path)  # aunque se elija el .pkl, se carga el .json
    main_app.ExamApp.load_grading_session(app)

    assert shown and shown[-1][0] == "info"
    assert app.grad_images_var.get() == ""
    assert app.grad_xmls_var.get() == "B/examen_1A.xml"
    assert app.grad_final_files_var.get() == "B/teoria.xlsx|0.6 ; B/practicas.xlsx|0.4"
    assert app.grad_final_cap_var.get() is False
