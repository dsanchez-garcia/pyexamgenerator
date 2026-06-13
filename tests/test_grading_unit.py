"""Tests del subpaquete de corrección `pyexamgenerator.grading`.

Cubren la corrección que NO necesita OCR (fusión de matriculados, punto extra de teoría y reporte
por tema). El OCR pesado (cv2/rapidocr) se prueba solo si el extra `[grading]` está instalado.
"""

import pandas as pd
import pytest
import numpy as np
from types import SimpleNamespace

from pyexamgenerator import grading
from pyexamgenerator.grading import (
    EnrollmentMerger,
    OcrGradeIntegrator,
    SharedExamDataStore,
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
    assert merger.source_dfs is not None
    assert len(merger.source_dfs) == 2


def test_exam_type_inference_accepts_letter_only_and_numeric_letter():
    infer = SharedExamDataStore._infer_exam_type_from_filename
    assert infer("examen_Geo_Parcial_25-26_A.xml") == "A"
    assert infer("examen_Geo_Parcial_25-26_1A.xml") == "1A"


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


@pytest.mark.parametrize("exam_type", ["1A", "A"])
def test_ocr_integrator_quiz_totals_uses_group_hint(tmp_path, exam_type):
    """En formato quiz-totals, cuando un tipo de examen existe en >1 grupo (GIM vs GITI...),
    la nota manuscrita debe aterrizar en la columna del grupo indicado por la fila OCR
    (Grupo_Principal), no quedarse sin volcar."""
    general = pd.DataFrame(
        [{
            "Nombre de usuario": "uy8862138",
            "Apellido(s)": "CHEBBI",
            "Nombre": "LOUAY",
            "Dirección de correo": "louay.chebbi@x.es",
            f"Cuestionario:GIM_Tipo {exam_type} (Real)": "-",
            f"Cuestionario:GITI-GIE-GIEI_Tipo {exam_type} (Real)": "-",
        }]
    )
    ocr = pd.DataFrame(
        [{
            "Imagen": "img.jpg",
            "Tipo_Examen": exam_type,
            "Nombre": "LOUAY",
            "Apellido(s)": "CHEBBI",
            "Número de ID": "190708",
            "Grupo_Principal": "GITI-GIE-GIEI",
            "Calificacion/10,00": "9,13",
        }]
    )
    general_path = tmp_path / "teoria.xlsx"
    ocr_path = tmp_path / "ocr.xlsx"
    out_path = tmp_path / "integrada.xlsx"
    general.to_excel(general_path, index=False)
    ocr.to_excel(ocr_path, index=False)

    result = OcrGradeIntegrator(
        general_xlsx_path=str(general_path),
        ocr_xlsx_path=str(ocr_path),
    ).integrate(str(out_path))

    row = result[result["Apellido(s)"] == "CHEBBI"].iloc[0]
    assert float(row["Calificación/10,00"]) == pytest.approx(9.13)
    assert row["Tipo_Grupo"] == "GITI-GIE-GIEI"
    assert row["Tipo_Examen"] == exam_type


def test_image_grader_available_only_with_ocr_extra():
    if grading.HAS_OCR:
        pytest.importorskip("cv2")
        assert grading.ImageExamGrader is not None
    else:
        assert grading.ImageExamGrader is None


def test_answer_sheet_extractor_image_read_fallback_when_imread_fails(tmp_path, monkeypatch):
    if not grading.HAS_OCR:
        pytest.skip("OCR extra no disponible")

    cv2 = pytest.importorskip("cv2")
    from pyexamgenerator.grading.extraction import AnswerSheetExtractor

    img_dir = tmp_path / "exam_images"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = img_dir / "sheet.jpg"

    img = np.zeros((12, 12, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    encoded.tofile(str(img_path))

    monkeypatch.setattr(cv2, "imread", lambda *args, **kwargs: None)
    loaded = AnswerSheetExtractor._load_grayscale_image(str(img_path))
    assert loaded is not None
    assert tuple(loaded.shape) == (12, 12)


def test_answer_sheet_extractor_last_resort_temp_copy_fallback(tmp_path, monkeypatch):
    if not grading.HAS_OCR:
        pytest.skip("OCR extra no disponible")

    cv2 = pytest.importorskip("cv2")
    from pyexamgenerator.grading.extraction import AnswerSheetExtractor

    img_path = tmp_path / "origen.jpg"
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    encoded.tofile(str(img_path))

    extractor = AnswerSheetExtractor.__new__(AnswerSheetExtractor)
    temp_root = tmp_path / "pyexamgenerator_temp"
    extractor.temp_image_dir = str(temp_root)

    source_path = str(img_path)
    real_fromfile = np.fromfile
    monkeypatch.setattr(cv2, "imread", lambda *args, **kwargs: None)

    def fake_fromfile(path, dtype=np.uint8):
        if str(path) == source_path:
            raise OSError("force temp-copy fallback")
        return real_fromfile(path, dtype=dtype)

    monkeypatch.setattr(np, "fromfile", fake_fromfile)

    loaded = extractor._load_grayscale_image_with_fallback(source_path)
    assert loaded is not None
    assert tuple(loaded.shape) == (10, 10)
    assert temp_root.exists()
    assert list(temp_root.iterdir()) == []


def test_image_exam_grader_defaults_single_available_type_when_missing():
    if not grading.HAS_OCR:
        pytest.skip("OCR extra no disponible")

    from pyexamgenerator.grading.extraction import ImageExamGrader

    grader = ImageExamGrader.__new__(ImageExamGrader)
    grader.questions_by_exam_type = {"A": {}}
    grader.available_exam_types = ["A"]

    sheet = SimpleNamespace(image="20260612_112047.jpg", exam_type=None, answers={})
    resolved = grader._resolve_exam_type(sheet, forced_type_by_image={}, prompt_if_missing=False)
    assert resolved == "A"


def test_image_exam_grader_accepts_forced_type_by_full_image_path():
    if not grading.HAS_OCR:
        pytest.skip("OCR extra no disponible")

    from pyexamgenerator.grading.extraction import ImageExamGrader

    grader = ImageExamGrader.__new__(ImageExamGrader)
    grader.questions_by_exam_type = {"A": {}, "B": {}}
    grader.available_exam_types = ["A", "B"]

    sheet = SimpleNamespace(image="D:/tmp/20260612_112047.jpg", exam_type=None, answers={})
    forced = {"D:\\TMP\\20260612_112047.jpg": "b"}
    resolved = grader._resolve_exam_type(sheet, forced_type_by_image=forced, prompt_if_missing=False)
    assert resolved == "B"


