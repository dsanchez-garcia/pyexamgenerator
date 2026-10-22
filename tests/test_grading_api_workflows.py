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


def _moodle_file(path, rows):
    return _write(path, [{"Número de ID": student_id, "Nombre": first, "Apellido(s)": last,
                          "Calificación/10,00": grade} for student_id, first, last, grade in rows])


class _CountingPandas:
    """Replaces ``pd`` inside the facade module to count the Excel files it reads itself."""

    def __init__(self):
        self.read_excel_calls = []

    def read_excel(self, path, *args, **kwargs):
        self.read_excel_calls.append(str(path))
        return pd.read_excel(path, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(pd, name)


def test_facade_reads_the_inputs_again_only_to_export_steps(tmp_path, monkeypatch):
    """GRD-13: sin `export_steps_dir`, la fachada volvía a leer todos los ficheros de entrada solo
    para exportarlos como pasos."""
    import pyexamgenerator.grading.api as api_module

    counting = _CountingPandas()
    monkeypatch.setattr(api_module, "pd", counting)
    first = _moodle_file(tmp_path / "moodle_GIM.xlsx", [("111", "Ana", "Gil", "5,00")])
    second = _moodle_file(tmp_path / "moodle_GITI.xlsx", [("222", "Leo", "Ruiz", "6,00")])
    api = ExamCorrectionAPI(default_output_dir=str(tmp_path / "salida"))

    api.integrate_moodle_grades(MoodleIntegrationConfig(xlsx_files=[first, second]))
    api.merge_enrollment_sources(EnrollmentMergeConfig(source_paths=[first, second]))
    assert counting.read_excel_calls == []

    api.integrate_moodle_grades(MoodleIntegrationConfig(xlsx_files=[first, second]),
                                export_steps_dir=str(tmp_path / "pasos"))
    assert counting.read_excel_calls == [first, second]


def test_moodle_integration_accepts_a_generator_of_files(tmp_path):
    """GRD-13: `xlsx_files` se recorría dos veces; con un generador, la segunda vez estaba vacío."""
    files = [_moodle_file(tmp_path / "moodle_GIM.xlsx", [("111", "Ana", "Gil", "5,00")]),
             _moodle_file(tmp_path / "moodle_GITI.xlsx", [("222", "Leo", "Ruiz", "6,00")])]
    api = ExamCorrectionAPI(default_output_dir=str(tmp_path / "salida"))

    df = api.integrate_moodle_grades(MoodleIntegrationConfig(xlsx_files=(path for path in files)),
                                     export_steps_dir=str(tmp_path / "pasos"))

    assert sorted(df["Nombre"]) == ["Ana", "Leo"]
    assert api.session.workflow_configs["integrate_moodle_grades"]["xlsx_files"] == files


def test_explicit_absolute_output_paths_are_respected(tmp_path):
    """GRD-14: una ruta de salida absoluta acababa en la carpeta de salida por defecto (fachada y
    clases de trabajo)."""
    moodle = _moodle_file(tmp_path / "entrada" / "moodle.xlsx", [("111", "Ana", "Gil", "5,00")])
    ocr = _write(tmp_path / "entrada" / "ocr.xlsx",
                 [{"Número de ID": "111", "Nombre": "Ana", "Apellido(s)": "Gil", "Calificacion/10,00": "5,00"}])
    elsewhere = tmp_path / "otra" / "carpeta"
    api = ExamCorrectionAPI(default_output_dir=str(tmp_path / "salida"))

    api.integrate_moodle_grades(MoodleIntegrationConfig(xlsx_files=[moodle],
                                                        output_path=str(elsewhere / "moodle_integrado.xlsx")))
    api.integrate_ocr_grades(OCRIntegrationConfig(general_xlsx_path=moodle, ocr_xlsx_path=ocr,
                                                  output_path=str(elsewhere / "teoria.xlsx")))
    api.merge_enrollment_sources(EnrollmentMergeConfig(source_paths=[moodle], output_path="matricula.xlsx"))

    assert sorted(p.name for p in elsewhere.iterdir()) == ["moodle_integrado.xlsx", "teoria.xlsx"]
    assert sorted(p.name for p in (tmp_path / "salida").iterdir()) == ["matricula.xlsx"]  # relative: as before
    outputs = api.session.results_summary["integrate_ocr_grades"]["outputs"]
    assert outputs["output_path"] == str(elsewhere / "teoria.xlsx")


def test_session_leaves_out_config_callbacks():
    """ARC-7: los callbacks de un config no son datos; antes `asdict` los copiaba en profundidad
    (con un método de la GUI, la ventana entera) y fallaba con objetos que no se pueden copiar."""
    import threading

    from pyexamgenerator.grading.api import ImageGradingConfig
    from pyexamgenerator.grading.session import GradingSession

    class Window:
        def __init__(self):
            self.lock = threading.Lock()  # cannot be deep-copied

        def review(self, *args):
            return None

    cfg = ImageGradingConfig(xml_paths=["examen_1A.xml"], image_paths=["hoja.jpg"], enrollment_path=None,
                             review_callback=Window().review)
    session = GradingSession()

    session.record_workflow("grade_from_images", config=cfg)

    stored = session.workflow_configs["grade_from_images"]
    assert stored["review_callback"] is None and stored["exam_type_callback"] is None
    assert stored["xml_paths"] == ["examen_1A.xml"]
