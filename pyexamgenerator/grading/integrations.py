import os
from pathlib import Path
import re
import unicodedata
from typing import Iterable, List, Optional, Tuple

import pandas as pd


class MoodleGradeIntegrator:
    def __init__(
        self,
        xlsx_files: Optional[Iterable[str]] = None,
        group_types: Iterable[str] = (),
        sheet: int = 0,
        id_col: str = "Número de ID",
        first_name_col: str = "Nombre",
        last_name_col: str = "Apellido(s)",
        total_grade_col: str = "Calificación/10,00",
        **legacy_kwargs,
    ):
        """Integrates multiple Moodle grade exports into a single table."""
        if xlsx_files is None:
            xlsx_files = legacy_kwargs.pop("archivos_xlsx", None)
        if not group_types:
            group_types = legacy_kwargs.pop("tipos", group_types)
        if legacy_kwargs:
            raise TypeError(f"Unexpected arguments: {sorted(legacy_kwargs.keys())}")

        self.xlsx_files = list(xlsx_files or [])
        self.group_types = [str(t).strip() for t in (group_types or []) if str(t).strip()]
        self.sheet = sheet
        self.id_col = id_col
        self.first_name_col = first_name_col
        self.last_name_col = last_name_col
        self.total_grade_col = total_grade_col

        self._validate_paths()

    @staticmethod
    def _matches_group_type(filename: str, group_type: str) -> bool:
        name = os.path.basename(filename).upper()
        group_type = str(group_type).strip().upper()
        if not group_type:
            return False
        pattern = rf"(?<![A-Z0-9]){re.escape(group_type)}(?![A-Z0-9])"
        return re.search(pattern, name) is not None

    @classmethod
    def build_paths_from_list_and_types(cls, xlsx_files: Iterable[str], group_types: Iterable[str]) -> List[str]:
        files = [str(f).strip() for f in xlsx_files if str(f).strip()]
        types = [str(t).strip() for t in group_types if str(t).strip()]

        if not files:
            raise ValueError("You must provide a non-empty XLSX file list.")
        if not types:
            raise ValueError("You must provide at least one group type (e.g. 1A, 1B, 2A, 2B).")

        path_by_type = {}
        for group_type in types:
            matches = [
                path for path in files
                if cls._matches_group_type(os.path.basename(path), group_type)
            ]
            if not matches:
                raise ValueError(f"No XLSX found for group type '{group_type}'.")
            if len(matches) > 1:
                details = "\n".join(f"- {path}" for path in matches)
                raise ValueError(
                    f"Group type '{group_type}' matches multiple files:\n{details}\n"
                    "Refine filenames or pass a more specific list."
                )
            path_by_type[group_type] = matches[0]

        return [path_by_type[group_type] for group_type in types]

    @staticmethod
    def build_paths_from_template(template_1a_path: str, group_types: Iterable[str]) -> List[str]:
        group_types = list(group_types)
        if not group_types:
            raise ValueError("You must provide at least one group type (e.g. 1A, 1B, 2A, 2B).")

        base_name = os.path.basename(template_1a_path)
        match = re.search(r"-\s*([^-]+)-calificaciones\.xlsx$", base_name, re.IGNORECASE)
        if not match:
            raise ValueError(
                "Could not detect group type in template filename. "
                "Expected format: '... - 1A-calificaciones.xlsx'."
            )

        original_type = match.group(1).strip()
        directory = os.path.dirname(template_1a_path)

        paths = []
        for group_type in group_types:
            new_name = base_name.replace(f"- {original_type}-calificaciones.xlsx", f"- {group_type}-calificaciones.xlsx")
            paths.append(os.path.join(directory, new_name))
        return paths

    def _validate_paths(self):
        if not self.xlsx_files:
            raise ValueError("No XLSX files were provided for integration.")

        missing = [path for path in self.xlsx_files if not os.path.exists(path)]
        if missing:
            details = "\n".join(f"- {path}" for path in missing)
            raise FileNotFoundError(f"Missing files:\n{details}")

    def _extract_group_type_from_filename(self, file_path: str) -> str:
        if self.group_types:
            matches = [group_type for group_type in self.group_types if self._matches_group_type(file_path, group_type)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                return "AMBIGUOUS"

        name = os.path.basename(file_path)
        match = re.search(r"-\s*([^-]+)-calificaciones\.xlsx$", name, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "UNKNOWN"

    @staticmethod
    def _parse_grade(grade) -> float:
        if pd.isna(grade):
            return 0.0

        grade_str = str(grade).strip().replace(",", ".")
        try:
            return float(grade_str)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_quiz_total_column(column_name: str) -> Optional[Tuple[str, str]]:
        text = str(column_name).strip()
        match = re.match(r"^Cuestionario:(.+?)_Tipo\s*([0-9]*[A-Z])\s*\(Real\)$", text, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip(), match.group(2).strip().upper()

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = str(text).strip().lower()
        return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")

    @classmethod
    def _find_column(cls, columns: List[str], candidates: Iterable[str]) -> Optional[str]:
        normalized_map = {cls._normalize_text(c).replace(" ", ""): c for c in columns}
        for candidate in candidates:
            key = cls._normalize_text(candidate).replace(" ", "")
            if key in normalized_map:
                return normalized_map[key]
        return None

    def _is_grade_column(self, column_name: str) -> bool:
        column_norm = self._normalize_text(column_name)
        if column_norm.startswith("calificacion/"):
            return True
        if self._parse_quiz_total_column(column_name) is not None:
            return True
        return re.match(r"^p\.\s*\d+\s*/", column_norm) is not None

    @staticmethod
    def _to_float_grade(value):
        if pd.isna(value):
            return pd.NA
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if text in {"", "-"}:
            return pd.NA

        text = text.replace(",", ".")
        if re.fullmatch(r"[-+]?\d+(\.\d+)?", text):
            return float(text)
        return pd.NA

    def _convert_grade_columns_to_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        grade_columns = [col for col in df.columns if self._is_grade_column(col)]

        for col in grade_columns:
            df[col] = df[col].apply(self._to_float_grade)
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _contains_summary_word(text: str) -> bool:
        text = str(text).strip().lower()
        words = ("promedio", "media", "resumen", "total", "general")
        return any(word in text for word in words)

    def _is_moodle_summary_row(self, row: pd.Series) -> bool:
        id_value = row.get(self.id_col, None)
        id_text = "" if pd.isna(id_value) else str(id_value).strip().lower()

        first_name_text = str(row.get(self.first_name_col, "")).strip().lower()
        last_name_text = str(row.get(self.last_name_col, "")).strip().lower()
        combined = f"{id_text} {first_name_text} {last_name_text}".strip()

        has_summary_marker = self._contains_summary_word(combined)
        id_empty = pd.isna(id_value) or str(id_value).strip() == ""
        id_has_no_digits = (not id_empty) and re.search(r"\d", str(id_value)) is None

        return has_summary_marker and (id_empty or id_has_no_digits)

    def _is_exam_totals_format(self, df: pd.DataFrame) -> bool:
        cols = list(df.columns)
        has_total_columns = any(self._parse_quiz_total_column(c) is not None for c in cols)
        first_name_col = self._find_column(cols, ["Nombre"])
        last_name_col = self._find_column(cols, ["Apellido(s)", "Apellidos", "Apellido"])
        return has_total_columns and first_name_col is not None and last_name_col is not None

    def _normalize_exam_totals_file(self, df: pd.DataFrame, file_path: str) -> pd.DataFrame:
        columns = list(df.columns)
        id_source_col = self._find_column(columns, ["Número de ID", "Nmero de ID", "ID", "Nombre de usuario"])
        first_name_source_col = self._find_column(columns, ["Nombre"])
        last_name_source_col = self._find_column(columns, ["Apellido(s)", "Apellidos", "Apellido"])
        email_source_col = self._find_column(columns, ["Dirección de correo", "Direccin de correo", "Email", "Correo"])

        quiz_columns = []
        for col in columns:
            parsed = self._parse_quiz_total_column(col)
            if parsed is None:
                continue
            group_name, exam_type = parsed
            quiz_columns.append((col, group_name, exam_type))

        if first_name_source_col is None or last_name_source_col is None or not quiz_columns:
            raise ValueError(
                f"File '{file_path}' does not have expected columns for exam totals format."
            )

        normalized_rows = []
        for _, row in df.iterrows():
            best_grade = pd.NA
            best_exam_type = ""
            best_group = ""

            for col, group_name, exam_type in quiz_columns:
                grade_val = self._to_float_grade(row.get(col, ""))
                if pd.isna(grade_val):
                    continue
                if pd.isna(best_grade) or float(grade_val) > float(best_grade):
                    best_grade = float(grade_val)
                    best_exam_type = exam_type
                    best_group = group_name

            normalized_rows.append(
                {
                    self.id_col: "" if id_source_col is None else str(row.get(id_source_col, "")).strip(),
                    self.first_name_col: str(row.get(first_name_source_col, "")).strip(),
                    self.last_name_col: str(row.get(last_name_source_col, "")).strip(),
                    "Dirección de correo": "" if email_source_col is None else str(row.get(email_source_col, "")).strip(),
                    self.total_grade_col: "-" if pd.isna(best_grade) else f"{float(best_grade):.2f}".replace(".", ","),
                    "Tipo_Grupo": best_group,
                    "Tipo_Examen": best_exam_type,
                    "Archivo_Origen": os.path.basename(file_path),
                }
            )

        return pd.DataFrame(normalized_rows)

    def _normalize_legacy_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        rename_map = {}
        cols = list(df.columns)

        id_col = self._find_column(cols, [self.id_col, "Número de ID", "Nmero de ID", "ID", "Nombre de usuario"])
        if id_col and id_col != self.id_col:
            rename_map[id_col] = self.id_col

        first_col = self._find_column(cols, [self.first_name_col, "Nombre"])
        if first_col and first_col != self.first_name_col:
            rename_map[first_col] = self.first_name_col

        last_col = self._find_column(cols, [self.last_name_col, "Apellido(s)", "Apellidos", "Apellido"])
        if last_col and last_col != self.last_name_col:
            rename_map[last_col] = self.last_name_col

        total_col = self._find_column(cols, [self.total_grade_col, "Calificación/10,00", "Calificacin/10,00"])
        if total_col and total_col != self.total_grade_col:
            rename_map[total_col] = self.total_grade_col

        return df.rename(columns=rename_map)

    def _load_file(self, file_path: str) -> pd.DataFrame:
        df = pd.read_excel(file_path, sheet_name=self.sheet)

        if self._is_exam_totals_format(df):
            df = self._normalize_exam_totals_file(df, file_path)
            if self.total_grade_col in df.columns:
                df["_Numeric_Grade"] = df[self.total_grade_col].apply(self._parse_grade)
            else:
                df["_Numeric_Grade"] = 0.0
            return self._convert_grade_columns_to_numeric(df)

        df = self._normalize_legacy_columns(df)

        required_cols = {self.id_col, self.first_name_col, self.last_name_col}
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"File '{file_path}' is missing required columns: {missing}")

        df = df.copy()

        summary_mask = df.apply(self._is_moodle_summary_row, axis=1)
        dropped_count = int(summary_mask.sum())
        if dropped_count > 0:
            print(f"Notice: dropped {dropped_count} summary row(s) in '{os.path.basename(file_path)}'.")
        df = df.loc[~summary_mask].copy()

        df["Tipo_Grupo"] = self._extract_group_type_from_filename(file_path)
        df["Archivo_Origen"] = os.path.basename(file_path)

        if self.total_grade_col in df.columns:
            df["_Numeric_Grade"] = df[self.total_grade_col].apply(self._parse_grade)
        else:
            df["_Numeric_Grade"] = 0.0

        return df

    def integrate_grades(self, deduplicate_by_id: bool = False) -> pd.DataFrame:
        dataframes = [self._load_file(path) for path in self.xlsx_files]
        merged_df = pd.concat(dataframes, ignore_index=True)

        if deduplicate_by_id:
            merged_df = merged_df.sort_values("_Numeric_Grade", ascending=False)
            merged_df = merged_df.drop_duplicates(subset=[self.id_col], keep="first")

        merged_df = merged_df.sort_values([self.last_name_col, self.first_name_col], na_position="last")
        merged_df = merged_df.drop(columns=["_Numeric_Grade"], errors="ignore")
        return self._convert_grade_columns_to_numeric(merged_df)

    def integrate_and_export(
        self,
        output_path: str,
        deduplicate_by_id: bool = False,
        output_dir: Optional[str] = None,
        **legacy_kwargs,
    ) -> pd.DataFrame:
        if "deduplicar_por_id" in legacy_kwargs:
            deduplicate_by_id = bool(legacy_kwargs.pop("deduplicar_por_id"))
        if legacy_kwargs:
            raise TypeError(f"Unexpected arguments: {sorted(legacy_kwargs.keys())}")
        if output_dir:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / Path(output_path).name)
        final_df = self.integrate_grades(deduplicate_by_id=deduplicate_by_id)
        final_df.to_excel(output_path, index=False)
        print(f"OK: integration completed. Output saved to: {output_path}")
        return final_df


# Backward-compatible alias
IntegradorCalificacionesMoodle = MoodleGradeIntegrator
MoodleGradeIntegrator.construir_rutas_desde_lista_y_tipos = staticmethod(MoodleGradeIntegrator.build_paths_from_list_and_types)
MoodleGradeIntegrator.construir_rutas_desde_plantilla = staticmethod(MoodleGradeIntegrator.build_paths_from_template)
MoodleGradeIntegrator.integrar = MoodleGradeIntegrator.integrate_grades
MoodleGradeIntegrator.integrar_y_exportar = MoodleGradeIntegrator.integrate_and_export




# OCR overlay integration

import argparse
from pathlib import Path
import re
import unicodedata
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from pyexamgenerator.grading.data import build_merged_enrollment_from_sources


class OcrGradeIntegrator:
    """Integrates OCR grades into a general Moodle-grade workbook while preserving structure."""

    def __init__(
        self,
        general_xlsx_path: Optional[str] = None,
        ocr_xlsx_path: Optional[str] = None,
        enrollment_paths: Optional[Sequence[str]] = None,
        enrollment_sheet: int = 0,
        **legacy_kwargs,
    ) -> None:
        if general_xlsx_path is None:
            general_xlsx_path = legacy_kwargs.pop("xlsx_general_path", None)
        if ocr_xlsx_path is None:
            ocr_xlsx_path = legacy_kwargs.pop("xlsx_ocr_path", None)
        if legacy_kwargs:
            raise TypeError(f"Unexpected arguments: {sorted(legacy_kwargs.keys())}")
        if not general_xlsx_path or not ocr_xlsx_path:
            raise ValueError("Both general_xlsx_path and ocr_xlsx_path are required.")

        self.general_xlsx_path = general_xlsx_path
        self.ocr_xlsx_path = ocr_xlsx_path
        self.enrollment_paths = [str(p).strip() for p in (enrollment_paths or []) if str(p).strip()]
        self.enrollment_sheet = int(enrollment_sheet)

    @staticmethod
    def _normalize(text: str) -> str:
        text = str(text).strip().lower()
        text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]", "", text)

    @classmethod
    def _normalized_column_map(cls, columns: List[str]) -> Dict[str, str]:
        return {cls._normalize(c): c for c in columns}

    @classmethod
    def _find_column(cls, columns: List[str], normalized_candidates: List[str]) -> Optional[str]:
        col_map = cls._normalized_column_map(columns)
        for cand in normalized_candidates:
            if cand in col_map:
                return col_map[cand]
        return None

    @staticmethod
    def _is_empty(value) -> bool:
        if pd.isna(value):
            return True
        return str(value).strip() == ""

    @staticmethod
    def _normalize_id(value) -> str:
        if pd.isna(value):
            return ""
        return str(value).strip()

    @staticmethod
    def _best_grade_from_quiz_columns(row: pd.Series, quiz_columns: List[Tuple[str, str, str]]) -> Tuple[object, str, str]:
        best_grade = pd.NA
        best_group = ""
        best_exam_type = ""
        for col, group_name, exam_type in quiz_columns:
            grade_val = OcrGradeIntegrator._to_float_grade(row.get(col, ""))
            if pd.isna(grade_val):
                continue
            if pd.isna(best_grade) or float(grade_val) > float(best_grade):
                best_grade = float(grade_val)
                best_group = str(group_name).strip()
                best_exam_type = str(exam_type).strip().upper()
        return best_grade, best_group, best_exam_type

    @staticmethod
    def _to_float_grade(value):
        if pd.isna(value):
            return pd.NA
        text = str(value).strip()
        if text in {"", "-"}:
            return pd.NA
        text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return pd.NA

    @staticmethod
    def _name_match(general_row: pd.Series, ocr_row: pd.Series) -> bool:
        g_first = str(general_row.get("Nombre", "")).strip().lower()
        g_last = str(general_row.get("Apellido(s)", "")).strip().lower()
        o_first = str(ocr_row.get("Nombre", "")).strip().lower()
        o_last = str(ocr_row.get("Apellido(s)", "")).strip().lower()
        if not (g_first or g_last or o_first or o_last):
            return False
        return (g_first == o_first) and (g_last == o_last)

    @staticmethod
    def _parse_quiz_total_column(column_name: str) -> Optional[Tuple[str, str]]:
        text = str(column_name).strip()
        match = re.match(r"^Cuestionario:(.+?)_Tipo\s*([0-9]*[A-Z])\s*\(Real\)$", text, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip(), match.group(2).strip().upper()

    @classmethod
    def _find_exam_type_col(cls, ocr_cols: List[str]) -> Optional[str]:
        return cls._find_column(ocr_cols, ["tipoexamen", "tipoexamenusado", "tipo", "tipogrupo"])

    @classmethod
    def _find_total_grade_col(cls, ocr_cols: List[str]) -> Optional[str]:
        return cls._find_column(ocr_cols, ["calificacion1000", "calificacin1000", "total", "nota", "grade"])

    def _build_group_map_from_enrollment(self) -> Dict[str, str]:
        if not self.enrollment_paths:
            return {}

        merged = build_merged_enrollment_from_sources(self.enrollment_paths, sheet_name=self.enrollment_sheet)
        if merged.empty:
            return {}

        out: Dict[str, str] = {}
        for _, row in merged.iterrows():
            student_id = self._normalize_id(row.get("Número de ID", ""))
            group_name = str(row.get("Grupo_Principal", "")).strip()
            if student_id and group_name:
                out[student_id] = group_name
        return out

    @staticmethod
    def _looks_like_quiz_totals_format(columns: List[str]) -> bool:
        return any(OcrGradeIntegrator._parse_quiz_total_column(c) is not None for c in columns)

    def _resolve_target_quiz_column(
        self,
        general_row: pd.Series,
        exam_type: str,
        quizzes_by_group_type: Dict[Tuple[str, str], str],
        group_by_id: Dict[str, str],
        general_id_col: Optional[str],
        ocr_group_hint: str = "",
    ) -> Optional[str]:
        if not exam_type:
            return None

        target_exam = exam_type.strip().upper()
        available_groups = sorted({group for group, qtype in quizzes_by_group_type.keys() if qtype == target_exam})
        if not available_groups:
            return None
        if len(available_groups) == 1:
            return quizzes_by_group_type.get((available_groups[0], target_exam))

        # El grupo que viene en la propia fila OCR (p. ej. Grupo_Principal de la matrícula) es la
        # señal más fiable para desambiguar entre grupos que comparten tipo de examen (GIM vs GITI...).
        if ocr_group_hint:
            for candidate in available_groups:
                if self._normalize(candidate) == self._normalize(ocr_group_hint):
                    return quizzes_by_group_type.get((candidate, target_exam))

        if general_id_col:
            row_id = self._normalize_id(general_row.get(general_id_col, ""))
            preferred_group = group_by_id.get(row_id, "")
            if preferred_group:
                for candidate in available_groups:
                    if self._normalize(candidate) == self._normalize(preferred_group):
                        return quizzes_by_group_type.get((candidate, target_exam))

        non_empty_in_row = []
        for group in available_groups:
            col = quizzes_by_group_type.get((group, target_exam))
            if not col:
                continue
            value = general_row.get(col, "")
            if not self._is_empty(value) and str(value).strip() != "-":
                non_empty_in_row.append(col)
        if len(non_empty_in_row) == 1:
            return non_empty_in_row[0]

        return None

    def _integrate_quiz_totals_format(
        self,
        general_df: pd.DataFrame,
        ocr_df: pd.DataFrame,
        output_path: str,
    ) -> pd.DataFrame:
        general_cols = list(general_df.columns)
        ocr_cols = list(ocr_df.columns)

        general_id_col = self._find_column(general_cols, ["numerodeid", "nmerodeid", "id", "nombredeusuario"])
        ocr_id_col = self._find_column(ocr_cols, ["numerodeid", "nmerodeid", "idoficial", "id"])
        exam_type_col = self._find_exam_type_col(ocr_cols)
        total_grade_col = self._find_total_grade_col(ocr_cols)
        ocr_group_col = self._find_column(ocr_cols, ["grupoprincipal", "tipogrupo", "grupo"])
        if exam_type_col is None or total_grade_col is None:
            raise ValueError(
                "OCR file must include exam type and total grade columns (e.g. Tipo_Examen and Calificacion/10,00)."
            )

        quizzes_by_group_type: Dict[Tuple[str, str], str] = {}
        quiz_columns_meta: List[Tuple[str, str, str]] = []
        for col in general_cols:
            parsed = self._parse_quiz_total_column(col)
            if parsed is None:
                continue
            group_name, exam_type = parsed
            quizzes_by_group_type[(group_name, exam_type)] = col
            quiz_columns_meta.append((col, group_name, exam_type))

        if not quizzes_by_group_type:
            raise ValueError("General file does not contain quiz total columns with pattern 'Cuestionario:..._Tipo X (Real)'.")

        group_by_id = self._build_group_map_from_enrollment()
        out_df = general_df.copy()

        index_by_id: Dict[str, int] = {}
        if general_id_col:
            for idx, val in out_df[general_id_col].items():
                key = self._normalize_id(val)
                if key and key not in index_by_id:
                    index_by_id[key] = idx

        for _, ocr_row in ocr_df.iterrows():
            target_idx: Optional[int] = None

            if general_id_col and ocr_id_col:
                row_id = self._normalize_id(ocr_row.get(ocr_id_col, ""))
                if row_id and row_id in index_by_id:
                    target_idx = index_by_id[row_id]

            if target_idx is None:
                for idx_general, general_row in out_df.iterrows():
                    if self._name_match(general_row, ocr_row):
                        target_idx = int(idx_general)
                        break

            if target_idx is None:
                continue

            exam_type = str(ocr_row.get(exam_type_col, "")).strip().upper()
            ocr_group_hint = str(ocr_row.get(ocr_group_col, "")).strip() if ocr_group_col else ""
            target_col = self._resolve_target_quiz_column(
                general_row=out_df.loc[target_idx],
                exam_type=exam_type,
                quizzes_by_group_type=quizzes_by_group_type,
                group_by_id=group_by_id,
                general_id_col=general_id_col,
                ocr_group_hint=ocr_group_hint,
            )
            if not target_col:
                continue

            grade_value = self._to_float_grade(ocr_row.get(total_grade_col, ""))
            if pd.isna(grade_value):
                continue
            out_df.at[target_idx, target_col] = grade_value

        for col in quizzes_by_group_type.values():
            out_df[col] = pd.to_numeric(out_df[col].apply(self._to_float_grade), errors="coerce")

        id_source_col = self._find_column(general_cols, ["numerodeid", "nmerodeid", "id", "nombredeusuario"])
        first_name_source_col = self._find_column(general_cols, ["nombre", "firstname"])
        last_name_source_col = self._find_column(general_cols, ["apellidos", "apellido", "apellidosynombre", "lastname"])
        email_source_col = self._find_column(general_cols, ["direcciondecorreo", "direccindecorreo", "email", "correo"])

        normalized_rows = []
        source_basename = Path(self.general_xlsx_path).name
        for _, row in out_df.iterrows():
            best_grade, best_group, best_exam_type = self._best_grade_from_quiz_columns(row, quiz_columns_meta)
            normalized_rows.append(
                {
                    "Número de ID": "" if id_source_col is None else str(row.get(id_source_col, "")).strip(),
                    "Nombre": "" if first_name_source_col is None else str(row.get(first_name_source_col, "")).strip(),
                    "Apellido(s)": "" if last_name_source_col is None else str(row.get(last_name_source_col, "")).strip(),
                    "Dirección de correo": "" if email_source_col is None else str(row.get(email_source_col, "")).strip(),
                    "Calificación/10,00": pd.NA if pd.isna(best_grade) else float(best_grade),
                    "Tipo_Grupo": best_group,
                    "Tipo_Examen": best_exam_type,
                    "Archivo_Origen": source_basename,
                }
            )

        normalized_df = pd.DataFrame(normalized_rows)
        normalized_df = normalized_df.sort_values(["Apellido(s)", "Nombre"], na_position="last")
        normalized_df.to_excel(output_path, index=False)
        return normalized_df

    def integrate(self, output_path: str, output_dir: Optional[str] = None) -> pd.DataFrame:
        if output_dir:
            out_dir_path = Path(output_dir)
            out_dir_path.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir_path / Path(output_path).name)

        general_df = pd.read_excel(self.general_xlsx_path)
        ocr_df = pd.read_excel(self.ocr_xlsx_path)

        if self._looks_like_quiz_totals_format(list(general_df.columns)):
            return self._integrate_quiz_totals_format(general_df, ocr_df, output_path)

        general_cols = list(general_df.columns)
        ocr_cols = list(ocr_df.columns)

        general_id_col = self._find_column(general_cols, ["numerodeid", "nmerodeid", "id"])
        ocr_id_col = self._find_column(ocr_cols, ["numerodeid", "nmerodeid", "idoficial", "id"])

        general_group_col = self._find_column(general_cols, ["tipogrupo", "tipo"])
        ocr_group_col = self._find_column(ocr_cols, ["tipoexamen", "tipogrupo", "tipo"])

        grade_cols_general = [
            c for c in general_cols
            if self._normalize(c).startswith("calificacion")
            or re.match(r"^p\.?\s*\d+\s*/", str(c).strip().lower()) is not None
        ]
        grade_cols_set = set(grade_cols_general)

        shared_cols = [c for c in general_cols if c in set(ocr_cols)]
        out_df = general_df.copy()

        index_by_id: Dict[str, int] = {}
        if general_id_col:
            for idx, val in out_df[general_id_col].items():
                key = self._normalize_id(val)
                if key and key not in index_by_id:
                    index_by_id[key] = idx

        for _, ocr_row in ocr_df.iterrows():
            target_idx: Optional[int] = None

            if general_id_col and ocr_id_col:
                row_id = self._normalize_id(ocr_row.get(ocr_id_col, ""))
                if row_id and row_id in index_by_id:
                    target_idx = index_by_id[row_id]

            if target_idx is None:
                for idx_general, general_row in out_df.iterrows():
                    if self._name_match(general_row, ocr_row):
                        target_idx = int(idx_general)
                        break

            if target_idx is None:
                new_row = {c: "" for c in general_cols}

                for c in shared_cols:
                    value = ocr_row.get(c, "")
                    if not self._is_empty(value):
                        if c in grade_cols_set:
                            value = self._to_float_grade(value)
                        new_row[c] = value

                for general_col in grade_cols_general:
                    if general_col in ocr_cols:
                        continue
                    norm_general = self._normalize(general_col)
                    for ocr_col in ocr_cols:
                        if self._normalize(ocr_col) == norm_general:
                            value = ocr_row.get(ocr_col, "")
                            if not self._is_empty(value):
                                new_row[general_col] = self._to_float_grade(value)
                            break

                if general_group_col and ocr_group_col and self._is_empty(new_row.get(general_group_col, "")):
                    group_value = ocr_row.get(ocr_group_col, "")
                    if not self._is_empty(group_value):
                        new_row[general_group_col] = group_value

                out_df = pd.concat([out_df, pd.DataFrame([new_row])], ignore_index=True)
                continue

            for c in shared_cols:
                value = ocr_row.get(c, "")
                if not self._is_empty(value):
                    if c in grade_cols_set:
                        value = self._to_float_grade(value)
                    out_df.at[target_idx, c] = value

            for general_col in grade_cols_general:
                if general_col in ocr_cols:
                    continue
                norm_general = self._normalize(general_col)
                for ocr_col in ocr_cols:
                    if self._normalize(ocr_col) == norm_general:
                        value = ocr_row.get(ocr_col, "")
                        if not self._is_empty(value):
                            out_df.at[target_idx, general_col] = self._to_float_grade(value)
                        break

            if general_group_col and ocr_group_col:
                group_value = ocr_row.get(ocr_group_col, "")
                if not self._is_empty(group_value):
                    out_df.at[target_idx, general_group_col] = group_value

        out_df = out_df.reindex(columns=general_cols)
        for c in grade_cols_general:
            out_df[c] = pd.to_numeric(out_df[c].apply(self._to_float_grade), errors="coerce")
        out_df.to_excel(output_path, index=False)
        return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrate OCR grades into a general Moodle XLSX")
    parser.add_argument("--general", required=True, help="General XLSX to update")
    parser.add_argument("--ocr", required=True, help="OCR grades XLSX")
    parser.add_argument("--output", required=True, help="Output integrated XLSX")
    parser.add_argument("--output-dir", default=None, help="Directory where output is generated")
    parser.add_argument("--enrollment-list", nargs="+", default=None, help="Optional enrollment Excels to resolve group per student")
    parser.add_argument("--enrollment-sheet", type=int, default=0, help="Sheet index for enrollment files")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    integrator = OcrGradeIntegrator(
        general_xlsx_path=args.general,
        ocr_xlsx_path=args.ocr,
        enrollment_paths=args.enrollment_list,
        enrollment_sheet=args.enrollment_sheet,
    )
    df = integrator.integrate(args.output, output_dir=args.output_dir)
    print(f"OK: integrated file generated at {args.output}")
    print(f"Total rows: {len(df)}")


if __name__ == "__main__":
    main()


# Backward-compatible alias
IntegradorCalificacionesOCR = OcrGradeIntegrator
OcrGradeIntegrator.integrar = OcrGradeIntegrator.integrate

