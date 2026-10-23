"""Absence justifications: emails that justify missed classes, crossed with the attendance export.

The PIR bonus and the theory bonus now live in :mod:`pyexamgenerator.grading.pir_bonus` and
:mod:`pyexamgenerator.grading.theory_bonus` (ARC-5); their names are still importable from here.
"""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd

from pyexamgenerator._console import log_to_console
from pyexamgenerator.grading._ids import normalize_id
from pyexamgenerator.grading._names import match_name
from pyexamgenerator.grading._paths import prepare_output_path
from pyexamgenerator.grading._text import find_column, normalize_key, parse_decimal
from pyexamgenerator.grading._topics import topic_key
from pyexamgenerator.grading.settings import current_settings

# Moved to their own modules (ARC-5); still importable from here.
from pyexamgenerator.grading.pir_bonus import PIRBonusCalculator as PIRBonusCalculator
from pyexamgenerator.grading.pir_bonus import PIRSession as PIRSession
from pyexamgenerator.grading.theory_bonus import TheoryBonusApplier as TheoryBonusApplier
from pyexamgenerator.grading.theory_bonus import TheoryTopicReporter as TheoryTopicReporter
from pyexamgenerator.grading.theory_bonus import (
    apply_theory_bonus_from_attendance_quiz as apply_theory_bonus_from_attendance_quiz,
    export_theory_topic_reports as export_theory_topic_reports,
)

logger = logging.getLogger(__name__)


@dataclass
class AbsenceJustificationResult:
    summary_df: pd.DataFrame
    detailed_df: pd.DataFrame
    attendance_overview_df: Optional[pd.DataFrame] = None
    sender_absence_check_df: Optional[pd.DataFrame] = None
    attendance_quiz_df: Optional[pd.DataFrame] = None
    extreme_justified_absences_df: Optional[pd.DataFrame] = None


