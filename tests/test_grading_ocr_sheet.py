"""Hojas de respuestas sintéticas con un RapidOCR simulado (TST-4).

Las imágenes son reales (PNG con casillas y marcas dibujadas con OpenCV) y recorren todo el flujo de
`AnswerSheetExtractor` e `ImageExamGrader`: lectura del fichero, orientación, tinta de cada casilla,
identificación del alumno y nota. Solo se simula el reconocimiento de texto: el OCR falso «lee» los
textos impresos de la hoja cuando la imagen está derecha, como el real, sin cargar modelos. Se prueba
con la API de los dos backends (`rapidocr` y `rapidocr_onnxruntime`).
"""

from types import SimpleNamespace

import pandas as pd
import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
extraction = pytest.importorskip("pyexamgenerator.grading.extraction")

AnswerSheetExtractor = extraction.AnswerSheetExtractor
ImageExamGrader = extraction.ImageExamGrader

# Layout of the synthetic sheet (pixels, upright).
_OPTION_X = {"a": 250, "b": 310, "c": 370, "d": 430, "nc": 490}
_HEADER_Y = 200
_FIRST_QUESTION_Y = 240
_QUESTION_SPACING = 40
_QUESTION_X = 80
_HALF_BOX = 9
_FONT = cv2.FONT_HERSHEY_SIMPLEX

# Answers marked on the sheet ("-" = nothing marked).
_ANA_ANSWERS = ["a", "b", "c", "d", "a", "-", "nc", "b", "c", "d"]
_EXPECTED_ANA = {f"Pregunta {n:02d}": answer for n, answer in enumerate(_ANA_ANSWERS, start=1)}


def _draw_sheet(answers, exam_type, first_name, last_name):
    """Returns the upright sheet and the ``[box, text, score]`` items an OCR would find on it."""
    image = np.full((700, 600), 255, dtype=np.uint8)
    texts = [
        (f"Tipo: {exam_type}", 480, 40),
        ("Nombre", 80, 80),
        (first_name, 250, 80),
        ("Apellidos", 80, 130),
        (last_name, 260, 130),
    ]
    texts += [(label.upper(), x, _HEADER_Y) for label, x in _OPTION_X.items()]
    for number, answer in enumerate(answers, start=1):
        y = _FIRST_QUESTION_Y + (number - 1) * _QUESTION_SPACING
        texts.append((f"{number:02d}", _QUESTION_X, y))
        for label, x in _OPTION_X.items():
            filled = cv2.FILLED if label == answer else 1
            cv2.rectangle(image, (x - _HALF_BOX, y - _HALF_BOX), (x + _HALF_BOX, y + _HALF_BOX), 0, filled)

    items = []
    for text, cx, cy in texts:
        (width, height), _ = cv2.getTextSize(text, _FONT, 0.6, 1)
        x0, y0 = cx - width // 2, cy - height // 2
        cv2.putText(image, text, (x0, y0 + height), _FONT, 0.6, 0, 1, cv2.LINE_AA)
        box = [[x0, y0], [x0 + width, y0], [x0 + width, y0 + height], [x0, y0 + height]]
        items.append([box, text, 0.95])
    return image, items


@pytest.fixture(params=["new", "legacy"])
def ocr_sheets(request, monkeypatch):
    """Sheets known to a fake ``RapidOCR`` that answers with the API of each backend."""
    backend = request.param
    sheets = []

    class FakeRapidOCR:
        def __call__(self, image):
            gray = image[:, :, 0] if image.ndim == 3 else image
            items = next((items for upright, items in sheets if np.array_equal(gray, upright)), [])
            if backend == "legacy":
                return (items or None), 0.01
            if not items:
                return SimpleNamespace(boxes=None, txts=None, scores=None)
            return SimpleNamespace(
                boxes=np.array([box for box, _, _ in items], dtype=float),
                txts=tuple(text for _, text, _ in items),
                scores=tuple(score for _, _, score in items),
            )

    monkeypatch.setattr(extraction, "RapidOCR", FakeRapidOCR)
    monkeypatch.setattr(extraction, "_RAPIDOCR_BACKEND", backend)
    return sheets


def _scan(path, sheets, answers, exam_type="A", first_name="Ana", last_name="Gil", rotation=None):
    """Writes the sheet as a PNG (optionally scanned turned) and registers it with the fake OCR."""
    upright, items = _draw_sheet(answers, exam_type, first_name, last_name)
    sheets.append((upright, items))
    scanned = upright if rotation is None else cv2.rotate(upright, rotation)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", scanned)[1].tofile(str(path))  # tofile: also with non-ASCII paths
    return str(path)


def _enrollment():
    return pd.DataFrame(
        [
            {"Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": "45123456", "Dirección de correo": "ana@example.com"},
            {"Apellido(s)": "Ruiz", "Nombre": "Leo", "Número de ID": "45654321", "Dirección de correo": "leo@example.com"},
        ]
    )


def _decisions(result):
    return {row["Pregunta"]: row["Decision"] for row in result.audit_rows}


