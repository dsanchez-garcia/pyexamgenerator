from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from pyexamgenerator.grading._ids import normalize_id


QuestionMap = Dict[str, Dict[str, float]]
QuestionsByExamTypeMap = Dict[str, QuestionMap]


def infer_exam_type_from_xml_filename(xml_path: str) -> str:
    """Infer exam type from XML filename (supports both `1A` and letter-only `A`)."""
    name = Path(xml_path).name.upper()

    # Prefer explicit suffixes such as "..._1A.xml" or "..._A.xml".
    suffix_match = re.search(r"[_\-\s]([0-9]*[A-Z])\.XML$", name)
    if suffix_match:
        return suffix_match.group(1)

    # Fallback: scan stem tokens right-to-left and keep the first token shaped as type.
    stem = Path(xml_path).stem.upper()
    tokens = [t for t in re.split(r"[^0-9A-Z]+", stem) if t]
    for token in reversed(tokens):
        if re.fullmatch(r"[0-9]*[A-Z]", token):
            return token

    raise ValueError(f"Could not infer exam type from XML filename: {xml_path}")


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

            questions[q_name] = self._answer_map_from_question(question)

        if not questions:
            raise ValueError(f"No multichoice questions found in {xml_path}")

        self._xml_cache[key] = questions
        return questions

    @staticmethod
    def _answer_map_from_question(question: ET.Element) -> Dict[str, float]:
        """Devuelve ``{letra: fracción}`` para las respuestas de una pregunta del XML.

        Las hojas de respuestas y los xlsx de respuestas contienen letras (a, b, c, d). Si el XML
        usa esas letras como texto de las respuestas (en cualquier orden), se usan como clave. Si el
        XML contiene el texto completo de cada respuesta (``xml_use_answer_text=True`` al generarlo),
        la letra se asigna por posición: el generador escribe siempre las opciones en orden A, B, C, D.
        En ese caso se conservan además las claves de texto, sin pisar nunca las letras.
        """
        texts: List[str] = []
        fractions: List[float] = []
        for answer in question.findall("answer"):
            text_node = answer.find("text")
            text = "" if text_node is None or text_node.text is None else text_node.text.strip().lower()
            texts.append(text)
            fractions.append(float(answer.get("fraction", "0")) / 100.0)

        letters = [chr(ord("a") + i) for i in range(min(len(texts), 26))]
        letter_texts = []
        for text in texts:
            match = re.fullmatch(r"\(?([a-z])[\).:]?", text)
            letter_texts.append(match.group(1) if match else None)

        answers: Dict[str, float] = {}
        if None not in letter_texts and sorted(letter_texts) == letters:
            # XML con letras como texto de respuesta (formato por defecto).
            for letter, fraction in zip(letter_texts, fractions):
                answers[letter] = fraction
            return answers

        # XML con el texto completo de las respuestas: letra por posición (A, B, C, D...).
        for letter, fraction in zip(letters, fractions):
            answers[letter] = fraction
        for text, fraction in zip(texts, fractions):
            if text and text not in answers:
                answers[text] = fraction
        return answers

    def load_questions_by_exam_type(
        self,
        xml_paths: Sequence[str],
        infer_exam_type: Optional[Callable[[str], str]] = None,
    ) -> QuestionsByExamTypeMap:
        """Carga varias plantillas XML indexadas por tipo de examen (inferido del nombre).

        Si dos ficheros distintos corresponden al mismo tipo y sus claves de respuesta difieren
        (p. ej. ``GIM/examen_..._1A.xml`` y ``GITI/examen_..._1A.xml``), se lanza ``ValueError``:
        de lo contrario la última plantilla pisaría a la otra y se corregiría con la clave errónea.
        """
        infer = infer_exam_type or self._infer_exam_type_from_filename
        out: QuestionsByExamTypeMap = {}
        source_by_type: Dict[str, str] = {}
        for xml_path in xml_paths:
            exam_type = infer(xml_path)
            questions = self.load_questions_xml(xml_path)
            if exam_type in out:
                previous_path = source_by_type[exam_type]
                same_file = self._normalize_path(previous_path) == self._normalize_path(xml_path)
                if not same_file and out[exam_type] != questions:
                    raise ValueError(
                        f"Hay varias plantillas XML distintas para el tipo de examen '{exam_type}':\n"
                        f"- {previous_path}\n- {xml_path}\n"
                        "Corrige cada grupo por separado o renombra las plantillas para que cada tipo "
                        "sea único (p. ej. ..._1A.xml y ..._2A.xml)."
                    )
                continue
            out[exam_type] = questions
            source_by_type[exam_type] = str(xml_path)
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
        return infer_exam_type_from_xml_filename(xml_path)

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


