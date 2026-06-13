import pandas as pd

from pyexamgenerator.exam_generator import ExamGenerator
from pyexamgenerator.grading.session import GradingSession
from pyexamgenerator.grading.final_grade import FinalGradeCalculator
from pyexamgenerator.grading.attendance import AbsenceJustificationManager
from pyexamgenerator.grading.integrations import MoodleGradeIntegrator
from pyexamgenerator.grading.graders import ExamGrader
from pyexamgenerator.grading.comparison import ResultComparator
from pyexamgenerator.grading.api import ExamCorrectionAPI, ComparisonConfig, OCRIntegrationConfig


# --- Session persistence -----------------------------------------------------------------------

def test_grading_session_roundtrip_pkl_and_json_are_equivalent(tmp_path):
    session = GradingSession(name="demo")
    session.add_generated_exam(
        subject="Geo", exam="Parcial", course="25-26", exam_type="1A",
        docx="a.docx", full_docx="a_c.docx", xlsx="a_c.xlsx", xml="a.xml",
    )
    session.set_grading_inputs(enrollment="m.xlsx", output_dir="out")
    session.record_workflow("grade_from_excel", config={"id_col": "Número de ID"},
                            outputs={"output_path": "x.xlsx"}, summary={"rows": 30})

    pkl_path, json_path = session.save(str(tmp_path / "sess"))
    assert pkl_path.endswith(".pkl") and json_path.endswith(".json")

    from_pkl = GradingSession.load(pkl_path)
    from_json = GradingSession.load(json_path)

    assert from_pkl.to_dict() == from_json.to_dict()
    assert from_pkl.generated_xml_paths() == ["a.xml"]
    assert from_json.grading_inputs["enrollment"] == "m.xlsx"
    assert from_json.results_summary["grade_from_excel"]["rows"] == 30


def test_grading_session_load_prefers_base_name(tmp_path):
    session = GradingSession(name="x")
    session.add_generated_exam(xml="only.xml")
    session.save(str(tmp_path / "base"))
    # Loading by base name (no extension) finds the pickle/json.
    loaded = GradingSession.load(str(tmp_path / "base"))
    assert loaded.generated_xml_paths() == ["only.xml"]


def test_exam_generator_writes_session_with_generated_paths(tmp_path):
    rows = []
    number = 1
    for topic, count in {"Tema 01": 3, "Tema 02": 3}.items():
        for i in range(count):
            rows.append({
                "Número de pregunta": number, "Tema": topic, "Estado": "aceptable",
                "Pregunta": f"{topic} P{i + 1}", "Respuesta A": "A", "Respuesta B": "B",
                "Respuesta C": "C", "Respuesta D": "D", "Respuesta correcta": "a",
                "Texto relevante": "rel",
            })
            number += 1
    bank = tmp_path / "bank.xlsx"
    pd.DataFrame(rows).to_excel(bank, index=False)

    generator = ExamGenerator()
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank), output_dir=str(tmp_path), subject="Geo", exam="E",
        course="25-26", exam_names=["1A", "1B"], export_moodle_xml=True, update_excel=False,
        session_output_path=str(tmp_path / "sesion"),
    )

    session = GradingSession.load(str(tmp_path / "sesion.json"))
    assert len(session.generated_exams) == 2
    xml_names = sorted(p.split("\\")[-1].split("/")[-1] for p in session.generated_xml_paths())
    assert xml_names == ["examen_Geo_E_25-26_1A.xml", "examen_Geo_E_25-26_1B.xml"]


# --- Moodle naming suggestions -----------------------------------------------------------------

def test_suggest_moodle_config_matches_integrator_regex():
    suggestion = ExamGenerator.suggest_moodle_config(exam="Parcial 1", exam_type="1A", group="GIM")
    column = suggestion["exam_grade_column"]
    parsed = MoodleGradeIntegrator._parse_quiz_total_column(column)
    assert parsed is not None
    group_name, exam_type = parsed
    assert exam_type == "1A"
    assert "GIM" in group_name


# --- Structured justification email parser -----------------------------------------------------

def test_parse_structured_justification_extracts_all_fields_mmdd():
    message = (
        "Día de la falta (formato mm/dd/aaaa): 04/15/2026\n"
        "Nº Tema/Práctica a la que se ha faltado: Tema 3\n"
        "Grupo (GIM o GITI-GIE-GIEI): GITI-GIE-GIEI\n"
        "Grupo de prácticas (MC1, etc): MC1\n"
        "Motivo de la ausencia: cita médica"
    )
    parsed = AbsenceJustificationManager._parse_structured_justification("Justificación", message)
    assert parsed is not None
    assert parsed["fecha_normalizada"] == "2026-04-15"
    assert parsed["tema_practica"] == "Tema 3"
    assert parsed["grupo"] == "GITI-GIE-GIEI"
    assert parsed["subgrupo_practicas"] == "MC1"
    assert parsed["motivo"] == "cita médica"


