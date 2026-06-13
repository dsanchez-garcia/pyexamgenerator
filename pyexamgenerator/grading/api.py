from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from pyexamgenerator.grading.data import SharedExamDataStore
from pyexamgenerator.grading.data import build_merged_enrollment_from_sources
from pyexamgenerator.grading.session import GradingSession


@dataclass
class ExcelGradingConfig:
    exam_xml_path: str
    answers_xlsx_path: str
    enrollment_xlsx_path: str
    output_path: str = "calificaciones_finales_moodle.xlsx"
    output_dir: Optional[str] = None
    enrollment_sheet: int = 0
    last_name_col: str = "Apellido(s)"
    first_name_col: str = "Nombre"
    id_col: str = "Número de ID"
    email_col: str = "Dirección de correo"


@dataclass
class ImageGradingConfig:
    xml_paths: Sequence[str]
    image_paths: Sequence[str]
    enrollment_path: Optional[str]
    enrollment_paths: Sequence[str] = field(default_factory=tuple)
    output_answers: str = "respuestas_alumnos_paso1_desde_imagenes.xlsx"
    output_grades: str = "calificaciones_desde_imagenes.xlsx"
    output_audit: Optional[str] = None
    output_incidents: Optional[str] = None
    output_review: Optional[str] = None
    output_manual_changes: Optional[str] = None
    output_dir: Optional[str] = None
    interactive_review: bool = False
    open_image_on_review: bool = True
    forced_type_by_image: Dict[str, str] = field(default_factory=dict)
    forced_student_by_image: Dict[str, str] = field(default_factory=dict)
    prompt_missing_type: bool = True
    debug_dir: Optional[str] = None
    temp_image_dir: Optional[str] = None
    min_mark_ratio: float = 0.17
    min_gap: float = 0.05
    aggressive_recovery: bool = False
    aggressive_min_ratio: float = 0.11
    aggressive_min_gap_ratio: float = 0.25
    aggressive_min_top_vs_second: float = 1.10
    enrollment_sheet: int = 0
    last_name_col: str = "Apellido(s)"
    first_name_col: str = "Nombre"
    id_col: str = "Número de ID"
    email_col: str = "Dirección de correo"


@dataclass
class MoodleIntegrationConfig:
    xlsx_files: Iterable[str]
    output_path: str = "calificaciones_moodle_integradas.xlsx"
    output_dir: Optional[str] = None
    group_types: Iterable[str] = field(default_factory=tuple)
    sheet: int = 0
    deduplicate_by_id: bool = False
    id_col: str = "Número de ID"
    first_name_col: str = "Nombre"
    last_name_col: str = "Apellido(s)"
    total_grade_col: str = "Calificación/10,00"


@dataclass
class OCRIntegrationConfig:
    general_xlsx_path: str
    ocr_xlsx_path: str
    output_path: str = "calificaciones_moodle_integradas.xlsx"
    output_dir: Optional[str] = None
    enrollment_paths: Sequence[str] = field(default_factory=tuple)
    enrollment_sheet: int = 0
    append_unmatched_students: bool = True


@dataclass
class PIRBonusConfig:
    attendance_path: str
    schedule_path: str
    schedule_sheet: str
    quizzes_path: str
    summary_output_path: str = "pir_bonus_resumen.xlsx"
    incidents_output_path: str = "pir_bonus_incidencias.xlsx"
    attendance_header_row: int = 3
    min_quiz_grade: float = 7.5
    bonus_points: float = 1.0
    theory_xlsx_path: Optional[str] = None
    theory_output_with_bonus_path: Optional[str] = None
    theory_grade_col: str = "Calificación/10,00"
    output_dir: Optional[str] = None


@dataclass
class EnrollmentMergeConfig:
    source_paths: Sequence[str]
    output_path: str = "matriculados_totales.xlsx"
    output_dir: Optional[str] = None
    sheet: int = 0


