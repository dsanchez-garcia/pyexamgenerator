"""Regresiones del punto extra PIR y de la detección de columnas de asistencia."""

import pandas as pd
import pytest

from pyexamgenerator.grading import attendance
from pyexamgenerator.grading.attendance import AbsenceJustificationManager, PIRBonusCalculator


def _pir_calculator(attendance_df, schedule_df, quizzes_df):
    calculator = PIRBonusCalculator(
        attendance_path="asistencia.xlsx",
        schedule_path="horario.xlsx",
        schedule_sheet=0,
        quizzes_path="cuestionarios.xlsx",
    )
    calculator._load_attendance = lambda: attendance_df
    calculator._load_schedule = lambda: schedule_df
    calculator._load_quizzes = lambda: quizzes_df
    return calculator


def _students():
    return pd.DataFrame(
        [
            {"Apellido(s)": "Gil", "Nombre": "Ana", "3 mar 2026 10:00": "P"},
            {"Apellido(s)": "Ruiz", "Nombre": "Leo", "3 mar 2026 10:00": "F"},
        ]
    )


def _quizzes(grades):
    return pd.DataFrame(
        [
            {"Apellido(s)": "Gil", "Nombre": "Ana", "Cuestionario:Cuestionario Tema 01 - GIM (Real)": grades[0]},
            {"Apellido(s)": "Ruiz", "Nombre": "Leo", "Cuestionario:Cuestionario Tema 01 - GIM (Real)": grades[1]},
        ]
    )


def _schedule(day):
    return pd.DataFrame(
        [{"Fecha de inicio": day, "Descripción": "Tema 01", "Título (EDITABLE)": "Teoría GIM"}]
    )


def test_pir_bonus_requires_attendance_and_quiz():
    calculator = _pir_calculator(_students(), _schedule("2026-03-03"), _quizzes(["8,5", "9"]))

    summary, _incidents, _warnings = calculator.calculate()

    bonus = dict(zip(summary["Nombre"], summary["PIR_Bonus"]))
    assert bonus == {"Ana": 1.0, "Leo": 0.0}


def test_pir_bonus_not_awarded_when_no_session_matches_schedule():
    """GRD-1: sin sesiones emparejadas, all([]) concedía el punto extra a todo el mundo."""
    calculator = _pir_calculator(_students(), _schedule("2026-04-20"), _quizzes(["8,5", "9"]))

    summary, _incidents, warnings = calculator.calculate()

    assert summary["PIR_Bonus"].tolist() == [0.0, 0.0]
    assert any("no PIR bonus" in warning for warning in warnings)


def test_attendance_date_columns_are_detected_for_any_year():
    """GRD-2: la detección estaba limitada a columnas que contenían '2026'."""
    is_date_col = AbsenceJustificationManager._is_attendance_date_column

    assert is_date_col("3 mar 2026 10:00 AM Todos los estudiantes")
    assert is_date_col("12 oct 2027 10:00 AM Todos los estudiantes")
    assert is_date_col("15 feb 2031 Todos los estudiantes")
    assert not is_date_col("Todos los estudiantes")
    assert not is_date_col("12 oct 2027 10:00 AM")


@pytest.mark.parametrize("text, expected", [
    ("Ley 31/95", "LPRL"),
    ("Ley 31_95", "LPRL"),
    ("LEY 31-95 (PRL)", "LPRL"),
    ("Ley 31/1995", "LPRL"),
    ("RD 39/97", "RSP"),
    ("rd 39_97", "RSP"),
    ("Tema 3", "TEMA 03"),
    ("TEMA 03 - Riesgos", "TEMA 03"),
    ("tema_10", "TEMA 10"),
])
def test_attendance_and_pir_detect_topics_the_same_way(text, expected):
    """GRD-10: el cálculo PIR solo aceptaba 'Ley 31_95' / 'RD 39_97' y la asistencia también
    'Ley 31/95': la misma sesión contaba como tema en un flujo y no en el otro."""
    assert attendance._topic_from_text(text) == expected
    assert AbsenceJustificationManager._topic_from_text(text) == expected


def test_topic_words_must_be_whole():
    assert attendance._topic_from_text("Sistema 3D") is None
    assert AbsenceJustificationManager._topic_from_text("Sistema 3D") == "Sistema 3D"  # not a known topic
    assert AbsenceJustificationManager._topic_from_text("Prácticas tema 3") == ""  # practice sessions excluded