def test_parse_structured_justification_date_ddmm_fallback():
    parsed = AbsenceJustificationManager._parse_structured_justification(
        "", "Día de la falta (formato mm/dd/aaaa): 15/04/2026"
    )
    assert parsed["fecha_normalizada"] == "2026-04-15"


def test_parse_structured_justification_returns_none_without_template():
    assert AbsenceJustificationManager._parse_structured_justification("Consulta", "Tengo una duda") is None


# --- Weighted final grade ----------------------------------------------------------------------

def _write(path, records):
    pd.DataFrame(records).to_excel(path, index=False)


def test_final_grade_by_files_weighted_and_capped(tmp_path):
    f1 = tmp_path / "teoria.xlsx"
    f2 = tmp_path / "practicas.xlsx"
    _write(f1, [
        {"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "8,00"},
        {"Número de ID": "2", "Nombre": "Leo", "Apellido(s)": "Paz", "Calificación/10,00": "6,00"},
    ])
    _write(f2, [
        {"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "10,00"},
        {"Número de ID": "2", "Nombre": "Leo", "Apellido(s)": "Paz", "Calificación/10,00": "5,00"},
    ])

    calc = FinalGradeCalculator(cap_to_10=True)
    df = calc.compute_by_files([
        {"path": str(f1), "label": "Teoria", "weight": 0.6},
        {"path": str(f2), "label": "Practicas", "weight": 0.4},
    ])

    by_name = {r["Nombre"]: r for _, r in df.iterrows()}
    assert by_name["Ana"]["Nota_Final"] == 8.8   # 0.6*8 + 0.4*10
    assert by_name["Leo"]["Nota_Final"] == 5.6   # 0.6*6 + 0.4*5
    assert "Nota_Teoria" in df.columns and "Nota_Practicas" in df.columns


def test_final_grade_by_files_caps_at_10(tmp_path):
    f1 = tmp_path / "a.xlsx"
    f2 = tmp_path / "b.xlsx"
    _write(f1, [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "10,00"}])
    _write(f2, [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "10,00"}])
    df = FinalGradeCalculator(cap_to_10=True).compute_by_files([
        {"path": str(f1), "weight": 1.0}, {"path": str(f2), "weight": 1.0},
    ])
    assert df["Nota_Final"].iloc[0] == 10.0


def test_final_grade_by_columns_weighted(tmp_path):
    source = tmp_path / "mixed.xlsx"
    _write(source, [{"Nombre": "Ana", "Teoria": "8,00", "Practicas": "10,00"}])
    df = FinalGradeCalculator().compute_by_columns(str(source), {"Teoria": 3, "Practicas": 1})
    assert df["Nota_Final"].iloc[0] == 8.5  # (3*8 + 1*10) / 4


# --- User-definable columns (ExamGrader) -------------------------------------------------------

_MINIMAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<quiz>
  <question type="multichoice">
    <name><text>Pregunta 01</text></name>
    <answer fraction="100"><text>a</text></answer>
    <answer fraction="0"><text>b</text></answer>
    <answer fraction="0"><text>c</text></answer>
    <answer fraction="0"><text>d</text></answer>
  </question>
