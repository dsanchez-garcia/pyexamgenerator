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

import pandas as pd
from docx import Document
import os
import re
from typing import Optional, List, Tuple

class QuestionBankManager:
    """
    Manages a question bank, allowing reading from DOCX files,
    saving to Excel, and adding new questions while avoiding duplicates.
    """
    #TODO: review how the transformation from revised docx to xlsx, etc. is used in the code.
    def read_questions_from_docx(self, docx_path: str) -> Optional[pd.DataFrame]:
        """
        Reads revised questions from a DOCX file and returns a pandas DataFrame.
        The DOCX file must follow a specific format where each piece of information
        (question, topic, state, options, etc.) is prefixed with a specific keyword.

        Args:
            docx_path (str): The path to the DOCX file containing the questions.

        Returns:
            Optional[pd.DataFrame]: A pandas DataFrame with the extracted questions.
                                    Returns None if an error occurs while reading the file.
        """
        try:
            document = Document(docx_path)
            questions = []
            current_question = {}
            state = None  # To track what information we are reading

            for paragraph in document.paragraphs:
                text = paragraph.text.strip()
                if text.startswith("Pregunta "):
                    if current_question:
                        questions.append(current_question)
                    current_question = {"Número de pregunta": text.split(":")[0].replace("Pregunta ", "").strip(), "Pregunta": text.split(":")[1].strip()}
                    state = "pregunta"
                elif text.startswith("Tema:"):
                    current_question["Tema"] = text.replace("Tema:", "").strip()
                    state = "tema"
                elif text.startswith("Estado:"):
                    current_question["Estado"] = text.replace("Estado:", "").strip()
                    state = "estado"
                elif text.startswith("A)"):
                    current_question["Respuesta A"] = text.replace("A)", "").strip()
                    state = "respuesta_a"
                elif text.startswith("B)"):
                    current_question["Respuesta B"] = text.replace("B)", "").strip()
                    state = "respuesta_b"
                elif text.startswith("C)"):
                    current_question["Respuesta C"] = text.replace("C)", "").strip()
                    state = "respuesta_c"
                elif text.startswith("D)"):
                    current_question["Respuesta D"] = text.replace("D)", "").strip()
                    state = "respuesta_d"
                elif text.startswith("Respuesta correcta:"):
                    current_question["Respuesta correcta"] = text.replace("Respuesta correcta:", "").strip().upper()
                    state = "respuesta_correcta"
                elif text.startswith("Texto relevante:"):
                    current_question["Texto relevante"] = text.replace("Texto relevante:", "").strip()
                    state = "texto_relevante"

            if current_question:
                questions.append(current_question)

            df = pd.DataFrame(questions)
            # Ensure column order for consistency
            expected_columns = ['Número de pregunta', 'Tema', 'Estado', 'Pregunta', 'Respuesta A', 'Respuesta B', 'Respuesta C', 'Respuesta D', 'Respuesta correcta', 'Texto relevante']
            df = df.reindex(columns=expected_columns)
            return df

        except Exception as e:
            print(f"Error al leer el archivo DOCX: {e}")
            return None

    def save_questions_to_excel(self, df: pd.DataFrame, output_filename: str = 'preguntas_revisadas') -> None:
        """
        Saves the question DataFrame to an Excel file.

        Args:
            df (pd.DataFrame): The pandas DataFrame containing the questions to save.
            output_filename (str): The name of the output Excel file (without the extension).
                                   Defaults to 'preguntas_revisadas'.
        """
        if not df.empty:
            print("Guardando preguntas revisadas en:", f'{output_filename}.xlsx')
            df.to_excel(f'{output_filename}.xlsx', index=False)
            print(f"Preguntas revisadas guardadas en '{output_filename}.xlsx'")
        else:
            print("No hay preguntas revisadas para guardar.")

    def add_questions_without_duplicates(
            self,
            existing_bank_path: str,
            reviewed_questions_path: str,
            duplicate_check_columns: Optional[List[str]] = ['Pregunta', 'Respuesta A', 'Respuesta B', 'Respuesta C', 'Respuesta D'],
            add_only_acceptable: bool = False
    ) -> Tuple[int, Optional[pd.DataFrame]]:
        """
        Adds questions from a reviewed Excel file to an existing bank, avoiding duplicates.
        It can filter questions by their 'Estado' (State) column.

        Args:
            existing_bank_path (str): Path to the existing question bank Excel file.
            reviewed_questions_path (str): Path to the Excel file with revised questions to add.
            duplicate_check_columns (Optional[List[str]]): List of column names used to
                                                            identify duplicate questions.
                                                            Defaults to checking question and all answers.
            add_only_acceptable (bool, optional): If True, only adds questions with 'Aceptable' status.
                                                  Defaults to False (adds all).

        Returns:
            Tuple[int, Optional[pd.DataFrame]]: A tuple containing the number of questions added and the updated
                                                question bank DataFrame. Returns (-1, None) if there are
                                                errors reading the files.
        """
        try:
            df_existing = pd.read_excel(existing_bank_path)
            df_reviewed = pd.read_excel(reviewed_questions_path)
        except FileNotFoundError:
            print(f"Error: Uno o ambos archivos no se encontraron.")
            return -1, None
        except Exception as e:
            print(f"Error al leer los archivos Excel: {e}")
            return -1, None

        # Block to filter the reviewed questions DataFrame if the option is enabled.
        if add_only_acceptable:
            print("Filtrando para añadir solo preguntas con estado 'Aceptable'.")
            if 'Estado' in df_reviewed.columns:
                original_count = len(df_reviewed)
                df_reviewed = df_reviewed[
                    df_reviewed['Estado'].astype(str).str.strip().str.lower() == 'aceptable'
                ].copy()
                print(f"Se encontraron {len(df_reviewed)} preguntas 'Aceptable' de un total de {original_count}.")
                if df_reviewed.empty:
                    print("No se encontraron preguntas con estado 'Aceptable' para añadir.")
            else:
                print("Advertencia: La columna 'Estado' no se encontró en el archivo a añadir. No se pudo aplicar el filtro.")

        added_count = 0
        existing_count = len(df_existing)

        # Iterate through each question in the reviewed file
        for index, row_reviewed in df_reviewed.iterrows():
            is_duplicate = False
            # Compare it against every question in the existing bank
            for index_existing, row_existing in df_existing.iterrows():
                match = True
                # Check all specified columns for a perfect match
                for col in duplicate_check_columns:
                    # Logic to handle different scenarios of matching, including NaN values
                    if col in row_reviewed and col in row_existing and pd.notna(row_reviewed[col]) and pd.notna(row_existing[col]) and row_reviewed[col] != row_existing[col]:
                        match = False
                        break
                    elif (col in row_reviewed and col not in row_existing) or \
                            (col not in row_reviewed and col in row_existing) or \
                            (col in row_reviewed and col in row_existing and pd.isna(row_reviewed[col]) and pd.notna(row_existing[col])) or \
                            (col in row_reviewed and col in row_existing and pd.notna(row_reviewed[col]) and pd.isna(row_existing[col])):
                        match = False
                        break
                if match:
                    is_duplicate = True
                    break

            # If no duplicate was found after checking the entire existing bank, add the question
            if not is_duplicate:
                df_existing = pd.concat([df_existing, pd.DataFrame([row_reviewed])], ignore_index=True)
                added_count += 1

        return added_count, df_existing

    def update_bank_with_exam(
            self,
            bank_path: str,
            exam_path: str,
            exam_label: Optional[str] = None,
            match_columns: Optional[List[str]] = None
    ) -> Tuple[int, Optional[pd.DataFrame]]:
        """Marks, in an existing question bank, the questions used in an already generated exam.

        This complements the on-the-fly usage tracking done during exam generation: given a bank XLSX
        and an exam file (typically the ``*_completo.xlsx`` produced by the generator), it matches the
        exam questions back to the bank by question statement, adds/updates a per-exam usage column
        (``<label>_uso``) and recomputes the aggregated ``Veces usada en examen`` column.

        Matching is done by the question statement ('Pregunta') by default because exams shuffle the
        answer order, which makes answer-based matching unreliable.

        Args:
            bank_path (str): Path to the existing question bank XLSX file.
            exam_path (str): Path to the generated exam XLSX file with the questions used.
            exam_label (Optional[str]): Label used to name the usage column. If None, the exam file name
                (without extension) is used.
            match_columns (Optional[List[str]]): Columns used to match exam questions to bank questions.
                Defaults to ['Pregunta'].

        Returns:
            Tuple[int, Optional[pd.DataFrame]]: The number of exam questions matched in the bank and the
            updated bank DataFrame. Returns (-1, None) on read errors or missing match columns.
        """
        if match_columns is None:
            match_columns = ['Pregunta']

        try:
            df_bank = pd.read_excel(bank_path)
            df_exam = pd.read_excel(exam_path)
        except FileNotFoundError:
            print("Error: Uno o ambos archivos no se encontraron.")
            return -1, None
        except Exception as e:
            print(f"Error al leer los archivos Excel: {e}")
            return -1, None

        missing = [col for col in match_columns if col not in df_bank.columns or col not in df_exam.columns]
        if missing:
            print(f"Error: faltan columnas para emparejar en el banco o el examen: {missing}")
            return -1, None

        # Build the usage column name from the provided label (or the exam file name).
        label = (exam_label or '').strip() or os.path.splitext(os.path.basename(exam_path))[0]
        safe_label = re.sub(r'[^a-zA-Z0-9_]', '_', label)
        usage_column_name = f'{safe_label}_uso'
        if usage_column_name not in df_bank.columns:
            df_bank[usage_column_name] = 0

        def _normalize(series: pd.Series) -> pd.Series:
            return series.astype(str).str.strip()

        matched_count = 0
        for _, exam_row in df_exam.iterrows():
            mask = pd.Series(True, index=df_bank.index)
            for col in match_columns:
                mask &= _normalize(df_bank[col]) == str(exam_row[col]).strip()
            matching_index = df_bank.index[mask]
            if len(matching_index) > 0:
                df_bank.loc[matching_index, usage_column_name] = 1
                matched_count += 1

        # Recompute the aggregated usage column from every per-exam '_uso' column.
        usage_columns = [col for col in df_bank.columns if col.endswith('_uso')]
        if usage_columns:
            df_bank['Veces usada en examen'] = df_bank[usage_columns].sum(axis=1)

        # Keep 'Veces usada en examen' right after 'Texto relevante' for readability, mirroring the
        # column layout used by the exam generator.
        if 'Veces usada en examen' in df_bank.columns and 'Texto relevante' in df_bank.columns:
            usage_aggregate = df_bank.pop('Veces usada en examen')
            try:
                texto_relevante_idx = df_bank.columns.get_loc('Texto relevante')
                df_bank.insert(texto_relevante_idx + 1, 'Veces usada en examen', usage_aggregate)
            except KeyError:
                df_bank['Veces usada en examen'] = usage_aggregate

        df_bank = df_bank.loc[:, ~df_bank.columns.str.contains('unnamed', case=False)]
        return matched_count, df_bank

    def save_dataframe_to_excel(
            self,
            df: pd.DataFrame,
            filepath: str,
            overwrite: bool = True,
            new_suffix: str = '_actualizado'
    ) -> Optional[str]:
        """
        Saves a pandas DataFrame to an Excel file.

        Args:
            df (pd.DataFrame): The DataFrame to save.
            filepath (str): The destination Excel file path.
            overwrite (bool, optional): If True, overwrites the existing file.
                                         If False, saves to a new file with a suffix.
                                         Defaults to True.
            new_suffix (str, optional): The suffix to add to the filename if
                                         overwrite is False. Defaults to '_actualizado'.

        Returns:
            Optional[str]: The path of the file where the data was saved, or None if there was an error.
        """
        try:
            if overwrite:
                df.to_excel(filepath, index=False)
                return filepath
            else:
                base, ext = os.path.splitext(filepath)
                new_filepath = f"{base}{new_suffix}{ext}"
                df.to_excel(new_filepath, index=False)
                return new_filepath
        except Exception as e:
            print(f"Error al guardar el archivo Excel: {e}")
            return None

    def generate_excel_from_docx(
            self,
            docx_path: str,
            excel_output_filename: str,
            output_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        Generates an XLSX file from a revised DOCX file. This is a convenience
        wrapper around `read_questions_from_docx` and `save_questions_to_excel`.

        Args:
            docx_path (str): The path to the input DOCX file.
            excel_output_filename (str): The filename for the output XLSX file.
            output_dir (Optional[str]): The directory to save the output file.
                                    If None, saves it in the same directory as the input docx_path.

        Returns:
            Optional[str]: The path to the saved XLSX file if the operation is successful, otherwise None.
        """

        if output_dir is None:
            output_dir = os.path.dirname(docx_path)

        os.makedirs(output_dir, exist_ok=True)

        full_output_path = os.path.join(output_dir, excel_output_filename)

        df_from_docx: Optional[pd.DataFrame] = self.read_questions_from_docx(docx_path)
        if df_from_docx is not None:
            saved_path = self.save_dataframe_to_excel(df_from_docx, full_output_path, overwrite=True)
            if saved_path:
                print(f"Archivo Excel generado en: {saved_path}")
                return saved_path
        else:
            print("No se pudo leer el archivo DOCX o no se generó el DataFrame.")
        return None

    def add_reviewed_questions_to_existing_excel(
            self,
            existing_excel_path: str,
            reviewed_excel_path: str
    ) -> Optional[str]:
        """
        Adds questions from a reviewed XLSX file to another existing XLSX file,
        avoiding duplication. This is a high-level wrapper function.

        Args:
            existing_excel_path (str): The path to the existing question bank XLSX file.
            reviewed_excel_path (str): The path to the XLSX file containing the revised questions.

        Returns:
            Optional[str]: The path to the updated XLSX file if the operation is successful, otherwise None.
        """
        added_count, updated_df = self.add_questions_without_duplicates(
            existing_excel_path, reviewed_excel_path
        )

        if added_count >= 0:
            print(f"Se añadieron {added_count} preguntas sin duplicados.")
            # Save the updated DataFrame to a new file
            save_path: str = "banco_de_preguntas_actualizado.xlsx"
            self.save_dataframe_to_excel(updated_df, save_path, overwrite=False)
            print(f"Banco de preguntas actualizado guardado en: {save_path}")
            return save_path
        else:
            print("Ocurrió un error al añadir las preguntas.")
        return None

## Example of QuestionBankManager usage

# # Create an instance of the class
# manager = QuestionBankManager()
#
# # Example usage: Generate Excel from DOCX
# docx_file = "preguntas_revisadas.docx"  # Replace with your DOCX file
# excel_file = "preguntas_generadas.xlsx"
# generated_excel_path = manager.generate_excel_from_docx(docx_file, excel_file)
# if generated_excel_path:
#     print(f"Archivo Excel generado: {generated_excel_path}")
#
# # Example usage: Add questions to an existing Excel
# existing_excel = "banco_existente.xlsx"  # Replace with your existing Excel file
# reviewed_excel = "preguntas_generadas.xlsx"  # Using the previously generated file
# updated_excel_path = manager.add_reviewed_questions_to_existing_excel(
#     existing_excel, reviewed_excel
# )
# if updated_excel_path:
#     print(f"Archivo Excel actualizado: {updated_excel_path}")