from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple

import pandas as pd


QuestionMap = Dict[str, Dict[str, float]]
QuestionsByExamTypeMap = Dict[str, QuestionMap]


class SharedExamDataStore:
    """In-memory cache for XML/Excel datasets shared across pipeline modules."""

    def __init__(self) -> None:
        self._xml_cache: Dict[str, QuestionMap] = {}
        self._enrollment_cache: Dict[Tuple[str, int], pd.DataFrame] = {}
        self._answers_cache: Dict[str, pd.DataFrame] = {}

    @staticmethod
    def _normalize_path(path: str) -> str:
        return str(Path(path).resolve())

    def load_questions_xml(self, xml_path: str) -> QuestionMap:
        key = self._normalize_path(xml_path)
        if key in self._xml_cache:
            return self._xml_cache[key]

        tree = ET.parse(xml_path)
        root = tree.getroot()
        questions: QuestionMap = {}

        for question in root.findall("question"):
            if question.get("type") != "multichoice":
                continue

            name_node = question.find("name/text")
            if name_node is None or not name_node.text:
                continue

            num_match = re.search(r"\d+", name_node.text)
            if not num_match:
                continue

            q_num = int(num_match.group())
            q_name = f"Pregunta {q_num:02d}"

            answers: Dict[str, float] = {}
            for answer in question.findall("answer"):
                text_node = answer.find("text")
                if text_node is None or text_node.text is None:
                    continue
                letter = text_node.text.strip().lower()
                answers[letter] = float(answer.get("fraction", "0")) / 100.0

            questions[q_name] = answers

        if not questions:
            raise ValueError(f"No multichoice questions found in {xml_path}")

        self._xml_cache[key] = questions
        return questions

    def load_questions_by_exam_type(
        self,
        xml_paths: Sequence[str],
        infer_exam_type: Optional[Callable[[str], str]] = None,
    ) -> QuestionsByExamTypeMap:
        infer = infer_exam_type or self._infer_exam_type_from_filename
        out: QuestionsByExamTypeMap = {}
        for xml_path in xml_paths:
            exam_type = infer(xml_path)
            out[exam_type] = self.load_questions_xml(xml_path)
        return out

    def load_enrollment(
        self,
        xlsx_path: str,
        sheet_name: int = 0,
        first_name_col: str = "Nombre",
        last_name_col: str = "Apellido(s)",
        with_lookup_name: bool = False,
    ) -> pd.DataFrame:
        key = (self._normalize_path(xlsx_path), int(sheet_name))
        if key not in self._enrollment_cache:
            self._enrollment_cache[key] = pd.read_excel(xlsx_path, sheet_name=sheet_name)

        df = self._enrollment_cache[key]
        if with_lookup_name and "Lookup_Name" not in df.columns:
            df = df.copy()
            df["Lookup_Name"] = (
                df[first_name_col].astype(str).str.strip() + " " + df[last_name_col].astype(str).str.strip()
            ).str.lower()
            self._enrollment_cache[key] = df
        return df

    def load_answers_excel(self, xlsx_path: str) -> pd.DataFrame:
        key = self._normalize_path(xlsx_path)
        if key not in self._answers_cache:
            self._answers_cache[key] = pd.read_excel(xlsx_path)
        return self._answers_cache[key]

    @staticmethod
    def _infer_exam_type_from_filename(xml_path: str) -> str:
        name = Path(xml_path).name.upper()
        match = re.search(r"_([0-9]+[A-Z])\.XML$", name)
        if match:
            return match.group(1)

        match = re.search(r"\b([0-9]+[A-Z])\b", name)
        if match:
            return match.group(1)

        raise ValueError(f"Could not infer exam type from XML filename: {xml_path}")

    # Backward-compatible aliases
    load_preguntas_xml = load_questions_xml
    load_preguntas_por_tipo = load_questions_by_exam_type
    load_matriculados = load_enrollment
    load_respuestas_excel = load_answers_excel




# Enrollment merge utilities

import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

import pandas as pd


def _normalize(text: str) -> str:
    text = str(text).strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text)