</quiz>
"""


def test_exam_grader_respects_custom_column_names(tmp_path):
    xml_path = tmp_path / "exam.xml"
    xml_path.write_text(_MINIMAL_XML, encoding="utf-8")

    enrollment = tmp_path / "enrollment.xlsx"
    _write(enrollment, [{"Apellidos2": "Gil", "Nombre2": "Ana", "DNI": "111", "Mail": "ana@x.com"}])

    answers = tmp_path / "answers.xlsx"
    _write(answers, [{"Nombre_Alumno_Generado": "Ana Gil", "Pregunta 01": "a"}])

    grader = ExamGrader(
        exam_xml_path=str(xml_path), answers_xlsx_path=str(answers), enrollment_xlsx_path=str(enrollment),
        last_name_col="Apellidos2", first_name_col="Nombre2", id_col="DNI", email_col="Mail",
    )
    result = grader.grade_and_export(str(tmp_path / "out.xlsx"))

    assert len(result) == 1
    row = result.iloc[0]
    assert row["Apellido(s)"] == "Gil"
    assert str(row["Número de ID"]) == "111"
    assert row["Calificación/10,00"] == "10,00"


# --- Compare / overwrite results ---------------------------------------------------------------

def _build_old_new(tmp_path):
    old = tmp_path / "old.xlsx"
    new = tmp_path / "new.xlsx"
    _write(old, [
        {"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "8,00"},
        {"Número de ID": "2", "Nombre": "Leo", "Apellido(s)": "Paz", "Calificación/10,00": "5,00"},
        {"Número de ID": "3", "Nombre": "Mia", "Apellido(s)": "Sol", "Calificación/10,00": "7,00"},
    ])
    _write(new, [
        {"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "9,00"},  # changed
        {"Número de ID": "2", "Nombre": "Leo", "Apellido(s)": "Paz", "Calificación/10,00": "5,00"},  # same
        {"Número de ID": "4", "Nombre": "Zoe", "Apellido(s)": "Mar", "Calificación/10,00": "6,00"},  # new
    ])
    return old, new


def test_result_comparator_detects_changes_added_removed(tmp_path):
    old, new = _build_old_new(tmp_path)
    result = ResultComparator().compare(str(old), str(new))
    assert result.summary == {
        "changed_cells": 1, "changed_students": 1, "added": 1,
        "removed": 1, "common": 2, "value_columns": 1,
    }
    change = result.changes_df.iloc[0]
    assert change["Nombre"] == "Ana"
    assert change["Valor_Anterior"] == "8,00"
    assert change["Valor_Nuevo"] == "9,00"
    assert list(result.only_in_existing_df["Nombre"]) == ["Mia"]
    assert list(result.only_in_new_df["Nombre"]) == ["Zoe"]


def test_result_comparator_overwrite_merges_new_values_and_rows(tmp_path):
    old, new = _build_old_new(tmp_path)
    result = ResultComparator().compare(str(old), str(new), overwrite=True, add_new_rows=True)
    merged = result.merged_df
    assert merged is not None
    by_name = {r["Nombre"]: r for _, r in merged.iterrows()}
    assert by_name["Ana"]["Calificación/10,00"] == "9,00"  # overwritten with the new value
    assert "Mia" in by_name  # kept (only in old)
    assert "Zoe" in by_name   # appended (only in new)
    assert len(merged) == 4


def test_integrate_ocr_api_exposes_and_exports_integration_incidents(tmp_path):
    general = tmp_path / "teoria.xlsx"
    ocr = tmp_path / "ocr.xlsx"
    pd.DataFrame([
        {"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificación/10,00": "6,00", "P. 1 /0,40": "0,40"},
        {"Número de ID": "", "Nombre": "", "Apellido(s)": "Promedio general", "Calificación/10,00": "6,00", "P. 1 /0,40": "0,40"},
    ]).to_excel(general, index=False)
    pd.DataFrame([
        {
            "Imagen": "img_unmatched.jpg",
            "Tipo_Examen": "A",
            "Nombre": "Zoe",
            "Apellido(s)": "Mar",
            "ID_Oficial": "999",
            "Calificacion/10,00": "5,33",
        },
    ]).to_excel(ocr, index=False)

    api = ExamCorrectionAPI(default_output_dir=str(tmp_path))
    result = api.integrate_ocr_grades(OCRIntegrationConfig(
        general_xlsx_path=str(general),
        ocr_xlsx_path=str(ocr),
        output_path="teoria_integrada.xlsx",
        output_dir=str(tmp_path),
        append_unmatched_students=False,
    ))

    assert len(result) == 1
    summary = api.results.get("ocr_integration_summary")
    assert isinstance(summary, dict)
    assert summary["general_summary_rows_removed"] == 1
    assert summary["blocked_unmatched"] == 1
    incidents = api.results.get("ocr_integration_incidents")
    assert isinstance(incidents, pd.DataFrame)
    assert len(incidents) == 1
    assert incidents["Tipo"].iloc[0] == "UNMATCHED_STUDENT"
    assert (tmp_path / "incidencias_integracion_ocr.xlsx").exists()


def test_compare_results_api_in_place_overwrites_existing_file(tmp_path):
    old, new = _build_old_new(tmp_path)
    api = ExamCorrectionAPI(default_output_dir=str(tmp_path))
    api.compare_results(ComparisonConfig(
        existing_path=str(old), new_path=str(new), overwrite=True, merged_in_place=True,
    ))
    after = pd.read_excel(old)
    ana = after[after["Nombre"] == "Ana"]["Calificación/10,00"].iloc[0]
    assert str(ana) == "9,0" or str(ana) == "9.0" or str(ana) == "9,00"
    assert "Zoe" in set(after["Nombre"])  # new student added in place
    assert (tmp_path / "comparacion_resultados.xlsx").exists()


def test_result_comparator_value_cols_restricts_comparison(tmp_path):
    old = tmp_path / "old.xlsx"
    new = tmp_path / "new.xlsx"
    _write(old, [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": "8,00", "Otra": "x"}])
    _write(new, [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": "8,00", "Otra": "y"}])
    # Only compare "Nota": the change in "Otra" must be ignored.
    result = ResultComparator().compare(str(old), str(new), value_cols=["Nota"])
    assert result.summary["changed_cells"] == 0
    assert result.summary["value_columns"] == 1