class AbsenceJustificationManager:
    """Crosses justification emails with enrollment, attendance, and optional quizzes."""

    def __init__(
        self,
        attendance_xlsx_path: str,
        justifications_xlsx_path: str,
        enrollment_xlsx_path: str,
        schedule_xlsx_path: Optional[str] = None,
        schedule_sheet: object = 0,
        quizzes_xlsx_path: Optional[str] = None,
        attendance_header_row: int = 3,
        attendance_sheet: int = 0,
        justifications_sheet: int = 0,
        enrollment_sheet: int = 0,
        sender_col: str = "REMITENTE",
        subject_col: str = "ASUNTO",
        message_col: str = "MENSAJE",
        first_name_col: Optional[str] = None,
        last_name_col: Optional[str] = None,
        id_col: Optional[str] = None,
        email_col: Optional[str] = None,
        justification_mode: str = "extremo",
        min_quiz_grade: float = 7.5,
    ) -> None:
        self.attendance_xlsx_path = attendance_xlsx_path
        self.justifications_xlsx_path = justifications_xlsx_path
        self.enrollment_xlsx_path = enrollment_xlsx_path
        self.schedule_xlsx_path = schedule_xlsx_path
        self.schedule_sheet = schedule_sheet
        self.quizzes_xlsx_path = quizzes_xlsx_path
        self.attendance_header_row = int(attendance_header_row)
        self.attendance_sheet = int(attendance_sheet)
        self.justifications_sheet = int(justifications_sheet)
        self.enrollment_sheet = int(enrollment_sheet)
        self.sender_col = sender_col
        self.subject_col = subject_col
        self.message_col = message_col
        # Optional explicit column names; when set they take precedence over the fuzzy candidates.
        self.first_name_col = first_name_col
        self.last_name_col = last_name_col
        self.id_col = id_col
        self.email_col = email_col
        self.justification_mode = str(justification_mode or "extremo").strip().lower()
        # Class-quiz grade needed in every topic for the theory bonus point.
        self.min_quiz_grade = float(min_quiz_grade)

    _normalize = staticmethod(normalize_key)
    _find_column = staticmethod(find_column)

    @staticmethod
    def _candidates(override: Optional[str], defaults: Sequence[str]) -> List[str]:
        """Builds the candidate list for :meth:`_find_column`, giving priority to a user override."""
        if override:
            return [override, *defaults]
        return list(defaults)

    @staticmethod
    def _normalize_justification_date(value: object) -> str:
        """Normalizes a justification date to ISO ``YYYY-MM-DD``.

        The template asks for ``mm/dd/aaaa``; if the first field is > 12 it is treated as ``dd/mm/aaaa``.
        Any unparseable value is returned stripped, unchanged.
        """
        text = "" if pd.isna(value) else str(value).strip()
        match = re.match(r"^(\d{1,2})\D(\d{1,2})\D(\d{2,4})$", text)
        if not match:
            return text
        a, b, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if year < 100:
            year += 2000
        month, day = a, b
        if a > 12 and b <= 12:  # Clearly dd/mm.
            month, day = b, a
        try:
            return pd.Timestamp(year=year, month=month, day=day).strftime("%Y-%m-%d")
        except ValueError:
            return text

    @classmethod
    def _parse_structured_justification(cls, subject: object, message: object) -> Optional[Dict[str, str]]:
        """Parses the structured justification template, if present, into its fields.

        Recognized lines (accent/space-insensitive labels)::

            Día de la falta (formato mm/dd/aaaa): ...
            Nº Tema/Práctica a la que se ha faltado: ...
            Grupo (GIM o GITI-GIE-GIEI): ...
            Grupo de prácticas (MC1, etc): ...
            Motivo de la ausencia: ...

        Returns a dict with the keys ``fecha`` (+ ``fecha_normalizada``), ``tema_practica``, ``grupo``,
        ``subgrupo_practicas`` and ``motivo`` for the fields found, or ``None`` if none are present.
        """
        text = ""
        for part in (subject, message):
            if part is not None and not (isinstance(part, float) and pd.isna(part)):
                text += str(part) + "\n"
        if not text.strip():
            return None

        fields: Dict[str, str] = {}
        for raw_line in re.split(r"[\r\n]+", text):
            if ":" not in raw_line:
                continue
            label, _, value = raw_line.partition(":")
            value = value.strip()
            if not value:
                continue
            norm = cls._normalize(label)
            if norm.startswith("diadelafalta"):
                fields["fecha"] = value
            elif "temapractica" in norm or ("tema" in norm and "practica" in norm) or norm.startswith("notema"):
                fields["tema_practica"] = value
            elif norm.startswith("grupodepracticas"):
                fields["subgrupo_practicas"] = value
            elif norm.startswith("grupo"):
                fields["grupo"] = value
            elif norm.startswith("motivo"):
                fields["motivo"] = value

        if not fields:
            return None

        if "fecha" in fields:
            fields["fecha_normalizada"] = cls._normalize_justification_date(fields["fecha"])
        if "grupo" in fields:
            normalized_group = cls._group_from_text(fields["grupo"])
            if normalized_group:
                fields["grupo"] = normalized_group
        return fields

    @staticmethod
    def _parse_sender_name(sender: str) -> str:
        text = str(sender or "").strip()
        quoted = re.search(r'"([^"]+)"', text)
        if quoted:
            text = quoted.group(1)
        # The address is not part of the name ("Leo Ruiz <leo@uca.es>" is "Leo Ruiz"): it used to stay
        # in it, and a student writing from another address was matched to nobody.
        text = re.sub(r"<[^>]*>", "", text)
        text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", text)
        text = re.sub(r"\(.*?\)", "", text).strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _parse_sender_email(sender: str) -> str:
        text = str(sender or "")
        match = re.search(r"<([^>]+)>", text)
        if match:
            return match.group(1).strip().lower()
        match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        return match.group(0).strip().lower() if match else ""

    @staticmethod
    def _is_attendance_date_column(column_name: str) -> bool:
        text = str(column_name)
        # Any academic year (not only 2026): Moodle names these columns '<date> ... Todos los estudiantes'.
        return "Todos los estudiantes" in text and re.search(r"\b(19|20)\d{2}\b", text) is not None

    @staticmethod
    def _is_present_value(value: object) -> bool:
        text = "" if pd.isna(value) else str(value).strip().upper()
        return text.startswith("P")

    @staticmethod
    def _is_absence_value(value: object) -> bool:
        text = "" if pd.isna(value) else str(value).strip().upper()
        if not text or text == "?":
            return False
        return text.startswith("F") or text.startswith("A") or "0/2" in text or "0/1" in text

    @staticmethod
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
        return months.get(AbsenceJustificationManager._normalize(token)[:3], 0)

    @staticmethod
    def _parse_attendance_date(column_name: str) -> Optional[pd.Timestamp]:
        match = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", str(column_name).strip())
        if not match:
            return None
        month = AbsenceJustificationManager._parse_spanish_month(match.group(2))
        if month <= 0:
            return None
        try:
            return pd.Timestamp(year=int(match.group(3)), month=month, day=int(match.group(1)))
        except ValueError:
            return None

    @staticmethod
    def _topic_from_text(text: object) -> str:
        raw = "" if pd.isna(text) else str(text).strip()
        normalized = AbsenceJustificationManager._normalize(raw)
        if "practic" in normalized:
            return ""
        # Sesiones teóricas sin el literal "tema" (Ley 31/95, RD 39/97) también cuentan como tema.
        return topic_key(raw) or raw

    @staticmethod
    def _group_from_text(text: object) -> str:
        normalized = AbsenceJustificationManager._normalize(text)
        for group in current_settings().groups_longest_first:
            if normalize_key(group.name) in normalized:
                return group.name
        return ""

    @staticmethod
    def _student_name_key(first_name: object, last_name: object) -> str:
        return (
            f"{AbsenceJustificationManager._normalize(first_name)}_{AbsenceJustificationManager._normalize(last_name)}"
        )

    @staticmethod
    def _student_lookup_keys(student_id: object, first_name: object, last_name: object) -> List[str]:
        keys: List[str] = []
        sid = normalize_id(student_id)
        if sid:
            keys.append(f"id:{sid}")
        sname = AbsenceJustificationManager._student_name_key(first_name, last_name)
        if sname and sname != "_":
            keys.append(f"name:{sname}")
            # Split-independent key: a full name split at its first space ('María' + 'José García')
            # and the enrollment fields ('María José' + 'García') must still meet.
            keys.append(f"full:{sname.replace('_', '')}")
        return keys

    @staticmethod
    def _short_topic_code(topic: object) -> str:
        text = str(topic or "").strip().upper()
        match = re.match(r"^TEMA\s+(\d{1,2})$", text)
        if match:
            return f"T{int(match.group(1)):02d}"
        if text in current_settings().named_topic_names:
            return text
        return "TOP"

    @staticmethod
    def _short_group_code(group: object) -> str:
        text = str(group or "").strip().upper()
        for known in current_settings().groups:
            if text == known.name.upper():
                return known.code
        return "GRP"

    @staticmethod
    def _short_date_code(date_text: object) -> str:
        text = str(date_text or "").strip()
        match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", text)
        if match:
            return f"{match.group(1)}{match.group(2)}"
        return "0000"

    @classmethod
    def _short_class_column_name(cls, idx: int, date_text: object, topic: object, group: object) -> str:
        d = cls._short_date_code(date_text)
        t = cls._short_topic_code(topic)
        g = cls._short_group_code(group)
        return f"C{idx:02d}_{d}_{t}_{g}"

    @staticmethod
    def _extract_quiz_columns(quizzes_df: pd.DataFrame) -> Dict[Tuple[str, str], str]:
        out: Dict[Tuple[str, str], str] = {}
        quiz_column = current_settings().quiz_column_re()
        for col in quizzes_df.columns:
            match = quiz_column.match(str(col))
            if not match:
                continue
            topic = AbsenceJustificationManager._topic_from_text(match.group(1))
            group = AbsenceJustificationManager._group_from_text(match.group(2))
            if topic and group:
                out[(topic, group)] = str(col)
        return out

    @staticmethod
    def _classify_justification_text(subject: object, message: object) -> Tuple[str, int, str]:
        text = f"{'' if pd.isna(subject) else str(subject)}\n{'' if pd.isna(message) else str(message)}".lower()
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return "no_justifica", 0, "sin_texto"

        positive_patterns = [
            r"justific",
            r"justificante",
            r"adjunt",
            r"certific",
            r"parte med",
            r"m[ée]dic",
            r"ausenc",
            r"falta",
            r"asisten",
            r"no pude",
            r"no he podido",
            r"motivo",
            r"permiso",
        ]
        evidence_patterns = [r"archivo adjunto", r"adjunto", r"enlace", r"certificado"]
        negative_patterns = [r"consulta", r"duda", r"gracias", r"examen", r"tutor[íi]a"]

        score = 0
        reasons: List[str] = []

        for pat in positive_patterns:
            if re.search(pat, text):
                score += 1
                reasons.append(f"pos:{pat}")
        for pat in evidence_patterns:
            if re.search(pat, text):
                score += 1
                reasons.append(f"evid:{pat}")
        for pat in negative_patterns:
            if re.search(pat, text):
                score -= 1
                reasons.append(f"neg:{pat}")

        if score >= 3:
            label = "justifica_falta"
        elif score >= 1:
            label = "dudosa"
        else:
            label = "no_justifica"

        return label, int(score), " | ".join(reasons[:8])

    def _load_enrollment(self) -> pd.DataFrame:
        df = pd.read_excel(self.enrollment_xlsx_path, sheet_name=self.enrollment_sheet)
        first_name_col = self._find_column(df.columns, self._candidates(self.first_name_col, ["Nombre"]))
        last_name_col = self._find_column(
            df.columns, self._candidates(self.last_name_col, ["Apellido(s)", "Apellidos", "Apellido"])
        )
        email_col = self._find_column(
            df.columns,
            self._candidates(self.email_col, ["Dirección de correo", "Direccin de correo", "Correo", "Email"]),
        )
        id_col = self._find_column(df.columns, self._candidates(self.id_col, ["Número de ID", "Nmero de ID", "ID"]))

        if first_name_col is None or last_name_col is None:
            raise ValueError("Enrollment file must contain first and last name columns.")

        out = df.copy()
        out["_first_name_col"] = first_name_col
        out["_last_name_col"] = last_name_col
        out["_email_col"] = email_col or ""
        out["_id_col"] = id_col or ""
        out["_full_name"] = (
            out[first_name_col].astype(str).str.strip() + " " + out[last_name_col].astype(str).str.strip()
        ).str.strip()
        out["_full_name_norm"] = out["_full_name"].map(self._normalize)
        if email_col:
            out["_email_norm"] = out[email_col].astype(str).str.strip().str.lower()
        else:
            out["_email_norm"] = ""
        return out

    def _match_sender_to_enrollment(
        self,
        sender_name: str,
        sender_email: str,
        enrollment_df: pd.DataFrame,
    ) -> Tuple[Optional[pd.Series], str, float, str]:
        """The enrolled student who sent a justification, only when the match is safe (GRD-6).

        By email address, or by name with the rules of :func:`~pyexamgenerator.grading._names.match_name`
        (a similarity threshold assigned other students' emails, e.g. «Lea» to «Leo»). Returns
        ``(row, match_type, score, candidate)``: ``row`` is None when nobody is assigned, and
        ``candidate`` is then the most similar student, to review by hand.
        """
        if sender_email:
            email_matches = enrollment_df[enrollment_df["_email_norm"] == sender_email]
            if not email_matches.empty:
                return email_matches.iloc[0], "email", 1.0, ""

        full_names = enrollment_df["_full_name"].tolist()
        match = match_name(sender_name, full_names)
        if match.position is not None:
            return enrollment_df.iloc[match.position], match.kind, float(match.score), ""
        candidate = full_names[match.candidate] if match.candidate is not None else ""
        return None, match.kind, float(match.score), str(candidate)

    def _build_attendance_lookup(self) -> Tuple[pd.DataFrame, List[str], str, str, str]:
        attendance_df = pd.read_excel(
            self.attendance_xlsx_path, sheet_name=self.attendance_sheet, header=self.attendance_header_row
        )
        first_name_col = self._find_column(attendance_df.columns, self._candidates(self.first_name_col, ["Nombre"]))
        last_name_col = self._find_column(
            attendance_df.columns, self._candidates(self.last_name_col, ["Apellido(s)", "Apellidos", "Apellido"])
        )
        id_col = self._find_column(
            attendance_df.columns,
            self._candidates(self.id_col, ["Número de ID", "Nmero de ID", "ID", "ID de estudiante"]),
        )

        if first_name_col is None or last_name_col is None:
            raise ValueError("Attendance file must contain first and last name columns.")

        attendance_df["_full_name"] = (
            attendance_df[first_name_col].astype(str).str.strip()
            + " "
            + attendance_df[last_name_col].astype(str).str.strip()
        ).str.strip()
        attendance_df["_full_name_norm"] = attendance_df["_full_name"].map(self._normalize)
        attendance_df["_id_norm"] = attendance_df[id_col].map(normalize_id) if id_col else ""
        date_cols = [c for c in attendance_df.columns if self._is_attendance_date_column(str(c))]
        return attendance_df, date_cols, first_name_col, last_name_col, (id_col or "")

    def _build_sessions_catalog(self, date_cols: List[str]) -> pd.DataFrame:
        rows: List[Dict[str, str]] = []
        schedule_df = None
        start_date_col = None
        desc_col = None
        title_col = None

        if self.schedule_xlsx_path:
            schedule_df = pd.read_excel(self.schedule_xlsx_path, sheet_name=self.schedule_sheet)
            start_date_col = self._find_column(schedule_df.columns, ["Fecha de Inicio"])
            desc_col = self._find_column(schedule_df.columns, ["Descripción", "Descripcin", "Descripcion"])
            title_col = self._find_column(
                schedule_df.columns, ["Título (EDITABLE)", "Ttulo (EDITABLE)", "Titulo (EDITABLE)"]
            )
            if start_date_col:
                schedule_df = schedule_df.copy()
                schedule_df[start_date_col] = pd.to_datetime(schedule_df[start_date_col], errors="coerce")
                schedule_df = schedule_df.dropna(subset=[start_date_col])
                schedule_df["_date"] = schedule_df[start_date_col].dt.date

        for col in date_cols:
            date_ts = self._parse_attendance_date(col)
            topic = ""
            group = ""

            if schedule_df is not None and start_date_col and date_ts is not None:
                rows_by_date = schedule_df[schedule_df["_date"] == date_ts.date()]
                if not rows_by_date.empty:
                    topics = []
                    groups = []
                    for _, srow in rows_by_date.iterrows():
                        if desc_col:
                            parsed_topic = self._topic_from_text(srow.get(desc_col, ""))
                            if parsed_topic:
                                topics.append(parsed_topic)
                        if title_col:
                            parsed_group = self._group_from_text(srow.get(title_col, ""))
                            if parsed_group:
                                groups.append(parsed_group)
                    topic = " | ".join(sorted(set(topics)))
                    group = " | ".join(sorted(set(groups)))

            date_text = "" if date_ts is None else date_ts.strftime("%d/%m/%Y")
            label_parts = [part for part in [date_text, topic, group] if part]
            rows.append(
                {
                    "Fecha_Asistencia_Col": str(col),
                    "Fecha_Clase": date_text,
                    "Tema_Clase": topic,
                    "Grupo_Clase": group,
                    "Clase_Label": " | ".join(label_parts) if label_parts else str(col),
                    "Es_Teoria": "si" if topic else "no",
                }
            )

        return pd.DataFrame(rows)

    def _build_attendance_overview(
        self,
        enrollment_df: pd.DataFrame,
        attendance_df: pd.DataFrame,
        date_cols: List[str],
        attendance_id_col: str,
    ) -> pd.DataFrame:
        sessions_df = self._build_sessions_catalog(date_cols)
        theory_sessions_df = sessions_df[sessions_df["Es_Teoria"].astype(str).str.lower() == "si"].copy()
        session_by_col = {str(row["Fecha_Asistencia_Col"]): row for _, row in theory_sessions_df.iterrows()}
        session_columns: List[Tuple[str, str, str]] = []
        for idx, col in enumerate(theory_sessions_df["Fecha_Asistencia_Col"].tolist(), start=1):
            meta = session_by_col.get(str(col), {})
            class_label = str(meta.get("Clase_Label", col))
            session_col_name = self._short_class_column_name(
                idx,
                meta.get("Fecha_Clase", ""),
                meta.get("Tema_Clase", ""),
                meta.get("Grupo_Clase", ""),
            )
            session_columns.append((str(col), class_label, session_col_name))
        topic_by_col = {
            str(row["Fecha_Asistencia_Col"]): str(row.get("Tema_Clase", "")).strip()
            for _, row in theory_sessions_df.iterrows()
        }

        by_id: Dict[str, pd.Series] = {}
        by_name: Dict[str, pd.Series] = {}
        for _, arow in attendance_df.iterrows():
            sid = str(arow.get("_id_norm", "")).strip()
            sname = str(arow.get("_full_name_norm", "")).strip()
            if sid and sid not in by_id:
                by_id[sid] = arow
            if sname and sname not in by_name:
                by_name[sname] = arow

        rows: List[Dict[str, object]] = []
        for _, erow in enrollment_df.iterrows():
            id_col = str(erow.get("_id_col", "")).strip()
            email_col = str(erow.get("_email_col", "")).strip()
            student_id = normalize_id(erow.get(id_col, "")) if id_col else ""
            student_name = str(erow.get("_full_name", "")).strip()
            student_name_norm = str(erow.get("_full_name_norm", "")).strip()
            student_email = str(erow.get(email_col, "")).strip() if email_col else ""

            att_row = by_id.get(student_id) if (student_id and attendance_id_col) else None
            if att_row is None:
                att_row = by_name.get(student_name_norm)

            attended_labels: List[str] = []
            absence_labels: List[str] = []
            uncertain_labels: List[str] = []
            row_out: Dict[str, object] = {
                "ID_Alumno": student_id,
                "Alumno": student_name,
                "Email_Alumno": student_email,
            }

            # Regla PIR: para un tema, asistir a cualquiera de los dos grupos cuenta como asistencia al tema.
            topic_has_presence: Dict[str, bool] = {}
            for col, _, _ in session_columns:
                topic = topic_by_col.get(col, "")
                if not topic:
                    continue
                att_value = "" if att_row is None else att_row.get(col, "")
                if self._is_present_value(att_value):
                    topic_has_presence[topic] = True
                elif topic not in topic_has_presence:
                    topic_has_presence[topic] = False

            for col, class_label, session_col_name in session_columns:
                topic = topic_by_col.get(col, "")
                att_value = "" if att_row is None else att_row.get(col, "")
                attended_by_topic = bool(topic) and topic_has_presence.get(topic, False)

                if self._is_present_value(att_value):
                    attended_labels.append(class_label)
                    row_out[session_col_name] = "asiste"
                elif attended_by_topic:
                    attended_labels.append(class_label)
                    row_out[session_col_name] = "asiste_por_tema"
                elif self._is_absence_value(att_value):
                    absence_labels.append(class_label)
                    row_out[session_col_name] = "falta"
                else:
                    uncertain_labels.append(class_label)
                    row_out[session_col_name] = "dudosa"

            attended_topics = {t for t, present in topic_has_presence.items() if present}
            row_out["Num_Asistencias"] = len(attended_topics)
            row_out["Num_Faltas"] = len(absence_labels)
            row_out["Num_Dudosas"] = len(uncertain_labels)
            rows.append(row_out)

        return pd.DataFrame(rows)

    def _build_attendance_with_quizzes_df(
        self,
        attendance_df: pd.DataFrame,
        date_cols: List[str],
        justified_classes_by_student: Optional[Dict[str, Set[str]]] = None,
    ) -> pd.DataFrame:
        if not self.quizzes_xlsx_path:
            return pd.DataFrame()
        justified_classes_by_student = justified_classes_by_student or {}

        quizzes_df = pd.read_excel(self.quizzes_xlsx_path)
        quiz_cols = self._extract_quiz_columns(quizzes_df)
        sessions_df = self._build_sessions_catalog(date_cols)
        sessions_df = sessions_df[sessions_df["Es_Teoria"].astype(str).str.lower() == "si"].copy()
        session_by_col = {str(row["Fecha_Asistencia_Col"]): row for _, row in sessions_df.iterrows()}
        session_columns: List[Tuple[str, str, str, str, str]] = []
        for idx, col in enumerate(sessions_df["Fecha_Asistencia_Col"].tolist(), start=1):
            meta = session_by_col.get(str(col), {})
            topic = str(meta.get("Tema_Clase", "")).strip()
            group = str(meta.get("Grupo_Clase", "")).strip()
            class_label = str(meta.get("Clase_Label", col))
            session_col_name = self._short_class_column_name(
                idx,
                meta.get("Fecha_Clase", ""),
                topic,
                group,
            )
            session_columns.append((str(col), class_label, session_col_name, topic, group))

        # Añade los temas con nombre (LPRL/RSP) desde cuestionarios aunque no existan columnas de
        # asistencia para esas fechas.
        existing_topics = {topic for _, _, _, topic, _ in session_columns if topic}
        synthetic_idx = len(session_columns)
        for topic in current_settings().named_topic_names:
            if topic in existing_topics:
                continue
            for group in current_settings().group_names:
                if (topic, group) not in quiz_cols:
                    continue
                synthetic_idx += 1
                class_label = f"SIN_ASISTENCIA_REGISTRADA | {topic} | {group}"
                session_col_name = self._short_class_column_name(synthetic_idx, "", topic, group)
                session_columns.append(
                    (
                        f"__synthetic__{topic}__{group}",
                        class_label,
                        session_col_name,
                        topic,
                        group,
                    )
                )

        q_first_col = self._find_column(quizzes_df.columns, ["Nombre"])
        q_last_col = self._find_column(quizzes_df.columns, ["Apellido(s)", "Apellidos", "Apellido"])
        if q_first_col is None or q_last_col is None:
            return pd.DataFrame()

        quiz_by_key = {}
        for _, qrow in quizzes_df.iterrows():
            key = self._student_name_key(qrow.get(q_first_col, ""), qrow.get(q_last_col, ""))
            if key and key not in quiz_by_key:
                quiz_by_key[key] = qrow

        a_first_col = self._find_column(attendance_df.columns, ["Nombre"])
        a_last_col = self._find_column(attendance_df.columns, ["Apellido(s)", "Apellidos", "Apellido"])
        a_id_col = self._find_column(attendance_df.columns, ["Número de ID", "Nmero de ID", "ID", "ID de estudiante"])

        rows: List[Dict[str, object]] = []
        for _, arow in attendance_df.iterrows():
            key = self._student_name_key(arow.get(a_first_col, ""), arow.get(a_last_col, ""))
            qrow = quiz_by_key.get(key)
            student_id_val = "" if a_id_col is None else normalize_id(arow.get(a_id_col, ""))
            student_first_name = "" if a_first_col is None else str(arow.get(a_first_col, "")).strip()
            student_last_name = "" if a_last_col is None else str(arow.get(a_last_col, "")).strip()
            row_out: Dict[str, object] = {
                "ID_Alumno": student_id_val,
                "Nombre": student_first_name,
                "Apellido(s)": student_last_name,
            }

            topic_has_presence: Dict[str, bool] = {}
            for col, _, _, topic, _ in session_columns:
                if not topic:
                    continue
                if str(col).startswith("__synthetic__"):
                    topic_has_presence[topic] = True
                    continue
                att_value = arow.get(col, "")
                if self._is_present_value(att_value):
                    topic_has_presence[topic] = True
                elif topic not in topic_has_presence:
                    topic_has_presence[topic] = False

            justified_labels: Set[str] = set()
            for lookup_key in self._student_lookup_keys(student_id_val, student_first_name, student_last_name):
                justified_labels.update(justified_classes_by_student.get(lookup_key, set()))
            full_justified = "__ALL_ABSENCES__" in justified_labels

            attendance_state_by_label: Dict[str, str] = {}
            topic_best_score: Dict[str, float] = {}
            expected_topics = sorted({t for _, _, _, t, _ in session_columns if t})

            for col, class_label, session_col_name, topic, _group in session_columns:
                att_value = arow.get(col, "")
                attended_by_topic = bool(topic) and topic_has_presence.get(topic, False)

                if str(col).startswith("__synthetic__"):
                    attendance_state = "asiste"
                elif self._is_present_value(att_value):
                    attendance_state = "asiste"
                elif attended_by_topic:
                    attendance_state = "asiste_por_tema"
                elif self._is_absence_value(att_value):
                    attendance_state = "falta"
                else:
                    attendance_state = "dudosa"
                attendance_state_by_label[class_label] = attendance_state

                quiz_topic_scores = []
                if qrow is not None and topic:
                    for g in current_settings().group_names:
                        qcol = quiz_cols.get((topic, g))
                        if not qcol:
                            continue
                        score = parse_decimal(qrow.get(qcol, ""))
                        if score is not None:
                            quiz_topic_scores.append(score)

                topic_max = max(quiz_topic_scores) if quiz_topic_scores else None
                if topic and topic_max is not None:
                    prev = topic_best_score.get(topic)
                    if prev is None or topic_max > prev:
                        topic_best_score[topic] = topic_max

                row_out[f"{session_col_name}__Asistencia"] = attendance_state
                row_out[f"{session_col_name}__Quiz_Nota_Tema_Max"] = topic_max

            attended_topics = {t for t, present in topic_has_presence.items() if present}
            row_out["Num_Temas_Asistidos"] = len(attended_topics)

            attendance_ok = True
            attendance_missing_labels: List[str] = []
            for class_label, state in attendance_state_by_label.items():
                if state in {"asiste", "asiste_por_tema"}:
                    continue
                if full_justified:
                    continue
                if class_label in justified_labels:
                    continue
                attendance_ok = False
                attendance_missing_labels.append(class_label)

            all_topics = expected_topics
            quiz_ok = bool(all_topics) and all(
                (topic_best_score.get(t) is not None and float(topic_best_score[t]) >= self.min_quiz_grade)
                for t in all_topics
            )
            quiz_fail_topics: List[str] = []
            for topic in all_topics:
                score = topic_best_score.get(topic)
                if score is None or float(score) < self.min_quiz_grade:
                    quiz_fail_topics.append(topic)

            reasons: List[str] = []
            if not attendance_ok:
                reasons.append("faltas_no_justificadas")
                if attendance_missing_labels:
                    reasons.append(f"clase_pendiente:{attendance_missing_labels[0]}")
            if not bool(all_topics):
                reasons.append("sin_notas_cuestionarios")
            elif quiz_fail_topics:
                reasons.append("nota_baja_en_temas:" + "|".join(quiz_fail_topics))

            row_out["Tiene_Punto_Adicional_Teoria"] = "si" if (attendance_ok and quiz_ok) else "no"
            row_out["Motivo_No_Punto"] = "" if row_out["Tiene_Punto_Adicional_Teoria"] == "si" else " ; ".join(reasons)
            rows.append(row_out)

        return pd.DataFrame(rows)

    def _build_extreme_justified_absences_df(
        self,
        summary_df: pd.DataFrame,
        attendance_quiz_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if self.justification_mode != "extremo":
            return pd.DataFrame()
        if summary_df.empty or attendance_quiz_df.empty:
            return pd.DataFrame()

        sender_keys: Set[str] = set()
        sender_ids: Set[str] = set()
        sender_name_norms: Set[str] = set()
        sender_info: Dict[str, Dict[str, str]] = {}
        for _, row in summary_df.iterrows():
            student_id = normalize_id(row.get("ID_Alumno", ""))
            student_name = str(row.get("Alumno_Matcheado", "")).strip()
            if not student_name or row.get("Cuenta_Para_Justificar") != "si":
                continue
            student_name_norm = self._normalize(student_name)
            key = f"{student_id}|{student_name_norm}"
            sender_keys.add(key)
            if student_id:
                sender_ids.add(student_id)
            if student_name_norm:
                sender_name_norms.add(student_name_norm)
            if key not in sender_info:
                sender_info[key] = {
                    "Remitente_Raw": str(row.get("Remitente_Raw", "")).strip(),
                    "Remitente_Nombre": str(row.get("Remitente_Nombre", "")).strip(),
                    "Remitente_Email": str(row.get("Remitente_Email", "")).strip(),
                }

        rows: List[Dict[str, object]] = []
        base_cols = ["ID_Alumno", "Nombre", "Apellido(s)"]
        if any(c not in attendance_quiz_df.columns for c in base_cols):
            return pd.DataFrame()

        attendance_cols = [c for c in attendance_quiz_df.columns if str(c).endswith("__Asistencia")]
        for _, row in attendance_quiz_df.iterrows():
            student_id = normalize_id(row.get("ID_Alumno", ""))
            full_name = f"{str(row.get('Nombre', '')).strip()} {str(row.get('Apellido(s)', '')).strip()}".strip()
            full_name_norm = self._normalize(full_name)
            key = f"{student_id}|{full_name_norm}"
            if not (
                key in sender_keys
                or (student_id and student_id in sender_ids)
                or (full_name_norm and full_name_norm in sender_name_norms)
            ):
                continue

            sender = sender_info.get(key, {})
            for col in attendance_cols:
                state = str(row.get(col, "")).strip().lower()
                if state not in {"falta", "dudosa"}:
                    continue
                rows.append(
                    {
                        "ID_Alumno": student_id,
                        "Alumno_Matcheado": full_name,
                        "Remitente_Raw": sender.get("Remitente_Raw", ""),
                        "Remitente_Nombre": sender.get("Remitente_Nombre", ""),
                        "Remitente_Email": sender.get("Remitente_Email", ""),
                        "Clase_Columna": str(col).replace("__Asistencia", ""),
                        "Estado_Original": state,
                        "Justificada_Por_Modo_Extremo": "si",
                    }
                )

        return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)

    def analyze(self) -> AbsenceJustificationResult:
        enrollment_df = self._load_enrollment()
        attendance_df, date_cols, _, _, attendance_id_col = self._build_attendance_lookup()
        just_df = pd.read_excel(self.justifications_xlsx_path, sheet_name=self.justifications_sheet)

        if self.sender_col not in just_df.columns:
            raise ValueError(f"Justifications file must include column '{self.sender_col}'.")

        attendance_overview_df = self._build_attendance_overview(
            enrollment_df=enrollment_df,
            attendance_df=attendance_df,
            date_cols=date_cols,
            attendance_id_col=attendance_id_col,
        )

        summary_rows: List[Dict[str, object]] = []
        detailed_rows: List[Dict[str, object]] = []

        session_map = self._build_sessions_catalog(date_cols)
        session_label_by_col = {
            str(row.get("Fecha_Asistencia_Col", "")): str(row.get("Clase_Label", ""))
            for _, row in session_map.iterrows()
        }

        for _, mail_row in just_df.iterrows():
            sender_raw = str(mail_row.get(self.sender_col, ""))
            sender_name = self._parse_sender_name(sender_raw)
            sender_email = self._parse_sender_email(sender_raw)
            mail_subject = mail_row.get(self.subject_col, "")
            mail_message = mail_row.get(self.message_col, "")
            message_class, message_score, message_reasons = self._classify_justification_text(
                mail_subject,
                mail_message,
            )
            # The structured template, when present, is authoritative: it confirms the student is
            # justifying an absence and provides explicit date/topic/group/subgroup/reason fields.
            structured = self._parse_structured_justification(mail_subject, mail_message)
            if structured:
                message_class = "justifica_falta"
                message_reasons = ("plantilla_estructurada | " + message_reasons).strip(" |")
            structured_cols = {
                "Justif_Fecha": (structured.get("fecha_normalizada") or structured.get("fecha", ""))
                if structured
                else "",
                "Justif_Tema_Practica": structured.get("tema_practica", "") if structured else "",
                "Justif_Grupo": structured.get("grupo", "") if structured else "",
                "Justif_Subgrupo_Practicas": structured.get("subgrupo_practicas", "") if structured else "",
                "Justif_Motivo": structured.get("motivo", "") if structured else "",
            }
            enrollment_match, match_type, match_score, candidate = self._match_sender_to_enrollment(
                sender_name, sender_email, enrollment_df
            )
            # Only an email assigned to a student and not classified as unrelated (a question about
            # the exam, thanks…) justifies absences, in either mode (GRD-6).
            counts = "si" if enrollment_match is not None and message_class != "no_justifica" else "no"
            review_cols = {
                "Cuenta_Para_Justificar": counts,
                "Revisar": "no" if enrollment_match is not None else "si",
                "Candidato_Mas_Parecido": candidate,
            }

            student_name = ""
            student_id = ""
            student_email = ""
            attendance_match = None

            if enrollment_match is not None:
                student_name = str(enrollment_match.get("_full_name", "")).strip()
                id_col = str(enrollment_match.get("_id_col", "")).strip()
                email_col = str(enrollment_match.get("_email_col", "")).strip()
                student_id = normalize_id(enrollment_match.get(id_col, "")) if id_col else ""
                student_email = str(enrollment_match.get(email_col, "")).strip() if email_col else ""

                if student_id and attendance_id_col:
                    att = attendance_df[attendance_df["_id_norm"] == student_id]
                    if not att.empty:
                        attendance_match = att.iloc[0]
                if attendance_match is None:
                    full_norm = str(enrollment_match.get("_full_name_norm", ""))
                    att = attendance_df[attendance_df["_full_name_norm"] == full_norm]
                    if not att.empty:
                        attendance_match = att.iloc[0]

            absences: List[str] = []
            uncertain_dates: List[str] = []

            if attendance_match is not None:
                for date_col in date_cols:
                    value = attendance_match.get(date_col, "")
                    value_text = "" if pd.isna(value) else str(value).strip()
                    col_label = session_label_by_col.get(str(date_col), str(date_col))
                    if self._is_absence_value(value):
                        absences.append(col_label)
                    elif not self._is_present_value(value):
                        uncertain_dates.append(col_label)

                    detailed_rows.append(
                        {
                            "Fecha_Correo": mail_row.get("FECHA", ""),
                            **structured_cols,
                            "Remitente_Raw": sender_raw,
                            "Remitente_Nombre": sender_name,
                            "Remitente_Email": sender_email,
                            "Asunto": mail_row.get("ASUNTO", ""),
                            "ID_Correo": mail_row.get("ID", ""),
                            "Mensaje_Clasificacion": message_class,
                            "Mensaje_Score": message_score,
                            "Mensaje_Motivos": message_reasons,
                            "Alumno_Matcheado": student_name,
                            "ID_Alumno": student_id,
                            "Email_Alumno": student_email,
                            "Tipo_Match": match_type,
                            "Score_Match": round(match_score, 4),
                            **review_cols,
                            "Fecha_Asistencia_Col": str(date_col),
                            "Clase_Label": col_label,
                            "Valor_Asistencia": value_text,
                            "Es_Falta_Clara": "si" if self._is_absence_value(value) else "no",
                            "Es_Dudosa": "si"
                            if (not self._is_present_value(value) and not self._is_absence_value(value))
                            else "no",
                        }
                    )
            else:
                detailed_rows.append(
                    {
                        "Fecha_Correo": mail_row.get("FECHA", ""),
                        **structured_cols,
                        "Remitente_Raw": sender_raw,
                        "Remitente_Nombre": sender_name,
                        "Remitente_Email": sender_email,
                        "Asunto": mail_row.get("ASUNTO", ""),
                        "ID_Correo": mail_row.get("ID", ""),
                        "Mensaje_Clasificacion": message_class,
                        "Mensaje_Score": message_score,
                        "Mensaje_Motivos": message_reasons,
                        "Alumno_Matcheado": "",
                        "ID_Alumno": "",
                        "Email_Alumno": "",
                        "Tipo_Match": match_type,
                        "Score_Match": round(match_score, 4),
                        **review_cols,
                        "Fecha_Asistencia_Col": "",
                        "Clase_Label": "",
                        "Valor_Asistencia": "",
                        "Es_Falta_Clara": "no",
                        "Es_Dudosa": "si",
                    }
                )

            summary_rows.append(
                {
                    "Fecha_Correo": mail_row.get("FECHA", ""),
                    **structured_cols,
                    "Remitente_Raw": sender_raw,
                    "Remitente_Nombre": sender_name,
                    "Remitente_Email": sender_email,
                    "Asunto": mail_row.get("ASUNTO", ""),
                    "ID_Correo": mail_row.get("ID", ""),
                    "Mensaje_Clasificacion": message_class,
                    "Mensaje_Score": message_score,
                    "Mensaje_Motivos": message_reasons,
                    "Alumno_Matcheado": student_name,
                    "ID_Alumno": student_id,
                    "Email_Alumno": student_email,
                    "Tipo_Match": match_type,
                    "Score_Match": round(match_score, 4),
                    **review_cols,
                    "Tiene_Faltas_Claras": "si" if absences else "no",
                    "Num_Faltas_Claras": len(absences),
                    "Fechas_Faltas_Claras": " | ".join(absences),
                    "Num_Fechas_Dudosas": len(uncertain_dates),
                    "Fechas_Dudosas": " | ".join(uncertain_dates),
                }
            )

        summary_df = pd.DataFrame(summary_rows)
        detailed_df = pd.DataFrame(detailed_rows)

        overview_by_name = {str(row.get("Alumno", "")).strip(): row for _, row in attendance_overview_df.iterrows()}

        sender_check_rows: List[Dict[str, object]] = []
        for _, row in summary_df.iterrows():
            matched_name = str(row.get("Alumno_Matcheado", "")).strip()
            ov = overview_by_name.get(matched_name)
            if ov is not None:
                class_absences: List[str] = []
                for col_name, col_val in ov.items():
                    col_name_str = str(col_name)
                    if not re.match(r"^C\d{2}_", col_name_str):
                        continue
                    if str(col_val).strip().lower() == "falta":
                        class_absences.append(col_name_str)
                num_faltas = len(class_absences)
                clases_faltadas = " | ".join(class_absences)
            else:
                num_faltas = int(row.get("Num_Faltas_Claras", 0) or 0)
                clases_faltadas = str(row.get("Fechas_Faltas_Claras", "")).strip()

            sender_check_rows.append(
                {
                    "Fecha_Correo": row.get("Fecha_Correo", ""),
                    "Remitente_Raw": row.get("Remitente_Raw", ""),
                    "Remitente_Nombre": row.get("Remitente_Nombre", ""),
                    "Remitente_Email": row.get("Remitente_Email", ""),
                    "Alumno_Matcheado": matched_name,
                    "ID_Alumno": row.get("ID_Alumno", ""),
                    "Tipo_Match": row.get("Tipo_Match", ""),
                    "Score_Match": row.get("Score_Match", ""),
                    "Mensaje_Clasificacion": row.get("Mensaje_Clasificacion", ""),
                    "Mensaje_Score": row.get("Mensaje_Score", ""),
                    "Tiene_Faltas_Punto1": "si" if num_faltas > 0 else "no",
                    "Num_Faltas_Punto1": num_faltas,
                    "Clases_Faltadas_Punto1": clases_faltadas,
                }
            )

        sender_absence_check_df = pd.DataFrame(sender_check_rows)
        justified_classes_by_student: Dict[str, Set[str]] = {}
        if self.justification_mode == "extremo":
            # Modo extremo: cualquier alumno que haya escrito una justificación (no una consulta o un
            # agradecimiento: Cuenta_Para_Justificar) queda con todas las faltas justificadas.
            for _, row in summary_df.iterrows():
                full_name = str(row.get("Alumno_Matcheado", "")).strip()
                if not full_name or row.get("Cuenta_Para_Justificar") != "si":
                    continue
                student_id = normalize_id(row.get("ID_Alumno", ""))
                first_name = ""
                last_name = ""
                parts = [p for p in full_name.split(" ") if p]
                if parts:
                    first_name = parts[0]
                    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                for lookup_key in self._student_lookup_keys(student_id, first_name, last_name):
                    justified_classes_by_student.setdefault(lookup_key, set()).add("__ALL_ABSENCES__")
        else:
            for _, row in detailed_df.iterrows():
                if str(row.get("Es_Falta_Clara", "")).strip().lower() != "si":
                    continue
                if row.get("Cuenta_Para_Justificar") != "si":
                    continue
                class_label = str(row.get("Clase_Label", "")).strip()
                if not class_label:
                    continue
                student_id = normalize_id(row.get("ID_Alumno", ""))
                full_name = str(row.get("Alumno_Matcheado", "")).strip()
                first_name = ""
                last_name = ""
                parts = [p for p in full_name.split(" ") if p]
                if parts:
                    first_name = parts[0]
                    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                for lookup_key in self._student_lookup_keys(student_id, first_name, last_name):
                    justified_classes_by_student.setdefault(lookup_key, set()).add(class_label)

        attendance_quiz_df = self._build_attendance_with_quizzes_df(
            attendance_df,
            date_cols,
            justified_classes_by_student=justified_classes_by_student,
        )

        extreme_justified_absences_df = self._build_extreme_justified_absences_df(
            summary_df=summary_df,
            attendance_quiz_df=attendance_quiz_df,
        )

        return AbsenceJustificationResult(
            summary_df=summary_df,
            detailed_df=detailed_df,
            attendance_overview_df=attendance_overview_df,
            sender_absence_check_df=sender_absence_check_df,
            attendance_quiz_df=attendance_quiz_df,
            extreme_justified_absences_df=extreme_justified_absences_df,
        )

    def analyze_and_export(
        self,
        summary_output_path: str,
        detailed_output_path: str,
        attendance_overview_output_path: Optional[str] = None,
        sender_absence_check_output_path: Optional[str] = None,
        attendance_quiz_output_path: Optional[str] = None,
        extreme_justified_absences_output_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> AbsenceJustificationResult:
        result = self.analyze()

        # Relative paths go to output_dir; absolute ones are kept.
        summary_output_path = prepare_output_path(summary_output_path, output_dir)
        detailed_output_path = prepare_output_path(detailed_output_path, output_dir)
        if attendance_overview_output_path:
            attendance_overview_output_path = prepare_output_path(attendance_overview_output_path, output_dir)
        if sender_absence_check_output_path:
            sender_absence_check_output_path = prepare_output_path(sender_absence_check_output_path, output_dir)
        if attendance_quiz_output_path:
            attendance_quiz_output_path = prepare_output_path(attendance_quiz_output_path, output_dir)
        if extreme_justified_absences_output_path:
            extreme_justified_absences_output_path = prepare_output_path(
                extreme_justified_absences_output_path, output_dir
            )

        result.summary_df.to_excel(summary_output_path, index=False)
        result.detailed_df.to_excel(detailed_output_path, index=False)

        if attendance_overview_output_path and result.attendance_overview_df is not None:
            result.attendance_overview_df.to_excel(attendance_overview_output_path, index=False)
        if sender_absence_check_output_path and result.sender_absence_check_df is not None:
            result.sender_absence_check_df.to_excel(sender_absence_check_output_path, index=False)
        if (
            attendance_quiz_output_path
            and result.attendance_quiz_df is not None
            and not result.attendance_quiz_df.empty
        ):
            result.attendance_quiz_df.to_excel(attendance_quiz_output_path, index=False)
        if (
            extreme_justified_absences_output_path
            and result.extreme_justified_absences_df is not None
            and not result.extreme_justified_absences_df.empty
        ):
            result.extreme_justified_absences_df.to_excel(extreme_justified_absences_output_path, index=False)

        logger.info(f"OK: justification summary -> {summary_output_path} ({len(result.summary_df)} rows)")
        logger.info(f"OK: justification detail -> {detailed_output_path} ({len(result.detailed_df)} rows)")
        if attendance_overview_output_path and result.attendance_overview_df is not None:
            logger.info(
                f"OK: attendance overview -> {attendance_overview_output_path} ({len(result.attendance_overview_df)} rows)"
            )
        if sender_absence_check_output_path and result.sender_absence_check_df is not None:
            logger.info(
                f"OK: sender absence check -> {sender_absence_check_output_path} ({len(result.sender_absence_check_df)} rows)"
            )
        if attendance_quiz_output_path and result.attendance_quiz_df is not None:
            logger.info(
                f"OK: attendance + quizzes -> {attendance_quiz_output_path} ({len(result.attendance_quiz_df)} rows)"
            )
        if extreme_justified_absences_output_path and result.extreme_justified_absences_df is not None:
            logger.info(
                f"OK: justified absences (extreme mode) -> {extreme_justified_absences_output_path} "
                f"({len(result.extreme_justified_absences_df)} rows)"
            )

        return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross absence justifications with attendance")
    parser.add_argument("--attendance", required=True, help="Attendance XLSX path")
    parser.add_argument("--justifications", required=True, help="Justifications XLSX path")
    parser.add_argument("--enrollment", required=True, help="Merged enrollment XLSX path")
    parser.add_argument("--schedule", default=None, help="Optional schedule XLSX path")
    parser.add_argument("--schedule-sheet", default=0, help="Schedule sheet name or index")
    parser.add_argument("--quizzes", default=None, help="Optional class quizzes XLSX path")
    parser.add_argument("--output-summary", default="justificaciones_resumen.xlsx")
    parser.add_argument("--output-detail", default="justificaciones_detalle.xlsx")
    parser.add_argument("--output-attendance-overview", default="asistencias_resumen_alumnos.xlsx")
    parser.add_argument("--output-sender-check", default="justificaciones_vs_faltas.xlsx")
    parser.add_argument("--output-attendance-quizzes", default="asistencias_con_cuestionarios.xlsx")
    parser.add_argument("--output-extreme-justified-absences", default="faltas_justificadas_modo_extremo.xlsx")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--attendance-header-row", type=int, default=3)
    parser.add_argument("--sender-col", default="REMITENTE")
    parser.add_argument("--justification-mode", default="extremo")
    return parser.parse_args()


def main() -> None:
    log_to_console()
    args = _parse_args()
    manager = AbsenceJustificationManager(
        attendance_xlsx_path=args.attendance,
        justifications_xlsx_path=args.justifications,
        enrollment_xlsx_path=args.enrollment,
        schedule_xlsx_path=args.schedule,
        schedule_sheet=args.schedule_sheet,
        quizzes_xlsx_path=args.quizzes,
        attendance_header_row=args.attendance_header_row,
        sender_col=args.sender_col,
        justification_mode=args.justification_mode,
    )
    manager.analyze_and_export(
        summary_output_path=args.output_summary,
        detailed_output_path=args.output_detail,
        attendance_overview_output_path=args.output_attendance_overview,
        sender_absence_check_output_path=args.output_sender_check,
        attendance_quiz_output_path=args.output_attendance_quizzes,
        extreme_justified_absences_output_path=args.output_extreme_justified_absences,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
