"""Comportamiento de la fachada `ExamCorrectionAPI` y de la nota final (GRD-14..17)."""

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from pyexamgenerator.grading.api import (
    ComparisonConfig,
    EnrollmentMergeConfig,
    ExamCorrectionAPI,
    FullPipelineConfig,
    MoodleIntegrationConfig,
    OCRIntegrationConfig,
)
from pyexamgenerator.grading.final_grade import FinalGradeCalculator


def _write(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    return str(path)


def test_pipeline_does_not_modify_the_caller_configs(tmp_path, monkeypatch):
    """GRD-14: run_moodle_plus_ocr_pipeline cambiaba output_dir y general_xlsx_path de los
    config que recibía."""
    api = ExamCorrectionAPI(default_output_dir=str(tmp_path / "salida"))
    received = {}

    def fake_moodle(cfg, export_steps_dir=None):
        received["moodle"] = cfg
        return pd.DataFrame()

    def fake_ocr(cfg, export_steps_dir=None):
        received["ocr"] = cfg
        return pd.DataFrame()

    monkeypatch.setattr(api, "integrate_moodle_grades", fake_moodle)
    monkeypatch.setattr(api, "integrate_ocr_grades", fake_ocr)
    moodle_cfg = MoodleIntegrationConfig(xlsx_files=["moodle.xlsx"])
    ocr_cfg = OCRIntegrationConfig(general_xlsx_path="original.xlsx", ocr_xlsx_path="ocr.xlsx")

    api.run_moodle_plus_ocr_pipeline(moodle_cfg, ocr_cfg)

    assert moodle_cfg.output_dir is None
    assert ocr_cfg.output_dir is None and ocr_cfg.general_xlsx_path == "original.xlsx"
    assert received["moodle"].output_dir == str(tmp_path / "salida")
    assert received["ocr"].general_xlsx_path.endswith("calificaciones_moodle_integradas.xlsx")


def test_compare_in_place_keeps_a_backup_and_blank_cells(tmp_path):
    """GRD-15: combinar «en su sitio» sobrescribía sin copia y una celda vacía en el fichero
    nuevo borraba el valor anterior."""
    existing = _write(
        tmp_path / "notas.xlsx",
        [
            {"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 5.0, "Practicas": 7.0},
            {"Número de ID": "2", "Nombre": "Leo", "Apellido(s)": "Ruiz", "Nota": 6.0, "Practicas": 8.0},
        ],
    )
    new = _write(
        tmp_path / "nuevas.xlsx",
        [
            {"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 9.0, "Practicas": None},
            {"Número de ID": "2", "Nombre": "Leo", "Apellido(s)": "Ruiz", "Nota": 6.5, "Practicas": 8.5},
        ],
    )

    api = ExamCorrectionAPI()
    api.compare_results(
        ComparisonConfig(existing_path=existing, new_path=new, overwrite=True, merged_in_place=True,
                         report_output_path=str(tmp_path / "comparacion.xlsx"))
    )

    merged = pd.read_excel(existing).set_index("Número de ID")
    assert merged.loc[1, "Nota"] == pytest.approx(9.0)
    assert merged.loc[1, "Practicas"] == pytest.approx(7.0)  # el hueco no borra la nota anterior
    assert merged.loc[2, "Practicas"] == pytest.approx(8.5)
    backups = list(tmp_path.glob("notas_copia_*.xlsx"))
    assert len(backups) == 1
    assert pd.read_excel(backups[0])["Nota"].tolist() == [5.0, 6.0]
    assert api.session.results_summary["compare_results"]["outputs"]["backup_of_existing"] == str(backups[0])


def test_final_grade_with_two_files_with_the_same_name(tmp_path):
    """GRD-16: dos ficheros con el mismo nombre en carpetas distintas compartían etiqueta y la nota
    del segundo se contaba dos veces."""
    first = _write(tmp_path / "parcial1" / "notas.xlsx",
                   [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 4.0}])
    second = _write(tmp_path / "parcial2" / "notas.xlsx",
                    [{"Número de ID": "1", "Nombre": "Ana", "Apellido(s)": "Gil", "Nota": 8.0}])

    df = FinalGradeCalculator().compute_by_files(
        [{"path": first, "weight": 1.0, "grade_col": "Nota"}, {"path": second, "weight": 1.0, "grade_col": "Nota"}]
    )

    row = df.iloc[0]
    assert row["Nota_notas"] == pytest.approx(4.0)
    assert row["Nota_notas (2)"] == pytest.approx(8.0)
    assert row["Nota_Final"] == pytest.approx(6.0)


def test_enrollment_merge_is_recorded_in_the_session(tmp_path):
    """GRD-17: varios flujos (matrícula, OCR, PIR, informes por tema) no quedaban en la sesión."""
    source = _write(tmp_path / "matricula_GIM.xlsx",
                    [{"Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": "1", "Consulta": "P1"}])

    api = ExamCorrectionAPI()
    api.merge_enrollment_sources(EnrollmentMergeConfig(source_paths=[source], output_dir=str(tmp_path / "out")))

    entry = api.session.results_summary["merge_enrollment_sources"]
    assert entry["rows"] == 1
    assert entry["outputs"]["output_path"].endswith("matriculados_totales.xlsx")
    assert "merge_enrollment_sources" in api.session.workflow_configs


class _FakeImageExamGrader:
    """Stands in for the OCR grader: writes the grades and incidents files the real one writes."""

    def __init__(self, xml_paths, enrollment_path=None, **kwargs):
        assert Path(enrollment_path).exists()  # the merged roster is written before the OCR step
        self.kwargs = kwargs

    def grade_from_images(self, image_paths, output_answers, output_grades, output_dir=None,
                          output_incidents=None, **kwargs):
        out = Path(output_dir)
        grades = pd.DataFrame(
            [{"Imagen": "hoja1.jpg", "Tipo_Examen": "1A", "Apellido(s)": "Gil", "Nombre": "Ana",
              "Número de ID": "11111111", "Calificacion/10,00": "6,00"}]
        )
        grades.to_excel(out / output_grades, index=False)
        pd.DataFrame({"Imagen": list(image_paths)}).to_excel(out / output_answers, index=False)
        incidents = pd.DataFrame([{"Imagen": "hoja2.jpg", "Tipo": "UNREADABLE_IMAGE", "Detalle": "ilegible"}])
        incidents.to_excel(out / output_incidents, index=False)
        self.last_incidents_df = incidents
        return pd.DataFrame(), grades, None


def _attendance_quiz():
    return pd.DataFrame(
        [
            {"ID_Alumno": "11111111", "Nombre": "Ana", "Apellido(s)": "Gil",
             "Tiene_Punto_Adicional_Teoria": "si", "Motivo_No_Punto": ""},
            {"ID_Alumno": "22222222", "Nombre": "Leo", "Apellido(s)": "Ruiz",
             "Tiene_Punto_Adicional_Teoria": "no", "Motivo_No_Punto": "faltas"},
        ]
    )


@pytest.fixture
def full_pipeline(tmp_path, monkeypatch):
    """Inputs for run_full_pipeline with the OCR and the attendance analysis simulated."""
    fake_extraction = types.ModuleType("pyexamgenerator.grading.extraction")
    fake_extraction.ImageExamGrader = _FakeImageExamGrader
    monkeypatch.setitem(sys.modules, "pyexamgenerator.grading.extraction", fake_extraction)

    state = {"analyze": _attendance_quiz}

    class FakeJustificationManager:
        def __init__(self, **kwargs):
            state["justification_kwargs"] = kwargs

        def analyze(self):
            return SimpleNamespace(attendance_quiz_df=state["analyze"]())

    monkeypatch.setattr("pyexamgenerator.grading.attendance.AbsenceJustificationManager", FakeJustificationManager)

    people = [("Gil", "Ana", "11111111"), ("Ruiz", "Leo", "22222222")]
    enrollment = _write(tmp_path / "entrada" / "matricula_GIM.xlsx",
                        [{"Apellido(s)": a, "Nombre": n, "Número de ID": i, "Consulta": "P1"} for a, n, i in people])
    theory = _write(tmp_path / "entrada" / "teoria.xlsx",
                    [{"Apellido(s)": "Gil", "Nombre": "Ana", "Número de ID": "11111111", "Calificación/10,00": "-"},
                     {"Apellido(s)": "Ruiz", "Nombre": "Leo", "Número de ID": "22222222", "Calificación/10,00": "5,50"}])
    cfg = FullPipelineConfig(
        enrollment_paths=[enrollment], xml_paths=["examen_1A.xml"], image_paths=["hoja1.jpg", "hoja2.jpg"],
        theory_xlsx_path=theory, attendance_xlsx_path="asistencias.xlsx", schedule_xlsx_path="horario.xlsx",
        justifications_xlsx_path="justificaciones.xlsx", quizzes_xlsx_path="cuestionarios.xlsx",
        output_dir=str(tmp_path / "salida"), attendance_header_row=4,
    )
    return SimpleNamespace(cfg=cfg, out=tmp_path / "salida", state=state)


def test_full_pipeline_writes_only_the_final_tables(full_pipeline):
    """GUI-7: el pipeline completo vive en la librería y deja solo las tablas finales."""
    api = ExamCorrectionAPI()
    steps = []

    theory_df = api.run_full_pipeline(full_pipeline.cfg, progress_callback=steps.append)

    out = full_pipeline.out
    assert sorted(p.name for p in out.iterdir()) == [
        "calificaciones_examen_teoria.xlsx",
        "cuestionarios_clase_y_punto_extra.xlsx",
        "incidencias_identificacion_respuestas.xlsx",
    ]
    final = pd.read_excel(out / "calificaciones_examen_teoria.xlsx").set_index("Nombre")
    assert final.loc["Ana", "Nota_Final_Teoria"] == pytest.approx(7.0)  # 6 (OCR) + punto extra
    assert final.loc["Leo", "Nota_Final_Teoria"] == pytest.approx(5.5)
    assert list(theory_df["Nota_Final_Teoria"]) == list(final.reset_index()["Nota_Final_Teoria"])
    assert len(api.results["ocr_incidents"]) == 1
    assert full_pipeline.state["justification_kwargs"]["attendance_header_row"] == 4
    assert steps == ["Fusionando matriculados…", "OCR de hojas (puede tardar)…", "Integrando notas OCR en teoría…",
                     "Asistencias y cuestionarios…", "Aplicando punto extra…"]
    entry = api.session.results_summary["run_full_pipeline"]
    assert entry["rows"] == 2 and entry["ocr_incidents"] == 1
    assert entry["outputs"]["theory_grades"] == str(out / "calificaciones_examen_teoria.xlsx")


def test_full_pipeline_removes_intermediate_files_after_an_error(full_pipeline):
    """GUI-7: tras un error, `_intermedios` (matrícula fusionada, notas OCR...) se quedaba en disco."""

    def broken_analysis():
        raise RuntimeError("asistencias ilegibles")

    full_pipeline.state["analyze"] = broken_analysis

    with pytest.raises(RuntimeError, match="asistencias ilegibles"):
        ExamCorrectionAPI().run_full_pipeline(full_pipeline.cfg)

    assert full_pipeline.out.exists()
    assert not (full_pipeline.out / "_intermedios").exists()


def test_full_pipeline_can_keep_the_intermediate_files(full_pipeline):
    from dataclasses import replace

    ExamCorrectionAPI().run_full_pipeline(replace(full_pipeline.cfg, keep_intermediate=True))

    kept = {p.name for p in (full_pipeline.out / "_intermedios").iterdir()}
    assert {"matriculados.xlsx", "calificaciones_manuscritos.xlsx", "teoria_integrada.xlsx"} <= kept