@dataclass
class AbsenceJustificationConfig:
    attendance_xlsx_path: str
    justifications_xlsx_path: str
    enrollment_xlsx_path: str
    schedule_xlsx_path: Optional[str] = None
    schedule_sheet: object = 0
    quizzes_xlsx_path: Optional[str] = None
    summary_output_path: str = "justificaciones_resumen.xlsx"
    detailed_output_path: str = "justificaciones_detalle.xlsx"
    attendance_overview_output_path: str = "asistencias_resumen_alumnos.xlsx"
    sender_absence_check_output_path: str = "justificaciones_vs_faltas.xlsx"
    attendance_quiz_output_path: str = "asistencias_con_cuestionarios.xlsx"
    extreme_justified_absences_output_path: str = "faltas_justificadas_modo_extremo.xlsx"
    output_dir: Optional[str] = None
    attendance_header_row: int = 3
    sender_col: str = "REMITENTE"
    subject_col: str = "ASUNTO"
    message_col: str = "MENSAJE"
    first_name_col: Optional[str] = None
    last_name_col: Optional[str] = None
    id_col: Optional[str] = None
    email_col: Optional[str] = None
    justification_mode: str = "extremo"


@dataclass
class TheoryBonusConfig:
    theory_xlsx_path: str
    attendance_quiz_xlsx_path: str
    output_path: str = "calificaciones_teoria_con_punto.xlsx"
    output_dir: Optional[str] = None
    theory_grade_col: Optional[str] = None
    cap_to_10: bool = True


@dataclass
class TheoryTopicReportConfig:
    attendance_quiz_xlsx_path: str
    output_dir: str = "reporte_teoria_por_tema"


@dataclass
class FinalGradeConfig:
    """Weighted final grade configuration.

    ``mode='by_file'`` weights one grade column per file (``sources`` items:
    ``{path, label?, weight?, grade_col?, id_col?}``). ``mode='by_column'`` weights several columns
    inside a single ``source_path`` (``weights``: ``{column_name: weight}``).
    """

    mode: str = "by_file"
    sources: Sequence[Dict[str, object]] = field(default_factory=tuple)
    source_path: Optional[str] = None
    weights: Dict[str, float] = field(default_factory=dict)
    output_path: str = "calificaciones_finales_ponderadas.xlsx"
    output_dir: Optional[str] = None
    cap_to_10: bool = True
    id_col: Optional[str] = None
    first_name_col: Optional[str] = None
    last_name_col: Optional[str] = None


@dataclass
class ComparisonConfig:
    """Compare a results table (grades or attendance) against a previous version, optionally overwriting.

    Matches students by ID (falling back to name). ``value_cols`` empty = compare every column common to
    both files that is not an identity column. With ``overwrite=True`` a merged table is written where the
    new values replace the previous ones; ``merged_in_place=True`` writes it over ``existing_path`` itself.
    """

    existing_path: str
    new_path: str
    value_cols: Sequence[str] = field(default_factory=tuple)
    overwrite: bool = False
    add_new_rows: bool = True
    merged_in_place: bool = False
    report_output_path: str = "comparacion_resultados.xlsx"
    merged_output_path: str = "resultados_combinados.xlsx"
    output_dir: Optional[str] = None
    id_col: Optional[str] = None
    first_name_col: Optional[str] = None
    last_name_col: Optional[str] = None


