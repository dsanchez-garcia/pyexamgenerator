"""Regresiones de robustez de `ExamGenerator` (BUG-3, BUG-4, BUG-5, BUG-8)."""

import random
import xml.etree.ElementTree as ET

import pandas as pd
import pytest
from docx import Document

from pyexamgenerator.exam_generator import ExamGenerator


def _bank(rows=None, **overrides):
    if rows is None:
        rows = 4
    data = []
    for i in range(rows):
        row = {
            "Número de pregunta": i + 1,
            "Tema": "Tema 01",
            "Estado": "Aceptable",
            "Pregunta": f"Pregunta {i + 1}",
            "Respuesta A": f"A{i}",
            "Respuesta B": f"B{i}",
            "Respuesta C": f"C{i}",
            "Respuesta D": f"D{i}",
            "Respuesta correcta": "b",
            "Texto relevante": "",
        }
        data.append(row)
    df = pd.DataFrame(data)
    for column, values in overrides.items():
        df[column] = values
    return df


def _generate(bank_path, out_dir=None, **kwargs):
    generator = ExamGenerator()
    params = dict(
        bank_excel_path=str(bank_path),
        subject="Asig",
        exam="Parcial",
        course="25-26",
        exam_names=["A"],
    )
    if out_dir is not None:
        params["output_dir"] = str(out_dir)
    params.update(kwargs)
    generator.generate_exam_from_excel(**params)
    return generator


def _xml_questions(xml_path):
    root = ET.parse(str(xml_path)).getroot()
    return root.findall("./question[@type='multichoice']")


def test_bank_given_as_bare_file_name(tmp_path, monkeypatch):
    """BUG-3: 'banco.xlsx' sin carpeta hacía os.makedirs('') y fallaba."""
    monkeypatch.chdir(tmp_path)
    _bank().to_excel("banco.xlsx", index=False)

    _generate("banco.xlsx")

    assert (tmp_path / "examen_Asig_Parcial_25-26_A.docx").exists()


def test_moodle_xml_with_numeric_and_empty_answers(tmp_path):
    """BUG-4: con xml_use_answer_text=True, respuestas numéricas o vacías rompían la serialización."""
    bank = _bank(
        2,
        **{
            "Respuesta A": [25, 3.5],
            "Respuesta B": [30, None],
            "Respuesta C": ["texto", 7],
            "Respuesta D": [None, 8],
            "Respuesta correcta": ["a", "c"],
        },
    )
    bank_path = tmp_path / "banco.xlsx"
    bank.to_excel(bank_path, index=False)

    random.seed(0)
    _generate(bank_path, tmp_path / "out", export_moodle_xml=True, xml_use_answer_text=True)

    questions = _xml_questions(tmp_path / "out" / "examen_Asig_Parcial_25-26_A.xml")
    assert len(questions) == 2
    answer_texts = {(a.find("text").text or "") for q in questions for a in q.findall("answer")}
    # Los enteros leídos como float (columna con huecos) se escriben sin decimales.
    assert answer_texts == {"25", "30", "3.5", "7", "8", "texto", ""}
    # Cada pregunta conserva exactamente una respuesta correcta.
    for question in questions:
        assert [a.get("fraction") for a in question.findall("answer")].count("100") == 1

    # El DOCX del profesor tampoco muestra 'nan' ni '25.0'.
    docx_text = "\n".join(
        p.text for p in Document(str(tmp_path / "out" / "examen_Asig_Parcial_25-26_A_completo.docx")).paragraphs
    )
    assert "nan" not in docx_text
    assert "25.0" not in docx_text
    assert ") 25" in docx_text


def test_menos_usadas_without_usage_column(tmp_path):
    """BUG-5: 'menos usadas' lanzaba KeyError si el banco no tenía 'Veces usada en examen'."""
    bank_path = tmp_path / "banco.xlsx"
    _bank(4).to_excel(bank_path, index=False)

    generator = _generate(
        bank_path, tmp_path / "out", questions_per_topic={"Tema 01": 2}, selection_method="menos usadas"
    )

    assert len(generator.exam_df) == 2


def test_menos_usadas_prefers_least_used(tmp_path):
    bank_path = tmp_path / "banco.xlsx"
    _bank(4, **{"Veces usada en examen": [3, 0, 2, 1]}).to_excel(bank_path, index=False)

    generator = _generate(
        bank_path, tmp_path / "out", questions_per_topic={"Tema 01": 2}, selection_method="menos usadas"
    )

    assert sorted(generator.exam_df["Pregunta"]) == ["Pregunta 2", "Pregunta 4"]


@pytest.mark.parametrize("raw_letter", ["B)", " b ", "b.", "(B)"])
def test_handwritten_correct_letter_variants(tmp_path, raw_letter):
    """BUG-8: variantes como 'B)' lanzaban KeyError al barajar."""
    bank_path = tmp_path / "banco.xlsx"
    _bank(3, **{"Respuesta correcta": [raw_letter] * 3}).to_excel(bank_path, index=False)

    random.seed(1)
    _generate(bank_path, tmp_path / "out", export_moodle_xml=True, xml_use_answer_text=True)

    exam = pd.read_excel(tmp_path / "out" / "examen_Asig_Parcial_25-26_A_completo.xlsx")
    for _, row in exam.iterrows():
        letter = row["Respuesta correcta"]
        assert letter in {"a", "b", "c", "d"}
        # Tras barajar, la letra sigue apuntando al texto correcto original ('B<i>').
        assert str(row[f"Respuesta {letter.upper()}"]).startswith("B")


def test_duplicated_answer_texts_keep_the_right_letter(tmp_path):
    """Con textos de respuesta repetidos, la letra correcta sigue apuntando al texto correcto."""
    bank = _bank(
        1,
        **{
            "Respuesta A": ["Igual"],
            "Respuesta B": ["Igual"],
            "Respuesta C": ["Otra"],
            "Respuesta D": ["Correcta"],
            "Respuesta correcta": ["d"],
        },
    )
    bank_path = tmp_path / "banco.xlsx"
    bank.to_excel(bank_path, index=False)

    for seed in range(5):
        random.seed(seed)
        _generate(bank_path, tmp_path / f"out{seed}")
        exam = pd.read_excel(tmp_path / f"out{seed}" / "examen_Asig_Parcial_25-26_A_completo.xlsx")
        letter = exam["Respuesta correcta"].iloc[0]
        assert exam[f"Respuesta {letter.upper()}"].iloc[0] == "Correcta"


def test_invalid_correct_letter_raises_clear_error(tmp_path):
    """BUG-8: una respuesta correcta vacía o inválida producía un examen sin respuesta correcta."""
    bank_path = tmp_path / "banco.xlsx"
    _bank(3, **{"Respuesta correcta": ["a", None, "E"]}).to_excel(bank_path, index=False)

    with pytest.raises(ValueError, match="Respuesta correcta"):
        _generate(bank_path, tmp_path / "out")
    assert not (tmp_path / "out" / "examen_Asig_Parcial_25-26_A.docx").exists()
