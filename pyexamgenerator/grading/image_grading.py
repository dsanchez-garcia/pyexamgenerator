"""Grading of scanned answer sheets: OCR, exam type, review of doubtful marks and grades over 10.

:class:`ImageExamGrader` reads the sheets with :class:`~pyexamgenerator.grading.extraction.AnswerSheetExtractor`
and grades them against the exam's Moodle XML. Moved from :mod:`pyexamgenerator.grading.extraction`
(ARC-5), which keeps the OCR itself and still exports these names. Needs the OCR extra
(``pip install pyexamgenerator[grading]``).
"""

import argparse
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from pyexamgenerator._console import log_to_console, stdin_is_interactive
from pyexamgenerator.grading._ids import normalize_id
from pyexamgenerator.grading._paths import prepare_output_path
from pyexamgenerator.grading._text import parse_decimal
from pyexamgenerator.grading.data import (
    SharedExamDataStore,
    build_merged_enrollment_from_sources,
    infer_exam_type_from_xml_filename,
)
from pyexamgenerator.grading.extraction import (
    AnswerSheetExtractor,
    SheetResult,
    audit_to_dataframe,
    results_to_dataframe,
)

logger = logging.getLogger(__name__)


_REVIEW_ANSWERS = {"a", "b", "c", "d", "nc", "-"}


def _ask_exam_type_in_console(image_name: str, available_types: Sequence[str], suggestion: Optional[str]) -> str:
    """Default ``exam_type_callback`` from a terminal: asks until a valid type (Enter = suggestion)."""
    options = ", ".join(available_types)
    prompt = (
        f"Exam type not detected for '{image_name}'. "
        f"Options [{options}]" + (f" (suggested: {suggestion})" if suggestion else "") + ": "
    )
    while True:
        selected = input(prompt).strip().upper()
        if not selected and suggestion:
            return suggestion
        if selected in available_types:
            return selected
        print(f"Invalid value. Must be one of: {options}")


def _ask_review_in_console(image_path: str, question: str, current: str, suggested: str, margin: float) -> str:
    """Default ``review_callback`` from a terminal: asks until a valid answer (Enter keeps it)."""
    while True:
        answer = (
            input(f"{question} | current={current} | suggested={suggested} (margin={margin:.3f}) -> ").strip().lower()
        )
        if answer == "":
            return current
        if answer in _REVIEW_ANSWERS:
            return answer
        print("Invalid value. Use: a/b/c/d/nc/- or Enter.")


@dataclass
class QuestionInfo:
    name: str
    answers: Dict[str, float]


