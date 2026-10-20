import difflib
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import pandas as pd

from pyexamgenerator.grading._ids import normalize_id
from pyexamgenerator.grading.data import SharedExamDataStore


# Columnas del fichero de respuestas que pueden identificar al alumno (por orden de prioridad).
_ANSWER_ID_COLUMNS = ("ID_Oficial", "Número de ID", "Numero de ID", "Nmero de ID")
_ANSWER_NAME_COLUMNS = ("Nombre_Alumno_Generado", "Nombre_Oficial", "Nombre_OCR")
# Columnas con el tipo de examen de cada fila (respuestas.xlsx del OCR: Tipo_Examen_Usado es el resuelto).
_ANSWER_TYPE_COLUMNS = ("Tipo_Examen_Usado", "Tipo_Examen", "Tipo")
# Datos del intento de Moodle que se copian si el fichero de respuestas los trae (nunca se inventan).
_ATTEMPT_COLUMNS = ("Estado", "Comenzado", "Finalizado", "Duración")

_INCIDENT_COLUMNS = ["Fila", "Nombre_Leido", "ID_Leido", "Tipo_Examen", "Tipo", "Detalle"]


def _norm_header(text: object) -> str:
    raw = str(text).strip().lower()
    raw = "".join(c for c in unicodedata.normalize("NFD", raw) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", raw)


def _find_header(columns, candidates) -> Optional[str]:
    by_norm = {_norm_header(c): c for c in columns}
    for candidate in candidates:
        found = by_norm.get(_norm_header(candidate))
        if found is not None:
            return found
    return None


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


class ExamGrader:
    """Grades an answers XLSX (one row per student) against Moodle XML answer keys.

    With ``questions_by_exam_type`` (``{tipo: preguntas}``, see
    :meth:`SharedExamDataStore.load_questions_by_exam_type`) each row is graded with the key of its
    own exam type, read from ``exam_type_col`` or from a ``Tipo_Examen_Usado`` / ``Tipo_Examen`` /
    ``Tipo`` column. Rows that cannot be matched to the enrollment, or whose exam type is unknown, are
    skipped and recorded in :attr:`incidents_df` (no row is ever graded with a guessed key).
    """

    def __init__(
        self,
        exam_xml_path: str,
        answers_xlsx_path: str,
        enrollment_xlsx_path: str,
        enrollment_sheet: int = 0,
        last_name_col: str = "Apellido(s)",
        first_name_col: str = "Nombre",
        id_col: str = "Número de ID",
        email_col: str = "Dirección de correo",
        shared_store: Optional[SharedExamDataStore] = None,
        questions_info: Optional[dict] = None,
        enrollment_df: Optional[pd.DataFrame] = None,
        answers_df: Optional[pd.DataFrame] = None,
        questions_by_exam_type: Optional[Dict[str, dict]] = None,
        exam_type_col: Optional[str] = None,
    ) -> None:
        self.exam_xml_path = exam_xml_path
        self.answers_xlsx_path = answers_xlsx_path
        self.enrollment_xlsx_path = enrollment_xlsx_path

        self.enrollment_sheet = enrollment_sheet
        self.last_name_col = last_name_col
        self.first_name_col = first_name_col
        self.id_col = id_col
        self.email_col = email_col
        self.shared_store = shared_store or SharedExamDataStore()
        self.questions_by_exam_type: Dict[str, dict] = dict(questions_by_exam_type or {})
        self.exam_type_col = exam_type_col

        if questions_info is not None:
            self.questions_info = questions_info
        elif self.questions_by_exam_type and not exam_xml_path:
            self.questions_info = next(iter(self.questions_by_exam_type.values()))
        else:
            self.questions_info = self._parse_moodle_xml()
        self._validate_enrollment_columns(enrollment_df)
        self.enrollment_df = enrollment_df if enrollment_df is not None else self._load_enrollment()
        self.answers_df = answers_df if answers_df is not None else self.shared_store.load_answers_excel(self.answers_xlsx_path)
        # Filas no corregidas (alumno no encontrado, tipo desconocido...), rellenado por grade_and_export.
        self.incidents_df = pd.DataFrame(columns=_INCIDENT_COLUMNS)

    def _parse_moodle_xml(self):
        return self.shared_store.load_questions_xml(self.exam_xml_path)

    def _validate_enrollment_columns(self, enrollment_df: Optional[pd.DataFrame]) -> None:
        """Comprueba que la matrícula tiene las columnas configuradas antes de corregir nada."""
        if enrollment_df is None:
            enrollment_df = self.shared_store.load_enrollment(
                xlsx_path=self.enrollment_xlsx_path, sheet_name=self.enrollment_sheet,
            )
        required = [self.last_name_col, self.first_name_col, self.id_col, self.email_col]
        missing = [col for col in required if col not in enrollment_df.columns]
        if missing:
            available = ", ".join(str(c) for c in enrollment_df.columns)
            raise ValueError(
                f"Faltan columnas en la matrícula '{self.enrollment_xlsx_path}': "
                f"{', '.join(repr(c) for c in missing)}. Columnas disponibles: {available}."
            )

    def _load_enrollment(self):
        return self.shared_store.load_enrollment(
            xlsx_path=self.enrollment_xlsx_path,
            sheet_name=self.enrollment_sheet,
            first_name_col=self.first_name_col,
            last_name_col=self.last_name_col,
            with_lookup_name=True,
        )

    def _match_student(self, input_name):
        name_list = self.enrollment_df["Lookup_Name"].tolist()
        cleaned_name = str(input_name).strip().lower()
        matches = difflib.get_close_matches(cleaned_name, name_list, n=1, cutoff=0.6)
        if matches:
            return self.enrollment_df[self.enrollment_df["Lookup_Name"] == matches[0]].iloc[0]
        return None

    def _match_student_by_id(self, student_id: str) -> Optional[pd.Series]:
        """Coincidencia exacta por ID normalizado (``11111111.0`` == ``11111111``); None si no hay una única."""
        if not student_id or self.id_col not in self.enrollment_df.columns:
            return None
        ids = self.enrollment_df[self.id_col].map(normalize_id)
        matches = self.enrollment_df[ids == student_id]
        if len(matches) != 1:
            return None
        return matches.iloc[0]

    def _row_identity(self, row: pd.Series) -> Tuple[str, str]:
        """Devuelve (nombre leído, ID leído) de una fila del fichero de respuestas."""
        id_col = _find_header(row.index, _ANSWER_ID_COLUMNS + (self.id_col,))
        student_id = normalize_id(row.get(id_col, "")) if id_col else ""
        name = ""
        for candidate in _ANSWER_NAME_COLUMNS:
            if candidate in row.index:
                name = _cell_text(row.get(candidate, ""))
                if name:
                    break
        if not name and len(row.index) > 0:
            # Formato histórico: el nombre en la primera columna.
            name = _cell_text(row.iloc[0])
        return name, student_id

    def _resolve_type_column(self) -> Optional[str]:
        columns = list(self.answers_df.columns)
        if self.exam_type_col:
            found = _find_header(columns, [self.exam_type_col])
            if found is None:
                raise ValueError(
                    f"El fichero de respuestas '{self.answers_xlsx_path}' no tiene la columna de tipo "
                    f"de examen '{self.exam_type_col}'."
                )
            return found
        return _find_header(columns, _ANSWER_TYPE_COLUMNS)

    def _questions_for_row(self, row: pd.Series, type_col: Optional[str]) -> Tuple[Optional[dict], str]:
        """Devuelve (preguntas, tipo) para la fila; preguntas=None si su tipo no está cargado."""
        if not self.questions_by_exam_type:
            return self.questions_info, ""
        if len(self.questions_by_exam_type) == 1:
            only_type = next(iter(self.questions_by_exam_type))
            return self.questions_by_exam_type[only_type], only_type
        raw_type = _cell_text(row.get(type_col, "")).upper() if type_col else ""
        return self.questions_by_exam_type.get(raw_type), raw_type

    def grade_and_export(self, output_path: str) -> pd.DataFrame:
        by_type = len(self.questions_by_exam_type) > 1
        type_col = self._resolve_type_column() if by_type or self.exam_type_col else None
        if by_type and type_col is None:
            raise ValueError(
                f"Hay {len(self.questions_by_exam_type)} plantillas XML cargadas "
                f"(tipos {', '.join(sorted(self.questions_by_exam_type))}) pero el fichero de respuestas "
                f"'{self.answers_xlsx_path}' no tiene columna de tipo de examen "
                f"({' / '.join(_ANSWER_TYPE_COLUMNS)}). Añade esa columna o carga solo la plantilla "
                "del tipo que corresponde a estas respuestas."
            )

        attempt_cols = {col: _find_header(self.answers_df.columns, [col]) for col in _ATTEMPT_COLUMNS}
        result_rows = []
        incidents: List[Dict[str, object]] = []

        for row_number, (_, row) in enumerate(self.answers_df.iterrows(), start=2):
            generated_name, read_id = self._row_identity(row)
            questions, exam_type = self._questions_for_row(row, type_col)
            if questions is None:
                incidents.append({
                    "Fila": row_number, "Nombre_Leido": generated_name, "ID_Leido": read_id,
                    "Tipo_Examen": exam_type, "Tipo": "TIPO_EXAMEN_DESCONOCIDO",
                    "Detalle": (
                        f"Tipo de examen '{exam_type or '-'}' no disponible "
                        f"(tipos cargados: {', '.join(sorted(self.questions_by_exam_type))}). Fila no corregida."
                    ),
                })
                print(f"Warning: unknown exam type '{exam_type}' for '{generated_name}', row skipped.")
                continue

            official_student = self._match_student_by_id(read_id)
            if official_student is None:
                official_student = self._match_student(generated_name)

            if official_student is None:
                incidents.append({
                    "Fila": row_number, "Nombre_Leido": generated_name, "ID_Leido": read_id,
                    "Tipo_Examen": exam_type, "Tipo": "ALUMNO_NO_ENCONTRADO",
                    "Detalle": "No se encontró el alumno en la matrícula (ni por ID ni por nombre). Fila no corregida.",
                })
                print(f"Warning: could not match student '{generated_name}', row skipped.")
                continue

            question_count = len(questions)
            points_per_question = 10.0 / question_count
            points_str = f"{points_per_question:.2f}".replace(".", ",")

            student_result = {
                "Apellido(s)": official_student[self.last_name_col],
                "Nombre": official_student[self.first_name_col],
                "Número de ID": normalize_id(official_student[self.id_col]),
                "Dirección de correo": official_student[self.email_col],
            }
            # Datos del intento: solo si vienen en el fichero de respuestas (no se inventan fechas).
            for col, source_col in attempt_cols.items():
                student_result[col] = _cell_text(row.get(source_col, "")) if source_col else ""
            if not student_result["Estado"]:
                student_result["Estado"] = "Finalizado"
            if by_type:
                student_result["Tipo_Examen"] = exam_type

            total_score = 0.0
            per_question_scores = {}

            for question_name, answer_map in questions.items():
                question_num = int(re.search(r"\d+", question_name).group())
                output_col = f"P. {question_num} /{points_str}"

                student_answer = None
                for candidate in (question_name, str(question_num), question_num):
                    if candidate in row.index:
                        student_answer = row[candidate]
                        break

                if student_answer is None or pd.isna(student_answer) or str(student_answer).strip() == "":
                    per_question_scores[output_col] = "-"
                    continue

                answer_clean = str(student_answer).strip().lower()
                if answer_clean in {"-", "nc"}:
                    per_question_scores[output_col] = "-"
                    continue
                fraction = answer_map.get(answer_clean, 0.0)
                points = points_per_question * fraction
                total_score += points
                per_question_scores[output_col] = f"{points:.2f}".replace(".", ",")

            total_score = max(0.0, total_score)
            student_result["Calificación/10,00"] = f"{total_score:.2f}".replace(".", ",")
            student_result.update(per_question_scores)
            result_rows.append(student_result)

        self.incidents_df = pd.DataFrame(incidents, columns=_INCIDENT_COLUMNS)
        if not result_rows:
            examples = "; ".join(
                f"fila {inc['Fila']}: {inc['Nombre_Leido'] or inc['ID_Leido'] or '-'} ({inc['Tipo']})"
                for inc in incidents[:5]
            )
            raise ValueError(
                f"No se ha podido corregir ninguna fila de '{self.answers_xlsx_path}' "
                f"({len(incidents)} fila(s) sin corregir). "
                + (f"Ejemplos: {examples}. " if examples else "")
                + "Comprueba que el fichero tiene una columna con el nombre o el ID del alumno "
                "(Nombre_Alumno_Generado, Nombre_Oficial, ID_Oficial o Número de ID)."
            )

        final_df = pd.DataFrame(result_rows)
        final_df.to_excel(output_path, index=False)
        if incidents:
            print(f"Warning: {len(incidents)} row(s) were not graded (see incidents).")
        print(f"OK: grading completed. Output saved to: {output_path}")
        return final_df


# Backward-compatible alias
CorrectorExamenes = ExamGrader
