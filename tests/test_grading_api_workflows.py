"""Comportamiento de la fachada `ExamCorrectionAPI` y de la nota final (GRD-14..17)."""

from pathlib import Path

import pandas as pd
import pytest

from pyexamgenerator.grading.api import (
    ComparisonConfig,
    EnrollmentMergeConfig,
    ExamCorrectionAPI,
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
