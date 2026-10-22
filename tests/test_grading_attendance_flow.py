"""Flujo completo de asistencia + justificaciones + cuestionarios (`AbsenceJustificationManager.analyze`,
TST-4) con datos sintéticos en el formato de las exportaciones de Moodle."""

from datetime import datetime

import pandas as pd
import pytest

from pyexamgenerator.grading.api import AbsenceJustificationConfig, ExamCorrectionAPI
from pyexamgenerator.grading.attendance import AbsenceJustificationManager

CLASS_1 = "3 mar 2026 10:00 Todos los estudiantes"
CLASS_2 = "10 mar 2026 10:00 Todos los estudiantes"
QUIZ_T3 = "Cuestionario:Cuestionario Tema 3 - GIM (Real)"
QUIZ_LPRL = "Cuestionario:Cuestionario Ley 31/95 - GIM (Real)"
STUDENTS = [("Gil", "Ana", "111"), ("Ruiz", "Leo", "222"), ("Sanz", "Eva", "333")]


@pytest.fixture
def course(tmp_path):
    """Enrollment, attendance (header in row 3, as Moodle exports it), schedule, justifications and
    class quizzes for three students: Ana attends everything, Leo misses one class and justifies it by
    email, Eva misses one class without justifying it and fails the quizzes."""
    pd.DataFrame([{"Apellido(s)": a, "Nombre": n, "Número de ID": i, "Dirección de correo": f"{n.lower()}@uca.es"}
                  for a, n, i in STUDENTS]).to_excel(tmp_path / "matricula.xlsx", index=False)

    attendance = pd.DataFrame([
        {"Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": "111", CLASS_1: "P (2/2)", CLASS_2: "P (2/2)"},
        {"Apellido(s)": "Ruiz", "Nombre": "Leo", "Número de ID": "222", CLASS_1: "P (2/2)", CLASS_2: "A (0/2)"},
        {"Apellido(s)": "Sanz", "Nombre": "Eva", "Número de ID": "333", CLASS_1: "P (2/2)", CLASS_2: "A (0/2)"},
    ])
    with pd.ExcelWriter(tmp_path / "asistencias.xlsx") as writer:
        pd.DataFrame([["Asistencia del curso"], [""], [""]]).to_excel(writer, index=False, header=False)
        attendance.to_excel(writer, index=False, startrow=3)

    pd.DataFrame([
        {"Fecha de Inicio": datetime(2026, 3, 3, 10), "Descripción": "Tema 3", "Título (EDITABLE)": "Teoría GIM"},
        {"Fecha de Inicio": datetime(2026, 3, 10, 10), "Descripción": "Ley 31/95", "Título (EDITABLE)": "Teoría GIM"},
    ]).to_excel(tmp_path / "horario.xlsx", index=False)

    pd.DataFrame([{
        "FECHA": "11/03/2026",
        "REMITENTE": "Leo Ruiz <leo@uca.es>",
        "ASUNTO": "Justificación de falta",
        "MENSAJE": ("Día de la falta (formato mm/dd/aaaa): 03/10/2026\n"
                    "Nº Tema/Práctica a la que se ha faltado: Ley 31/95\n"
                    "Grupo (GIM o GITI-GIE-GIEI): GIM\n"
                    "Motivo de la ausencia: cita médica"),
    }]).to_excel(tmp_path / "justificaciones.xlsx", index=False)

    pd.DataFrame([
        {"Apellido(s)": "Gil", "Nombre": "Ana", QUIZ_T3: "8,00", QUIZ_LPRL: "9,00"},
        {"Apellido(s)": "Ruiz", "Nombre": "Leo", QUIZ_T3: "9,00", QUIZ_LPRL: "8,00"},
        {"Apellido(s)": "Sanz", "Nombre": "Eva", QUIZ_T3: "5,00", QUIZ_LPRL: "4,00"},
    ]).to_excel(tmp_path / "cuestionarios.xlsx", index=False)
    return tmp_path


