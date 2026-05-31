"""Tests del subpaquete de corrección `pyexamgenerator.grading`.

Cubren la corrección que NO necesita OCR (fusión de matriculados, punto extra de teoría y reporte
por tema). El OCR pesado (cv2/rapidocr) se prueba solo si el extra `[grading]` está instalado.
"""

import pandas as pd
import pytest

from pyexamgenerator import grading
from pyexamgenerator.grading import (
    EnrollmentMerger,
    TheoryBonusApplier,
    TheoryTopicReporter,
)


def test_grading_imports_and_has_ocr_flag():
    assert isinstance(grading.HAS_OCR, bool)
    # La API que no es OCR siempre está disponible.
    assert grading.ExamCorrectionAPI is not None
    assert grading.TheoryBonusApplier is not None


def test_enrollment_merger_combines_sources(tmp_path):
    df_gim = pd.DataFrame(
        [{"Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": "1",
          "Dirección de correo": "ana@x.es", "Grupo": "GIM", "Consulta": "P1"}]
    )
    df_giti = pd.DataFrame(
        [{"Apellido(s)": "Ruiz", "Nombre": "Leo", "Número de ID": "2",
          "Dirección de correo": "leo@x.es", "Grupo": "GITI", "Consulta": "P2"}]
    )
    p1 = tmp_path / "gim.xlsx"
    p2 = tmp_path / "giti.xlsx"
    df_gim.to_excel(p1, index=False)
    df_giti.to_excel(p2, index=False)

    merger = EnrollmentMerger([str(p1), str(p2)])
    merged = merger.merge()

    assert len(merged) == 2
    assert set(merged["Número de ID"]) == {"1", "2"}
    # El objeto retiene inputs y output.
    assert merger.merged_df is merged
    assert len(merger.source_dfs) == 2


def test_theory_bonus_applies_plus_one(tmp_path):
    theory = pd.DataFrame(
        [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "6,00"}]
    )
    attendance_quiz = pd.DataFrame(
        [{"ID_Alumno": "1", "Nombre": "Ana", "Apellido(s)": "Gil",
          "Tiene_Punto_Adicional_Teoria": "si", "Motivo_No_Punto": ""}]
    )
    out = tmp_path / "teoria.xlsx"
    result = TheoryBonusApplier(theory, attendance_quiz, cap_to_10=True).apply(str(out))

    assert out.exists()
    assert float(result["Nota_Final_Teoria"].iloc[0]) == 7.0
    assert float(result["Incremento_Aplicado"].iloc[0]) == 1.0


def test_theory_bonus_caps_at_ten():
    theory = pd.DataFrame(
        [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "10,00"}]
    )
    attendance_quiz = pd.DataFrame(
        [{"ID_Alumno": "1", "Nombre": "Ana", "Apellido(s)": "Gil",
          "Tiene_Punto_Adicional_Teoria": "si", "Motivo_No_Punto": ""}]
    )
    result = TheoryBonusApplier(theory, attendance_quiz, cap_to_10=True).apply()

    assert float(result["Nota_Final_Teoria"].iloc[0]) == 10.0
    assert float(result["Incremento_Aplicado"].iloc[0]) == 0.0
    assert result["Motivo_No_Incremento"].iloc[0] == "nota_ya_en_tope"


def test_theory_bonus_not_granted_when_no_bonus():
    theory = pd.DataFrame(
        [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "6,00"}]
    )
    attendance_quiz = pd.DataFrame(
        [{"ID_Alumno": "1", "Nombre": "Ana", "Apellido(s)": "Gil",
          "Tiene_Punto_Adicional_Teoria": "no", "Motivo_No_Punto": "nota_baja_cuestionario"}]
    )
    result = TheoryBonusApplier(theory, attendance_quiz).apply()

    assert float(result["Incremento_Aplicado"].iloc[0]) == 0.0
    assert float(result["Nota_Final_Teoria"].iloc[0]) == 6.0


def test_theory_topic_reporter_exposes_extra_point():
    attendance_quiz = pd.DataFrame(
        [{"ID_Alumno": "1", "Nombre": "Ana", "Apellido(s)": "Gil",
          "Tiene_Punto_Adicional_Teoria": "si", "Motivo_No_Punto": ""}]
    )
    reporter = TheoryTopicReporter(attendance_quiz)
    attendance_report, quiz_report = reporter.build()

    assert "Obtiene_Punto_Extra" in quiz_report.columns
    assert quiz_report["Obtiene_Punto_Extra"].iloc[0] == "si"
    # Reporte por tema con las columnas de cuestionario esperadas.
    assert "T02_Nota_Cuestionario" in quiz_report.columns
    assert reporter.quiz_report_df is quiz_report


def test_image_grader_available_only_with_ocr_extra():
    if grading.HAS_OCR:
        pytest.importorskip("cv2")
        assert grading.ImageExamGrader is not None
    else:
        assert grading.ImageExamGrader is None