def test_answers_and_student_are_read_from_a_synthetic_sheet(ocr_sheets, tmp_path):
    image = _scan(tmp_path / "hoja.png", ocr_sheets, _ANA_ANSWERS)
    extractor = AnswerSheetExtractor(enrollment_df=_enrollment(), debug_dir=str(tmp_path / "debug"))

    result = extractor.process_image(image)

    assert result.exam_type == "A"
    assert (result.first_name_raw, result.last_name_raw) == ("Ana", "Gil")
    assert (result.student_name_official, result.student_id_official) == ("Ana Gil", "45123456")
    assert result.rotation_degrees == 0
    assert result.answers == _EXPECTED_ANA
    decisions = _decisions(result)
    assert decisions.pop("Pregunta 06") == "blank"
    assert decisions.pop("Pregunta 07") == "nc"
    assert set(decisions.values()) == {"strict"}
    assert (tmp_path / "debug" / "hoja_debug.png").exists()


@pytest.mark.parametrize(
    "rotation, degrees_back",
    [(cv2.ROTATE_90_CLOCKWISE, 270), (cv2.ROTATE_180, 180), (cv2.ROTATE_90_COUNTERCLOCKWISE, 90)],
)
def test_turned_scan_is_put_upright_before_reading(ocr_sheets, tmp_path, rotation, degrees_back):
    image = _scan(tmp_path / "girada.png", ocr_sheets, _ANA_ANSWERS, rotation=rotation)
    extractor = AnswerSheetExtractor(enrollment_df=_enrollment())

    result = extractor.process_image(image)

    assert result.rotation_degrees == degrees_back
    assert result.answers == _EXPECTED_ANA
    assert result.student_id_official == "45123456"


def test_sheet_in_a_folder_with_accents_is_read(ocr_sheets, tmp_path):
    """OpenCV no abre rutas con tildes en Windows: se lee por la vía alternativa."""
    image = _scan(tmp_path / "Exámenes 1º" / "hoja_Núñez.png", ocr_sheets, _ANA_ANSWERS)

    result = AnswerSheetExtractor().process_image(image)

    assert result.answers == _EXPECTED_ANA


def _write_quiz_xml(path, correct):
    """Moodle XML whose answers are the letters: right +100 %, wrong -25 %."""
    questions = []
    for number, right in enumerate(correct, start=1):
        answers = "".join(
            f'<answer fraction="{100 if letter == right else -25}"><text>{letter}</text></answer>'
            for letter in "abcd"
        )
        questions.append(
            f'<question type="multichoice"><name><text>Pregunta {number:02d}</text></name>{answers}</question>'
        )
    path.write_text(f'<?xml version="1.0" encoding="UTF-8"?><quiz>{"".join(questions)}</quiz>', encoding="utf-8")
    return str(path)


def test_synthetic_sheets_are_graded_end_to_end(ocr_sheets, tmp_path):
    xml_a = _write_quiz_xml(tmp_path / "examen_A.xml", ["a", "b", "c", "d", "a", "a", "b", "b", "c", "a"])
    xml_b = _write_quiz_xml(tmp_path / "examen_B.xml", ["b"] * 10)
    enrollment = tmp_path / "matricula.xlsx"
    _enrollment().to_excel(enrollment, index=False)
    ana = _scan(tmp_path / "hojas" / "ana.png", ocr_sheets, _ANA_ANSWERS)
    leo = _scan(
        tmp_path / "hojas" / "leo.png", ocr_sheets, ["b"] * 9 + ["-"], exam_type="B",
        first_name="Leo", last_name="Ruiz", rotation=cv2.ROTATE_90_CLOCKWISE,
    )
    grader = ImageExamGrader(xml_paths=[xml_a, xml_b], enrollment_path=str(enrollment))

    _answers, grades, _audit = grader.grade_from_images(
        image_paths=[ana, leo],
        output_answers="respuestas.xlsx",
        output_grades="calificaciones.xlsx",
        output_dir=str(tmp_path / "salida"),
        output_audit="auditoria.xlsx",
        output_incidents="incidencias.xlsx",
        prompt_missing_type=False,
    )

    by_image = grades.set_index("Imagen")
    # Ana: 7 right, question 10 wrong (-0,25), 6 blank and 7 "no contesta".
    assert by_image.loc[ana, "Tipo_Examen"] == "A"
    assert by_image.loc[ana, "Calificacion/10,00"] == "6,75"
    assert by_image.loc[ana, ["P. 6 /1,00", "P. 7 /1,00", "P. 10 /1,00"]].tolist() == ["-", "-", "-0,25"]
    assert by_image.loc[ana, ["Nombre", "Apellido(s)", "Número de ID"]].tolist() == ["Ana", "Gil", "45123456"]
    # Leo: type B, scanned sideways, 9 right and one blank.
    assert by_image.loc[leo, "Tipo_Examen"] == "B"
    assert by_image.loc[leo, "Calificacion/10,00"] == "9,00"
    assert by_image.loc[leo, "Dirección de correo"] == "leo@example.com"

    incidents = pd.read_excel(tmp_path / "salida" / "incidencias.xlsx")
    assert sorted(zip(incidents["Imagen"], incidents["Tipo"])) == [
        (ana, "UNRESOLVED_ANSWERS"), (leo, "UNRESOLVED_ANSWERS"),
    ]
    assert (tmp_path / "salida" / "auditoria.xlsx").exists()