def _manager(course, **kwargs):
    return AbsenceJustificationManager(
        attendance_xlsx_path=str(course / "asistencias.xlsx"),
        justifications_xlsx_path=str(course / "justificaciones.xlsx"),
        enrollment_xlsx_path=str(course / "matricula.xlsx"),
        schedule_xlsx_path=str(course / "horario.xlsx"),
        quizzes_xlsx_path=str(course / "cuestionarios.xlsx"),
        **kwargs,
    )


def test_justification_is_matched_to_the_student_and_the_missed_class(course):
    result = _manager(course).analyze()

    summary = result.summary_df.iloc[0]
    assert summary["Alumno_Matcheado"] == "Leo Ruiz" and summary["ID_Alumno"] == "222"
    assert summary["Mensaje_Clasificacion"] == "justifica_falta"
    assert summary["Justif_Tema_Practica"] == "Ley 31/95" and summary["Justif_Grupo"] == "GIM"
    assert summary["Num_Faltas_Claras"] == 1
    assert "10/03/2026 | LPRL | GIM" in summary["Fechas_Faltas_Claras"]


def test_bonus_point_needs_attendance_or_justification_and_quizzes(course):
    """Extreme mode (default): a student who wrote a justification has every absence justified."""
    bonus = _manager(course).analyze().attendance_quiz_df.set_index("Nombre")

    assert bonus.loc["Ana", "Tiene_Punto_Adicional_Teoria"] == "si"
    assert bonus.loc["Leo", "Tiene_Punto_Adicional_Teoria"] == "si"
    assert bonus.loc["Eva", "Tiene_Punto_Adicional_Teoria"] == "no"
    assert "faltas_no_justificadas" in bonus.loc["Eva", "Motivo_No_Punto"]
    assert "nota_baja_en_temas" in bonus.loc["Eva", "Motivo_No_Punto"]
    assert bonus.loc["Ana", "ID_Alumno"] == "111"


def test_without_extreme_mode_only_the_classes_in_the_email_count(course):
    bonus = _manager(course, justification_mode="normal").analyze().attendance_quiz_df.set_index("Nombre")

    # Leo's email justifies the class he missed, so he keeps the bonus point.
    assert bonus.loc["Leo", "Tiene_Punto_Adicional_Teoria"] == "si"
    assert bonus.loc["Eva", "Tiene_Punto_Adicional_Teoria"] == "no"


def test_facade_exports_every_table_and_the_steps_manifest(course):
    """TST-4: `export_steps_dir` + `manifest.json` no tenían test."""
    import json

    api = ExamCorrectionAPI()
    cfg = AbsenceJustificationConfig(
        attendance_xlsx_path=str(course / "asistencias.xlsx"),
        justifications_xlsx_path=str(course / "justificaciones.xlsx"),
        enrollment_xlsx_path=str(course / "matricula.xlsx"),
        schedule_xlsx_path=str(course / "horario.xlsx"),
        quizzes_xlsx_path=str(course / "cuestionarios.xlsx"),
        output_dir=str(course / "salida"),
    )

    api.process_absence_justifications(cfg, export_steps_dir=str(course / "pasos"))

    written = sorted(p.name for p in (course / "salida").iterdir())
    assert written == sorted([
        "justificaciones_resumen.xlsx", "justificaciones_detalle.xlsx", "asistencias_resumen_alumnos.xlsx",
        "justificaciones_vs_faltas.xlsx", "asistencias_con_cuestionarios.xlsx", "faltas_justificadas_modo_extremo.xlsx",
    ])
    (run_dir,) = list((course / "pasos").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["workflow"] == "process_absence_justifications"
    names = [step["name"] for step in manifest["steps"]]
    assert names[:3] == ["attendance_input", "justifications_input", "enrollment_input"]
    assert "attendance_with_quizzes" in names
    for step in manifest["steps"]:
        assert (run_dir / step["file"]).exists()
    assert manifest["outputs"]["summary_output"].endswith("justificaciones_resumen.xlsx")