class ExamCorrectionAPI:
    """High-level facade to run exam correction workflows as a reusable library."""

    def __init__(
        self,
        shared_store: Optional[SharedExamDataStore] = None,
        default_output_dir: Optional[str] = None,
    ) -> None:
        self.shared_store = shared_store or SharedExamDataStore()
        self.default_output_dir = str(default_output_dir).strip() if default_output_dir else None
        # Every workflow records its outputs here so they can be inspected or reused later.
        self.results: Dict[str, object] = {}
        # Resumable session: accumulates inputs, configs and a summary of each workflow run.
        self.session = GradingSession()

    def save_session(self, path: str) -> Tuple[str, str]:
        """Writes the accumulated session to ``<base>.pkl`` and ``<base>.json``."""
        return self.session.save(path)

    def load_session(self, path: str) -> GradingSession:
        """Loads a session (``.pkl`` or ``.json``) and adopts it as the current session."""
        self.session = GradingSession.load(path)
        return self.session

    def _resolve_output_dir(self, explicit_output_dir: Optional[str]) -> Optional[str]:
        out_dir = explicit_output_dir or self.default_output_dir
        if out_dir:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
        return out_dir

    def _resolve_output_path(self, filename_or_path: str, explicit_output_dir: Optional[str]) -> str:
        out_dir = self._resolve_output_dir(explicit_output_dir)
        if not out_dir:
            return filename_or_path
        return str(Path(out_dir) / Path(filename_or_path).name)

    @staticmethod
    def _backend_import_error(module_name: str, error: Exception) -> RuntimeError:
        _ = error
        return RuntimeError(
            f"Could not import backend module '{module_name}'. "
            "Ensure the package is installed with required dependencies."
        )

    @staticmethod
    def _start_step_export(export_steps_dir: Optional[str], workflow_name: str) -> Optional[Dict[str, object]]:
        if not export_steps_dir:
            return None
        base_dir = Path(export_steps_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = base_dir / f"{workflow_name}_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return {
            "workflow": workflow_name,
            "run_id": run_id,
            "run_dir": run_dir,
            "steps": [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    @staticmethod
    def _sanitize_step_name(step_name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", step_name.strip()).strip("_") or "step"

    @classmethod
    def _export_step_dataframe(
        cls,
        state: Optional[Dict[str, object]],
        step_name: str,
        df: Optional[pd.DataFrame],
    ) -> None:
        if state is None or df is None:
            return

        steps: List[Dict[str, object]] = state["steps"]  # type: ignore[assignment]
        run_dir: Path = state["run_dir"]  # type: ignore[assignment]

        step_index = len(steps) + 1
        safe_name = cls._sanitize_step_name(step_name)
        filename = f"{step_index:02d}_{safe_name}.xlsx"
        output_path = run_dir / filename
        df.to_excel(output_path, index=False)

        steps.append(
            {
                "index": step_index,
                "name": step_name,
                "file": filename,
                "rows": int(len(df)),
                "columns": int(len(df.columns)),
            }
        )

    @staticmethod
    def _finalize_step_export(
        state: Optional[Dict[str, object]],
        outputs: Optional[Dict[str, object]] = None,
    ) -> None:
        if state is None:
            return

        run_dir: Path = state["run_dir"]  # type: ignore[assignment]
        manifest = {
            "workflow": state["workflow"],
            "run_id": state["run_id"],
            "created_at": state["created_at"],
            "steps": state["steps"],
            "outputs": outputs or {},
        }
        manifest_path = run_dir / "manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=True)

    def grade_from_excel(self, cfg: ExcelGradingConfig, export_steps_dir: Optional[str] = None) -> pd.DataFrame:
        from pyexamgenerator.grading.graders import ExamGrader

        export_state = self._start_step_export(export_steps_dir, "grade_from_excel")

        grader = ExamGrader(
            exam_xml_path=cfg.exam_xml_path,
            answers_xlsx_path=cfg.answers_xlsx_path,
            enrollment_xlsx_path=cfg.enrollment_xlsx_path,
            enrollment_sheet=cfg.enrollment_sheet,
            last_name_col=cfg.last_name_col,
            first_name_col=cfg.first_name_col,
            id_col=cfg.id_col,
            email_col=cfg.email_col,
            shared_store=self.shared_store,
        )
        self._export_step_dataframe(export_state, "enrollment_loaded", grader.enrollment_df)
        self._export_step_dataframe(export_state, "answers_loaded", grader.answers_df)
        output_path = self._resolve_output_path(cfg.output_path, cfg.output_dir)

        result_df = grader.grade_and_export(output_path)
        self._export_step_dataframe(export_state, "graded_output", result_df)
        self._finalize_step_export(export_state, {"output_path": output_path})
        self.session.record_workflow(
            "grade_from_excel", config=cfg, outputs={"output_path": output_path},
            summary={"rows": int(len(result_df))},
        )
        return result_df

    def grade_from_images(
        self,
        cfg: ImageGradingConfig,
        export_steps_dir: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        from pyexamgenerator.grading.extraction import ImageExamGrader

        export_state = self._start_step_export(export_steps_dir, "grade_from_images")

        grader = ImageExamGrader(
            xml_paths=list(cfg.xml_paths),
            enrollment_path=cfg.enrollment_path,
            enrollment_paths=list(cfg.enrollment_paths),
            min_mark_ratio=cfg.min_mark_ratio,
            min_gap=cfg.min_gap,
            aggressive_recovery=cfg.aggressive_recovery,
            aggressive_min_ratio=cfg.aggressive_min_ratio,
            aggressive_min_gap_ratio=cfg.aggressive_min_gap_ratio,
            aggressive_min_top_vs_second=cfg.aggressive_min_top_vs_second,
            debug_dir=cfg.debug_dir,
            temp_image_dir=cfg.temp_image_dir,
            enrollment_sheet=cfg.enrollment_sheet,
            last_name_col=cfg.last_name_col,
            first_name_col=cfg.first_name_col,
            id_col=cfg.id_col,
            email_col=cfg.email_col,
            forced_student_by_image=cfg.forced_student_by_image,
            shared_store=self.shared_store,
        )
        answers_df, grades_df, audit_df = grader.grade_from_images(
            image_paths=list(cfg.image_paths),
            output_answers=cfg.output_answers,
            output_grades=cfg.output_grades,
            output_dir=self._resolve_output_dir(cfg.output_dir),
            output_audit=cfg.output_audit,
            output_incidents=cfg.output_incidents,
            output_review=cfg.output_review,
            output_manual_changes=cfg.output_manual_changes,
            interactive_review=cfg.interactive_review,
            open_image_on_review=cfg.open_image_on_review,
            forced_type_by_image=cfg.forced_type_by_image,
            prompt_missing_type=cfg.prompt_missing_type,
        )
        self._export_step_dataframe(export_state, "answers_detected", answers_df)
        self._export_step_dataframe(export_state, "grades_generated", grades_df)
        self._export_step_dataframe(export_state, "audit_details", audit_df)
        if cfg.output_incidents:
            incidents_path = self._resolve_output_path(cfg.output_incidents, cfg.output_dir)
            if Path(incidents_path).exists():
                self._export_step_dataframe(export_state, "ocr_incidents", pd.read_excel(incidents_path))
        if cfg.output_review:
            review_path = self._resolve_output_path(cfg.output_review, cfg.output_dir)
            if Path(review_path).exists():
                self._export_step_dataframe(export_state, "ocr_manual_review", pd.read_excel(review_path))
        if cfg.output_manual_changes:
            changes_path = self._resolve_output_path(cfg.output_manual_changes, cfg.output_dir)
            if Path(changes_path).exists():
                self._export_step_dataframe(export_state, "ocr_manual_changes", pd.read_excel(changes_path))
        out_answers = self._resolve_output_path(cfg.output_answers, cfg.output_dir)
        out_grades = self._resolve_output_path(cfg.output_grades, cfg.output_dir)
        out_audit = self._resolve_output_path(cfg.output_audit, cfg.output_dir) if cfg.output_audit else None
        out_incidents = self._resolve_output_path(cfg.output_incidents, cfg.output_dir) if cfg.output_incidents else None
        out_review = self._resolve_output_path(cfg.output_review, cfg.output_dir) if cfg.output_review else None
        out_manual_changes = self._resolve_output_path(cfg.output_manual_changes, cfg.output_dir) if cfg.output_manual_changes else None
        self._finalize_step_export(
            export_state,
            {
                "output_answers": out_answers,
                "output_grades": out_grades,
                "output_audit": out_audit,
                "output_incidents": out_incidents,
                "output_review": out_review,
                "output_manual_changes": out_manual_changes,
            },
        )
        self.results["image_answers"] = answers_df
        self.results["image_grades"] = grades_df
        self.results["image_audit"] = audit_df
        if cfg.output_incidents:
            incidents_path = self._resolve_output_path(cfg.output_incidents, cfg.output_dir)
            if Path(incidents_path).exists():
                self.results["ocr_incidents"] = pd.read_excel(incidents_path)
        return answers_df, grades_df, audit_df

    def integrate_moodle_grades(self, cfg: MoodleIntegrationConfig, export_steps_dir: Optional[str] = None) -> pd.DataFrame:
        from pyexamgenerator.grading.integrations import MoodleGradeIntegrator

        export_state = self._start_step_export(export_steps_dir, "integrate_moodle_grades")
        for i, path in enumerate(cfg.xlsx_files, start=1):
            source_df = pd.read_excel(path, sheet_name=cfg.sheet)
            self._export_step_dataframe(export_state, f"source_file_{i}", source_df)

        integrator = MoodleGradeIntegrator(
            xlsx_files=list(cfg.xlsx_files),
            group_types=list(cfg.group_types),
            sheet=cfg.sheet,
            id_col=cfg.id_col,
            first_name_col=cfg.first_name_col,
            last_name_col=cfg.last_name_col,
            total_grade_col=cfg.total_grade_col,
        )
        result_df = integrator.integrate_and_export(
            output_path=cfg.output_path,
            output_dir=self._resolve_output_dir(cfg.output_dir),
            deduplicate_by_id=cfg.deduplicate_by_id,
        )
        self._export_step_dataframe(export_state, "moodle_integrated", result_df)
        output_path = self._resolve_output_path(cfg.output_path, cfg.output_dir)
        self._finalize_step_export(export_state, {"output_path": output_path})
        self.session.record_workflow(
            "integrate_moodle_grades", config=cfg, outputs={"output_path": output_path},
            summary={"rows": int(len(result_df))},
        )
        return result_df

    def integrate_ocr_grades(self, cfg: OCRIntegrationConfig, export_steps_dir: Optional[str] = None) -> pd.DataFrame:
        from pyexamgenerator.grading.integrations import OcrGradeIntegrator

        export_state = self._start_step_export(export_steps_dir, "integrate_ocr_grades")
        self._export_step_dataframe(export_state, "general_input", pd.read_excel(cfg.general_xlsx_path))
        self._export_step_dataframe(export_state, "ocr_input", pd.read_excel(cfg.ocr_xlsx_path))

        integrator = OcrGradeIntegrator(
            general_xlsx_path=cfg.general_xlsx_path,
            ocr_xlsx_path=cfg.ocr_xlsx_path,
            enrollment_paths=list(cfg.enrollment_paths),
            enrollment_sheet=cfg.enrollment_sheet,
            append_unmatched_students=cfg.append_unmatched_students,
        )
        result_df = integrator.integrate(cfg.output_path, output_dir=self._resolve_output_dir(cfg.output_dir))
        self._export_step_dataframe(export_state, "ocr_integrated", result_df)

        integration_summary = dict(getattr(integrator, "last_integration_summary", {}) or {})
        integration_incidents_df = getattr(integrator, "last_integration_incidents_df", None)
        incidents_output_path: Optional[str] = None
        if isinstance(integration_incidents_df, pd.DataFrame):
            self.results["ocr_integration_incidents"] = integration_incidents_df
            if not integration_incidents_df.empty:
                resolved_incidents_path = self._resolve_output_path("incidencias_integracion_ocr.xlsx", cfg.output_dir)
                incidents_output_path = resolved_incidents_path
                integration_incidents_df.to_excel(resolved_incidents_path, index=False)
                self.results["ocr_integration_incidents_path"] = incidents_output_path
                self._export_step_dataframe(export_state, "ocr_integration_incidents", integration_incidents_df)
        self.results["ocr_integration_summary"] = integration_summary

        output_path = self._resolve_output_path(cfg.output_path, cfg.output_dir)
        outputs: Dict[str, object] = {"output_path": output_path}
        if incidents_output_path:
            outputs["incidents_path"] = incidents_output_path
        self._finalize_step_export(export_state, outputs)
        self.results["integrated_theory"] = result_df

        summary_payload = {"rows": int(len(result_df))}
        for key in (
            "ocr_rows_total",
            "rows_matched",
            "rows_updated",
            "rows_appended_unmatched",
            "general_summary_rows_removed",
            "blocked_missing_identity",
            "blocked_unmatched",
            "blocked_missing_target",
            "blocked_missing_grade",
        ):
            if key in integration_summary:
                summary_payload[key] = int(integration_summary.get(key, 0) or 0)

        self.session.record_workflow(
            "integrate_ocr_grades", config=cfg, outputs={"output_path": output_path},
            summary=summary_payload,
        )
        return result_df

    def run_moodle_plus_ocr_pipeline(
        self,
        moodle_cfg: MoodleIntegrationConfig,
        ocr_cfg: OCRIntegrationConfig,
        export_steps_dir: Optional[str] = None,
    ) -> pd.DataFrame:
        export_state = self._start_step_export(export_steps_dir, "run_moodle_plus_ocr_pipeline")
        if self.default_output_dir:
            if not moodle_cfg.output_dir:
                moodle_cfg.output_dir = self.default_output_dir
            if not ocr_cfg.output_dir:
                ocr_cfg.output_dir = self.default_output_dir
        moodle_df = self.integrate_moodle_grades(moodle_cfg)
        self._export_step_dataframe(export_state, "moodle_integrated", moodle_df)
        moodle_output_path = self._resolve_output_path(moodle_cfg.output_path, moodle_cfg.output_dir)
        ocr_cfg.general_xlsx_path = moodle_output_path
        final_df = self.integrate_ocr_grades(ocr_cfg)
        self._export_step_dataframe(export_state, "ocr_overlay_applied", final_df)
        self._finalize_step_export(
            export_state,
            {
                "moodle_output": moodle_output_path,
                "final_output": self._resolve_output_path(ocr_cfg.output_path, ocr_cfg.output_dir),
            },
        )
        return final_df

    def merge_enrollment_sources(
        self,
        cfg: EnrollmentMergeConfig,
        export_steps_dir: Optional[str] = None,
    ) -> pd.DataFrame:
        export_state = self._start_step_export(export_steps_dir, "merge_enrollment_sources")
        for i, source_path in enumerate(cfg.source_paths, start=1):
            src_df = pd.read_excel(source_path, sheet_name=cfg.sheet)
            self._export_step_dataframe(export_state, f"source_enrollment_{i}", src_df)

        merged_df = build_merged_enrollment_from_sources(cfg.source_paths, sheet_name=cfg.sheet)
        output_path = self._resolve_output_path(cfg.output_path, cfg.output_dir)
        merged_df.to_excel(output_path, index=False)

        self._export_step_dataframe(export_state, "enrollment_merged", merged_df)
        self._finalize_step_export(export_state, {"output_path": output_path})
        self.results["merged_enrollment"] = merged_df
        return merged_df

    def process_absence_justifications(
        self,
        cfg: AbsenceJustificationConfig,
        export_steps_dir: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        from pyexamgenerator.grading.attendance import AbsenceJustificationManager

        export_state = self._start_step_export(export_steps_dir, "process_absence_justifications")
        self._export_step_dataframe(
            export_state,
            "attendance_input",
            pd.read_excel(cfg.attendance_xlsx_path, header=cfg.attendance_header_row),
        )
        self._export_step_dataframe(export_state, "justifications_input", pd.read_excel(cfg.justifications_xlsx_path))
        self._export_step_dataframe(export_state, "enrollment_input", pd.read_excel(cfg.enrollment_xlsx_path))

        manager = AbsenceJustificationManager(
            attendance_xlsx_path=cfg.attendance_xlsx_path,
            justifications_xlsx_path=cfg.justifications_xlsx_path,
            enrollment_xlsx_path=cfg.enrollment_xlsx_path,
            schedule_xlsx_path=cfg.schedule_xlsx_path,
            schedule_sheet=cfg.schedule_sheet,
            quizzes_xlsx_path=cfg.quizzes_xlsx_path,
            attendance_header_row=cfg.attendance_header_row,
            sender_col=cfg.sender_col,
            subject_col=cfg.subject_col,
            message_col=cfg.message_col,
            first_name_col=cfg.first_name_col,
            last_name_col=cfg.last_name_col,
            id_col=cfg.id_col,
            email_col=cfg.email_col,
            justification_mode=cfg.justification_mode,
        )

        result = manager.analyze_and_export(
            summary_output_path=cfg.summary_output_path,
            detailed_output_path=cfg.detailed_output_path,
            attendance_overview_output_path=cfg.attendance_overview_output_path,
            sender_absence_check_output_path=cfg.sender_absence_check_output_path,
            attendance_quiz_output_path=cfg.attendance_quiz_output_path,
            extreme_justified_absences_output_path=cfg.extreme_justified_absences_output_path,
            output_dir=self._resolve_output_dir(cfg.output_dir),
        )

        self._export_step_dataframe(export_state, "justifications_summary", result.summary_df)
        self._export_step_dataframe(export_state, "justifications_detail", result.detailed_df)
        self._export_step_dataframe(export_state, "attendance_overview", result.attendance_overview_df)
        self._export_step_dataframe(export_state, "justifications_vs_absences", result.sender_absence_check_df)
        self._export_step_dataframe(export_state, "attendance_with_quizzes", result.attendance_quiz_df)
        self._export_step_dataframe(export_state, "extreme_mode_justified_absences", result.extreme_justified_absences_df)
        self._finalize_step_export(
            export_state,
            {
                "summary_output": self._resolve_output_path(cfg.summary_output_path, cfg.output_dir),
                "detailed_output": self._resolve_output_path(cfg.detailed_output_path, cfg.output_dir),
                "attendance_overview_output": self._resolve_output_path(cfg.attendance_overview_output_path, cfg.output_dir),
                "sender_absence_check_output": self._resolve_output_path(cfg.sender_absence_check_output_path, cfg.output_dir),
                "attendance_quiz_output": self._resolve_output_path(cfg.attendance_quiz_output_path, cfg.output_dir),
                "extreme_justified_absences_output": self._resolve_output_path(
                    cfg.extreme_justified_absences_output_path,
                    cfg.output_dir,
                ),
            },
        )
        self.results["justifications_summary"] = result.summary_df
        self.results["justifications_detail"] = result.detailed_df
        self.results["attendance_with_quizzes"] = result.attendance_quiz_df
        self.session.record_workflow(
            "process_absence_justifications", config=cfg,
            outputs={
                "summary_output": self._resolve_output_path(cfg.summary_output_path, cfg.output_dir),
                "detailed_output": self._resolve_output_path(cfg.detailed_output_path, cfg.output_dir),
            },
            summary={"summary_rows": int(len(result.summary_df))},
        )
        return result.summary_df, result.detailed_df

    def apply_theory_bonus(
        self,
        cfg: TheoryBonusConfig,
        export_steps_dir: Optional[str] = None,
    ) -> pd.DataFrame:
        from pyexamgenerator.grading.attendance import apply_theory_bonus_from_attendance_quiz

        export_state = self._start_step_export(export_steps_dir, "apply_theory_bonus")
        self._export_step_dataframe(export_state, "theory_input", pd.read_excel(cfg.theory_xlsx_path))
        self._export_step_dataframe(export_state, "attendance_quiz_input", pd.read_excel(cfg.attendance_quiz_xlsx_path))

        output_path = self._resolve_output_path(cfg.output_path, cfg.output_dir)
        result_df = apply_theory_bonus_from_attendance_quiz(
            theory_xlsx_path=cfg.theory_xlsx_path,
            attendance_quiz_xlsx_path=cfg.attendance_quiz_xlsx_path,
            output_path=output_path,
            theory_grade_col=cfg.theory_grade_col,
            cap_to_10=cfg.cap_to_10,
        )

        self._export_step_dataframe(export_state, "theory_with_bonus", result_df)
        self._finalize_step_export(export_state, {"output_path": output_path})
        self.results["theory_with_bonus"] = result_df
        self.session.record_workflow(
            "apply_theory_bonus", config=cfg, outputs={"output_path": output_path},
            summary={"rows": int(len(result_df))},
        )
        return result_df

    def export_theory_topic_reports(
        self,
        cfg: TheoryTopicReportConfig,
        export_steps_dir: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        from pyexamgenerator.grading.attendance import export_theory_topic_reports

        output_dir = self._resolve_output_path(cfg.output_dir, None)
        export_state = self._start_step_export(export_steps_dir, "export_theory_topic_reports")
        self._export_step_dataframe(export_state, "attendance_quiz_input", pd.read_excel(cfg.attendance_quiz_xlsx_path))

        attendance_report_df, quiz_report_df = export_theory_topic_reports(
            attendance_quiz_xlsx_path=cfg.attendance_quiz_xlsx_path,
            output_dir=output_dir,
        )

        self._export_step_dataframe(export_state, "attendance_by_topic", attendance_report_df)
        self._export_step_dataframe(export_state, "quizzes_by_topic", quiz_report_df)
        self._finalize_step_export(
            export_state,
            {
                "attendance_report": str(Path(output_dir) / "asistencia_teoria_por_tema.xlsx"),
                "quiz_report": str(Path(output_dir) / "cuestionarios_por_tema_y_punto_extra.xlsx"),
            },
        )
        self.results["topic_attendance_report"] = attendance_report_df
        self.results["topic_quiz_report"] = quiz_report_df
        return attendance_report_df, quiz_report_df

    def compute_final_grade(self, cfg: FinalGradeConfig, export_steps_dir: Optional[str] = None) -> pd.DataFrame:
        """Computes a weighted final grade by file or by column (see :class:`FinalGradeConfig`)."""
        from pyexamgenerator.grading.final_grade import FinalGradeCalculator

        export_state = self._start_step_export(export_steps_dir, "compute_final_grade")
        calculator = FinalGradeCalculator(
            cap_to_10=cfg.cap_to_10,
            id_col=cfg.id_col,
            first_name_col=cfg.first_name_col,
            last_name_col=cfg.last_name_col,
        )

        if cfg.mode == "by_column":
            if not cfg.source_path:
                raise ValueError("En modo 'by_column' se requiere 'source_path'.")
            result_df = calculator.compute_by_columns(cfg.source_path, dict(cfg.weights))
        else:
            result_df = calculator.compute_by_files(list(cfg.sources))

        output_path = self._resolve_output_path(cfg.output_path, cfg.output_dir)
        calculator.export(output_path)

        self._export_step_dataframe(export_state, "final_grades", result_df)
        self._finalize_step_export(export_state, {"output_path": output_path})
        self.results["final_grades"] = result_df
        self.session.record_workflow(
            "compute_final_grade",
            config=cfg,
            outputs={"output_path": output_path},
            summary={"rows": int(len(result_df))},
        )
        return result_df

    def compare_results(self, cfg: ComparisonConfig, export_steps_dir: Optional[str] = None):
        """Compares a results table against a previous version and optionally writes a merged file.

        Returns the :class:`~pyexamgenerator.grading.comparison.ComparisonResult`.
        """
        from pyexamgenerator.grading.comparison import ResultComparator

        export_state = self._start_step_export(export_steps_dir, "compare_results")
        comparator = ResultComparator(
            id_col=cfg.id_col, first_name_col=cfg.first_name_col, last_name_col=cfg.last_name_col,
        )
        result = comparator.compare(
            existing_path=cfg.existing_path, new_path=cfg.new_path,
            value_cols=list(cfg.value_cols) or None,
            overwrite=cfg.overwrite, add_new_rows=cfg.add_new_rows,
        )

        report_path = self._resolve_output_path(cfg.report_output_path, cfg.output_dir)
        comparator.export_report(result, report_path)
        outputs: Dict[str, object] = {"report_output": report_path}

        if cfg.overwrite and result.merged_df is not None:
            merged_path = cfg.existing_path if cfg.merged_in_place else self._resolve_output_path(cfg.merged_output_path, cfg.output_dir)
            comparator.export_merged(result, merged_path)
            outputs["merged_output"] = merged_path

        self._export_step_dataframe(export_state, "comparison_changes", result.changes_df)
        self._finalize_step_export(export_state, outputs)
        self.results["comparison"] = result
        self.session.record_workflow("compare_results", config=cfg, outputs=outputs, summary=result.summary)
        return result

    @staticmethod
    def build_paths_by_group_types(xlsx_files: Iterable[str], group_types: Iterable[str]) -> List[str]:
        from pyexamgenerator.grading.integrations import MoodleGradeIntegrator

        return MoodleGradeIntegrator.build_paths_from_list_and_types(
            xlsx_files=xlsx_files,
            group_types=group_types,
        )

    def calculate_pir_bonus(
        self,
        cfg: PIRBonusConfig,
        export_steps_dir: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], Optional[pd.DataFrame]]:
        from pyexamgenerator.grading.attendance import PIRBonusCalculator

        export_state = self._start_step_export(export_steps_dir, "calculate_pir_bonus")
        self._export_step_dataframe(export_state, "attendance_input", pd.read_excel(cfg.attendance_path, header=cfg.attendance_header_row))
        self._export_step_dataframe(export_state, "schedule_input", pd.read_excel(cfg.schedule_path, sheet_name=cfg.schedule_sheet))
        self._export_step_dataframe(export_state, "quizzes_input", pd.read_excel(cfg.quizzes_path))

        calculator = PIRBonusCalculator(
            attendance_path=cfg.attendance_path,
            schedule_path=cfg.schedule_path,
            schedule_sheet=cfg.schedule_sheet,
            quizzes_path=cfg.quizzes_path,
            attendance_header_row=cfg.attendance_header_row,
            min_quiz_grade=cfg.min_quiz_grade,
            bonus_points=cfg.bonus_points,
        )

        summary_df, incidents_df, warnings = calculator.export(
            summary_path=self._resolve_output_path(cfg.summary_output_path, cfg.output_dir),
            incidents_path=self._resolve_output_path(cfg.incidents_output_path, cfg.output_dir),
        )
        self._export_step_dataframe(export_state, "pir_summary", summary_df)
        self._export_step_dataframe(export_state, "pir_incidents", incidents_df)

        theory_df = None
        if cfg.theory_xlsx_path and cfg.theory_output_with_bonus_path:
            theory_df = calculator.apply_bonus_to_theory(
                bonus_df=summary_df,
                theory_xlsx_path=cfg.theory_xlsx_path,
                output_path=self._resolve_output_path(cfg.theory_output_with_bonus_path, cfg.output_dir),
                theory_grade_col=cfg.theory_grade_col,
            )
            self._export_step_dataframe(export_state, "theory_with_bonus", theory_df)

        self._finalize_step_export(
            export_state,
            {
                "summary_output": self._resolve_output_path(cfg.summary_output_path, cfg.output_dir),
                "incidents_output": self._resolve_output_path(cfg.incidents_output_path, cfg.output_dir),
                "theory_output": self._resolve_output_path(cfg.theory_output_with_bonus_path, cfg.output_dir)
                if cfg.theory_output_with_bonus_path
                else None,
                "warnings": warnings,
            },
        )

        return summary_df, incidents_df, warnings, theory_df
