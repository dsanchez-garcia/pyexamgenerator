"""Lógica de la GUI que no necesita pantalla (`pyexamgenerator.gui_logic`, ARC-1 y TST-5).

Lo que el usuario escribe en los campos se interpreta aquí; `main_app.py` solo lee los widgets.
Estas pruebas no importan `tkinter`, así que se ejecutan también donde no hay pantalla.
"""

import pytest

from pyexamgenerator import gui_logic


def test_gui_logic_does_not_need_tk():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(gui_logic))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom) and node.module}
    assert "tkinter" not in imported


def test_split_paths_uses_semicolons_and_new_lines(tmp_path):
    assert gui_logic.split_paths("a.pdf; b, c.pdf\n d.pdf ;") == ["a.pdf", "b, c.pdf", "d.pdf"]
    assert gui_logic.split_paths("") == []
    assert gui_logic.split_paths(None) == []


def test_split_paths_accepts_a_comma_list_typed_by_hand(tmp_path):
    a, b = str(tmp_path / "a.pdf"), str(tmp_path / "b.pdf")
    for path in (a, b):
        open(path, "wb").close()

    assert gui_logic.split_paths(f"{a}, {b}") == [a, b]
    assert gui_logic.split_paths(f"{a};{b}") == [a, b]


def test_split_paths_keeps_a_file_whose_name_has_a_comma(tmp_path):
    path = tmp_path / "Tema 1, introducción.pdf"
    path.write_bytes(b"")

    assert gui_logic.split_paths(str(path)) == [str(path)]


@pytest.mark.parametrize("text, expected", [("", -25.0), ("  ", -25.0), ("-33,33", -33.33), ("-25", -25.0), ("0", 0.0)])
def test_parse_penalty(text, expected):
    assert gui_logic.parse_penalty(text) == expected


def test_parse_penalty_rejects_text():
    with pytest.raises(ValueError):
        gui_logic.parse_penalty("-1/3")


def test_parse_final_grade_files():
    text = "teoria.xlsx|0,6|Teoría ; practicas.xlsx|0.4\n extra.xlsx"

    assert gui_logic.parse_final_grade_files(text) == [
        {"path": "teoria.xlsx", "weight": 0.6, "label": "Teoría"},
        {"path": "practicas.xlsx", "weight": 0.4},
        {"path": "extra.xlsx"},
    ]


def test_parse_final_grade_files_names_the_file_with_a_bad_weight():
    with pytest.raises(ValueError, match="teoria.xlsx"):
        gui_logic.parse_final_grade_files("teoria.xlsx|mucho")


def test_parse_column_weights():
    assert gui_logic.parse_column_weights("Teoria|3 ; Practicas|1,5 ; sin peso") == {"Teoria": 3.0, "Practicas": 1.5}
    with pytest.raises(ValueError, match="Practicas"):
        gui_logic.parse_column_weights("Practicas|x")


def test_parse_forced_types():
    text = "hoja1.jpg=a, hoja2.jpg = 1b\nhoja3.jpg=\nsin_tipo.jpg"

    assert gui_logic.parse_forced_types(text) == {"hoja1.jpg": "A", "hoja2.jpg": "1B"}


def test_parse_exam_names():
    assert gui_logic.parse_exam_names("") is None
    assert gui_logic.parse_exam_names(" 1A , 1B") == ["1A", "1B"]


def test_parse_questions_per_topic():
    assert gui_logic.parse_questions_per_topic("Tema 01:2, Tema 02: 3") == {"Tema 01": 2, "Tema 02": 3}
    assert gui_logic.parse_questions_per_topic("") == {}
    with pytest.raises(ValueError):
        gui_logic.parse_questions_per_topic("Tema 01-2")


def test_trailing_comma_in_exam_names_does_not_add_an_exam():
    """Con «1A, 1B,» se generaba una tercera versión del examen, sin nombre."""
    assert gui_logic.parse_exam_names("1A, 1B,") == ["1A", "1B"]
    assert gui_logic.parse_exam_names("1A,,1B") == ["1A", "1B"]
    assert gui_logic.parse_exam_names(" , ") is None


def test_questions_per_topic_accepts_a_trailing_comma_and_colons_in_the_topic():
    """Una coma final o un «:» en el nombre del tema daban «Formato incorrecto»."""
    assert gui_logic.parse_questions_per_topic("Tema 01:2, Tema 02:3,") == {"Tema 01": 2, "Tema 02": 3}
    assert gui_logic.parse_questions_per_topic("Tema 1: Introducción:2") == {"Tema 1: Introducción": 2}


@pytest.mark.parametrize("text", ["Tema 01:-2", ":3", "Tema 01:", "Tema 01:dos"])
def test_questions_per_topic_rejects_negative_counts_and_empty_topics(text):
    """Antes se aceptaban un número negativo de preguntas o un tema vacío."""
    with pytest.raises(ValueError):
        gui_logic.parse_questions_per_topic(text)


@pytest.mark.parametrize("text", ["nan", "inf", "-inf"])
def test_penalty_and_weights_must_be_finite_numbers(text):
    """`float()` aceptaba «nan» o «inf»: la penalización o la nota final salían como NaN."""
    with pytest.raises(ValueError):
        gui_logic.parse_penalty(text)
    with pytest.raises(ValueError, match="teoria.xlsx"):
        gui_logic.parse_weight(text, "teoria.xlsx")


def test_weights_cannot_be_negative():
    assert gui_logic.parse_weight("0", "teoria.xlsx") == 0.0
    with pytest.raises(ValueError, match="teoria.xlsx"):
        gui_logic.parse_weight("-0,5", "teoria.xlsx")


def test_integration_warnings_mention_overwritten_grades():
    """GRD-12: la GUI avisa cuando la nota OCR sustituye a una nota que ya existía."""
    warnings = gui_logic.integration_warnings(
        {"blocked_unmatched": 1, "grades_overwritten": 2}, "incidencias_integracion_ocr.xlsx")

    assert len(warnings) == 2
    assert "Alumno no encontrado en teoría: 1" in warnings[0]
    assert "2 alumno(s)" in warnings[1] and "incidencias_integracion_ocr.xlsx" in warnings[1]


def test_integration_warnings_without_a_summary():
    assert gui_logic.integration_warnings(None, "x.xlsx") == []
    assert gui_logic.integration_warnings({}, "x.xlsx") == []
