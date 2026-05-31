from __future__ import annotations

import argparse
import difflib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd


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
        justification_mode: str = "extremo",
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
        self.justification_mode = str(justification_mode or "extremo").strip().lower()

    @staticmethod
    def _normalize(text: object) -> str:
        raw = "" if pd.isna(text) else str(text).strip().lower()
        raw = "".join(c for c in unicodedata.normalize("NFD", raw) if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]", "", raw)

    @classmethod
    def _find_column(cls, columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
        norm_map = {cls._normalize(c): c for c in columns}
        for cand in candidates:
            key = cls._normalize(cand)
            if key in norm_map:
                return norm_map[key]
        return None

    @staticmethod
    def _parse_sender_name(sender: str) -> str:
        text = str(sender or "").strip()
        quoted = re.search(r'"([^"]+)"', text)
        if quoted:
            text = quoted.group(1)
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
        return (match.group(0).strip().lower() if match else "")

    @staticmethod
    def _is_attendance_date_column(column_name: str) -> bool:
        text = str(column_name)
        return "2026" in text and "Todos los estudiantes" in text

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
        # Sesiones teóricas sin el literal "tema" que deben contar como tema.
        if "ley3195" in normalized:
            return "LPRL"
        if "rd3997" in normalized:
            return "RSP"
        match = re.search(r"tema0?(\d{1,2})", normalized)
        if match:
            return f"TEMA {int(match.group(1)):02d}"
        return raw

    @staticmethod
    def _group_from_text(text: object) -> str:
        normalized = AbsenceJustificationManager._normalize(text)
        if "gitigiegiei" in normalized:
            return "GITI-GIE-GIEI"
        if "gim" in normalized:
            return "GIM"
        return ""

    @staticmethod
    def _student_name_key(first_name: object, last_name: object) -> str:
        return f"{AbsenceJustificationManager._normalize(first_name)}_{AbsenceJustificationManager._normalize(last_name)}"

    @staticmethod
    def _student_lookup_keys(student_id: object, first_name: object, last_name: object) -> List[str]:
        keys: List[str] = []
        sid = str(student_id or "").strip()
        if sid:
            keys.append(f"id:{sid}")
        sname = AbsenceJustificationManager._student_name_key(first_name, last_name)
        if sname and sname != "_":
            keys.append(f"name:{sname}")
        return keys

    @staticmethod
    def _short_topic_code(topic: object) -> str:
        text = str(topic or "").strip().upper()
        match = re.match(r"^TEMA\s+(\d{1,2})$", text)
        if match:
            return f"T{int(match.group(1)):02d}"
        if text in {"LPRL", "RSP"}:
            return text
        return "TOP"

    @staticmethod
    def _short_group_code(group: object) -> str:
        text = str(group or "").strip().upper()
        if text == "GIM":
            return "GIM"
        if text == "GITI-GIE-GIEI":
            return "GGG"
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
        for col in quizzes_df.columns:
            match = re.match(r"^Cuestionario:Cuestionario\s+(.+?)\s+-\s+(GIM|GITI-GIE-GIEI)\s+\(Real\)$", str(col))
            if not match:
                continue
            topic = AbsenceJustificationManager._topic_from_text(match.group(1))
            group = AbsenceJustificationManager._group_from_text(match.group(2))
            if topic and group:
                out[(topic, group)] = str(col)
        return out

    @staticmethod
    def _parse_grade(value: object) -> Optional[float]:
        if pd.isna(value):
            return None
        text = str(value).strip()
        if text in {"", "-"}:
            return None
        text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _classify_justification_text(subject: object, message: object) -> Tuple[str, int, str]:
        text = f"{'' if pd.isna(subject) else str(subject)}\n{'' if pd.isna(message) else str(message)}".lower()
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return "no_justifica", 0, "sin_texto"

        positive_patterns = [
            r"justific", r"justificante", r"adjunt", r"certific", r"parte med", r"m[ée]dic",
            r"ausenc", r"falta", r"asisten", r"no pude", r"no he podido", r"motivo", r"permiso",
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
        first_name_col = self._find_column(df.columns, ["Nombre"])
        last_name_col = self._find_column(df.columns, ["Apellido(s)", "Apellidos", "Apellido"])
        email_col = self._find_column(df.columns, ["Dirección de correo", "Direccin de correo", "Correo", "Email"])
        id_col = self._find_column(df.columns, ["Número de ID", "Nmero de ID", "ID"])

        if first_name_col is None or last_name_col is None:
            raise ValueError("Enrollment file must contain first and last name columns.")

        out = df.copy()
        out["_first_name_col"] = first_name_col
        out["_last_name_col"] = last_name_col
        out["_email_col"] = email_col or ""
        out["_id_col"] = id_col or ""
        out["_full_name"] = (out[first_name_col].astype(str).str.strip() + " " + out[last_name_col].astype(str).str.strip()).str.strip()
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
    ) -> Tuple[Optional[pd.Series], str, float]:
        if sender_email:
            email_matches = enrollment_df[enrollment_df["_email_norm"] == sender_email]
            if not email_matches.empty:
                return email_matches.iloc[0], "email", 1.0

        sender_norm = self._normalize(sender_name)
        if not sender_norm:
            return None, "none", 0.0

        names = enrollment_df["_full_name_norm"].tolist()
        best = difflib.get_close_matches(sender_norm, names, n=1, cutoff=0.55)
        if not best:
            return None, "none", 0.0

        match_norm = best[0]
        row = enrollment_df[enrollment_df["_full_name_norm"] == match_norm].iloc[0]
        score = difflib.SequenceMatcher(None, sender_norm, match_norm).ratio()
        return row, "name_fuzzy", float(score)

    def _build_attendance_lookup(self) -> Tuple[pd.DataFrame, List[str], str, str, str]:
        attendance_df = pd.read_excel(self.attendance_xlsx_path, sheet_name=self.attendance_sheet, header=self.attendance_header_row)
        first_name_col = self._find_column(attendance_df.columns, ["Nombre"])
        last_name_col = self._find_column(attendance_df.columns, ["Apellido(s)", "Apellidos", "Apellido"])
        id_col = self._find_column(attendance_df.columns, ["Número de ID", "Nmero de ID", "ID", "ID de estudiante"])

        if first_name_col is None or last_name_col is None:
            raise ValueError("Attendance file must contain first and last name columns.")

        attendance_df["_full_name"] = (
            attendance_df[first_name_col].astype(str).str.strip() + " " + attendance_df[last_name_col].astype(str).str.strip()
        ).str.strip()
        attendance_df["_full_name_norm"] = attendance_df["_full_name"].map(self._normalize)
        attendance_df["_id_norm"] = attendance_df[id_col].astype(str).str.strip() if id_col else ""
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
            title_col = self._find_column(schedule_df.columns, ["Título (EDITABLE)", "Ttulo (EDITABLE)", "Titulo (EDITABLE)"])
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
        topic_by_col = {str(row["Fecha_Asistencia_Col"]): str(row.get("Tema_Clase", "")).strip() for _, row in theory_sessions_df.iterrows()}

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
            student_id = str(erow.get(id_col, "")).strip() if id_col else ""
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

        # Añade LPRL/RSP desde cuestionarios aunque no existan columnas de asistencia para esas fechas.
        existing_topics = {topic for _, _, _, topic, _ in session_columns if topic}
        synthetic_idx = len(session_columns)
        for topic in ["LPRL", "RSP"]:
            if topic in existing_topics:
                continue
            for group in ["GIM", "GITI-GIE-GIEI"]:
                if (topic, group) not in quiz_cols:
                    continue
                synthetic_idx += 1
                class_label = f"SIN_ASISTENCIA_REGISTRADA | {topic} | {group}"
                session_col_name = self._short_class_column_name(synthetic_idx, "", topic, group)
                session_columns.append((
                    f"__synthetic__{topic}__{group}",
                    class_label,
                    session_col_name,
                    topic,
                    group,
                ))

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
            student_id_val = "" if a_id_col is None else str(arow.get(a_id_col, "")).strip()
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

            for col, class_label, session_col_name, topic, group in session_columns:
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

                quiz_grade_group = None
                quiz_col_group = ""
                if qrow is not None and topic and group and "|" not in group:
                    qcol = quiz_cols.get((topic, group))
                    if qcol:
                        quiz_col_group = qcol
                        quiz_grade_group = self._parse_grade(qrow.get(qcol, ""))

                quiz_topic_scores = []
                if qrow is not None and topic:
                    for g in ["GIM", "GITI-GIE-GIEI"]:
                        qcol = quiz_cols.get((topic, g))
                        if not qcol:
                            continue
                        score = self._parse_grade(qrow.get(qcol, ""))
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
            quiz_ok = bool(all_topics) and all((topic_best_score.get(t) is not None and float(topic_best_score[t]) >= 7.5) for t in all_topics)
            quiz_fail_topics: List[str] = []
            for topic in all_topics:
                score = topic_best_score.get(topic)
                if score is None or float(score) < 7.5:
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
            student_id = str(row.get("ID_Alumno", "")).strip()
            student_name = str(row.get("Alumno_Matcheado", "")).strip()
            if not student_name:
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
            student_id = str(row.get("ID_Alumno", "")).strip()
            full_name = f"{str(row.get('Nombre', '')).strip()} {str(row.get('Apellido(s)', '')).strip()}".strip()
            full_name_norm = self._normalize(full_name)
            key = f"{student_id}|{full_name_norm}"
            if not (key in sender_keys or (student_id and student_id in sender_ids) or (full_name_norm and full_name_norm in sender_name_norms)):
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
            message_class, message_score, message_reasons = self._classify_justification_text(
                mail_row.get("ASUNTO", ""),
                mail_row.get("MENSAJE", ""),
            )
            enrollment_match, match_type, match_score = self._match_sender_to_enrollment(sender_name, sender_email, enrollment_df)

            student_name = ""
            student_id = ""
            student_email = ""
            attendance_match = None

            if enrollment_match is not None:
                student_name = str(enrollment_match.get("_full_name", "")).strip()
                id_col = str(enrollment_match.get("_id_col", "")).strip()
                email_col = str(enrollment_match.get("_email_col", "")).strip()
                student_id = str(enrollment_match.get(id_col, "")).strip() if id_col else ""
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
                            "Fecha_Asistencia_Col": str(date_col),
                            "Clase_Label": col_label,
                            "Valor_Asistencia": value_text,
                            "Es_Falta_Clara": "si" if self._is_absence_value(value) else "no",
                            "Es_Dudosa": "si" if (not self._is_present_value(value) and not self._is_absence_value(value)) else "no",
                        }
                    )
            else:
                detailed_rows.append(
                    {
                        "Fecha_Correo": mail_row.get("FECHA", ""),
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
                    "Tiene_Faltas_Claras": "si" if absences else "no",
                    "Num_Faltas_Claras": len(absences),
                    "Fechas_Faltas_Claras": " | ".join(absences),
                    "Num_Fechas_Dudosas": len(uncertain_dates),
                    "Fechas_Dudosas": " | ".join(uncertain_dates),
                }
            )

        summary_df = pd.DataFrame(summary_rows)
        detailed_df = pd.DataFrame(detailed_rows)

        overview_by_name = {
            str(row.get("Alumno", "")).strip(): row
            for _, row in attendance_overview_df.iterrows()
        }

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
            # Modo extremo: cualquier alumno que haya escrito queda con todas las faltas justificadas.
            for _, row in summary_df.iterrows():
                full_name = str(row.get("Alumno_Matcheado", "")).strip()
                if not full_name:
                    continue
                student_id = str(row.get("ID_Alumno", "")).strip()
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
                class_label = str(row.get("Clase_Label", "")).strip()
                if not class_label:
                    continue
                student_id = str(row.get("ID_Alumno", "")).strip()
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

        if output_dir:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            summary_output_path = str(out_dir / Path(summary_output_path).name)
            detailed_output_path = str(out_dir / Path(detailed_output_path).name)
            if attendance_overview_output_path:
                attendance_overview_output_path = str(out_dir / Path(attendance_overview_output_path).name)
            if sender_absence_check_output_path:
                sender_absence_check_output_path = str(out_dir / Path(sender_absence_check_output_path).name)
            if attendance_quiz_output_path:
                attendance_quiz_output_path = str(out_dir / Path(attendance_quiz_output_path).name)
            if extreme_justified_absences_output_path:
                extreme_justified_absences_output_path = str(out_dir / Path(extreme_justified_absences_output_path).name)

        result.summary_df.to_excel(summary_output_path, index=False)
        result.detailed_df.to_excel(detailed_output_path, index=False)

        if attendance_overview_output_path and result.attendance_overview_df is not None:
            result.attendance_overview_df.to_excel(attendance_overview_output_path, index=False)
        if sender_absence_check_output_path and result.sender_absence_check_df is not None:
            result.sender_absence_check_df.to_excel(sender_absence_check_output_path, index=False)
        if attendance_quiz_output_path and result.attendance_quiz_df is not None and not result.attendance_quiz_df.empty:
            result.attendance_quiz_df.to_excel(attendance_quiz_output_path, index=False)
        if (
            extreme_justified_absences_output_path
            and result.extreme_justified_absences_df is not None
            and not result.extreme_justified_absences_df.empty
        ):
            result.extreme_justified_absences_df.to_excel(extreme_justified_absences_output_path, index=False)

        print(f"OK: justification summary -> {summary_output_path} ({len(result.summary_df)} rows)")
        print(f"OK: justification detail -> {detailed_output_path} ({len(result.detailed_df)} rows)")
        if attendance_overview_output_path and result.attendance_overview_df is not None:
            print(f"OK: attendance overview -> {attendance_overview_output_path} ({len(result.attendance_overview_df)} rows)")
        if sender_absence_check_output_path and result.sender_absence_check_df is not None:
            print(f"OK: sender absence check -> {sender_absence_check_output_path} ({len(result.sender_absence_check_df)} rows)")
        if attendance_quiz_output_path and result.attendance_quiz_df is not None:
            print(f"OK: attendance + quizzes -> {attendance_quiz_output_path} ({len(result.attendance_quiz_df)} rows)")
        if extreme_justified_absences_output_path and result.extreme_justified_absences_df is not None:
            print(
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








# PIR bonus calculation

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class PIRSession:
    session_date: date
    topic: str
    group: str
    attendance_col: str


def _strip_accents(text: object) -> str:
    normalized = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalize_text(text: object) -> str:
    return _strip_accents(str(text)).strip().lower()


def _student_key(last_name: object, first_name: object) -> str:
    return re.sub(r"\s+", " ", f"{_normalize_text(first_name)} {_normalize_text(last_name)}").strip()


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
    t = _normalize_text(token)[:3]
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
    normalized = _normalize_text(text)
    if "ley 31_95" in normalized:
        return "LPRL"
    if "rd 39_97" in normalized:
        return "RSP"

    match = re.search(r"tema\s*0?(\d{1,2})", normalized)
    if match:
        return f"TEMA {int(match.group(1)):02d}"
    return None


def _group_from_text(text: object) -> Optional[str]:
    normalized = _normalize_text(text).upper()
    if "GITI-GIE-GIEI" in normalized:
        return "GITI-GIE-GIEI"
    if "GIM" in normalized:
        return "GIM"
    return None


def _parse_grade(value: object) -> Optional[float]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text in {"", "-"}:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
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

    def _build_sessions(self, attendance_df: pd.DataFrame, schedule_df: pd.DataFrame) -> Tuple[List[PIRSession], List[str]]:
        warnings: List[str] = []

        start_date_col = next((c for c in schedule_df.columns if _normalize_text(c) == "fecha de inicio"), None)
        desc_col = next((c for c in schedule_df.columns if _normalize_text(c) in {"descripcion", "descripcin"}), None)
        title_col = next((c for c in schedule_df.columns if "titulo" in _normalize_text(c) and "editable" in _normalize_text(c)), None)

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
        for col in quizzes_df.columns:
            text = str(col)
            match = re.match(r"^Cuestionario:Cuestionario\s+(.+?)\s+-\s+(GIM|GITI-GIE-GIEI)\s+\(Real\)$", text)
            if not match:
                continue
            topic = _topic_from_text(match.group(1))
            group = _group_from_text(match.group(2))
            if topic and group:
                out[(topic, group)] = text
        return out

    @staticmethod
    def _is_present(value: object) -> bool:
        return _normalize_text(value).startswith("p")

    def calculate(self) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        attendance_df = self._load_attendance()
        schedule_df = self._load_schedule()
        quizzes_df = self._load_quizzes()

        sessions, warnings = self._build_sessions(attendance_df, schedule_df)
        quiz_cols = self._extract_quiz_columns(quizzes_df)

        topics = sorted({s.topic for s in sessions})
        groups = ["GIM", "GITI-GIE-GIEI"]

        if not {"Apellido(s)", "Nombre"}.issubset(set(attendance_df.columns)):
            raise ValueError("Attendance file must include 'Apellido(s)' and 'Nombre'.")
        if not {"Apellido(s)", "Nombre"}.issubset(set(quizzes_df.columns)):
            raise ValueError("Quizzes file must include 'Apellido(s)' and 'Nombre'.")

        attendance_work = attendance_df.copy()
        attendance_work["_key"] = attendance_work.apply(lambda r: _student_key(r.get("Apellido(s)"), r.get("Nombre")), axis=1)

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
                        score = _parse_grade(quiz_row.get(col))
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

            bonus_applies = attended_all_topics and completed_all_valid_quizzes and meets_min_grades
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
        bonus_map = {
            row["_key"]: float(row.get("PIR_Bonus", 0.0) or 0.0)
            for _, row in bonus_work.iterrows()
        }

        def parse_theory_grade(value: object) -> float:
            parsed = _parse_grade(value)
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


def _normalize_bonus_text(text: object) -> str:
    raw = "" if pd.isna(text) else str(text).strip().lower()
    raw = "".join(c for c in unicodedata.normalize("NFD", raw) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", raw)


def _normalize_bonus_id(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def _parse_bonus_grade(value: object) -> Optional[float]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text in {"", "-"}:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _find_theory_grade_columns(theory_df: pd.DataFrame, theory_grade_col: Optional[str]) -> List[str]:
    columns = [str(c) for c in theory_df.columns]
    if theory_grade_col and theory_grade_col in theory_df.columns:
        return [theory_grade_col]

    normalized = {_normalize_bonus_text(c): c for c in columns}
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
    """Apply the PIR ``+1`` theory bonus, retaining inputs and outputs as attributes.

    Inputs (``theory`` and ``attendance_quiz``) may be either a path to an Excel file
    or an in-memory DataFrame, so the step can be chained without writing intermediate
    files. After :meth:`apply` the instance exposes:
      - ``theory_df`` / ``bonus_df``: the loaded inputs.
      - ``grade_columns``: the theory grade column(s) that received the bonus.
      - ``result_df``: the theory table with bonus columns added.
      - ``output_path``: where the result was written (filled by :meth:`apply`/:meth:`export`).
    """

    def __init__(
        self,
        theory: object,
        attendance_quiz: object,
        theory_grade_col: Optional[str] = None,
        cap_to_10: bool = True,
    ) -> None:
        self.theory = theory
        self.attendance_quiz = attendance_quiz
        self.theory_grade_col = theory_grade_col
        self.cap_to_10 = cap_to_10
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
        name_key = _normalize_bonus_text(f"{row.get('Nombre', '')} {row.get('Apellido(s)', '')}")
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
    out_df["Punto_Adicional_Cuestionarios"] = 0
    out_df["Nota_Original_Teoria"] = pd.NA
    out_df["Nota_Final_Teoria"] = pd.NA
    out_df["Incremento_Aplicado"] = 0.0
    out_df["Motivo_No_Incremento"] = ""

    id_candidates = ["Número de ID", "Numero de ID", "Nombre de usuario", "ID_Alumno", "ID_Oficial", "ID"]
    for idx, row in out_df.iterrows():
        id_keys = [_normalize_bonus_id(row.get(col, "")) for col in id_candidates if col in out_df.columns]
        name_key = _normalize_bonus_text(f"{row.get('Nombre', '')} {row.get('Apellido(s)', '')}")

        has_bonus = 0
        no_bonus_reason = "sin_regla_punto"
        for key in id_keys:
            if key and key in bonus_by_id:
                has_bonus, no_bonus_reason = bonus_by_id[key]
                break
        else:
            if name_key and name_key in bonus_by_name:
                has_bonus, no_bonus_reason = bonus_by_name[name_key]

        original_values = {
            col: _parse_bonus_grade(row.get(col, ""))
            for col in grade_columns
        }
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
            updated = original + 1.0
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
) -> pd.DataFrame:
    """Apply PIR +1 bonus to a theory workbook using attendance+quiz audit output.

    Thin functional wrapper kept for backward compatibility; delegates to
    :class:`TheoryBonusApplier`.
    """
    applier = TheoryBonusApplier(
        theory=theory_xlsx_path,
        attendance_quiz=attendance_quiz_xlsx_path,
        theory_grade_col=theory_grade_col,
        cap_to_10=cap_to_10,
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


def _compute_theory_topic_reports(source_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    topics = ["LPRL", "RSP"] + [f"T{idx:02d}" for idx in range(2, 12)]

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
                    parsed = _parse_bonus_grade(row.get(col, ""))
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

