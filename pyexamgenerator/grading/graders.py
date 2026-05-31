import difflib
import re
from typing import Optional

import pandas as pd

from pyexamgenerator.grading.data import SharedExamDataStore


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
        self.answers_df = answers_df if answers_df is not None else self.shared_store.load_answers_excel(self.answers_xlsx_path)

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

    def _match_student(self, input_name):
        name_list = self.enrollment_df["Lookup_Name"].tolist()
        cleaned_name = str(input_name).strip().lower()
        matches = difflib.get_close_matches(cleaned_name, name_list, n=1, cutoff=0.6)
        if matches:
            return self.enrollment_df[self.enrollment_df["Lookup_Name"] == matches[0]].iloc[0]
        return None

    def grade_and_export(self, output_path: str) -> pd.DataFrame:
        question_count = len(self.questions_info)
        points_per_question = 10.0 / question_count
        points_str = f"{points_per_question:.2f}".replace(".", ",")

        result_rows = []

        for _, row in self.answers_df.iterrows():
            generated_name = str(row.get("Nombre_Alumno_Generado", row.iloc[0]))
            official_student = self._match_student(generated_name)

            if official_student is None:
                print(f"Warning: could not match student '{generated_name}', row skipped.")
                continue

            student_result = {
                "Apellido(s)": official_student[self.last_name_col],
                "Nombre": official_student[self.first_name_col],
                "Número de ID": official_student[self.id_col],
                "Dirección de correo": official_student[self.email_col],
                "Estado": "Finalizado",
                "Comenzado": "20 de abril de 2026 17:05",
                "Finalizado": "20 de abril de 2026 17:09",
                "Duración": "4 minutos 00 segundos",
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

        final_df = pd.DataFrame(result_rows)
        final_df.to_excel(output_path, index=False)
        print(f"OK: grading completed. Output saved to: {output_path}")
        return final_df


# Backward-compatible alias
CorrectorExamenes = ExamGrader

