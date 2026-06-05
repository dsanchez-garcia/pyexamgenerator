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
import unicodedata
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

    @staticmethod
    def _strip_accents(text: str) -> str:
        """Removes diacritics from ``text`` (á→a, é→e, ñ→n, ü→u, ...).

        Used before building safe column names so accented letters are kept as their base
        letter instead of being turned into underscores by the ``[^a-zA-Z0-9_]`` sanitizer.
        """
        normalized = unicodedata.normalize('NFKD', str(text))
        return ''.join(ch for ch in normalized if not unicodedata.combining(ch))

    @classmethod
    def _usage_column_name(cls, exam_label: Optional[str], exam_path: str) -> str:
        """Builds the per-exam usage column name (``<label>_uso``) from a label or the file name.

        Accents are stripped first so e.g. 'Evaluación' becomes 'Evaluacion' (not 'Evaluaci_n').
        """
        label = (exam_label or '').strip() or os.path.splitext(os.path.basename(exam_path))[0]
        label = cls._strip_accents(label)
        safe_label = re.sub(r'[^a-zA-Z0-9_]', '_', label)
        return f'{safe_label}_uso'

    @staticmethod
    def _resolve_parts_indices(num_tokens: int, parts) -> List[int]:
        """Resolves a "parts" selection into a list of 0-based token indices, in the requested order.

        ``parts`` may be:
            - a list/tuple/iterable of ints: each is a **1-based** index; negative values count
              from the end (-1 = last token);
            - a string spec: comma-separated items, each either a single 1-based index ``n`` or an
              inclusive range ``a:b`` (both 1-based, negatives allowed), e.g. ``"2:-2, 4, 8:10"``.

        Indices that fall outside ``[0, num_tokens)`` after resolution are dropped by the caller.
        Index ``0`` is invalid in 1-based numbering and is ignored.
        """
        def to_zero_based(n: int) -> Optional[int]:
            if n > 0:
                return n - 1
            if n < 0:
                return num_tokens + n
            return None  # 0 is meaningless in 1-based numbering.

        indices: List[int] = []
        if isinstance(parts, str):
            for raw in (item.strip() for item in parts.split(',')):
                if not raw:
                    continue
                if ':' in raw:
                    start_str, end_str = raw.split(':', 1)
                    try:
                        start, end = int(start_str.strip()), int(end_str.strip())
                    except ValueError:
                        continue
                    start_idx, end_idx = to_zero_based(start), to_zero_based(end)
                    if start_idx is None or end_idx is None:
                        continue
                    step = 1 if end_idx >= start_idx else -1
                    indices.extend(range(start_idx, end_idx + step, step))
                else:
                    try:
                        n = int(raw)
                    except ValueError:
                        continue
                    idx = to_zero_based(n)
                    if idx is not None:
                        indices.append(idx)
        else:
            for item in parts:
                try:
                    n = int(item)
                except (ValueError, TypeError):
                    continue
                idx = to_zero_based(n)
                if idx is not None:
                    indices.append(idx)
        return indices

    @classmethod
    def label_from_filename(
            cls,
            path: str,
            delimiter: Optional[str] = None,
            parts=None,
            join_with: str = '_',
    ) -> str:
        """Derives a label from a file name by splitting it and keeping selected parts.

        Splits the base name (without extension) of ``path`` by ``delimiter`` and keeps the tokens
        selected by ``parts`` (see :meth:`_resolve_parts_indices`), joined with ``join_with``.

        If ``delimiter`` is falsy or ``parts`` is ``None``/empty, the full base name is returned, so
        the default behaviour (no splitting) keeps the whole file name as the label.

        Example::

            label_from_filename(
                "examen_Prevencion_Industrial_de_Riesgos_25_26_1A_completo.xlsx",
                delimiter="_", parts="2:3, -3:-1",
            )  # -> "Prevencion_Industrial_25_26_1A"
        """
        base = os.path.splitext(os.path.basename(path))[0]
        if not delimiter or parts is None or (isinstance(parts, str) and not parts.strip()):
            return base
        tokens = base.split(delimiter)
        if not tokens:
            return base
        indices = cls._resolve_parts_indices(len(tokens), parts)
        selected = [tokens[i] for i in indices if 0 <= i < len(tokens)]
        return join_with.join(selected) if selected else base

    def _mark_exam_usage(
            self,
            df_bank: pd.DataFrame,
            df_exam: pd.DataFrame,
            usage_column_name: str,
            match_columns: List[str],
    ) -> Tuple[pd.DataFrame, int]:
        """Flags, in ``df_bank``, the rows used by ``df_exam`` under ``usage_column_name``.

        Returns the (possibly mutated) bank DataFrame and the number of exam questions matched.
        """
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
        return df_bank, matched_count

    @staticmethod
    def _recompute_usage_aggregate(df_bank: pd.DataFrame) -> pd.DataFrame:
        """Recomputes 'Veces usada en examen' from every per-exam '_uso' column and tidies columns."""
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

        return df_bank.loc[:, ~df_bank.columns.str.contains('unnamed', case=False)]

    @staticmethod
    def _normalize_exam_specs(exams) -> List[Tuple[str, Optional[str]]]:
        """Normalizes a heterogeneous list of exam specs into ``[(path, label), ...]``.

        Each item of ``exams`` may be:
            - a plain path string (no label);
            - a ``(path, label)`` tuple/list (label optional);
            - a dict with ``path``/``exam_path`` and ``label``/``exam_label`` keys.

        Items without a usable path are skipped. Blank labels are normalized to ``None``.
        """
        if not exams:
            return []
        normalized: List[Tuple[str, Optional[str]]] = []
        for item in exams:
            if isinstance(item, dict):
                path = item.get("path") or item.get("exam_path")
                label = item.get("label") or item.get("exam_label")
            elif isinstance(item, (tuple, list)):
                path = item[0] if len(item) >= 1 else None
                label = item[1] if len(item) >= 2 else None
            else:
                path, label = item, None
            if not path:
                continue
            clean_label = str(label).strip() if label is not None else ""
            normalized.append((str(path), clean_label or None))
        return normalized

    def update_bank_with_exam(
            self,
            bank_path: str,
            exam_path: str,
            exam_label: Optional[str] = None,
            match_columns: Optional[List[str]] = None,
            label_delimiter: Optional[str] = None,
            label_parts=None,
    ) -> Tuple[int, Optional[pd.DataFrame]]:
        """Marks, in an existing question bank, the questions used in an already generated exam.

        This complements the on-the-fly usage tracking done during exam generation: given a bank XLSX
        and an exam file (typically the ``*_completo.xlsx`` produced by the generator), it matches the
        exam questions back to the bank by question statement, adds/updates a per-exam usage column
        (``<label>_uso``) and recomputes the aggregated ``Veces usada en examen`` column.

        Matching is done by the question statement ('Pregunta') by default because exams shuffle the
        answer order, which makes answer-based matching unreliable.

        To register several exams at once (each with its own label) in a single pass, use
        :meth:`update_bank_with_exams`.

        Args:
            bank_path (str): Path to the existing question bank XLSX file.
            exam_path (str): Path to the generated exam XLSX file with the questions used.
            exam_label (Optional[str]): Label used to name the usage column. If None/blank, the label is
                derived from the exam file name (optionally split with ``label_delimiter``/``label_parts``).
                Accents in the label are stripped when building the column name (e.g. 'Evaluación' ->
                'Evaluacion'), so they are not turned into underscores.
            match_columns (Optional[List[str]]): Columns used to match exam questions to bank questions.
                Defaults to ['Pregunta'].
            label_delimiter (Optional[str]): Delimiter used to split the file name when deriving the label
                (only used when ``exam_label`` is None/blank). See :meth:`label_from_filename`.
            label_parts: Parts of the split file name to keep as the label. See
                :meth:`label_from_filename` and :meth:`_resolve_parts_indices`.

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

        effective_label = (exam_label or '').strip() or self.label_from_filename(
            exam_path, label_delimiter, label_parts
        )
        usage_column_name = self._usage_column_name(effective_label, exam_path)
        df_bank, matched_count = self._mark_exam_usage(df_bank, df_exam, usage_column_name, match_columns)
        df_bank = self._recompute_usage_aggregate(df_bank)
        return matched_count, df_bank

    def update_bank_with_exams(
            self,
            bank_path: str,
            exams,
            match_columns: Optional[List[str]] = None,
            label_delimiter: Optional[str] = None,
            label_parts=None,
    ) -> Tuple[int, Optional[pd.DataFrame], dict]:
        """Registers the usage of **several** generated exams in a question bank in a single pass.

        This is the multi-exam counterpart of :meth:`update_bank_with_exam`. The bank is read once and
        each exam is matched back to it (by ``match_columns``, ['Pregunta'] by default), getting its own
        per-exam usage column ``<label>_uso``. After processing every exam, the aggregated
        ``Veces usada en examen`` column is recomputed from all the ``_uso`` columns.

        Per-exam read errors (or missing match columns in an exam) are reported in the returned ``stats``
        and skipped, so a single bad exam does not abort the rest. A failure to read the **bank** itself,
        or missing match columns in the bank, is a hard error that returns ``(-1, None, stats)``.

        Args:
            bank_path (str): Path to the existing question bank XLSX file.
            exams: Iterable of exam specs. Each item may be a path string, a ``(path, label)``
                tuple/list, or a dict with ``path``/``exam_path`` and ``label``/``exam_label`` keys.
                If two exams resolve to the same label, they share the same ``_uso`` column.
            match_columns (Optional[List[str]]): Columns used to match exam questions to bank questions.
                Defaults to ['Pregunta'].
            label_delimiter (Optional[str]): Default delimiter to split file names when an exam has no
                explicit label, used together with ``label_parts``. See :meth:`label_from_filename`.
            label_parts: Default parts of the split file name to keep as the label for exams without an
                explicit label. See :meth:`label_from_filename` and :meth:`_resolve_parts_indices`.

        Returns:
            Tuple[int, Optional[pd.DataFrame], dict]: The total number of exam questions matched across
            all exams, the updated bank DataFrame, and a stats dict::

                {
                    "exams": [{"path", "label", "column", "matched"}, ...],  # processed exams
                    "total_matched": int,
                    "errors": [{"path", "error"}, ...],                      # skipped exams
                }

            Returns ``(-1, None, stats)`` on bank read errors or missing match columns in the bank.
        """
        if match_columns is None:
            match_columns = ['Pregunta']

        specs = self._normalize_exam_specs(exams)
        stats: dict = {"exams": [], "total_matched": 0, "errors": []}
        if not specs:
            print("Error: no se proporcionó ningún examen para actualizar el banco.")
            return -1, None, stats

        try:
            df_bank = pd.read_excel(bank_path)
        except FileNotFoundError:
            print("Error: no se encontró el banco de preguntas.")
            return -1, None, stats
        except Exception as e:
            print(f"Error al leer el banco de preguntas: {e}")
            return -1, None, stats

        missing_bank = [col for col in match_columns if col not in df_bank.columns]
        if missing_bank:
            print(f"Error: faltan columnas para emparejar en el banco: {missing_bank}")
            return -1, None, stats

        total_matched = 0
        for exam_path, exam_label in specs:
            try:
                df_exam = pd.read_excel(exam_path)
            except FileNotFoundError:
                print(f"Advertencia: no se encontró el examen '{exam_path}'. Se omite.")
                stats["errors"].append({"path": exam_path, "error": "archivo no encontrado"})
                continue
            except Exception as e:  # noqa: BLE001 - report and continue with the rest of the exams.
                print(f"Advertencia: no se pudo leer el examen '{exam_path}': {e}. Se omite.")
                stats["errors"].append({"path": exam_path, "error": str(e)})
                continue

            missing = [col for col in match_columns if col not in df_exam.columns]
            if missing:
                print(f"Advertencia: al examen '{exam_path}' le faltan columnas {missing}. Se omite.")
                stats["errors"].append({"path": exam_path, "error": f"faltan columnas {missing}"})
                continue

            effective_label = (exam_label or '').strip() or self.label_from_filename(
                exam_path, label_delimiter, label_parts
            )
            usage_column_name = self._usage_column_name(effective_label, exam_path)
            df_bank, matched = self._mark_exam_usage(df_bank, df_exam, usage_column_name, match_columns)
            total_matched += matched
            stats["exams"].append({
                "path": exam_path,
                "label": effective_label,
                "column": usage_column_name,
                "matched": matched,
            })

        df_bank = self._recompute_usage_aggregate(df_bank)
        stats["total_matched"] = total_matched
        return total_matched, df_bank, stats

    @staticmethod
    def _normalize_text(value: object) -> str:
        """Normalizes a cell for duplicate comparison: NaN -> '', trim, lowercase, collapse spaces."""
        if pd.isna(value):
            return ""
        return re.sub(r"\s+", " ", str(value).strip().lower())

    @classmethod
    def _question_dedup_key(
            cls,
            row: pd.Series,
            statement_only: bool,
            statement_column: str,
            answer_columns: List[str],
    ):
        """Builds the duplicate key for a question row.

        With ``statement_only`` the key is just the normalized statement. Otherwise the key also
        includes the *set* of normalized answers, so the same statement with different answer
        options is treated as a distinct question, while a mere reordering of identical answers is
        treated as the same question.
        """
        statement = cls._normalize_text(row.get(statement_column, ""))
        if statement_only:
            return statement
        answers = frozenset(
            cls._normalize_text(row.get(col, "")) for col in answer_columns
            if cls._normalize_text(row.get(col, "")) != ""
        )
        return statement, answers

    def unify_question_banks(
            self,
            bank_paths: List[str],
            output_path: Optional[str] = None,
            duplicate_criterion: str = "enunciado_y_respuestas",
            statement_column: str = "Pregunta",
            answer_columns: Optional[List[str]] = None,
            save: bool = True,
    ) -> Tuple[Optional[pd.DataFrame], dict]:
        """Unifies several question banks into one, removing duplicates by the chosen criterion.

        Reads every bank in ``bank_paths`` (in order), concatenates them and removes duplicate
        questions keeping the **first** occurrence (so order the paths by priority: the first bank
        wins when a question appears in several).

        Args:
            bank_paths (List[str]): Paths of the bank XLSX files to unify (at least one).
            output_path (Optional[str]): Where to save the unified bank. If None or ``save`` is
                False, nothing is written and only the DataFrame/stats are returned.
            duplicate_criterion (str): Criterion to detect duplicates. Accepts two vocabularies:
                - ``"enunciado"`` / ``"pregunta_unica"``: same statement -> duplicate (answers ignored).
                - ``"enunciado_y_respuestas"`` / ``"pregunta_respuestas"``: duplicate only if the
                  statement **and** the set of answers match; same statement with different answers
                  is kept as a distinct question. (Default.)
            statement_column (str): Column holding the question statement. Defaults to 'Pregunta'.
            answer_columns (Optional[List[str]]): Answer columns compared as a set. Defaults to
                ['Respuesta A', 'Respuesta B', 'Respuesta C', 'Respuesta D'].
            save (bool): If True and ``output_path`` is given, writes the unified bank to disk.

        Returns:
            Tuple[Optional[pd.DataFrame], dict]: The unified DataFrame (None if nothing could be read)
            and a stats dict with per-bank counts, totals, duplicates removed and any read errors.
        """
        if not bank_paths:
            raise ValueError("Se requiere al menos un banco de preguntas para unificar.")

        statement_only_aliases = {"enunciado", "pregunta_unica"}
        full_aliases = {"enunciado_y_respuestas", "pregunta_respuestas"}
        criterion = str(duplicate_criterion).strip().lower()
        if criterion in statement_only_aliases:
            statement_only = True
        elif criterion in full_aliases:
            statement_only = False
        else:
            raise ValueError(
                f"Criterio de duplicado desconocido: '{duplicate_criterion}'. Use 'enunciado' "
                f"(solo enunciado) o 'enunciado_y_respuestas' (enunciado + respuestas)."
            )

        if answer_columns is None:
            answer_columns = ['Respuesta A', 'Respuesta B', 'Respuesta C', 'Respuesta D']

        frames: List[pd.DataFrame] = []
        stats: dict = {
            "criterion": "enunciado" if statement_only else "enunciado_y_respuestas",
            "banks": [],
            "total_read": 0,
            "unified": 0,
            "duplicates_removed": 0,
            "errors": [],
        }

        for path in bank_paths:
            try:
                df_bank = pd.read_excel(path)
            except Exception as e:  # noqa: BLE001 - report and continue with the rest of the banks.
                print(f"Advertencia: no se pudo leer '{path}': {e}")
                stats["errors"].append({"path": path, "error": str(e)})
                continue
            stats["banks"].append({"path": path, "rows": int(len(df_bank))})
            stats["total_read"] += int(len(df_bank))
            frames.append(df_bank)

        if not frames:
            print("No se pudo leer ningún banco de preguntas.")
            return None, stats

        combined = pd.concat(frames, ignore_index=True)

        seen = set()
        keep_indices: List[int] = []
        duplicates_removed = 0
        for idx, row in combined.iterrows():
            key = self._question_dedup_key(row, statement_only, statement_column, answer_columns)
            if key in seen:
                duplicates_removed += 1
                continue
            seen.add(key)
            keep_indices.append(idx)

        unified_df = combined.loc[keep_indices].reset_index(drop=True)
        unified_df = unified_df.loc[:, ~unified_df.columns.str.contains('unnamed', case=False)]

        stats["unified"] = int(len(unified_df))
        stats["duplicates_removed"] = int(duplicates_removed)

        if save and output_path:
            saved = self.save_dataframe_to_excel(unified_df, output_path, overwrite=True)
            stats["output_path"] = saved
            if saved:
                print(
                    f"Banco unificado guardado en '{saved}': {stats['unified']} preguntas "
                    f"({stats['duplicates_removed']} duplicados eliminados de {stats['total_read']} leídas)."
                )

        return unified_df, stats

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