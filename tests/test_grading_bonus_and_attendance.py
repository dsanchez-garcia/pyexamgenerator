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
    return pd.DataFrame([{"Fecha de inicio": day, "Descripción": "Tema 01", "Título (EDITABLE)": "Teoría GIM"}])


def test_pir_bonus_requires_attendance_and_quiz():
    calculator = _pir_calculator(_students(), _schedule("2026-03-03"), _quizzes(["8,5", "9"]))

    summary, _incidents, _warnings = calculator.calculate()

    bonus = dict(zip(summary["Nombre"], summary["PIR_Bonus"], strict=True))
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


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Ley 31/95", "LPRL"),
        ("Ley 31_95", "LPRL"),
        ("LEY 31-95 (PRL)", "LPRL"),
        ("Ley 31/1995", "LPRL"),
        ("RD 39/97", "RSP"),
        ("rd 39_97", "RSP"),
        ("Tema 3", "TEMA 03"),
        ("TEMA 03 - Riesgos", "TEMA 03"),
        ("tema_10", "TEMA 10"),
    ],
)
def test_attendance_and_pir_detect_topics_the_same_way(text, expected):
    """GRD-10: el cálculo PIR solo aceptaba 'Ley 31_95' / 'RD 39_97' y la asistencia también
    'Ley 31/95': la misma sesión contaba como tema en un flujo y no en el otro."""
    assert attendance._topic_from_text(text) == expected
    assert AbsenceJustificationManager._topic_from_text(text) == expected


def test_topic_words_must_be_whole():
    assert attendance._topic_from_text("Sistema 3D") is None
    assert AbsenceJustificationManager._topic_from_text("Sistema 3D") == "Sistema 3D"  # not a known topic
    assert AbsenceJustificationManager._topic_from_text("Prácticas tema 3") == ""  # practice sessions excluded


def test_theory_bonus_points_are_configurable():
    """GRD-11: el punto extra sumaba siempre +1, aunque PIRBonusCalculator acepta `bonus_points`."""
    from pyexamgenerator.grading.attendance import TheoryBonusApplier

    theory = pd.DataFrame([{"Número de ID": "111", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": 6.0}])
    bonus = pd.DataFrame(
        [
            {
                "ID_Alumno": "111",
                "Nombre": "Ana",
                "Apellido(s)": "Gil",
                "Tiene_Punto_Adicional_Teoria": "si",
                "Motivo_No_Punto": "",
            }
        ]
    )

    default = TheoryBonusApplier(theory, bonus).apply()
    half_point = TheoryBonusApplier(theory, bonus, bonus_points=0.5).apply()

    assert default["Nota_Final_Teoria"].iloc[0] == pytest.approx(7.0)
    assert half_point["Nota_Final_Teoria"].iloc[0] == pytest.approx(6.5)


def test_minimum_quiz_grade_for_the_bonus_is_configurable(tmp_path, monkeypatch):
    """GRD-11: la nota mínima de los cuestionarios (7,5) estaba fija en el análisis de asistencia."""
    quizzes = tmp_path / "cuestionarios.xlsx"
    pd.DataFrame(
        [{"Nombre": "Ana", "Apellido(s)": "Gil", "Cuestionario:Cuestionario Tema 3 - GIM (Real)": "7,00"}]
    ).to_excel(quizzes, index=False)
    sessions = pd.DataFrame(
        [
            {
                "Fecha_Asistencia_Col": "3 mar 2026 10:00",
                "Es_Teoria": "si",
                "Tema_Clase": "TEMA 03",
                "Grupo_Clase": "GIM",
                "Clase_Label": "03/03/2026 | TEMA 03 | GIM",
                "Fecha_Clase": "03/03/2026",
            }
        ]
    )
    attendance_df = pd.DataFrame([{"Nombre": "Ana", "Apellido(s)": "Gil", "3 mar 2026 10:00": "P"}])

    def has_bonus(**kwargs):
        manager = AbsenceJustificationManager(
            "asistencias.xlsx", "justificaciones.xlsx", "matricula.xlsx", quizzes_xlsx_path=str(quizzes), **kwargs
        )
        monkeypatch.setattr(manager, "_build_sessions_catalog", lambda date_cols: sessions)
        result = manager._build_attendance_with_quizzes_df(attendance_df, ["3 mar 2026 10:00"])
        return result["Tiene_Punto_Adicional_Teoria"].iloc[0]

    assert has_bonus() == "no"  # 7 < 7,5 (default)
    assert has_bonus(min_quiz_grade=7.0) == "si"


def test_topic_report_includes_topics_outside_the_usual_list():
    """GRD-11: el informe por tema solo tenía LPRL, RSP y T02..T11; T01 o T12 se perdían."""
    from pyexamgenerator.grading.attendance import TheoryTopicReporter

    source = pd.DataFrame(
        [
            {
                "ID_Alumno": "111",
                "Nombre": "Ana",
                "Apellido(s)": "Gil",
                "C01_0303_T01_GIM__Asistencia": "asiste",
                "C01_0303_T01_GIM__Quiz_Nota_Tema_Max": 8.0,
                "C02_1003_T12_GIM__Asistencia": "falta",
                "C02_1003_T12_GIM__Quiz_Nota_Tema_Max": 9.5,
                "Tiene_Punto_Adicional_Teoria": "no",
                "Motivo_No_Punto": "faltas_no_justificadas",
            }
        ]
    )

    attendance_report, quiz_report = TheoryTopicReporter(source).build()

    assert attendance_report["T01_Asistencia"].iloc[0] == "si"
    assert attendance_report["T12_Asistencia"].iloc[0] == "no"
    assert quiz_report["T12_Nota_Cuestionario"].iloc[0] == pytest.approx(9.5)
    assert "T05_Asistencia" in attendance_report.columns  # the usual columns are kept
    assert attendance_report["Total_Asistencias_Teoria"].iloc[0] == 1