def _find_column(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    col_map = {_normalize(c): c for c in columns}
    for cand in candidates:
        key = _normalize(cand)
        if key in col_map:
            return col_map[key]
    return None


def _clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _is_subgroup_selected(value: str) -> bool:
    text = _normalize(value)
    return text not in {"", "sincontestaraun", "sincontestar"}


def _detect_macro_group(path: str) -> str:
    name = Path(path).stem.upper()
    if "GITI" in name or "GIE" in name:
        return "GITI-GIE-GIEI"
    if "GIM" in name:
        return "GIM"
    return Path(path).stem


def _identity_key(row: pd.Series, id_col: Optional[str], name_col: Optional[str], last_name_col: Optional[str]) -> str:
    student_id = _clean_text(row.get(id_col, "")) if id_col else ""
    if student_id:
        return f"id::{student_id}"

    first_name = _normalize(_clean_text(row.get(name_col, ""))) if name_col else ""
    last_name = _normalize(_clean_text(row.get(last_name_col, ""))) if last_name_col else ""
    return f"name::{first_name}::{last_name}"


_ENROLLMENT_COLUMNS = [
    "Apellido(s)",
    "Nombre",
    "Número de ID",
    "Dirección de correo",
    "Grupo_Principal",
    "Subgrupo_Practicas",
    "Subgrupo_Estado",
    "Subgrupo_Origen",
    "Subgrupos_Detectados",
    "Subgrupo_Conflicto",
]


class EnrollmentMerger:
    """Merge several enrollment exports into one roster, keeping inputs and outputs.

    The instance retains every intermediate value so it can be inspected or reused:
      - ``source_paths`` / ``sheet_name``: the requested inputs.
      - ``source_dfs``: the raw DataFrames read from each file (filled by :meth:`merge`).
      - ``merged_df``: the consolidated roster (filled by :meth:`merge`).
      - ``output_path``: where the roster was written (filled by :meth:`export`).
    """

    def __init__(self, source_paths: Iterable[str], sheet_name: int = 0) -> None:
        self.source_paths: list = [str(p).strip() for p in source_paths if str(p).strip()]
        if not self.source_paths:
            raise ValueError("At least one enrollment path is required.")
        self.sheet_name = sheet_name
        self.source_dfs: Optional[list] = None
        self.merged_df: Optional[pd.DataFrame] = None
        self.output_path: Optional[str] = None

    def merge(self) -> pd.DataFrame:
        """Read every source, resolve subgroup selection per student and store the roster."""
        merged_by_key: Dict[str, Dict[str, str]] = {}
        self.source_dfs = []

        for path in self.source_paths:
            df = pd.read_excel(path, sheet_name=self.sheet_name)
            self.source_dfs.append(df)
            columns = list(df.columns)

            last_name_col = _find_column(columns, ["Apellido(s)", "Apellidos", "Apellido"])
            first_name_col = _find_column(columns, ["Nombre"])
            id_col = _find_column(columns, ["Número de ID", "Nmero de ID", "ID", "DNI"])
            email_col = _find_column(columns, ["Dirección de correo", "Direccin de correo", "Email", "Correo"])
            subgroup_col = _find_column(columns, ["Consulta", "Subgrupo", "Grupo", "Grupo prácticas"])
            source_group = _detect_macro_group(path)

            for _, row in df.iterrows():
                key = _identity_key(row, id_col, first_name_col, last_name_col)
                if key == "name::::" or key == "id::":
                    continue

                merged = merged_by_key.setdefault(
                    key,
                    {
                        "Apellido(s)": "",
                        "Nombre": "",
                        "Número de ID": "",
                        "Dirección de correo": "",
                        "Grupo_Principal": "",
                        "Subgrupo_Practicas": "",
                        "Subgrupo_Estado": "sin_contestar",
                        "Subgrupo_Origen": "",
                        "Subgrupos_Detectados": "",
                        "Subgrupo_Conflicto": "no",
                    },
                )

                if not merged["Apellido(s)"] and last_name_col:
                    merged["Apellido(s)"] = _clean_text(row.get(last_name_col, ""))
                if not merged["Nombre"] and first_name_col:
                    merged["Nombre"] = _clean_text(row.get(first_name_col, ""))
                if not merged["Número de ID"] and id_col:
                    merged["Número de ID"] = _clean_text(row.get(id_col, ""))
                if not merged["Dirección de correo"] and email_col:
                    merged["Dirección de correo"] = _clean_text(row.get(email_col, ""))

                subgroup_value = _clean_text(row.get(subgroup_col, "")) if subgroup_col else ""
                if _is_subgroup_selected(subgroup_value):
                    detected = [s for s in merged["Subgrupos_Detectados"].split(";") if s]
                    if subgroup_value not in detected:
                        detected.append(subgroup_value)
                    merged["Subgrupos_Detectados"] = ";".join(detected)

                    existing_subgroup = merged.get("Subgrupo_Practicas", "")
                    if existing_subgroup and existing_subgroup != subgroup_value:
                        merged["Subgrupo_Conflicto"] = "si"
                        merged["Subgrupo_Estado"] = "conflicto"

                    merged["Subgrupo_Practicas"] = subgroup_value
                    merged["Grupo_Principal"] = source_group
                    if merged["Subgrupo_Estado"] != "conflicto":
                        merged["Subgrupo_Estado"] = "asignado"
                    merged["Subgrupo_Origen"] = Path(path).name
                elif merged["Subgrupo_Estado"] not in {"asignado", "conflicto"}:
                    merged["Subgrupo_Estado"] = "sin_contestar"

        out = pd.DataFrame(list(merged_by_key.values()))
        if out.empty:
            out = pd.DataFrame(columns=_ENROLLMENT_COLUMNS)
        else:
            out = out.sort_values(["Apellido(s)", "Nombre"], na_position="last").reset_index(drop=True)
        self.merged_df = out
        return out

    def export(self, output_path: str) -> pd.DataFrame:
        """Run :meth:`merge` if needed and write the roster to ``output_path``."""
        if self.merged_df is None:
            self.merge()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self.merged_df.to_excel(output_path, index=False)
        self.output_path = output_path
        return self.merged_df


def build_merged_enrollment_from_sources(paths: Iterable[str], sheet_name: int = 0) -> pd.DataFrame:
    """Merge multiple enrollment exports and resolve subgroup selection per student.

    Thin functional wrapper kept for backward compatibility; delegates to
    :class:`EnrollmentMerger`.
    """
    return EnrollmentMerger(paths, sheet_name=sheet_name).merge()






# Backward-compatible aliases for legacy Spanish names.
PreguntasMap = QuestionMap
PreguntasPorTipoMap = QuestionsByExamTypeMap
