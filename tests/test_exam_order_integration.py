import random
import xml.etree.ElementTree as ET
from pathlib import Path

from docx import Document

from pyexamgenerator.exam_generator import ExamGenerator


def test_answer_sheet_order_matches_xml_using_prueba_error_fixture(tmp_path):
	project_root = Path(__file__).resolve().parents[1]
	bank_excel_path = project_root / "prueba_error" / "examen_CSP_Q-PA_25-26.xlsx"

	assert bank_excel_path.exists(), f"No se encuentra el fixture: {bank_excel_path}"

	subject = "Calidad, Seguridad y Protección ambiental"
	exam = "Calidad-Protección ambiental"
	course = "25-26"
	exam_type = "1A"

	generator = ExamGenerator()
	random.seed(20260518)
	generator.generate_exam_from_excel(
		bank_excel_path=str(bank_excel_path),
		output_dir=str(tmp_path),
		exam_names=[exam_type],
		subject=subject,
		exam=exam,
		course=course,
		export_moodle_xml=True,
		update_excel=False,
	)

	base_filename = f"examen_{subject}_{exam}_{course}_{exam_type}"
	docx_path = tmp_path / f"{base_filename}.docx"
	xml_path = tmp_path / f"{base_filename}.xml"

	assert docx_path.exists(), f"No se generó el DOCX esperado: {docx_path}"
	assert xml_path.exists(), f"No se generó el XML esperado: {xml_path}"

	document = Document(str(docx_path))
	answer_table = document.tables[-1]
	docx_question_numbers = [row.cells[0].text.strip() for row in answer_table.rows[1:]]

	assert docx_question_numbers == [f"{i:02d}" for i in range(1, len(docx_question_numbers) + 1)]

	xml_root = ET.parse(str(xml_path)).getroot()
	xml_question_labels = [
		question.find("./name/text").text
		for question in xml_root.findall("./question[@type='multichoice']")
	]

	expected_xml_labels = [f"Pregunta {question_number}" for question_number in docx_question_numbers]
	assert xml_question_labels == expected_xml_labels