class ImageExamGrader:
    """Integrated flow: OCR answer sheets -> resolve exam type -> grade over 10."""

    def __init__(
        self,
        xml_paths: Sequence[str],
        enrollment_path: Optional[str] = None,
        enrollment_paths: Optional[Sequence[str]] = None,
        min_mark_ratio: float = 0.17,
        min_gap: float = 0.05,
        debug_dir: Optional[str] = None,
        temp_image_dir: Optional[str] = None,
        aggressive_recovery: bool = False,
        aggressive_min_ratio: float = 0.11,
        aggressive_min_gap_ratio: float = 0.25,
        aggressive_min_top_vs_second: float = 1.10,
        enrollment_sheet: int = 0,
        last_name_col: str = "Apellido(s)",
        first_name_col: str = "Nombre",
        id_col: str = "Número de ID",
        email_col: str = "Dirección de correo",
        forced_student_by_image: Optional[Dict[str, str]] = None,
        shared_store: Optional[SharedExamDataStore] = None,
        **legacy_kwargs,
    ) -> None:
        enrollment_path = enrollment_path or legacy_kwargs.pop("matriculados_path", None)
        enrollment_paths = enrollment_paths or legacy_kwargs.pop("matriculados_paths", None)
        last_name_col = legacy_kwargs.pop("col_apellidos", last_name_col)
        first_name_col = legacy_kwargs.pop("col_nombre", first_name_col)
        id_col = legacy_kwargs.pop("col_id", id_col)
        email_col = legacy_kwargs.pop("col_email", email_col)
        if legacy_kwargs:
            raise TypeError(f"Unexpected arguments: {sorted(legacy_kwargs.keys())}")

        if not xml_paths:
            raise ValueError("At least one exam XML file is required.")

        self.xml_paths = [str(p) for p in xml_paths]
        self.enrollment_path = enrollment_path
        self.enrollment_paths = [str(p) for p in (enrollment_paths or []) if str(p).strip()]
        self.enrollment_sheet = enrollment_sheet
        self.last_name_col = last_name_col
        self.first_name_col = first_name_col
        self.id_col = id_col
        self.email_col = email_col
        self.shared_store = shared_store or SharedExamDataStore()

        self.enrollment_df = self._load_enrollment(enrollment_path)

        self.extractor = AnswerSheetExtractor(
            enrollment_df=self.enrollment_df,
            debug_dir=debug_dir,
            min_mark_ratio=min_mark_ratio,
            min_gap=min_gap,
            aggressive_recovery=aggressive_recovery,
            aggressive_min_ratio=aggressive_min_ratio,
            aggressive_min_gap_ratio=aggressive_min_gap_ratio,
            aggressive_min_top_vs_second=aggressive_min_top_vs_second,
            id_col=id_col,
            forced_student_by_image=forced_student_by_image,
            temp_image_dir=temp_image_dir,
        )

        self.questions_by_exam_type = self._load_xmls_by_exam_type(self.xml_paths)
        self.available_exam_types = sorted(self.questions_by_exam_type.keys())

    def _load_enrollment(self, enrollment_path: Optional[str]) -> Optional[pd.DataFrame]:
        if self.enrollment_paths:
            return build_merged_enrollment_from_sources(self.enrollment_paths, sheet_name=self.enrollment_sheet)

        if not enrollment_path:
            return None
        return self.shared_store.load_enrollment(
            xlsx_path=enrollment_path,
            sheet_name=self.enrollment_sheet,
            first_name_col=self.first_name_col,
            last_name_col=self.last_name_col,
            with_lookup_name=True,
        )

    @staticmethod
    def _infer_exam_type_from_xml_filename(xml_path: str) -> str:
        return infer_exam_type_from_xml_filename(xml_path)

    def _load_xmls_by_exam_type(self, xml_paths: Sequence[str]) -> Dict[str, Dict[str, QuestionInfo]]:
        raw = self.shared_store.load_questions_by_exam_type(
            xml_paths=xml_paths,
            infer_exam_type=self._infer_exam_type_from_xml_filename,
        )
        out: Dict[str, Dict[str, QuestionInfo]] = {}
        for exam_type, questions in raw.items():
            out[exam_type] = {
                q_name: QuestionInfo(name=q_name, answers=answer_map) for q_name, answer_map in questions.items()
            }
        return out

    @staticmethod
    def _normalize_forced_lookup_key(value: str) -> str:
        return str(value).strip().replace("\\", "/").lower()

    def _resolve_exam_type(
        self,
        sheet: SheetResult,
        forced_type_by_image: Dict[str, str],
        prompt_if_missing: bool,
        exam_type_callback: Optional[Callable[[str, List[str], Optional[str]], Optional[str]]] = None,
    ) -> str:
        image_name = Path(sheet.image).name
        normalized_forced: Dict[str, str] = {}
        for key, value in (forced_type_by_image or {}).items():
            key_raw = str(key).strip()
            value_raw = str(value).strip().upper()
            if not key_raw or not value_raw:
                continue
            normalized_forced[self._normalize_forced_lookup_key(key_raw)] = value_raw

        for lookup in (image_name, str(sheet.image)):
            exam_type = normalized_forced.get(self._normalize_forced_lookup_key(lookup))
            if not exam_type:
                continue
            if exam_type not in self.questions_by_exam_type:
                raise ValueError(f"Forced exam type unavailable for {image_name}: {exam_type}")
            return exam_type

        if sheet.exam_type:
            exam_type = str(sheet.exam_type).strip().upper()
            if exam_type in self.questions_by_exam_type:
                return exam_type

        # Si solo hay una plantilla cargada, no hace falta bloquear la corrección por tipo faltante.
        if len(self.available_exam_types) == 1:
            only_type = self.available_exam_types[0]
            if only_type in self.questions_by_exam_type:
                return only_type

        not_determined = (
            f"Could not determine exam type for {image_name}. Available types: {', '.join(self.available_exam_types)}"
        )
        if exam_type_callback is None:
            # Never block on input() without an interactive terminal (GUI, notebooks, CI).
            if not prompt_if_missing or not stdin_is_interactive():
                raise ValueError(not_determined)
            exam_type_callback = _ask_exam_type_in_console

        suggestion = self._suggest_exam_type_from_answers(sheet.answers)
        selected = str(exam_type_callback(image_name, list(self.available_exam_types), suggestion) or "")
        selected = selected.strip().upper()
        if selected in self.questions_by_exam_type:
            return selected
        raise ValueError(not_determined)

    def _suggest_exam_type_from_answers(self, answers: Dict[str, str]) -> Optional[str]:
        if not answers:
            return None

        best_exam_type = None
        best_score = float("-inf")
        for exam_type in self.available_exam_types:
            score, _ = self._calculate_score_for_type(answers, exam_type)
            if score > best_score:
                best_score = score
                best_exam_type = exam_type
        return best_exam_type

    def _calculate_score_for_type(self, answers: Dict[str, str], exam_type: str) -> Tuple[float, Dict[str, str]]:
        questions = self.questions_by_exam_type[exam_type]
        question_count = len(questions)
        points_per_question = 10.0 / float(question_count)
        points_per_question_output: Dict[str, str] = {}

        for question_name in sorted(questions.keys()):
            answer = str(answers.get(question_name, "")).strip().lower()
            if not answer or answer in {"-", "nc"}:
                points_per_question_output[question_name] = "-"
                continue

            fraction = questions[question_name].answers.get(answer, 0.0)
            points = points_per_question * fraction
            points_per_question_output[question_name] = f"{points:.2f}".replace(".", ",")

        total = 0.0
        for question_name in sorted(questions.keys()):
            answer = str(answers.get(question_name, "")).strip().lower()
            if not answer or answer in {"-", "nc"}:
                continue
            fraction = questions[question_name].answers.get(answer, 0.0)
            total += points_per_question * fraction

        return max(0.0, total), points_per_question_output

    def _enrollment_row_from_id(self, official_id: Optional[str]) -> Optional[pd.Series]:
        if self.enrollment_df is None or not official_id:
            return None

        normalized_id = normalize_id(official_id)
        if normalized_id == "":
            return None

        series = self.enrollment_df[self.id_col].map(normalize_id)
        matches = self.enrollment_df[series == normalized_id]
        if matches.empty:
            return None
        return matches.iloc[0]

    def _build_ocr_incidents(
        self,
        sheet_results: Sequence[SheetResult],
        grades_df: pd.DataFrame,
        audit_df: Optional[pd.DataFrame],
        skipped: Optional[Sequence[Dict[str, str]]] = None,
    ) -> pd.DataFrame:
        incidents: List[Dict[str, object]] = [
            {
                "Imagen": item["Imagen"],
                "Tipo": item["Tipo"],
                "Severidad": "alta",
                "Detalle": f"{item['Detalle']} La hoja no se ha corregido.",
            }
            for item in (skipped or [])
        ]
        grade_by_image: Dict[str, float] = {}
        for _, row in grades_df.iterrows():
            image = str(row.get("Imagen", "")).strip()
            grade = parse_decimal(row.get("Calificacion/10,00", ""))
            if image and grade is not None:
                grade_by_image[image] = grade

        low_margin_by_image: Dict[str, int] = {}
        if audit_df is not None and not audit_df.empty:
            for _, row in audit_df.iterrows():
                image = str(row.get("Imagen", "")).strip()
                selected = str(row.get("Seleccionada", "")).strip().lower()
                scores = [
                    float(row.get("Score_a", 0.0) or 0.0),
                    float(row.get("Score_b", 0.0) or 0.0),
                    float(row.get("Score_c", 0.0) or 0.0),
                    float(row.get("Score_d", 0.0) or 0.0),
                    float(row.get("Score_nc", 0.0) or 0.0),
                ]
                scores = sorted(scores, reverse=True)
                margin = scores[0] - scores[1] if len(scores) > 1 else 0.0
                if selected not in {"", "-"} and margin < (self.extractor.min_gap * 1.2):
                    low_margin_by_image[image] = low_margin_by_image.get(image, 0) + 1

        unresolved_by_image: Dict[str, int] = {}
        if audit_df is not None and not audit_df.empty:
            unresolved_mask = audit_df["Seleccionada"].astype(str).str.strip().eq("-")
            unresolved = audit_df.loc[unresolved_mask]
            for image, group in unresolved.groupby("Imagen"):
                unresolved_by_image[str(image)] = int(len(group))

        for sheet in sheet_results:
            image = sheet.image
            if not str(sheet.student_id_official or "").strip():
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "MISSING_ID",
                        "Severidad": "alta",
                        "Detalle": "No se pudo asociar ID oficial al OCR del alumno.",
                    }
                )

            if not str(sheet.exam_type or "").strip():
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "MISSING_EXAM_TYPE",
                        "Severidad": "alta",
                        "Detalle": "No se pudo detectar el tipo de examen en la hoja.",
                    }
                )

            grade = grade_by_image.get(image)
            if grade is not None and grade <= 0.0:
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "ZERO_SCORE",
                        "Severidad": "media",
                        "Detalle": "La nota total OCR es 0,00. Revisión manual recomendada.",
                    }
                )

            low_count = low_margin_by_image.get(image, 0)
            if low_count > 0:
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "LOW_CONFIDENCE_MARKS",
                        "Severidad": "media",
                        "Detalle": f"Se detectaron {low_count} pregunta(s) con margen de marcado bajo.",
                    }
                )

            unresolved_count = unresolved_by_image.get(image, 0)
            if unresolved_count > 0:
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "UNRESOLVED_ANSWERS",
                        "Severidad": "media",
                        "Detalle": f"Quedan {unresolved_count} respuesta(s) sin identificar ('-').",
                    }
                )

        if not incidents:
            return pd.DataFrame(columns=["Imagen", "Tipo", "Severidad", "Detalle"])
        return pd.DataFrame(incidents)

    @staticmethod
    def _best_option_from_audit_row(row: Dict[str, object]) -> Tuple[str, float, float]:
        score_map = {
            "a": float(row.get("Score_a", 0.0) or 0.0),
            "b": float(row.get("Score_b", 0.0) or 0.0),
            "c": float(row.get("Score_c", 0.0) or 0.0),
            "d": float(row.get("Score_d", 0.0) or 0.0),
            "nc": float(row.get("Score_nc", 0.0) or 0.0),
        }
        ordered = sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)
        best_label, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        return best_label, best_score, second_score

    def _is_doubtful_audit_row(self, row: Dict[str, object]) -> bool:
        selected = str(row.get("Seleccionada", "")).strip().lower()
        decision = str(row.get("Decision", "")).strip().lower()
        _, best_score, second_score = self._best_option_from_audit_row(row)
        margin = best_score - second_score
        if selected == "-":
            return True
        if decision in {"adaptive", "aggressive"}:
            return True
        return margin < (self.extractor.min_gap * 1.2)

    @staticmethod
    def _question_sort_key(question_label: str) -> int:
        match = re.search(r"(\d+)", str(question_label))
        return int(match.group(1)) if match else 9999

    def _run_interactive_review(
        self,
        sheet_results: Sequence[SheetResult],
        open_image_on_review: bool = True,
        review_callback: Optional[Callable[[str, str, str, str, float], Optional[str]]] = None,
    ) -> Tuple[int, List[Dict[str, object]]]:
        """Confirms the doubtful answers of each sheet with ``review_callback``.

        The callback receives ``(image_path, question, current, suggested, margin)`` and returns the
        answer to keep (a/b/c/d/nc/-), or None to keep the current one. Without a callback the console
        asks (only from an interactive terminal).
        """
        if review_callback is None:
            review_callback = _ask_review_in_console
        print("Interactive OCR review enabled. Confirming doubtful answers...")
        updated = 0
        changes: List[Dict[str, object]] = []

        for sheet in sheet_results:
            candidates = [row for row in sheet.audit_rows if self._is_doubtful_audit_row(row)]
            if not candidates:
                continue

            candidates = sorted(candidates, key=lambda row: self._question_sort_key(str(row.get("Pregunta", ""))))

            image_path = str(sheet.image)
            if open_image_on_review:
                try:
                    os.startfile(image_path)  # type: ignore[attr-defined]
                except Exception:
                    print(f"Could not open image automatically: {image_path}")

            print("\n---")
            print(f"Image: {image_path}")
            print(f"Detected exam type: {sheet.exam_type or '?'}")
            print("Options: a/b/c/d/nc/- ; Enter keeps current value.")

            for row in candidates:
                question = str(row.get("Pregunta", "")).strip()
                current = str(sheet.answers.get(question, "-")).strip().lower() or "-"
                suggested, top_score, second_score = self._best_option_from_audit_row(row)
                margin = top_score - second_score

                answer = review_callback(image_path, question, current, suggested, margin)
                answer = current if answer is None else str(answer).strip().lower()
                if answer not in _REVIEW_ANSWERS:
                    raise ValueError(f"Respuesta de revisión no válida para {question}: '{answer}' (usa a/b/c/d/nc/-).")

                if answer != current:
                    sheet.answers[question] = answer
                    row["Seleccionada"] = answer
                    row["Decision"] = "manual"
                    row["AutoRecovered"] = "no"
                    updated += 1
                    changes.append(
                        {
                            "Imagen": image_path,
                            "Pregunta": question,
                            "Valor_Anterior": current,
                            "Valor_Final": answer,
                            "Sugerida_OCR": suggested,
                            "Margen_OCR": round(float(margin), 4),
                        }
                    )

        print(f"Interactive review completed. Updated answers: {updated}")
        return updated, changes

    @staticmethod
    def _manual_changes_to_dataframe(changes: Sequence[Dict[str, object]]) -> pd.DataFrame:
        cols = ["Imagen", "Pregunta", "Valor_Anterior", "Valor_Final", "Sugerida_OCR", "Margen_OCR"]
        if not changes:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame(changes, columns=cols)

    @staticmethod
    def _build_manual_review_dataframe(audit_df: Optional[pd.DataFrame]) -> pd.DataFrame:
        columns = [
            "Imagen",
            "Pregunta",
            "Seleccionada",
            "Decision",
            "Sugerida",
            "Score_top",
            "Score_segunda",
            "Margen",
            "Accion_Manual",
            "Observaciones",
        ]
        if audit_df is None or audit_df.empty:
            return pd.DataFrame(columns=columns)

        work = audit_df.copy()
        work["Seleccionada"] = work["Seleccionada"].astype(str).str.strip().str.lower()
        unresolved = work[work["Seleccionada"] == "-"]
        if unresolved.empty:
            return pd.DataFrame(columns=columns)

        rows: List[Dict[str, object]] = []
        for _, row in unresolved.iterrows():
            scores = {
                "a": float(row.get("Score_a", 0.0) or 0.0),
                "b": float(row.get("Score_b", 0.0) or 0.0),
                "c": float(row.get("Score_c", 0.0) or 0.0),
                "d": float(row.get("Score_d", 0.0) or 0.0),
                "nc": float(row.get("Score_nc", 0.0) or 0.0),
            }
            sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            top_label, top_score = sorted_scores[0]
            second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
            rows.append(
                {
                    "Imagen": row.get("Imagen", ""),
                    "Pregunta": row.get("Pregunta", ""),
                    "Seleccionada": "-",
                    "Decision": row.get("Decision", ""),
                    "Sugerida": top_label,
                    "Score_top": round(top_score, 4),
                    "Score_segunda": round(second_score, 4),
                    "Margen": round(top_score - second_score, 4),
                    "Accion_Manual": "",
                    "Observaciones": "",
                }
            )
        return pd.DataFrame(rows, columns=columns)

    def grade_from_images(
        self,
        image_paths: Sequence[str],
        output_answers: str,
        output_grades: str,
        output_dir: Optional[str] = None,
        output_audit: Optional[str] = None,
        output_incidents: Optional[str] = None,
        output_review: Optional[str] = None,
        output_manual_changes: Optional[str] = None,
        interactive_review: bool = False,
        open_image_on_review: bool = True,
        forced_type_by_image: Optional[Dict[str, str]] = None,
        prompt_missing_type: bool = True,
        exam_type_callback: Optional[Callable[[str, List[str], Optional[str]], Optional[str]]] = None,
        review_callback: Optional[Callable[[str, str, str, str, float], Optional[str]]] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        """OCR + grading of the answer sheets in ``image_paths``.

        The user is asked through optional callbacks instead of ``input()``:
        ``exam_type_callback(image_name, available_types, suggestion)`` returns the type of a sheet
        whose type could not be detected (or None: the sheet is reported as an incident), and
        ``review_callback`` confirms doubtful answers when ``interactive_review=True`` (see
        :meth:`_run_interactive_review`). Without callbacks, ``prompt_missing_type`` and
        ``interactive_review`` ask in the console, only from an interactive terminal.
        """
        if interactive_review and review_callback is None and not stdin_is_interactive():
            raise ValueError("interactive_review=True necesita review_callback cuando no se ejecuta desde un terminal.")
        forced = {k: v for k, v in (forced_type_by_image or {}).items()}

        # Relative paths go to output_dir; absolute ones are kept.
        output_answers = prepare_output_path(output_answers, output_dir)
        output_grades = prepare_output_path(output_grades, output_dir)
        if output_audit:
            output_audit = prepare_output_path(output_audit, output_dir)
        if output_incidents:
            output_incidents = prepare_output_path(output_incidents, output_dir)
        if output_review:
            output_review = prepare_output_path(output_review, output_dir)
        if output_manual_changes:
            output_manual_changes = prepare_output_path(output_manual_changes, output_dir)

        sheet_results = self.extractor.process_batch(image_paths, skip_errors=True)
        # Sheets that could not be graded: reported as incidents instead of aborting the batch.
        skipped: List[Dict[str, str]] = [
            {"Imagen": image, "Tipo": "UNREADABLE_IMAGE", "Detalle": f"No se pudo procesar la imagen ({error})."}
            for image, error in getattr(self.extractor, "failed_images", [])
        ]
        manual_changes: List[Dict[str, object]] = []
        if interactive_review:
            _updated, manual_changes = self._run_interactive_review(
                sheet_results,
                open_image_on_review=open_image_on_review,
                review_callback=review_callback,
            )

        answers_df = results_to_dataframe(sheet_results)

        resolved_types: List[str] = []
        moodle_rows: List[Dict[str, str]] = []

        all_questions = sorted({q for exam in self.questions_by_exam_type.values() for q in exam.keys()})
        max_question_num = max(int(re.search(r"\d+", q).group()) for q in all_questions)
        reference_weight = 10.0 / max_question_num
        reference_weight_str = f"{reference_weight:.2f}".replace(".", ",")

        for sheet in sheet_results:
            try:
                exam_type = self._resolve_exam_type(sheet, forced, prompt_missing_type, exam_type_callback)
            except ValueError as exc:
                resolved_types.append("")
                skipped.append(
                    {
                        "Imagen": sheet.image,
                        "Tipo": "EXAM_TYPE_UNRESOLVED",
                        "Detalle": f"{exc}. Asigna el tipo (tipos forzados por imagen) y vuelve a corregir.",
                    }
                )
                continue
            resolved_types.append(exam_type)
            total_score, points_by_question = self._calculate_score_for_type(sheet.answers, exam_type)

            row: Dict[str, str] = {
                "Imagen": sheet.image,
                "Tipo_Examen": exam_type,
                "Nombre_OCR": sheet.student_name_ocr or "",
                "Nombre_Oficial": sheet.student_name_official or "",
                "ID_Oficial": sheet.student_id_official or "",
                "Calificacion/10,00": f"{total_score:.2f}".replace(".", ","),
            }

            enrollment_row = self._enrollment_row_from_id(sheet.student_id_official)
            if enrollment_row is not None:
                row[self.last_name_col] = str(enrollment_row.get(self.last_name_col, ""))
                row[self.first_name_col] = str(enrollment_row.get(self.first_name_col, ""))
                row[self.id_col] = normalize_id(enrollment_row.get(self.id_col, ""))
                row[self.email_col] = str(enrollment_row.get(self.email_col, ""))
                if "Grupo_Principal" in enrollment_row.index:
                    row["Grupo_Principal"] = str(enrollment_row.get("Grupo_Principal", ""))
                if "Subgrupo_Practicas" in enrollment_row.index:
                    row["Subgrupo_Practicas"] = str(enrollment_row.get("Subgrupo_Practicas", ""))

            for question in all_questions:
                question_num = int(re.search(r"\d+", question).group())
                col_name = f"P. {question_num} /{reference_weight_str}"
                row[col_name] = points_by_question.get(question, "-")

            moodle_rows.append(row)

        answers_df["Tipo_Examen_Usado"] = resolved_types
        answers_df.to_excel(output_answers, index=False)

        grades_df = pd.DataFrame(moodle_rows)
        grades_df.to_excel(output_grades, index=False)

        audit_df = None
        if output_audit:
            audit_df = audit_to_dataframe(sheet_results)
            audit_df.to_excel(output_audit, index=False)

        incidents_df = self._build_ocr_incidents(sheet_results, grades_df, audit_df, skipped=skipped)
        self.skipped_sheets = skipped
        self.last_incidents_df = incidents_df
        for item in skipped:
            logger.warning(f"AVISO: hoja sin corregir: {item['Imagen']} ({item['Tipo']}).")
        if output_incidents:
            incidents_df.to_excel(output_incidents, index=False)

        review_df = self._build_manual_review_dataframe(audit_df)
        if output_review:
            review_df.to_excel(output_review, index=False)

        if output_manual_changes:
            manual_df = self._manual_changes_to_dataframe(manual_changes)
            manual_df.to_excel(output_manual_changes, index=False)

        return answers_df, grades_df, audit_df

    def corregir_desde_imagenes(
        self,
        image_paths: Sequence[str],
        salida_respuestas: str,
        salida_calificaciones: str,
        salida_auditoria: Optional[str] = None,
        salida_incidencias: Optional[str] = None,
        salida_revision: Optional[str] = None,
        salida_cambios_manuales: Optional[str] = None,
        tipo_forzado_por_imagen: Optional[Dict[str, str]] = None,
        preguntar_tipo_faltante: bool = True,
        output_dir: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        return self.grade_from_images(
            image_paths=image_paths,
            output_answers=salida_respuestas,
            output_grades=salida_calificaciones,
            output_dir=output_dir,
            output_audit=salida_auditoria,
            output_incidents=salida_incidencias,
            output_review=salida_revision,
            output_manual_changes=salida_cambios_manuales,
            forced_type_by_image=tipo_forzado_por_imagen,
            prompt_missing_type=preguntar_tipo_faltante,
        )


def _parse_forced_type(items: Sequence[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --force-type item: {item}. Use IMAGE=TYPE")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip().upper()
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrated grading from scanned answer sheet images")
    parser.add_argument("images", nargs="+", help="JPG/PNG answer sheet images")
    parser.add_argument("--xmls", nargs="+", required=True, help="Available XML templates (e.g. 2A, 2B)")
    parser.add_argument("--enrollment", default=None, help="Enrollment Excel")
    parser.add_argument(
        "--enrollment-list", nargs="+", default=None, help="Optional list of enrollment Excels to merge"
    )
    parser.add_argument("--output-answers", default="respuestas_alumnos_paso1_desde_imagenes.xlsx")
    parser.add_argument("--output-grades", default="calificaciones_desde_imagenes.xlsx")
    parser.add_argument("--output-audit", default=None)
    parser.add_argument("--output-incidents", default=None)
    parser.add_argument("--output-review", default=None)
    parser.add_argument("--output-manual-changes", default=None)
    parser.add_argument("--interactive-review", action="store_true", help="Ask the user to confirm doubtful answers")
    parser.add_argument(
        "--no-open-image", action="store_true", help="Do not auto-open the image during interactive review"
    )
    parser.add_argument("--output-dir", default=None, help="Directory where all outputs are generated")
    parser.add_argument("--debug-dir", default=None)
    parser.add_argument(
        "--temp-image-dir",
        default=None,
        help="Fallback temp directory for OCR image copies (default: pyexamgenerator_temp in the system temp folder)",
    )
    parser.add_argument("--min-mark-ratio", type=float, default=0.17)
    parser.add_argument("--min-gap", type=float, default=0.05)
    parser.add_argument(
        "--force-type",
        action="append",
        default=[],
        help="Assign exam type by image: 'ImageName.jpg=2B'. Repeatable.",
    )
    parser.add_argument(
        "--no-prompt-type",
        action="store_true",
        help="Fail instead of prompting when exam type is missing and not forced.",
    )
    return parser.parse_args()


def main() -> None:
    log_to_console()
    args = _parse_args()
    forced = _parse_forced_type(args.force_type)

    grader = ImageExamGrader(
        xml_paths=args.xmls,
        enrollment_path=args.enrollment,
        enrollment_paths=args.enrollment_list,
        min_mark_ratio=args.min_mark_ratio,
        min_gap=args.min_gap,
        debug_dir=args.debug_dir,
        temp_image_dir=args.temp_image_dir,
    )

    answers_df, grades_df, audit_df = grader.grade_from_images(
        image_paths=args.images,
        output_answers=args.output_answers,
        output_grades=args.output_grades,
        output_dir=args.output_dir,
        output_audit=args.output_audit,
        output_incidents=args.output_incidents,
        output_review=args.output_review,
        output_manual_changes=args.output_manual_changes,
        interactive_review=args.interactive_review,
        open_image_on_review=not args.no_open_image,
        forced_type_by_image=forced,
        prompt_missing_type=not args.no_prompt_type,
    )

    print(f"OK: answers -> {args.output_answers} ({len(answers_df)} rows)")
    print(f"OK: grades -> {args.output_grades} ({len(grades_df)} rows)")
    if audit_df is not None:
        print(f"OK: audit -> {args.output_audit} ({len(audit_df)} rows)")
    if args.output_incidents:
        try:
            incidents_count = len(pd.read_excel(args.output_incidents))
            print(f"OK: incidents -> {args.output_incidents} ({incidents_count} rows)")
        except Exception:
            print(f"OK: incidents -> {args.output_incidents}")
    if args.output_review:
        try:
            review_count = len(pd.read_excel(args.output_review))
            print(f"OK: review -> {args.output_review} ({review_count} rows)")
        except Exception:
            print(f"OK: review -> {args.output_review}")
    if args.output_manual_changes:
        try:
            manual_count = len(pd.read_excel(args.output_manual_changes))
            print(f"OK: manual changes -> {args.output_manual_changes} ({manual_count} rows)")
        except Exception:
            print(f"OK: manual changes -> {args.output_manual_changes}")


# Backward-compatible aliases
PreguntaInfo = QuestionInfo
CorrectorExamenesDesdeImagenes = ImageExamGrader


if __name__ == "__main__":
    main()