def _name_tokens(stem: str) -> set:
    """Palabras del nombre de fichero (separadores y cambios minúscula->MAYÚSCULA), en mayúsculas."""
    tokens = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", str(stem))
    return {token.upper() for token in tokens}


def _detect_macro_group(path: str) -> str:
    # Se comparan palabras completas: 'HIGIENE' contiene 'GIE' y no debe clasificarse como GITI-GIE-GIEI.
    tokens = _name_tokens(Path(path).stem)
    if tokens & {"GITI", "GIE", "GIEI"}:
        return "GITI-GIE-GIEI"
    if "GIM" in tokens:
        return "GIM"
    return Path(path).stem


def _candidates(override: Optional[str], defaults: Sequence[str]) -> List[str]:
    """Lista de candidatos para :func:`_find_column`, con prioridad para el nombre indicado por el usuario."""
    if override and str(override).strip():
        return [str(override).strip(), *defaults]
    return list(defaults)


def _identity_key(row: pd.Series, id_col: Optional[str], name_col: Optional[str], last_name_col: Optional[str]) -> str:
    student_id = normalize_id(row.get(id_col, "")) if id_col else ""
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

    ``first_name_col`` / ``last_name_col`` / ``id_col`` / ``email_col`` are optional column names of
    the *source* files (e.g. the GUI column mapping); they take priority over the built-in candidates.
    The merged roster always uses the canonical names ``Apellido(s)``, ``Nombre``, ``Número de ID``
    and ``Dirección de correo``, and IDs are normalised (``11111111.0`` -> ``11111111``, blank -> ``''``).
    """

    def __init__(
        self,
        source_paths: Iterable[str],
        sheet_name: int = 0,
        first_name_col: Optional[str] = None,
        last_name_col: Optional[str] = None,
        id_col: Optional[str] = None,
        email_col: Optional[str] = None,
    ) -> None:
        self.source_paths: list = [str(p).strip() for p in source_paths if str(p).strip()]
        if not self.source_paths:
            raise ValueError("At least one enrollment path is required.")
        self.sheet_name = sheet_name
        self.first_name_col = first_name_col
        self.last_name_col = last_name_col
        self.id_col = id_col
        self.email_col = email_col
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

            last_name_col = _find_column(columns, _candidates(self.last_name_col, ["Apellido(s)", "Apellidos", "Apellido"]))
            first_name_col = _find_column(columns, _candidates(self.first_name_col, ["Nombre"]))
            id_col = _find_column(columns, _candidates(self.id_col, ["Número de ID", "Nmero de ID", "ID", "DNI"]))
            email_col = _find_column(
                columns,
                _candidates(self.email_col, ["Dirección de correo", "Direccin de correo", "Email", "Correo"]),
            )
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
                    merged["Número de ID"] = normalize_id(row.get(id_col, ""))
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
        """Run :meth:`merge` if needed and write the roster to ``output_path``.

        Raises ``ValueError`` if ``output_path`` is one of the source files: the merged roster only
        keeps the normalised columns, so writing it there would destroy the teacher's original file.
        """
        target = Path(output_path).resolve()
        for source in self.source_paths:
            if Path(source).resolve() == target:
                raise ValueError(
                    "La matrícula fusionada no puede guardarse sobre uno de los ficheros de matriculados "
                    f"de origen ('{source}'): se perderían sus columnas. Elige otra ruta de salida."
                )
        if self.merged_df is None:
            self.merge()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self.merged_df.to_excel(output_path, index=False)
        self.output_path = output_path
        return self.merged_df


def build_merged_enrollment_from_sources(
    paths: Iterable[str],
    sheet_name: int = 0,
    first_name_col: Optional[str] = None,
    last_name_col: Optional[str] = None,
    id_col: Optional[str] = None,
    email_col: Optional[str] = None,
) -> pd.DataFrame:
    """Merge multiple enrollment exports and resolve subgroup selection per student.

    Thin functional wrapper kept for backward compatibility; delegates to
    :class:`EnrollmentMerger` (the optional column names are passed through).
    """
    return EnrollmentMerger(
        paths,
        sheet_name=sheet_name,
        first_name_col=first_name_col,
        last_name_col=last_name_col,
        id_col=id_col,
        email_col=email_col,
    ).merge()






# Backward-compatible aliases for legacy Spanish names.
PreguntasMap = QuestionMap
PreguntasPorTipoMap = QuestionsByExamTypeMap
