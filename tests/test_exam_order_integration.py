import random
import xml.etree.ElementTree as ET

import pandas as pd
from docx import Document

from pyexamgenerator.exam_generator import ExamGenerator


def _build_realistic_bank(path):
    """Writes a synthetic bank that mimics a real exported one.

    It reproduces the traits of the original (untracked) fixture: several topics with two
    questions each, "Aceptable" capitalised, mixed-case correct letters, an extra
    'Texto respuesta correcta' column and a usage column from a previous exam.
    """
    letters = ["d", "b", "c", "c", "a", "c", "d", "b", "b", "c", "d", "a", "C", "a"]
    topics = [
        "Proteccion ambiental_T7_MARPOL",
        "Calidad_T1_Introduccion",
        "Calidad_T2_Gestion de la calidad",
        "Calidad_T3_ISO 9001_1-3",
        "Calidad_T4_ISO 9001_2-3",
        "Calidad_T5_ISO 9001_3-3",
        "Calidad_T6_EFQM",
    ]
    rows = []
    for i, letter in enumerate(letters):
        answers = {opt: f"Opción {opt} de la pregunta {i + 1}" for opt in "ABCD"}
        rows.append(
            {
                "Número de pregunta": i + 1,
                "Tema": topics[i // 2],
                "Estado": "Aceptable",
                "Pregunta": f"¿Enunciado {i + 1}: cuál es la respuesta correcta?",
                "Respuesta A": answers["A"],
                "Respuesta B": answers["B"],
                "Respuesta C": answers["C"],
                "Respuesta D": answers["D"],
                "Respuesta correcta": letter,
                "Texto relevante": f"Texto relevante {i + 1}",
                "Veces usada en examen": 1,
                "Texto respuesta correcta": answers[letter.upper()],
                "Examen_de_Prueba_Curso_2024_2025_uso": 1,
            }
        )
    pd.DataFrame(rows).to_excel(path, index=False)


def test_answer_sheet_order_matches_xml(tmp_path):
    bank_excel_path = tmp_path / "examen_CSP_Q-PA_25-26.xlsx"
    _build_realistic_bank(bank_excel_path)
    output_dir = tmp_path / "out"

    subject = "Calidad, Seguridad y Protección ambiental"
    exam = "Calidad-Protección ambiental"
    course = "25-26"
    exam_type = "1A"

    generator = ExamGenerator()
    random.seed(20260518)
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_excel_path),
        output_dir=str(output_dir),
        exam_names=[exam_type],
        subject=subject,
        exam=exam,
        course=course,
        export_moodle_xml=True,
        update_excel=False,
    )

    base_filename = f"examen_{subject}_{exam}_{course}_{exam_type}"
    docx_path = output_dir / f"{base_filename}.docx"
    xml_path = output_dir / f"{base_filename}.xml"

    assert docx_path.exists(), f"No se generó el DOCX esperado: {docx_path}"
    assert xml_path.exists(), f"No se generó el XML esperado: {xml_path}"

    document = Document(str(docx_path))
    answer_table = document.tables[-1]
    docx_question_numbers = [row.cells[0].text.strip() for row in answer_table.rows[1:]]

    assert len(docx_question_numbers) == 14
    assert docx_question_numbers == [f"{i:02d}" for i in range(1, len(docx_question_numbers) + 1)]

    xml_root = ET.parse(str(xml_path)).getroot()
    xml_question_labels = [
        question.find("./name/text").text for question in xml_root.findall("./question[@type='multichoice']")
    ]

    expected_xml_labels = [f"Pregunta {question_number}" for question_number in docx_question_numbers]
    assert xml_question_labels == expected_xml_labels
