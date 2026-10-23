"""PIR bonus: the extra point for attending a topic's sessions and passing its class quiz.

:class:`PIRBonusCalculator` crosses the attendance export, the schedule and the class quizzes.
Moved from :mod:`pyexamgenerator.grading.attendance` (ARC-5), which still exports it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd

from pyexamgenerator.grading._text import normalize_text, parse_decimal
from pyexamgenerator.grading._topics import topic_key
from pyexamgenerator.grading.settings import current_settings


@dataclass(frozen=True)
class PIRSession:
    session_date: date
    topic: str
    group: str
    attendance_col: str


def _student_key(last_name: object, first_name: object) -> str:
    return re.sub(r"\s+", " ", f"{normalize_text(first_name)} {normalize_text(last_name)}").strip()


def _parse_spanish_month(token: str) -> int:
    months = {
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12,
    }
    t = normalize_text(token)[:3]
    if t not in months:
        raise ValueError(f"Unknown month in attendance header: {token}")
    return months[t]


def _parse_attendance_date(col_name: str) -> date:
    match = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", str(col_name).strip())
    if not match:
        raise ValueError(f"Could not parse date from attendance column: {col_name}")
    day = int(match.group(1))
    month = _parse_spanish_month(match.group(2))
    year = int(match.group(3))
    return date(year, month, day)


def _topic_from_text(text: object) -> Optional[str]:
    # Same detection as the attendance flow (before, only 'ley 31_95' / 'rd 39_97' were accepted here).
    return topic_key(text)


def _group_from_text(text: object) -> Optional[str]:
    normalized = normalize_text(text).upper()
    for group in current_settings().groups_longest_first:
        if normalize_text(group.name).upper() in normalized:
            return group.name
    return None


class PIRBonusCalculator:
    """Calculates PIR bonus from attendance + in-class quizzes."""

    def __init__(
        self,
        attendance_path: Optional[str] = None,
        schedule_path: Optional[str] = None,
        schedule_sheet: object = None,
        quizzes_path: Optional[str] = None,
        attendance_header_row: int = 3,
        min_quiz_grade: float = 7.5,
        bonus_points: float = 1.0,
        **legacy_kwargs,
    ) -> None:
        if attendance_path is None:
            attendance_path = legacy_kwargs.pop("asistencias_path", None)
        if schedule_path is None:
            schedule_path = legacy_kwargs.pop("horario_path", None)
        if schedule_sheet is None:
            schedule_sheet = legacy_kwargs.pop("horario_sheet", None)
        if quizzes_path is None:
            quizzes_path = legacy_kwargs.pop("cuestionarios_path", None)
        if "asistencia_header_row" in legacy_kwargs:
            attendance_header_row = legacy_kwargs.pop("asistencia_header_row")
        if "nota_minima_quiz" in legacy_kwargs:
            min_quiz_grade = legacy_kwargs.pop("nota_minima_quiz")
        if "bonus_puntos" in legacy_kwargs:
            bonus_points = legacy_kwargs.pop("bonus_puntos")
        if legacy_kwargs:
            raise TypeError(f"Unexpected arguments: {sorted(legacy_kwargs.keys())}")

        missing = [
            name
            for name, value in {
                "attendance_path": attendance_path,
                "schedule_path": schedule_path,
                "schedule_sheet": schedule_sheet,
                "quizzes_path": quizzes_path,
            }.items()
            if value is None or str(value).strip() == ""
        ]
        if missing:
            raise ValueError(f"Missing required PIR bonus arguments: {missing}")

        self.attendance_path = str(attendance_path)
        self.schedule_path = str(schedule_path)
        self.schedule_sheet = schedule_sheet
        self.quizzes_path = str(quizzes_path)
        self.attendance_header_row = attendance_header_row
        self.min_quiz_grade = float(min_quiz_grade)
        self.bonus_points = float(bonus_points)

    def _load_attendance(self) -> pd.DataFrame:
        return pd.read_excel(self.attendance_path, header=self.attendance_header_row)

    def _load_schedule(self) -> pd.DataFrame:
        return pd.read_excel(self.schedule_path, sheet_name=self.schedule_sheet)

    def _load_quizzes(self) -> pd.DataFrame:
        return pd.read_excel(self.quizzes_path)

    def _build_sessions(
        self, attendance_df: pd.DataFrame, schedule_df: pd.DataFrame
    ) -> Tuple[List[PIRSession], List[str]]:
        warnings: List[str] = []

        start_date_col = next((c for c in schedule_df.columns if normalize_text(c) == "fecha de inicio"), None)
        desc_col = next((c for c in schedule_df.columns if normalize_text(c) in {"descripcion", "descripcin"}), None)
        title_col = next(
            (c for c in schedule_df.columns if "titulo" in normalize_text(c) and "editable" in normalize_text(c)), None
        )

        if not start_date_col or not desc_col or not title_col:
            raise ValueError("Required columns were not found in schedule file.")

        sched = schedule_df.copy()
        sched[start_date_col] = pd.to_datetime(sched[start_date_col], errors="coerce")
        sched = sched.dropna(subset=[start_date_col]).copy()
        sched["_date"] = sched[start_date_col].dt.date
        sched["_topic"] = sched[desc_col].apply(_topic_from_text)
        sched["_group"] = sched[title_col].apply(_group_from_text)

        attendance_cols = [c for c in attendance_df.columns if re.match(r"^\d{1,2}\s+", str(c).strip())]
        sessions: List[PIRSession] = []

        for col in attendance_cols:
            try:
                session_date = _parse_attendance_date(str(col))
            except ValueError as exc:
                warnings.append(str(exc))
                continue

            rows = sched[sched["_date"] == session_date].copy()
            rows = rows[rows["_topic"].notna() & rows["_group"].notna()]
            if rows.empty:
                warnings.append(f"No matching schedule class for attendance '{col}' ({session_date}).")
                continue
            if len(rows) > 1:
                warnings.append(f"Multiple classes found for '{col}' ({session_date}); first one selected.")

            row = rows.iloc[0]
            sessions.append(
                PIRSession(
                    session_date=session_date,
                    topic=str(row["_topic"]),
                    group=str(row["_group"]),
                    attendance_col=str(col),
                )
            )

        return sessions, warnings

    @staticmethod
    def _extract_quiz_columns(quizzes_df: pd.DataFrame) -> Dict[Tuple[str, str], str]:
        out: Dict[Tuple[str, str], str] = {}
        quiz_column = current_settings().quiz_column_re()
        for col in quizzes_df.columns:
            text = str(col)
            match = quiz_column.match(text)
            if not match:
                continue
            topic = _topic_from_text(match.group(1))
            group = _group_from_text(match.group(2))
            if topic and group:
                out[(topic, group)] = text
        return out

    @staticmethod
    def _is_present(value: object) -> bool:
        return normalize_text(value).startswith("p")

    def calculate(self) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        attendance_df = self._load_attendance()
        schedule_df = self._load_schedule()
        quizzes_df = self._load_quizzes()

        sessions, warnings = self._build_sessions(attendance_df, schedule_df)
        quiz_cols = self._extract_quiz_columns(quizzes_df)

        topics = sorted({s.topic for s in sessions})
        groups = current_settings().group_names
        if not topics:
            # all([]) is True: without this guard every student would receive the bonus.
            warnings.append("No attendance session matched the schedule: no PIR bonus is awarded.")

        if not {"Apellido(s)", "Nombre"}.issubset(set(attendance_df.columns)):
            raise ValueError("Attendance file must include 'Apellido(s)' and 'Nombre'.")
        if not {"Apellido(s)", "Nombre"}.issubset(set(quizzes_df.columns)):
            raise ValueError("Quizzes file must include 'Apellido(s)' and 'Nombre'.")

        attendance_work = attendance_df.copy()
        attendance_work["_key"] = attendance_work.apply(
            lambda r: _student_key(r.get("Apellido(s)"), r.get("Nombre")), axis=1
        )

        quizzes_work = quizzes_df.copy()
        quizzes_work["_key"] = quizzes_work.apply(lambda r: _student_key(r.get("Apellido(s)"), r.get("Nombre")), axis=1)
        quiz_row_by_key = {row["_key"]: row for _, row in quizzes_work.iterrows()}

        summary_rows: List[Dict[str, object]] = []
        incident_rows: List[Dict[str, object]] = []

        for _, attendance_row in attendance_work.iterrows():
            key = attendance_row["_key"]
            quiz_row = quiz_row_by_key.get(key)

            attendance_by_topic_group: Dict[Tuple[str, str], bool] = {}
            attendance_by_topic: Dict[str, bool] = {}

            for session in sessions:
                present = self._is_present(attendance_row.get(session.attendance_col, ""))
                attendance_by_topic_group[(session.topic, session.group)] = present
                attendance_by_topic[session.topic] = attendance_by_topic.get(session.topic, False) or present

            valid_topic_scores: Dict[str, float] = {}

            if quiz_row is not None:
                for topic in topics:
                    scores_for_topic: List[float] = []
                    for group in groups:
                        col = quiz_cols.get((topic, group))
                        if not col:
                            continue
                        score = parse_decimal(quiz_row.get(col))
                        if score is None:
                            continue

                        if attendance_by_topic_group.get((topic, group), False):
                            scores_for_topic.append(score)
                        elif not attendance_by_topic.get(topic, False):
                            incident_rows.append(
                                {
                                    "Apellido(s)": attendance_row.get("Apellido(s)", ""),
                                    "Nombre": attendance_row.get("Nombre", ""),
                                    "Tema": topic,
                                    "Grupo_Quiz": group,
                                    "Nota_Quiz": score,
                                    "Tipo": "Quiz without attendance in that topic",
                                }
                            )

                    if scores_for_topic:
                        valid_topic_scores[topic] = max(scores_for_topic)

            attended_all_topics = all(attendance_by_topic.get(topic, False) for topic in topics)
            completed_all_valid_quizzes = all(topic in valid_topic_scores for topic in topics)
            meets_min_grades = completed_all_valid_quizzes and all(
                valid_topic_scores[topic] >= self.min_quiz_grade for topic in topics
            )

            bonus_applies = bool(topics) and attended_all_topics and completed_all_valid_quizzes and meets_min_grades
            bonus = self.bonus_points if bonus_applies else 0.0

            summary_rows.append(
                {
                    "Apellido(s)": attendance_row.get("Apellido(s)", ""),
                    "Nombre": attendance_row.get("Nombre", ""),
                    "Attended_All_Topics": attended_all_topics,
                    "Completed_All_Valid_Quizzes": completed_all_valid_quizzes,
                    "Meets_Min_7_5_All_Topics": meets_min_grades,
                    "Topics_Attended": sum(1 for topic in topics if attendance_by_topic.get(topic, False)),
                    "Topics_With_Valid_Quiz": sum(1 for topic in topics if topic in valid_topic_scores),
                    "Valid_Quiz_Mean": round(sum(valid_topic_scores.values()) / len(valid_topic_scores), 4)
                    if valid_topic_scores
                    else None,
                    "PIR_Bonus": bonus,
                }
            )

        summary_df = pd.DataFrame(summary_rows)
        incidents_df = pd.DataFrame(incident_rows)
        return summary_df, incidents_df, warnings

    def export(self, summary_path: str, incidents_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        summary_df, incidents_df, warnings = self.calculate()
        summary_df.to_excel(summary_path, index=False)
        incidents_df.to_excel(incidents_path, index=False)
        return summary_df, incidents_df, warnings

    def calcular(self) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        return self.calculate()

    def exportar(self, resumen_path: str, incidencias_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        return self.export(summary_path=resumen_path, incidents_path=incidencias_path)

    @staticmethod
    def apply_bonus_to_theory(
        bonus_df: pd.DataFrame,
        theory_xlsx_path: str,
        output_path: str,
        theory_grade_col: str = "Calificación/10,00",
    ) -> pd.DataFrame:
        theory_df = pd.read_excel(theory_xlsx_path)
        required = {"Apellido(s)", "Nombre", theory_grade_col}
        missing = [c for c in required if c not in theory_df.columns]
        if missing:
            raise ValueError(f"Missing theory columns: {missing}")

        bonus_work = bonus_df.copy()
        bonus_work["_key"] = bonus_work.apply(lambda r: _student_key(r.get("Apellido(s)"), r.get("Nombre")), axis=1)
        bonus_map = {row["_key"]: float(row.get("PIR_Bonus", 0.0) or 0.0) for _, row in bonus_work.iterrows()}

        def parse_theory_grade(value: object) -> float:
            parsed = parse_decimal(value)
            return float(parsed) if parsed is not None else 0.0

        out_df = theory_df.copy()
        out_df["_key"] = out_df.apply(lambda r: _student_key(r.get("Apellido(s)"), r.get("Nombre")), axis=1)
        out_df["PIR_Bonus"] = out_df["_key"].map(lambda k: bonus_map.get(k, 0.0))
        out_df["Theory_Base"] = out_df[theory_grade_col].map(parse_theory_grade)
        out_df["Theory_With_Bonus"] = (out_df["Theory_Base"] + out_df["PIR_Bonus"]).clip(upper=10.0)
        out_df = out_df.drop(columns=["_key"])

        out_df.to_excel(output_path, index=False)
        return out_df

    @staticmethod
    def aplicar_bonus_a_teoria(
        df_bonus: pd.DataFrame,
        teoria_xlsx_path: str,
        output_path: str,
        col_nota_teoria: str = "Calificación/10,00",
    ) -> pd.DataFrame:
        return PIRBonusCalculator.apply_bonus_to_theory(
            bonus_df=df_bonus,
            theory_xlsx_path=teoria_xlsx_path,
            output_path=output_path,
            theory_grade_col=col_nota_teoria,
        )
