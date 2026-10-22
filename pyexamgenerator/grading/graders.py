import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from pyexamgenerator.grading._names import AMBIGUOUS, NameMatch, match_name
from pyexamgenerator.grading._paths import prepare_output_path
from pyexamgenerator.grading.data import SharedExamDataStore

INCIDENT_COLUMNS = ["Fila", "Nombre_Escrito", "Tipo", "Severidad", "Detalle", "Candidato", "Score"]


class ExamGrader:
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

        self.questions_info = questions_info if questions_info is not None else self._parse_moodle_xml()
        self.enrollment_df = enrollment_df if enrollment_df is not None else self._load_enrollment()
        self.answers_df = (
            answers_df if answers_df is not None else self.shared_store.load_answers_excel(self.answers_xlsx_path)
        )

    def _parse_moodle_xml(self):
        return self.shared_store.load_questions_xml(self.exam_xml_path)

    def _load_enrollment(self):
        return self.shared_store.load_enrollment(
            xlsx_path=self.enrollment_xlsx_path,
            sheet_name=self.enrollment_sheet,
            first_name_col=self.first_name_col,
            last_name_col=self.last_name_col,
            with_lookup_name=True,
        )

    def _full_names(self) -> List[str]:
        first = self.enrollment_df[self.first_name_col].astype(str).str.strip()
        last = self.enrollment_df[self.last_name_col].astype(str).str.strip()
        return (first + " " + last).str.strip().tolist()

    def _match_student(self, input_name) -> Tuple[Optional[pd.Series], NameMatch]:
        """The enrolled student for a name of the answers file, only when the match is safe (GRD-6).

        Returns ``(row, match)``; ``row`` is None when the name is not assigned, and the row is then
        reported for review instead of graded: the most similar name (threshold 0.6) used to get the
        grade, also another student's ("Mario" for "María").
        """
        match = match_name(input_name, self._full_names())
        row = self.enrollment_df.iloc[match.position] if match.position is not None else None
        return row, match

    def _unmatched_incident(self, file_row: int, written: str, match: NameMatch) -> Dict[str, object]:
        candidate = self._full_names()[match.candidate] if match.candidate is not None else ""
        if match.kind == AMBIGUOUS:
            kind = "AMBIGUOUS_STUDENT"
            detail = (
                f"Varios alumnos de la matrícula encajan con este nombre (p. ej. «{candidate}»): "
                "escríbelo completo en el fichero de respuestas y vuelve a corregir."
            )
        else:
            kind = "UNMATCHED_STUDENT"
            detail = "No coincide con ningún alumno de la matrícula"
            detail += f": el más parecido es «{candidate}». " if candidate else ". "
            detail += "Corrige el nombre en el fichero de respuestas y vuelve a corregir."
        return {
            "Fila": file_row,
            "Nombre_Escrito": written,
            "Tipo": kind,
            "Severidad": "alta",
            "Detalle": detail + " Esta fila no se ha corregido.",
            "Candidato": candidate,
            "Score": round(match.score, 4),
        }

    def grade_and_export(self, output_path: str, incidents_output_path: Optional[str] = None) -> pd.DataFrame:
        """Grades every row of the answers file and writes the result to ``output_path``.

        A row whose name is not safely matched to one enrolled student is not graded, and two rows
        matched to the same student are both kept; all of them are listed in ``last_incidents_df``
        (and written to ``incidents_output_path`` when given), with the most similar student.
        """
        question_count = len(self.questions_info)
        points_per_question = 10.0 / question_count
        points_str = f"{points_per_question:.2f}".replace(".", ",")

        result_rows = []
        incidents: List[Dict[str, object]] = []
        rows_by_student: Dict[int, List[Tuple[int, str]]] = {}

        for position, (_, row) in enumerate(self.answers_df.iterrows()):
            generated_name = str(row.get("Nombre_Alumno_Generado", row.iloc[0]))
            official_student, match = self._match_student(generated_name)
            file_row = position + 2  # row of the answers workbook (the header is row 1)

            if official_student is None or match.position is None:
                incidents.append(self._unmatched_incident(file_row, generated_name, match))
                continue
            rows_by_student.setdefault(match.position, []).append((file_row, generated_name))

            student_result = {
                "Apellido(s)": official_student[self.last_name_col],
                "Nombre": official_student[self.first_name_col],
                "Número de ID": official_student[self.id_col],
                "Dirección de correo": official_student[self.email_col],
                "Estado": "Finalizado",
                # Same columns as a Moodle export, but the real times of a paper exam are unknown:
                # leave them empty instead of inventing them.
                "Comenzado": "",
                "Finalizado": "",
                "Duración": "",
            }

            total_score = 0.0
            per_question_scores = {}

            for question_name, answer_map in self.questions_info.items():
                question_num = int(re.search(r"\d+", question_name).group())
                output_col = f"P. {question_num} /{points_str}"

                student_answer = None
                for candidate in (question_name, str(question_num), question_num):
                    if candidate in row.index:
                        student_answer = row[candidate]
                        break

                if pd.isna(student_answer) or str(student_answer).strip() == "":
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

        full_names = self._full_names()
        for student, file_rows in rows_by_student.items():
            if len(file_rows) < 2:
                continue
            others = ", ".join(str(r) for r, _ in file_rows)
            for file_row, written in file_rows:
                incidents.append(
                    {
                        "Fila": file_row,
                        "Nombre_Escrito": written,
                        "Tipo": "DUPLICATE_STUDENT",
                        "Severidad": "alta",
                        "Detalle": (
                            f"Las filas {others} se han asignado a «{full_names[student]}»: el resultado tiene "
                            "una fila por cada una. Revisa cuál es la buena."
                        ),
                        "Candidato": full_names[student],
                        "Score": 1.0,
                    }
                )

        final_df = pd.DataFrame(result_rows)
        final_df.to_excel(output_path, index=False)
        print(f"OK: grading completed. Output saved to: {output_path}")

        self.last_incidents_df = pd.DataFrame(incidents, columns=INCIDENT_COLUMNS).sort_values("Fila", kind="stable")
        if incidents_output_path:
            self.last_incidents_df.to_excel(prepare_output_path(incidents_output_path), index=False)
        if incidents:
            print(f"AVISO: {len(incidents)} incidencia(s) al asignar las respuestas a la matrícula.")
        return final_df


# Backward-compatible alias
CorrectorExamenes = ExamGrader
