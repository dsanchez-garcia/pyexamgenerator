"""Theory grades with the attendance bonus, and per-topic attendance and quiz reports.

:class:`TheoryBonusApplier` adds the bonus of the attendance + quizzes table to the theory grades;
:class:`TheoryTopicReporter` summarises that table per topic. Moved from
:mod:`pyexamgenerator.grading.attendance` (ARC-5), which still exports them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from pyexamgenerator.grading._ids import normalize_id
from pyexamgenerator.grading._text import normalize_key, parse_decimal
from pyexamgenerator.grading.settings import current_settings


def _normalize_bonus_id(value: object) -> str:
    return normalize_id(value)


def _find_theory_grade_columns(theory_df: pd.DataFrame, theory_grade_col: Optional[str]) -> List[str]:
    columns = [str(c) for c in theory_df.columns]
    if theory_grade_col and theory_grade_col in theory_df.columns:
        return [theory_grade_col]

    normalized = {normalize_key(c): c for c in columns}
    for candidate in ["calificacion1000", "calificacin1000", "calificacion10", "nota", "grade"]:
        if candidate in normalized:
            return [normalized[candidate]]

    quiz_columns = [c for c in columns if str(c).startswith("Cuestionario:")]
    if quiz_columns:
        return quiz_columns

    raise ValueError("No se encontro una columna de nota de teoria reconocible.")


def _as_dataframe(source: object) -> pd.DataFrame:
    """Accept either a DataFrame (returned as a copy) or a path to read from disk."""
    if isinstance(source, pd.DataFrame):
        return source.copy()
    return pd.read_excel(source)


class TheoryBonusApplier:
    """Apply the PIR theory bonus (``bonus_points``, +1 by default), retaining inputs and outputs as attributes.

    Inputs (``theory`` and ``attendance_quiz``) may be either a path to an Excel file
    or an in-memory DataFrame, so the step can be chained without writing intermediate
    files. After :meth:`apply`, the instance exposes ``theory_df`` / ``bonus_df`` for the loaded
    inputs, ``grade_columns`` for the theory grade column(s) that received the bonus, ``result_df``
    for the theory table with bonus columns added, and ``output_path`` for the written result.
    """

    def __init__(
        self,
        theory: object,
        attendance_quiz: object,
        theory_grade_col: Optional[str] = None,
        cap_to_10: bool = True,
        bonus_points: float = 1.0,
    ) -> None:
        self.theory = theory
        self.attendance_quiz = attendance_quiz
        self.theory_grade_col = theory_grade_col
        self.cap_to_10 = cap_to_10
        self.bonus_points = float(bonus_points)
        self.theory_df: Optional[pd.DataFrame] = None
        self.bonus_df: Optional[pd.DataFrame] = None
        self.grade_columns: Optional[List[str]] = None
        self.result_df: Optional[pd.DataFrame] = None
        self.output_path: Optional[str] = None

    def apply(self, output_path: Optional[str] = None) -> pd.DataFrame:
        self.theory_df = _as_dataframe(self.theory)
        self.bonus_df = _as_dataframe(self.attendance_quiz)
        self.result_df = _compute_theory_bonus(
            self.theory_df,
            self.bonus_df,
            theory_grade_col=self.theory_grade_col,
            cap_to_10=self.cap_to_10,
            bonus_points=self.bonus_points,
            grade_columns_out=self,
        )
        if output_path is not None:
            self.export(output_path)
        return self.result_df

    def export(self, output_path: str) -> pd.DataFrame:
        if self.result_df is None:
            self.apply()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self.result_df.to_excel(output_path, index=False)
        self.output_path = output_path
        return self.result_df


def _compute_theory_bonus(
    theory_df: pd.DataFrame,
    bonus_df: pd.DataFrame,
    theory_grade_col: Optional[str] = None,
    cap_to_10: bool = True,
    bonus_points: float = 1.0,
    grade_columns_out: Optional[object] = None,
) -> pd.DataFrame:
    if "Tiene_Punto_Adicional_Teoria" not in bonus_df.columns:
        raise ValueError("El archivo de asistencia+cuestionarios no incluye Tiene_Punto_Adicional_Teoria.")

    bonus_by_id: Dict[str, Tuple[int, str]] = {}
    bonus_by_name: Dict[str, Tuple[int, str]] = {}
    for _, row in bonus_df.iterrows():
        has_bonus = 1 if str(row.get("Tiene_Punto_Adicional_Teoria", "")).strip().lower() == "si" else 0
        reason = str(row.get("Motivo_No_Punto", "")).strip()
        student_id = _normalize_bonus_id(row.get("ID_Alumno", ""))
        name_key = normalize_key(f"{row.get('Nombre', '')} {row.get('Apellido(s)', '')}")
        if student_id:
            previous = bonus_by_id.get(student_id, (0, ""))
            bonus_by_id[student_id] = (max(has_bonus, previous[0]), reason or previous[1])
        if name_key:
            previous = bonus_by_name.get(name_key, (0, ""))
            bonus_by_name[name_key] = (max(has_bonus, previous[0]), reason or previous[1])

    grade_columns = _find_theory_grade_columns(theory_df, theory_grade_col)
    if grade_columns_out is not None:
        grade_columns_out.grade_columns = grade_columns
    out_df = theory_df.copy()
    # Pandas with StringDtype rejects assigning the numeric bonus to a text grade column.
    # Object dtype preserves the original cell values while allowing updated numeric grades.
    for grade_column in grade_columns:
        out_df[grade_column] = out_df[grade_column].astype(object)
    out_df["Punto_Adicional_Cuestionarios"] = 0
    out_df["Nota_Original_Teoria"] = pd.NA
    out_df["Nota_Final_Teoria"] = pd.NA
    out_df["Incremento_Aplicado"] = 0.0
    out_df["Motivo_No_Incremento"] = ""

    id_candidates = ["Número de ID", "Numero de ID", "Nombre de usuario", "ID_Alumno", "ID_Oficial", "ID"]
    for idx, row in out_df.iterrows():
        id_keys = [_normalize_bonus_id(row.get(col, "")) for col in id_candidates if col in out_df.columns]
        name_key = normalize_key(f"{row.get('Nombre', '')} {row.get('Apellido(s)', '')}")

        has_bonus = 0
        no_bonus_reason = "sin_regla_punto"
        for key in id_keys:
            if key and key in bonus_by_id:
                has_bonus, no_bonus_reason = bonus_by_id[key]
                break
        else:
            if name_key and name_key in bonus_by_name:
                has_bonus, no_bonus_reason = bonus_by_name[name_key]

        original_values = {col: parse_decimal(row.get(col, "")) for col in grade_columns}
        valid_values = [value for value in original_values.values() if value is not None]
        original_reference = max(valid_values) if valid_values else None
        out_df.at[idx, "Punto_Adicional_Cuestionarios"] = has_bonus
        out_df.at[idx, "Nota_Original_Teoria"] = original_reference

        if not has_bonus:
            out_df.at[idx, "Nota_Final_Teoria"] = original_reference
            out_df.at[idx, "Motivo_No_Incremento"] = no_bonus_reason or "no_cumple_condiciones_pir"
            continue
        if original_reference is None:
            out_df.at[idx, "Motivo_No_Incremento"] = "sin_nota_base_valida"
            continue

        final_values: List[float] = []
        for col, original in original_values.items():
            if original is None:
                continue
            updated = original + bonus_points
            if cap_to_10:
                updated = min(10.0, updated)
            updated = round(updated, 2)
            out_df.at[idx, col] = updated
            final_values.append(updated)

        final_reference = max(final_values) if final_values else original_reference
        out_df.at[idx, "Nota_Final_Teoria"] = final_reference
        out_df.at[idx, "Incremento_Aplicado"] = round(float(final_reference) - float(original_reference), 2)
        if float(out_df.at[idx, "Incremento_Aplicado"]) <= 0:
            out_df.at[idx, "Motivo_No_Incremento"] = "nota_ya_en_tope"

    return out_df


def apply_theory_bonus_from_attendance_quiz(
    theory_xlsx_path: str,
    attendance_quiz_xlsx_path: str,
    output_path: str,
    theory_grade_col: Optional[str] = None,
    cap_to_10: bool = True,
    bonus_points: float = 1.0,
) -> pd.DataFrame:
    """Apply the PIR bonus (``bonus_points``, +1 by default) to a theory workbook using attendance+quiz audit output.

    Thin functional wrapper kept for backward compatibility; delegates to
    :class:`TheoryBonusApplier`.
    """
    applier = TheoryBonusApplier(
        theory=theory_xlsx_path,
        attendance_quiz=attendance_quiz_xlsx_path,
        theory_grade_col=theory_grade_col,
        cap_to_10=cap_to_10,
        bonus_points=bonus_points,
    )
    return applier.apply(output_path=output_path)


class TheoryTopicReporter:
    """Build per-topic attendance and quiz reports, retaining inputs and outputs.

    The ``attendance_quiz`` input may be a path or an in-memory DataFrame. After
    :meth:`build` the instance exposes ``source_df``, ``attendance_report_df`` and
    ``quiz_report_df``; :meth:`export` also records ``attendance_output_path`` and
    ``quiz_output_path``.
    """

    def __init__(self, attendance_quiz: object) -> None:
        self.attendance_quiz = attendance_quiz
        self.source_df: Optional[pd.DataFrame] = None
        self.attendance_report_df: Optional[pd.DataFrame] = None
        self.quiz_report_df: Optional[pd.DataFrame] = None
        self.attendance_output_path: Optional[str] = None
        self.quiz_output_path: Optional[str] = None

    def build(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        self.source_df = _as_dataframe(self.attendance_quiz)
        self.attendance_report_df, self.quiz_report_df = _compute_theory_topic_reports(self.source_df)
        return self.attendance_report_df, self.quiz_report_df

    def export(self, output_dir: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if self.attendance_report_df is None or self.quiz_report_df is None:
            self.build()
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.attendance_output_path = str(out_dir / "asistencia_teoria_por_tema.xlsx")
        self.quiz_output_path = str(out_dir / "cuestionarios_por_tema_y_punto_extra.xlsx")
        self.attendance_report_df.to_excel(self.attendance_output_path, index=False)
        self.quiz_report_df.to_excel(self.quiz_output_path, index=False)
        return self.attendance_report_df, self.quiz_report_df


def _report_topics(columns: Sequence[object]) -> List[str]:
    """Topics of the per-topic report: the named topics (LPRL, RSP), T02..T11 (the usual layout) and
    any other topic found in the class columns (e.g. ``C01_0303_T12_GIM__Asistencia``), which used to
    be left out."""
    named = current_settings().named_topic_names
    t_codes = {f"T{idx:02d}" for idx in range(2, 12)}
    others: List[str] = []
    for col in columns:
        match = re.match(r"^C\d+_\d{4}_([A-Z]+\d*)_[A-Z]+__", str(col))
        if not match:
            continue
        topic = match.group(1)
        if re.fullmatch(r"T\d{2}", topic):
            t_codes.add(topic)
        elif topic not in {*named, "TOP"} and topic not in others:
            others.append(topic)
    return named + sorted(t_codes) + others


def _compute_theory_topic_reports(source_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    topics = _report_topics(source_df.columns)

    base_cols = ["ID_Alumno", "Nombre", "Apellido(s)"]
    attendance_rows: List[Dict[str, object]] = []
    quiz_rows: List[Dict[str, object]] = []

    for _, row in source_df.iterrows():
        attendance_row = {col: row.get(col, "") for col in base_cols}
        quiz_row = {col: row.get(col, "") for col in base_cols}

        for topic in topics:
            attendance_values = []
            quiz_values: List[float] = []
            for col in source_df.columns:
                col_text = str(col)
                if f"_{topic}_" not in col_text:
                    continue
                if col_text.endswith("__Asistencia"):
                    attendance_values.append(str(row.get(col, "")).strip())
                elif col_text.endswith("__Quiz_Nota_Tema_Max"):
                    parsed = parse_decimal(row.get(col, ""))
                    if parsed is not None:
                        quiz_values.append(parsed)

            attended = any(value in {"asiste", "asiste_por_tema"} for value in attendance_values)
            justified_or_uncertain = any(value in {"falta", "dudosa"} for value in attendance_values)
            attendance_row[f"{topic}_Asistencia"] = "si" if attended else ("no" if justified_or_uncertain else "")
            quiz_row[f"{topic}_Nota_Cuestionario"] = max(quiz_values) if quiz_values else pd.NA

        attendance_row["Total_Asistencias_Teoria"] = sum(
            1 for topic in topics if attendance_row.get(f"{topic}_Asistencia") == "si"
        )
        quiz_row["Obtiene_Punto_Extra"] = row.get("Tiene_Punto_Adicional_Teoria", "")
        quiz_row["Motivo_No_Punto"] = row.get("Motivo_No_Punto", "")

        attendance_rows.append(attendance_row)
        quiz_rows.append(quiz_row)

    attendance_report_df = pd.DataFrame(attendance_rows)
    quiz_report_df = pd.DataFrame(quiz_rows)
    return attendance_report_df, quiz_report_df


def export_theory_topic_reports(
    attendance_quiz_xlsx_path: str,
    output_dir: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Export per-topic attendance and quiz reports from attendance+quiz audit output.

    Thin functional wrapper kept for backward compatibility; delegates to
    :class:`TheoryTopicReporter`.
    """
    reporter = TheoryTopicReporter(attendance_quiz=attendance_quiz_xlsx_path)
    return reporter.export(output_dir)
