# pyexamgenerator: A tool for generating exams from PDF files using AI.
# Copyright (C) 2024 Daniel Sánchez-García

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from docx import Document
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, ns

import pandas as pd
import random
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import re
import os
from typing import Optional, Tuple, Dict  # Importing Optional and Tuple for type hinting


# Define the WordML namespace used for direct XML manipulation in docx files.
WML_NAMESPACE = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

class NoAcceptableQuestionsError(Exception):
    """Excepción personalizada para cuando no se encuentran preguntas aceptables."""
    pass

class ExamGenerator:
    """
    A class to generate exams from a question bank stored in an Excel file.
    It can create multiple versions of an exam, shuffle questions and answers,
    and export to various formats like DOCX and Moodle XML.
    """

    def __init__(self):
        """
        Initializes the pyexamgenerator instance.
        """
        # Added self.df attribute to persist the DataFrame between calls.
        self.df = None
        # Records (one per generated exam type) with the paths of every output file, so a grading
        # session can later be resumed directly from the generated exams.
        self.generated_exams = []

    @staticmethod
    def suggest_moodle_config(
        exam: Optional[str] = None,
        exam_type: Optional[str] = None,
        group: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Dict[str, str]:
        """Suggests Moodle quiz names / category so the exported grade columns are identifiable.

        The grading subpackage parses two column conventions (the prefix ``Cuestionario:`` is added by
        Moodle itself when exporting grades):
          - per exam type: ``Cuestionario:<nombre>_Tipo <1A> (Real)``
          - per class quiz (topic + group): ``Cuestionario:Cuestionario <tema> - <GIM|GITI-GIE-GIEI> (Real)``

        Args:
            exam: Exam name (e.g. 'Parcial 1').
            exam_type: Exam type/version in the form ``<n><LETTER>`` (e.g. '1A').
            group: Macro-group (e.g. 'GIM', 'GITI-GIE-GIEI').
            topic: Topic name for a class quiz (e.g. 'Tema 03').

        Returns:
            Dict[str, str]: Suggested names and the grade columns they will produce in Moodle.
        """
        suggestions: Dict[str, str] = {}

        if exam_type:
            base_parts = [p for p in [group, exam or "Examen"] if p]
            base = " ".join(str(p).strip() for p in base_parts).strip()
            quiz_name = f"{base}_Tipo {str(exam_type).strip().upper()} (Real)"
            suggestions["exam_quiz_name"] = quiz_name
            suggestions["exam_grade_column"] = f"Cuestionario:{quiz_name}"

        if topic and group:
            class_quiz_name = f"Cuestionario {str(topic).strip()} - {str(group).strip()} (Real)"
            suggestions["class_quiz_name"] = class_quiz_name
            suggestions["class_grade_column"] = f"Cuestionario:{class_quiz_name}"

        category = "$course$/top/Examen"
        if exam:
            category += f" {exam} -"
        if exam_type:
            category += f" {exam_type} -"
        suggestions["category_name"] = category.rstrip(" -")

        return suggestions

    @staticmethod
    def _format_question_number(question_number: int) -> str:
        """Formats question numbers using two digits (01, 02, ...)."""
        return f"{int(question_number):02d}"

    def _build_exam_variant_df(self, source_df: pd.DataFrame) -> pd.DataFrame:
        """Builds one exam variant with a canonical order reused by all outputs."""
        exam_df_variant = source_df.sample(frac=1).reset_index(drop=True).copy()
        exam_df_variant['Número de pregunta'] = range(1, len(exam_df_variant) + 1)
        exam_df_variant['Texto respuesta correcta'] = exam_df_variant.apply(
            lambda row: row[f"Respuesta {row['Respuesta correcta'].upper()}"]
            if pd.notnull(row['Respuesta correcta']) else None,
            axis=1
        )

        def shuffle_row_answers(row):
            answers = [row['Respuesta A'], row['Respuesta B'], row['Respuesta C'], row['Respuesta D']]
            original_correct_answer = row['Texto respuesta correcta']
            random.shuffle(answers)
            new_correct_answer_letter = None
            if original_correct_answer == answers[0]:
                new_correct_answer_letter = 'a'
            elif original_correct_answer == answers[1]:
                new_correct_answer_letter = 'b'
            elif original_correct_answer == answers[2]:
                new_correct_answer_letter = 'c'
            elif original_correct_answer == answers[3]:
                new_correct_answer_letter = 'd'
            return pd.Series([answers[0], answers[1], answers[2], answers[3], new_correct_answer_letter])

        exam_df_variant[['Respuesta A', 'Respuesta B', 'Respuesta C', 'Respuesta D', 'Respuesta correcta']] = \
            exam_df_variant.apply(shuffle_row_answers, axis=1)
        exam_df_variant.drop(columns=['Texto respuesta correcta'], inplace=True)
        return exam_df_variant

    def _select_questions_by_topic(
            self,
            questions_per_topic: dict,
            selection_method: str = "azar",
            verbose: bool = False
    ) -> pd.DataFrame:
        """Selects questions from `self.acceptable_df` according to a per-topic quantity dictionary.

        Args:
            questions_per_topic (dict): Mapping of topic -> number of questions to take from that topic.
            selection_method (str): How to pick questions inside each topic ('azar', 'primeras',
                'menos usadas').
            verbose (bool): If True, prints progress messages.

        Returns:
            pd.DataFrame: The concatenated selection (empty DataFrame with the same columns if nothing
            was selected).

        Raises:
            ValueError: If a topic does not have enough 'Aceptable' questions for the requested quantity.
        """
        selected_questions = []
        for topic, quantity in questions_per_topic.items():
            if verbose:
                print(f"Verbose: Tema: {topic}, Cantidad solicitada: {quantity}")
            topic_questions = self.acceptable_df[self.acceptable_df['Tema'] == topic]
            # Per-topic check: raise a clear error if there are not enough questions for a topic.
            if len(topic_questions) < quantity:
                raise ValueError(
                    f"No hay suficientes preguntas 'Aceptables' para el tema '{topic}'. "
                    f"Se solicitaron {quantity}, pero solo hay {len(topic_questions)} disponibles."
                )
            if selection_method == "primeras":
                topic_questions = topic_questions.head(quantity).copy()
            elif selection_method == "menos usadas":
                topic_questions = topic_questions.sort_values(by='Veces usada en examen').head(quantity).copy()
            else:  # 'azar' (default).
                topic_questions = topic_questions.sample(n=quantity).copy()
            selected_questions.append(topic_questions)
        if selected_questions:
            return pd.concat(selected_questions).copy()
        # Empty DataFrame with the same columns.
        return pd.DataFrame(columns=self.acceptable_df.columns)

    @staticmethod
    def _distribute_questions_equitably(acceptable_df: pd.DataFrame, total_questions: int) -> Dict[str, int]:
        """Spreads `total_questions` across the available topics as evenly as possible.

        Each topic receives the same number of questions; when the total is not divisible by the number
        of topics (e.g. an odd total), the first topics receive one extra question. If a topic does not
        have enough 'Aceptable' questions, its surplus is redistributed among the remaining topics
        (the "as far as possible" part).

        Args:
            acceptable_df (pd.DataFrame): The pool of acceptable questions (must contain a 'Tema' column).
            total_questions (int): The total number of questions to distribute.

        Returns:
            Dict[str, int]: Mapping of topic -> number of questions assigned (topics with 0 are omitted).

        Raises:
            ValueError: If `total_questions` exceeds the number of available questions.
        """
        topic_counts = acceptable_df['Tema'].value_counts().to_dict()
        topics = sorted(topic_counts.keys(), key=lambda topic: str(topic))
        total_available = int(sum(topic_counts.values()))
        if total_questions > total_available:
            raise ValueError(
                f"Se solicitaron {total_questions} preguntas en total, "
                f"pero solo hay {total_available} preguntas 'Aceptables' disponibles."
            )
        allocation = {topic: 0 for topic in topics}
        remaining = total_questions
        # Round-robin: hand out one question at a time to each topic that still has capacity.
        while remaining > 0:
            topics_with_capacity = [topic for topic in topics if allocation[topic] < topic_counts[topic]]
            if not topics_with_capacity:
                break
            for topic in topics_with_capacity:
                if remaining == 0:
                    break
                allocation[topic] += 1
                remaining -= 1
        return {topic: count for topic, count in allocation.items() if count > 0}

    def read_questions_from_excel(self, excel_path: str) -> Optional[pd.DataFrame]:
        """
        Reads questions from an Excel file and returns a pandas DataFrame.

        Args:
            excel_path (str): The path to the Excel file containing the questions.

        Returns:
            Optional[pd.DataFrame]: A DataFrame with the questions if the read is successful,
                                    None in case of an error.
        """
        try:
            df = pd.read_excel(excel_path)
            # Attempt to convert the 'Número de pregunta' (Question Number) column to an integer.
            if 'Número de pregunta' in df.columns:
                df['Número de pregunta'] = pd.to_numeric(df['Número de pregunta'], errors='coerce').fillna(0).astype(int)
            return df
        except Exception as e:
            print(f"Error al leer el archivo Excel: {e}")
            return None

    def generate_question_text(self, df: pd.DataFrame, renumber: bool = False, shuffle_answers: bool = False) -> Tuple[str, str, pd.DataFrame]:
        """
        Generates the formatted text of the questions (with and without solutions) from a DataFrame.
        This method is primarily used for the 'check' functionality to create a quick preview.

        Args:
            df (pd.DataFrame): The DataFrame containing the questions.
            renumber (bool, optional): If True, renumbers questions sequentially. Defaults to False.
            shuffle_answers (bool, optional): If True, shuffles the order of answers. Defaults to False.

        Returns:
            Tuple[str, str, pd.DataFrame]: A tuple containing the student's exam text, the full exam text (with solutions),
                                           and the modified DataFrame.
        """
        self.exam_text = ""
        self.full_exam_text = ""
        num_total_questions = len(df)
        use_two_digits = num_total_questions > 9

        # Create the "Texto respuesta correcta" (Correct answer text) column for shuffling.
        df['Texto respuesta correcta'] = df.apply(
            lambda row: row[f"Respuesta {row['Respuesta correcta'].upper()}"] if pd.notnull(
                row['Respuesta correcta']) else None, axis=1)
        for index, row in df.iterrows():
            pregunta_num = row['Número de pregunta'] if renumber else index + 1
            formatted_pregunta_num = f"{pregunta_num:02d}" if use_two_digits else str(pregunta_num)

            self.exam_text += f"Pregunta {formatted_pregunta_num}:\n"
            self.full_exam_text += f"Pregunta {formatted_pregunta_num}:\n"
            self.exam_text += f"{row['Pregunta']}\n"
            self.full_exam_text += f"{row['Pregunta']}\n"
            # Shuffle answer texts if shuffle_answers is True.
            if shuffle_answers:
                answers = [
                    row['Respuesta A'],
                    row['Respuesta B'],
                    row['Respuesta C'],
                    row['Respuesta D']
                ]
                random.shuffle(answers)  # Shuffle the list of answers.
                # Identify the new letter of the correct answer.
                new_correct_answer = None
                if row['Texto respuesta correcta'] == answers[0]:
                    new_correct_answer = 'a'
                elif row['Texto respuesta correcta'] == answers[1]:
                    new_correct_answer = 'b'
                elif row['Texto respuesta correcta'] == answers[2]:
                    new_correct_answer = 'c'
                elif row['Texto respuesta correcta'] == answers[3]:
                    new_correct_answer = 'd'
                # Print shuffled answers with letters in order.
                self.exam_text += f"a) {answers[0]}\n"
                self.exam_text += f"b) {answers[1]}\n"
                self.exam_text += f"c) {answers[2]}\n"
                self.exam_text += f"d) {answers[3]}\n"
                self.full_exam_text += f"a) {answers[0]}\n"
                self.full_exam_text += f"b) {answers[1]}\n"
                self.full_exam_text += f"c) {answers[2]}\n"
                self.full_exam_text += f"d) {answers[3]}\n"
                # Update the DataFrame with the new answers and correct answer.
                df.loc[index, 'Respuesta A'] = answers[0]
                df.loc[index, 'Respuesta B'] = answers[1]
                df.loc[index, 'Respuesta C'] = answers[2]
                df.loc[index, 'Respuesta D'] = answers[3]
                df.loc[index, 'Respuesta correcta'] = new_correct_answer
            else:
                # Print answers in original order.
                self.exam_text += f"a) {row['Respuesta A']}\n"
                self.exam_text += f"b) {row['Respuesta B']}\n"
                self.exam_text += f"c) {row['Respuesta C']}\n"
                self.exam_text += f"d) {row['Respuesta D']}\n"
                self.full_exam_text += f"a) {row['Respuesta A']}\n"
                self.full_exam_text += f"b) {row['Respuesta B']}\n"
                self.full_exam_text += f"c) {row['Respuesta C']}\n"
                self.full_exam_text += f"d) {row['Respuesta D']}\n"
                new_correct_answer = row['Respuesta correcta'].lower()  # Initialize here.
            self.full_exam_text += f"Respuesta correcta: {new_correct_answer}\n"
            self.full_exam_text += f"Texto relevante: {row['Texto relevante']}\n"
            self.exam_text += "\n"
            self.full_exam_text += "\n"
        df.drop('Texto respuesta correcta', axis=1, inplace=True)
        return self.exam_text, self.full_exam_text

    def _remove_empty_last_section(self, document: Document):
        """
        Attempts to remove the last section if it appears empty based on XML analysis.
        This is a workaround for a common issue in python-docx where an extra blank page is added.
        """
        body = document._body._element
        sect_prs = body.findall('.//w:sectPr', namespaces=WML_NAMESPACE)
        if sect_prs and sect_prs[-1] == body.getchildren()[-1]:  # Last element in body is sectPr.
            potential_empty = True
            preceding_elements = body.getchildren()[:-1]
            for element in preceding_elements:
                if element.tag.endswith(('}p', '}tbl')):  # Check for paragraphs or tables with namespace.
                    potential_empty = False
                    break
            if potential_empty:
                body.remove(sect_prs[-1])
                print("Se ha intentado eliminar la última sección vacía (XML revisado con namespace).")

    def _create_element(self, tag_name: str) -> OxmlElement:
        """Helper function to create an OxmlElement."""
        return OxmlElement(tag_name)

    def _create_attribute(self, element: OxmlElement, name: str, value: str):
        """Helper function to set an attribute on an OxmlElement."""
        element.set(ns.qn(name), value)

    def add_page_number(self, document: Document) -> Document:
        """
        Adds page numbers to the footer of a Word document using direct docx XML manipulation.
        The format will be "Página X de Y".

        Args:
            document (Document): The docx Document object to which page numbers will be added.

        Returns:
            Document: The Document object with the added page numbers.
        """
        section = document.sections[0]
        footer = section.footer
        if not footer.paragraphs:
            paragraph = footer.add_paragraph()
        else:
            paragraph = footer.paragraphs[0]
        paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        paragraph.text = "Página "

        r = paragraph.add_run()

        fldChar = self._create_element('w:fldChar')
        self._create_attribute(fldChar, 'w:fldCharType', 'begin')
        r._element.append(fldChar)

        instrText = self._create_element('w:instrText')
        self._create_attribute(instrText, 'xml:space', 'preserve')
        instrText.text = ' PAGE   \\* MERGEFORMAT '
        r._element.append(instrText)

        fldChar = self._create_element('w:fldChar')
        self._create_attribute(fldChar, 'w:fldCharType', 'separate')
        r._element.append(fldChar)

        fldChar = self._create_element('w:fldChar')
        self._create_attribute(fldChar, 'w:fldCharType', 'end')
        r._element.append(fldChar)

        r = paragraph.add_run(" de ")

        fldChar = self._create_element('w:fldChar')
        self._create_attribute(fldChar, 'w:fldCharType', 'begin')
        r._element.append(fldChar)

        instrText = self._create_element('w:instrText')
        self._create_attribute(instrText, 'xml:space', 'preserve')
        instrText.text = ' NUMPAGES   \\* MERGEFORMAT '
        r._element.append(instrText)

        fldChar = self._create_element('w:fldChar')
        self._create_attribute(fldChar, 'w:fldCharType', 'separate')
        r._element.append(fldChar)

        fldChar = self._create_element('w:fldChar')
        self._create_attribute(fldChar, 'w:fldCharType', 'end')
        r._element.append(fldChar)

        for run in paragraph.runs:
            run.font.size = Pt(8)

        return document

    def save_questions_to_docx(self, question_text: str, file_name: Optional[str] = None):
        """
        Saves the formatted question text to a .docx file.

        Args:
            question_text (str): The text of the questions to be saved.
            file_name (Optional[str], optional): The name of the .docx file.
        """
        document = Document()
        document.add_paragraph(question_text)
        document.save(file_name)

    def generate_moodle_xml(self, df: pd.DataFrame, file_name: str, num_total_questions: int,
                            exam: Optional[str] = None, exam_type: Optional[str] = None,
                            xml_cat_additional_text: Optional[str] = None, penalty: int = -25,
                            xml_use_answer_text: bool = False):
        """
        Generates a Moodle XML file from a DataFrame, including category information and correctly
        handling shuffled answers.

        Args:
            df (pd.DataFrame): The DataFrame containing the questions and answers.
            file_name (str): The name of the XML file to generate.
            num_total_questions (int): The total number of questions.
            exam (Optional[str], optional): The name of the exam.
            exam_type (Optional[str], optional): The type of exam.
            xml_cat_additional_text (Optional[str], optional): Additional text for the Moodle XML category.
            penalty (int, optional): The penalty percentage for an incorrect answer (e.g., -25 for 25%).
        """
        self.quiz = Element('quiz')
        self.category = SubElement(self.quiz, 'question', type='category')
        self.category_name = SubElement(self.category, 'category')
        self.text = SubElement(self.category_name, 'text')

        # Build the category text dynamically.
        category_text = "$course$/top/Examen"
        if exam:
            category_text += f" {exam} -"
        if exam_type:
            category_text += f" {exam_type} -"
        if xml_cat_additional_text:
            category_text += f" {xml_cat_additional_text}"

        self.text.text = category_text
        for _, row in df.iterrows():
            correct_answer = row['Respuesta correcta'].lower()

            pregunta_num = row['Número de pregunta']
            formatted_pregunta_num = self._format_question_number(pregunta_num)

            self.question = SubElement(self.quiz, 'question', type='multichoice')
            self.name = SubElement(self.question, 'name')
            self.text = SubElement(self.name, 'text')
            self.text.text = f"Pregunta {formatted_pregunta_num}"

            questiontext = SubElement(self.question, 'questiontext', format='html')
            questiontext_text = SubElement(questiontext, 'text')
            questiontext_text.text = row.get('Pregunta', '') if xml_use_answer_text else f"Pregunta {formatted_pregunta_num}"

            if correct_answer == 'a':
                self.answer_a = SubElement(self.question, 'answer', fraction='100')
            else:
                self.answer_a = SubElement(self.question, 'answer', fraction=str(penalty))
            self.text = SubElement(self.answer_a, 'text')
            self.text.text = row.get('Respuesta A', '') if xml_use_answer_text else 'a'

            if correct_answer == 'b':
                self.answer_b = SubElement(self.question, 'answer', fraction='100')
            else:
                self.answer_b = SubElement(self.question, 'answer', fraction=str(penalty))
            self.text = SubElement(self.answer_b, 'text')
            self.text.text = row.get('Respuesta B', '') if xml_use_answer_text else 'b'

            if correct_answer == 'c':
                self.answer_c = SubElement(self.question, 'answer', fraction='100')
            else:
                self.answer_c = SubElement(self.question, 'answer', fraction=str(penalty))
            self.text = SubElement(self.answer_c, 'text')
            self.text.text = row.get('Respuesta C', '') if xml_use_answer_text else 'c'

            if correct_answer == 'd':
                self.answer_d = SubElement(self.question, 'answer', fraction='100')
            else:
                self.answer_d = SubElement(self.question, 'answer', fraction=str(penalty))
            self.text = SubElement(self.answer_d, 'text')
            self.text.text = row.get('Respuesta D', '') if xml_use_answer_text else 'd'

        self.xml_str = minidom.parseString(tostring(self.quiz)).toprettyxml(indent="  ")
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(self.xml_str)

    def generate_exam_from_excel(
            self,
            bank_excel_path: str,
            output_dir: Optional[str] = None,
            exam_names: Optional[list] = None,
            questions_per_topic: Optional[dict] = None,
            selection_method: str = "azar",
            total_questions: Optional[int] = None,
            total_distribution: str = "equitativo",
            subject: Optional[str] = None,
            exam: Optional[str] = None,
            course: Optional[str] = None,
            num_exams: int = 2,
            top_margin: float = 1,
            bottom_margin: float = 1,
            left_margin: float = 0.5,
            right_margin: float = 0.5,
            export_moodle_xml: bool = False,
            font_size: int = 9,
            xml_cat_additional_text: Optional[str] = None,
            penalty: int = -25,
            xml_use_answer_text: bool = False,
            check: bool = False,
            update_excel: bool = False,
            answer_sheet_instructions: Optional[str] = None,
            template_docx_path: Optional[str] = None,
            session_output_path: Optional[str] = None,
            verbose: bool = False
    ):
        """
        Generates multiple exams in .docx format with varied question and answer orders.
        This is the main orchestrator method of the class.

        Args:
            bank_excel_path (str): Path to the Excel file with the question bank.
            output_dir (Optional[str]): The directory to save the generated exam files.
                If None, uses the same directory as the bank_excel_path.
            exam_names (Optional[list]): A list of names for the exam versions (e.g., ['1A', '1B']).
            questions_per_topic (Optional[dict]): A dictionary specifying how many questions to select from each topic.
            selection_method (str): Method for selecting questions within each topic: 'azar' (random),
                'primeras' (first N), 'menos usadas' (least used).
            total_questions (Optional[int]): If provided (and > 0), selects this exact total number of
                questions and overrides `questions_per_topic`. The way the total is spread is controlled
                by `total_distribution`.
            total_distribution (str): How to spread `total_questions`: 'equitativo' (same number of
                questions per topic as far as possible; the first topics get one extra when the total is
                not divisible) or 'azar' (pick the total at random from the whole acceptable pool,
                ignoring topics).
            subject (Optional[str]): The subject name for the exam header.
            exam (Optional[str]): The exam name (e.g., 'Parcial 1').
            course (Optional[str]): The course name or year (e.g., '24-25').
            num_exams (int): The number of different exam versions to generate if `exam_names` is not provided.
            top_margin (float): Top page margin in inches.
            bottom_margin (float): Bottom page margin in inches.
            left_margin (float): Left page margin in inches.
            right_margin (float): Right page margin in inches.
            export_moodle_xml (bool): If True, exports the exam to Moodle XML format.
            font_size (int): Font size for the text in the document.
            xml_cat_additional_text (Optional[str]): Additional text for the Moodle XML category.
            penalty (int): Penalty for incorrect answers in the Moodle XML export.
            xml_use_answer_text (bool): If True, XML stores full question and answer text instead of a/b/c/d.
            check (bool): If True, generates a preview and waits for user confirmation before creating all exams.
            update_excel (bool): If True, updates the source Excel file with usage statistics.
            answer_sheet_instructions (Optional[str]): Text with instructions for the answer sheet.
            template_docx_path (Optional[str]): Path to a DOCX template with placeholders like {{subject}}.
            session_output_path (Optional[str]): If set, writes a resumable grading session (``.pkl`` +
                ``.json``) recording the paths of every generated exam, so correction can be resumed later.
            verbose (bool): If True, prints detailed progress messages to the console.
        """
        # Start a fresh list of generated-exam records for this run.
        self.generated_exams = []

        if self.df is None:
            self.df = self.read_questions_from_excel(bank_excel_path)

        if self.df is None:
            return

        exam_columns = [col for col in self.df.columns if re.match(r'.*_\d{2}-\d{2}', col)]
        for col in exam_columns:
            self.df[col] = self.df[col].fillna(0)

        self.acceptable_df = self.df[self.df['Estado'].astype(str).str.strip().str.lower() == 'aceptable']

        # Comprobación temprana: si no hay NINGUNA pregunta aceptable, paramos aquí.
        if self.acceptable_df.empty:
            raise NoAcceptableQuestionsError("No se encontraron preguntas con estado 'Aceptable' en el banco de preguntas.")

        # Normalize the optional total-questions request.
        total_questions_int = None
        if total_questions is not None and str(total_questions).strip() != "":
            try:
                total_questions_int = int(total_questions)
            except (TypeError, ValueError):
                total_questions_int = None

        if total_questions_int and total_questions_int > 0:
            # A fixed total overrides any per-topic dictionary.
            available = len(self.acceptable_df)
            if total_questions_int > available:
                raise ValueError(
                    f"Se solicitaron {total_questions_int} preguntas en total, "
                    f"pero solo hay {available} preguntas 'Aceptables' disponibles."
                )
            if total_distribution == "azar":
                # Pick the total at random from the whole acceptable pool, ignoring topics.
                self.exam_df = self.acceptable_df.sample(n=total_questions_int).copy()
            else:
                # Spread the total across topics as evenly as possible.
                computed_per_topic = self._distribute_questions_equitably(self.acceptable_df, total_questions_int)
                if verbose:
                    print(f"Verbose: Reparto equitativo del total {total_questions_int}: {computed_per_topic}")
                self.exam_df = self._select_questions_by_topic(computed_per_topic, selection_method, verbose)
        elif questions_per_topic:
            self.exam_df = self._select_questions_by_topic(questions_per_topic, selection_method, verbose)
        else:
            self.exam_df = self.acceptable_df.copy()

        if verbose:
            print(f"Verbose: Tipo de self.exam_df antes del bucle: {type(self.exam_df)}")
            if isinstance(self.exam_df, pd.DataFrame):
                print(f"Verbose: Head de self.exam_df antes del bucle:\n{self.exam_df.head()}")
            else:
                print(f"Verbose: self.exam_df no es un DataFrame: {self.exam_df}")

        if check:
            preview_exam_df = self.exam_df.copy()
            preview_exam_df['Número de pregunta'] = range(1, len(preview_exam_df) + 1)
            preview_exam_df['Texto respuesta correcta'] = preview_exam_df.apply(
                lambda row: row[f"Respuesta {row['Respuesta correcta'].upper()}"] if pd.notnull(
                    row['Respuesta correcta']) else None, axis=1)
            preview_exam_text, preview_full_exam_text = self.generate_question_text(preview_exam_df.copy(),
                                                                                    renumber=True, shuffle_answers=True)
            preview_document = Document()
            title_paragraph = preview_document.add_paragraph(subject, style='Heading 1')
            title_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            subtitle_paragraph = preview_document.add_paragraph(
                f"Examen: {exam} - Curso: {course} - Tipo: Previsualización",
                style='Heading 1'
            )
            subtitle_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            preview_paragraph = preview_document.add_paragraph(preview_full_exam_text)
            preview_paragraph.runs[0].font.size = Pt(font_size)
            preview_document = self.add_page_number(preview_document)
            preview_document.save(f'examen_previsualizacion_{subject}_{exam}_{course}_completo.docx')

            print(
                f"Se ha generado un examen de previsualización: examen_previsualizacion_{subject}_{exam}_{course}_completo.docx")
            review = input("¿El examen es correcto? (sí/no): ").lower()

            if review == 'sí':
                try:
                    os.remove(f'examen_previsualizacion_{subject}_{exam}_{course}_completo.docx')
                    print("Archivo de previsualización eliminado.")
                except OSError as e:
                    print("Archivo de previsualización eliminado.")
                except OSError as e:
                    print(f"Error al eliminar el archivo de previsualización: {e}")
            else:
                print("Generación de exámenes cancelada.")
                return

        if exam_names is None:
            num_exams_to_generate = num_exams
            exam_name_list = [f'Tipo {i + 1}' for i in range(num_exams_to_generate)]
        else:
            num_exams_to_generate = len(exam_names)
            exam_name_list = exam_names

        if output_dir is None:
            output_dir = os.path.dirname(bank_excel_path)
        os.makedirs(output_dir, exist_ok=True)

        for i in range(num_exams_to_generate):
            exam_type_name = exam_name_list[i]
            exam_df_shuffled = self._build_exam_variant_df(self.exam_df)

            placeholder_map: Dict[str, str] = {
                "subject": subject or "",
                "exam": exam or "",
                "course": course or "",
                "exam_type": exam_type_name or "",
            }

            base_filename = f'examen_{subject}_{exam}_{course}_{exam_type_name}'

            docx_path = os.path.join(output_dir, f'{base_filename}.docx')
            full_docx_path = os.path.join(output_dir, f'{base_filename}_completo.docx')
            excel_path_out = os.path.join(output_dir, f'{base_filename}_completo.xlsx')
            xml_path = os.path.join(output_dir, f'{base_filename}.xml')

            if verbose:
                print(f"Verbose: Iteración {i}, tipo de exam_df_shuffled después de sample: {type(exam_df_shuffled)}")
                if isinstance(exam_df_shuffled, pd.DataFrame):
                    print(f"Verbose: Head de exam_df_shuffled:\n{exam_df_shuffled.head()}")
                else:
                    print(f"Verbose: exam_df_shuffled no es un DataFrame: {exam_df_shuffled}")

            exam_text, full_exam_text = self.generate_question_text(exam_df_shuffled.copy(), renumber=False,
                                                                    shuffle_answers=False)

            document = Document(template_docx_path) if template_docx_path and os.path.exists(template_docx_path) else Document()
            self._replace_placeholders_in_document(document, placeholder_map)
            title_paragraph = document.add_paragraph(subject, style='Heading 1')
            title_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            subtitle_paragraph = document.add_paragraph(
                f"Examen: {exam} - Curso: {course} - Tipo: {exam_type_name}",
                style='Heading 1'
            )
            subtitle_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            section = document.sections[0]
            section.top_margin = Inches(top_margin)
            section.bottom_margin = Inches(bottom_margin)
            section.left_margin = Inches(left_margin)
            section.right_margin = Inches(right_margin)

            header = section.header
            header_paragraph = header.paragraphs[0]
            header_paragraph.text = f"Asignatura: {subject} - Examen: {exam} - Curso: {course} - Tipo: {exam_type_name}"
            header_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            header_paragraph.runs[0].font.size = Pt(font_size)

            for index, row in exam_df_shuffled.iterrows():
                paragraph = document.add_paragraph()
                pregunta_num = row['Número de pregunta']
                use_two_digits = len(exam_df_shuffled) > 9
                formatted_pregunta_num = f"{pregunta_num:02d}" if use_two_digits else str(pregunta_num)

                # Add the question number in bold.
                run_numero = paragraph.add_run(f"Pregunta {formatted_pregunta_num}: ")
                run_numero.font.size = Pt(font_size)
                run_numero.font.bold = True
                # Add the question statement in bold.
                run_enunciado = paragraph.add_run(f"{row['Pregunta']}\n")
                run_enunciado.font.size = Pt(font_size)
                run_enunciado.font.bold = True
                # Add the answer options.
                paragraph.add_run(f"a) {row['Respuesta A']}\n").font.size = Pt(font_size)
                paragraph.add_run(f"b) {row['Respuesta B']}\n").font.size = Pt(font_size)
                paragraph.add_run(f"c) {row['Respuesta C']}\n").font.size = Pt(font_size)
                # No trailing line break on the last option: the paragraph style already provides
                # enough spacing to separate it from the next question.
                paragraph.add_run(f"d) {row['Respuesta D']}").font.size = Pt(font_size)

            # Start the answer sheet on an odd page so it prints as a single, self-contained sheet
            # (front of a physical page) while staying in the same document as the questions.
            document.add_section(WD_SECTION.ODD_PAGE)
            document.add_heading('Datos del alumno', level=1)
            document.paragraphs[-1].runs[0].font.size = Pt(font_size)
            student_table = document.add_table(rows=4, cols=2)
            student_table.style = 'Table Grid'
            # Use a fixed layout so the column widths below are honored by Word.
            student_table.autofit = False
            student_data = ['Nombre', 'Apellidos', 'DNI/NIE', 'Firma']
            for j, data in enumerate(student_data):
                cell = student_table.cell(j, 0)
                cell.text = data
                for paragraph in cell.paragraphs:
                    paragraph.runs[0].font.size = Pt(font_size)
            # The label column only needs room for words like 'Apellidos'/'DNI/NIE'; give the rest of
            # the page width to the data column so there is plenty of space to write name, surname, etc.
            answer_section = document.sections[-1]
            available_width = answer_section.page_width - answer_section.left_margin - answer_section.right_margin
            label_col_width = Cm(3.5)
            if label_col_width > available_width * 0.5:
                label_col_width = int(available_width * 0.4)
            value_col_width = available_width - label_col_width
            for row in student_table.rows:
                row.cells[0].width = label_col_width
                row.cells[1].width = value_col_width
            student_table.rows[3].height = Inches(1)

            document.add_heading('Hoja de respuestas', level=1)
            document.paragraphs[-1].runs[0].font.size = Pt(font_size)
            if answer_sheet_instructions:
                instructions_title = document.add_paragraph("Instrucciones de cumplimentación:")
                instructions_title.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                instructions_title.runs[0].font.size = Pt(font_size)
                instructions_paragraph = document.add_paragraph(answer_sheet_instructions)
                instructions_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                instructions_paragraph.runs[0].font.size = Pt(font_size)

            if verbose:
                print(f"Verbose: Tipo de exam_df_shuffled antes de crear la tabla: {type(exam_df_shuffled)}")
                if isinstance(exam_df_shuffled, pd.DataFrame):
                    print(f"Verbose: Longitud de exam_df_shuffled para número de filas: {len(exam_df_shuffled)}")
                else:
                    print(f"Verbose: exam_df_shuffled no es un DataFrame: {exam_df_shuffled}")

            # Answer sheet: 'Pregunta' + one column per answer option plus an extra 'NC' (no
            # contestada) column so students can explicitly mark a question as unanswered instead of
            # leaving it blank.
            headers = ['Pregunta', 'a', 'b', 'c', 'd', 'NC']
            table = document.add_table(rows=len(exam_df_shuffled) + 1, cols=len(headers))
            table.style = 'Table Grid'
            # Center the whole table on the page and use a fixed layout so the widths below are kept.
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = False
            for j, header in enumerate(headers):
                cell = table.cell(0, j)
                cell.text = header
                for paragraph in cell.paragraphs:
                    paragraph.runs[0].font.size = Pt(font_size)
            for j, (_, row) in enumerate(exam_df_shuffled.iterrows(), start=1):
                cell = table.cell(j, 0)
                cell.text = self._format_question_number(row['Número de pregunta'])
                for paragraph in cell.paragraphs:
                    paragraph.runs[0].font.size = Pt(font_size)

            # Column widths: 1 cm by default, growing only when the content needs more room (e.g. the
            # 'Pregunta' column). The answer columns (a/b/c/d/NC) stay at 1 cm.
            min_col_width_cm = 1.0
            approx_char_width_cm = 0.23
            col_widths = []
            for j in range(len(headers)):
                longest = max(len(table.cell(k, j).text) for k in range(len(exam_df_shuffled) + 1))
                width_cm = max(min_col_width_cm, longest * approx_char_width_cm + 0.2)
                col_widths.append(Cm(width_cm))

            # Apply the widths to every cell (most reliable in Word) and center the content both
            # horizontally and vertically, keeping the configured font size.
            for j in range(len(headers)):
                for row in table.rows:
                    cell = row.cells[j]
                    cell.width = col_widths[j]
                    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                    for paragraph in cell.paragraphs:
                        paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                        for run in paragraph.runs:
                            run.font.size = Pt(font_size)

            document = self.add_page_number(document)
            self._remove_empty_last_section(document)
            document.save(docx_path)

            full_document = Document(template_docx_path) if template_docx_path and os.path.exists(template_docx_path) else Document()
            self._replace_placeholders_in_document(full_document, placeholder_map)
            title_paragraph = full_document.add_paragraph(subject, style='Heading 1')
            title_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            subtitle_paragraph = full_document.add_paragraph(
                f"Examen: {exam} - Curso: {course} - Tipo: {exam_type_name} - Completo",
                style='Heading 1'
            )
            subtitle_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            full_section = full_document.sections[0]
            full_section.top_margin = Inches(top_margin)
            full_section.bottom_margin = Inches(bottom_margin)
            full_section.left_margin = Inches(left_margin)
            full_section.right_margin = Inches(right_margin)

            full_header = full_section.header
            full_header_paragraph = full_header.paragraphs[0]
            full_header_paragraph.text = f"Asignatura: {subject} - Examen: {exam} - Curso: {course} - Tipo: {exam_type_name} - Completo"
            full_header_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            full_header_paragraph.runs[0].font.size = Pt(font_size)

            for index, row in exam_df_shuffled.iterrows():
                paragraph = full_document.add_paragraph()
                pregunta_num = row['Número de pregunta']
                use_two_digits = len(exam_df_shuffled) > 9
                formatted_pregunta_num = f"{pregunta_num:02d}" if use_two_digits else str(pregunta_num)

                # Add the question number in bold.
                run_numero = paragraph.add_run(f"Pregunta {formatted_pregunta_num}: ")
                run_numero.font.size = Pt(font_size)
                run_numero.font.bold = True
                # Add the question statement in bold.
                run_enunciado = paragraph.add_run(f"{row['Pregunta']}\n")
                run_enunciado.font.size = Pt(font_size)
                run_enunciado.font.bold = True
                # Add the answer options (not bold).
                paragraph.add_run(f"a) {row['Respuesta A']}\n").font.size = Pt(font_size)
                paragraph.add_run(f"b) {row['Respuesta B']}\n").font.size = Pt(font_size)
                paragraph.add_run(f"c) {row['Respuesta C']}\n").font.size = Pt(font_size)
                paragraph.add_run(f"d) {row['Respuesta D']}\n").font.size = Pt(font_size)
                # Add the correct answer and relevant text (not bold).
                paragraph.add_run(f"Respuesta correcta: {row['Respuesta correcta'].lower()}\n").font.size = Pt(font_size)
                paragraph.add_run(f"Texto relevante: {row['Texto relevante']}\n").font.size = Pt(font_size)
                # No trailing line break: the paragraph style already separates one question from the next.
                paragraph.add_run(f"Tema: {row['Tema']}").font.size = Pt(font_size)


            full_document = self.add_page_number(full_document)
            self._remove_empty_last_section(full_document)
            full_document.save(full_docx_path)

            exam_df_shuffled.to_excel(excel_path_out, index=False)

            if export_moodle_xml:
                self.generate_moodle_xml(
                    df=exam_df_shuffled.copy(),
                    file_name=xml_path,
                    num_total_questions=len(exam_df_shuffled),
                    exam=exam,
                    exam_type=exam_type_name,
                    xml_cat_additional_text=xml_cat_additional_text,
                    penalty=penalty,
                    xml_use_answer_text=xml_use_answer_text
                )

            # Record this exam type's output paths for the optional resumable session.
            self.generated_exams.append({
                "subject": subject,
                "exam": exam,
                "course": course,
                "exam_type": exam_type_name,
                "docx": docx_path,
                "full_docx": full_docx_path,
                "xlsx": excel_path_out,
                "xml": xml_path if export_moodle_xml else None,
            })

        if session_output_path:
            self._save_grading_session(session_output_path, subject=subject, exam=exam, course=course)

        if update_excel:
            new_column_name_base = f'{exam}_{course}'
            safe_exam_name = re.sub(r'[^a-zA-Z0-9_]', '_', exam)
            safe_course_name = re.sub(r'[^a-zA-Z0-9_]', '_', course)
            usage_column_name = f'{safe_exam_name}_{safe_course_name}_uso'

            if usage_column_name not in self.df.columns:
                self.df[usage_column_name] = 0

            used_question_numbers = self.exam_df['Número de pregunta'].tolist()
            for question_number in used_question_numbers:
                original_index = self.df[self.df['Número de pregunta'] == question_number].index
                if not original_index.empty:
                    self.df.loc[original_index, usage_column_name] = 1

            usage_columns = [col for col in self.df.columns if col.endswith('_uso')]

            if not usage_columns:
                print("No se encontraron columnas de uso para sumar.")
                # Si la columna de suma no existe, la creamos.
                if 'Veces usada en examen' not in self.df.columns:
                    self.df['Veces usada en examen'] = 0
            else:
                print(f"Sumando las siguientes columnas de uso: {usage_columns}")
                self.df['Veces usada en examen'] = self.df[usage_columns].sum(axis=1)

            if 'Veces usada en examen' in self.df.columns and 'Texto relevante' in self.df.columns:
                veces_usada_col = self.df.pop('Veces usada en examen')
                try:
                    texto_relevante_idx = self.df.columns.get_loc('Texto relevante')
                    self.df.insert(texto_relevante_idx + 1, 'Veces usada en examen', veces_usada_col)
                    print("Columna 'Veces usada en examen' movida a su posición correcta.")
                except KeyError:
                    # Si 'Texto relevante' no existe, la añade al final.
                    self.df['Veces usada en examen'] = veces_usada_col
                    print("Advertencia: No se encontró la columna 'Texto relevante'. 'Veces usada en examen' se añadió al final.")

            self.df = self.df.loc[:, ~self.df.columns.str.contains('unnamed', case=False)]

            try:
                self.df.to_excel(bank_excel_path, index=False)
                print(
                    f"Archivo Excel '{bank_excel_path}' actualizado con la columna '{usage_column_name}' y 'Veces usada en examen'.")
            except Exception as e:
                print(f"Error al actualizar el archivo Excel '{bank_excel_path}': {e}")

    def _save_grading_session(self, session_output_path: str, subject: Optional[str] = None,
                              exam: Optional[str] = None, course: Optional[str] = None):
        """Builds and saves a resumable grading session from the exams generated in this run."""
        try:
            from pyexamgenerator.grading.session import GradingSession
        except Exception as exc:  # pragma: no cover - grading is part of the package
            print(f"No se pudo crear la sesión: {exc}")
            return None
        name_parts = [str(p) for p in (subject, exam, course) if p]
        session = GradingSession(name=" - ".join(name_parts) or "sesion_pyexamgenerator")
        for record in self.generated_exams:
            session.add_generated_exam(**record)
        pkl_path, json_path = session.save(session_output_path)
        print(f"Sesión guardada en:\n  {pkl_path}\n  {json_path}")
        return pkl_path, json_path

    @staticmethod
    def _replace_placeholders_in_document(document: Document, values: Dict[str, str]) -> None:
        """Replaces placeholders in the format {{field}}. Missing placeholders are ignored."""

        def replace_in_paragraphs(paragraphs):
            for paragraph in paragraphs:
                for key, value in values.items():
                    token = f"{{{{{key}}}}}"
                    if token in paragraph.text:
                        for run in paragraph.runs:
                            run.text = run.text.replace(token, str(value))

        replace_in_paragraphs(document.paragraphs)
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    replace_in_paragraphs(cell.paragraphs)

## Example of use

# generator = pyexamgenerator()
#
# df = pd.read_excel('banco_prueba_pendiente_de_revisar.xlsx')
# temas = [i for i in df['Tema']]
# temas = list(dict.fromkeys(temas))
#
#
# question_dict = {}
# for t in temas:
#     question_dict.update({t: 2})
#
# instrucciones = '''
# -	Marque con una “x” la respuesta correcta en la tabla que se muestra a continuación.
# -	La tabla debe estar LIBRE DE ANOTACIONES. Se pueden hacer anotaciones en la hoja de preguntas, o anotaciones con lápiz en la tabla de respuestas, siempre y cuando el examen se entregue cumplimentado a bolígrafo.
# '''
#
# generator.generate_exam_from_excel(
#     bank_excel_path='banco_prueba_pendiente_de_revisar.xlsx',
#     questions_per_topic=question_dict,
#     subject='Calidad, Seguridad y Protección ambiental',
#     exam='Parcial 1',
#     course='24-25',
#     # num_exams=2,
#     exam_names=['1A', '1B'],
#     export_moodle_xml=True,
#     xml_cat_additional_text='',
#     penalty=-25,
#     # check=True,
#     update_excel=True,
#     answer_sheet_instructions=instrucciones
# )