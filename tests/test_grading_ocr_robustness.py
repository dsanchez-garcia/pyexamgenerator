"""Regresiones del flujo OCR (GRD-7, GRD-8, SEC-4) sin ejecutar el OCR real.

Necesitan el extra `[grading]` (cv2/rapidocr) solo para importar el módulo; los objetos se
construyen con `__new__` y un extractor simulado, así que no se cargan modelos de OCR.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("cv2")
extraction = pytest.importorskip("pyexamgenerator.grading.extraction")

AnswerSheetExtractor = extraction.AnswerSheetExtractor
ImageExamGrader = extraction.ImageExamGrader
QuestionInfo = extraction.QuestionInfo
SheetResult = extraction.SheetResult


def _extractor_with_enrollment(enrollment_df):
    extractor = AnswerSheetExtractor.__new__(AnswerSheetExtractor)
    extractor.id_col = "Número de ID"
    extractor._set_enrollment_df(enrollment_df)
    return extractor


def test_match_official_student_uses_labels_not_positions():
    """GRD-7: con un índice no consecutivo, `.iloc[best_idx]` devolvía otro alumno (o fallaba)."""
    enrollment = pd.DataFrame(
        [
            {"Nombre": "Ana", "Apellido(s)": "Gil", "Número de ID": 111},
            {"Nombre": "Leo", "Apellido(s)": "Ruiz", "Número de ID": 222},
        ],
        index=[1, 0],  # p. ej. una matrícula ordenada o filtrada antes de pasarla
    )
    extractor = _extractor_with_enrollment(enrollment)

    assert extractor._match_official_student(None, "Leo", "Ruiz") == ("Leo Ruiz", "222")
    assert extractor._match_official_student(None, "Ana", "Gil") == ("Ana Gil", "111")


def test_match_official_student_normalizes_ids():
    """Un ID ausente ya no se devuelve como 'nan' y los leídos como float no llevan '.0'."""
    enrollment = pd.DataFrame(
        [
            {"Nombre": "Ana", "Apellido(s)": "Gil", "Número de ID": 12345678.0},
            {"Nombre": "Leo", "Apellido(s)": "Ruiz", "Número de ID": None},
        ]
    )
    extractor = _extractor_with_enrollment(enrollment)

    assert extractor._match_official_student(None, "Ana", "Gil") == ("Ana Gil", "12345678")
    assert extractor._match_official_student(None, "Leo", "Ruiz") == ("Leo Ruiz", None)


def test_process_batch_can_skip_unreadable_images(monkeypatch):
    """GRD-8: con skip_errors, una imagen ilegible se anota en failed_images y el lote sigue."""
    extractor = AnswerSheetExtractor.__new__(AnswerSheetExtractor)

    def fake_process_image(path):
        if path == "rota.jpg":
            raise FileNotFoundError("Could not read image: rota.jpg")
        return SheetResult(path, "A", None, None, None, None, None, {}, [])

    monkeypatch.setattr(extractor, "process_image", fake_process_image)

    results = extractor.process_batch(["ok1.jpg", "rota.jpg", "ok2.jpg"], skip_errors=True)

    assert [r.image for r in results] == ["ok1.jpg", "ok2.jpg"]
    assert [image for image, _ in extractor.failed_images] == ["rota.jpg"]
    with pytest.raises(FileNotFoundError):
        extractor.process_batch(["rota.jpg"])


class _FakeExtractor:
    min_gap = 0.05

    def __init__(self, sheets, failed):
        self._sheets = sheets
        self.failed_images = []
        self._failed = failed

    def process_batch(self, image_paths, skip_errors=False):
        self.failed_images = list(self._failed)
        return list(self._sheets)


def _grader(sheets, failed):
    grader = ImageExamGrader.__new__(ImageExamGrader)
    question = QuestionInfo(name="Pregunta 01", answers={"a": 1.0, "b": 0.0, "c": 0.0, "d": 0.0})
    grader.questions_by_exam_type = {"A": {"Pregunta 01": question}, "B": {"Pregunta 01": question}}
    grader.available_exam_types = ["A", "B"]
    grader.enrollment_df = None
    grader.last_name_col = "Apellido(s)"
    grader.first_name_col = "Nombre"
    grader.id_col = "Número de ID"
    grader.email_col = "Dirección de correo"
    grader.extractor = _FakeExtractor(sheets, failed)
    return grader


def test_grade_from_images_reports_unreadable_and_unresolved_sheets(tmp_path):
    """GRD-8: una imagen ilegible o sin tipo de examen deducible abortaba toda la corrección."""
    sheets = [
        SheetResult("buena.jpg", "A", None, None, None, "Ana Gil", "111", {"Pregunta 01": "a"}, []),
        SheetResult("sin_tipo.jpg", None, None, None, None, "Leo Ruiz", "222", {"Pregunta 01": "a"}, []),
    ]
    grader = _grader(sheets, failed=[("rota.jpg", "FileNotFoundError: Could not read image")])

    _answers, grades, _audit = grader.grade_from_images(
        image_paths=["buena.jpg", "sin_tipo.jpg", "rota.jpg"],
        output_answers="respuestas.xlsx",
        output_grades="calificaciones.xlsx",
        output_dir=str(tmp_path),
        output_incidents="incidencias.xlsx",
        prompt_missing_type=False,
    )

    assert grades["Imagen"].tolist() == ["buena.jpg"]
    incidents = pd.read_excel(tmp_path / "incidencias.xlsx")
    by_type = dict(zip(incidents["Tipo"], incidents["Imagen"]))
    assert by_type["UNREADABLE_IMAGE"] == "rota.jpg"
    assert by_type["EXAM_TYPE_UNRESOLVED"] == "sin_tipo.jpg"
    assert set(incidents.loc[incidents["Imagen"].isin(["rota.jpg", "sin_tipo.jpg"]), "Severidad"]) == {"alta"}
    assert [s["Imagen"] for s in grader.skipped_sheets] == ["rota.jpg", "sin_tipo.jpg"]


def test_default_temp_dir_is_not_the_desktop():
    """SEC-4: las copias temporales de escaneos ya no van al Escritorio (a menudo en la nube)."""
    default = Path(AnswerSheetExtractor._default_temp_image_dir())

    assert "Desktop" not in default.parts
    assert default.parent == Path(tempfile.gettempdir())


def test_missing_exam_type_is_asked_through_a_callback(tmp_path):
    """ARC-7: el tipo de examen no detectado solo se podía preguntar con input()."""
    sheets = [
        SheetResult("sin_tipo.jpg", None, None, None, None, "Leo Ruiz", "222", {"Pregunta 01": "a"}, []),
        SheetResult("otra.jpg", None, None, None, None, "Eva Sanz", "333", {"Pregunta 01": "a"}, []),
    ]
    grader = _grader(sheets, failed=[])
    asked = []

    def choose_type(image_name, available_types, suggestion):
        asked.append((image_name, available_types, suggestion))
        return "b" if image_name == "sin_tipo.jpg" else None  # None: not decided

    _answers, grades, _audit = grader.grade_from_images(
        image_paths=["sin_tipo.jpg", "otra.jpg"], output_answers="respuestas.xlsx",
        output_grades="calificaciones.xlsx", output_dir=str(tmp_path), exam_type_callback=choose_type,
    )

    assert asked == [("sin_tipo.jpg", ["A", "B"], "A"), ("otra.jpg", ["A", "B"], "A")]
    assert grades["Imagen"].tolist() == ["sin_tipo.jpg"]
    assert grades["Tipo_Examen"].tolist() == ["B"]
    assert [s["Tipo"] for s in grader.skipped_sheets] == ["EXAM_TYPE_UNRESOLVED"]


def test_doubtful_answers_are_reviewed_through_a_callback(tmp_path):
    """ARC-7: la revisión interactiva de respuestas dudosas solo funcionaba con input()."""
    audit = [{"Pregunta": "Pregunta 01", "Seleccionada": "-", "Decision": "", "Score_a": 0.10, "Score_b": 0.35}]
    sheets = [SheetResult("hoja.jpg", "A", None, None, None, "Ana Gil", "111", {"Pregunta 01": "-"}, audit)]
    grader = _grader(sheets, failed=[])
    reviewed = []

    def review(image_path, question, current, suggested, margin):
        reviewed.append((image_path, question, current, suggested))
        return "A"

    grader.grade_from_images(
        image_paths=["hoja.jpg"], output_answers="respuestas.xlsx", output_grades="calificaciones.xlsx",
        output_dir=str(tmp_path), output_manual_changes="cambios.xlsx",
        interactive_review=True, open_image_on_review=False, review_callback=review,
    )

    assert reviewed == [("hoja.jpg", "Pregunta 01", "-", "b")]
    assert sheets[0].answers["Pregunta 01"] == "a"
    changes = pd.read_excel(tmp_path / "cambios.xlsx")
    assert changes[["Valor_Anterior", "Valor_Final"]].values.tolist() == [["-", "a"]]


def test_interactive_review_without_a_terminal_needs_a_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(extraction, "stdin_is_interactive", lambda: False)
    grader = _grader([], failed=[])

    with pytest.raises(ValueError, match="review_callback"):
        grader.grade_from_images(
            image_paths=[], output_answers="respuestas.xlsx", output_grades="calificaciones.xlsx",
            output_dir=str(tmp_path), interactive_review=True,
        )
