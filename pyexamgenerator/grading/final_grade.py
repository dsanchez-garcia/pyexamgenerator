"""Weighted final grade from several exams.

Two modes are supported:
  - **by file**: each exam is a separate XLSX; the user assigns a weight (and optional label / grade
    column) per file. Students are matched across files by ID (falling back to normalized name).
  - **by column**: the exams are already columns inside a single XLSX and those columns are weighted.

In both modes weights are normalized (so they need not add up to 1), missing grades count as 0, and
the final grade can optionally be capped at 10. Grades are parsed tolerating comma decimals.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from pyexamgenerator.grading._ids import normalize_id


def _normalize(text: Any) -> str:
    text = str(text).strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text)


def _find_column(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    col_map = {_normalize(c): c for c in columns}
    for candidate in candidates:
        key = _normalize(candidate)
        if key in col_map:
            return col_map[key]
    return None


def _to_float_grade(value: Any) -> Optional[float]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text in {"", "-"}:
        return None
    text = text.replace(",", ".")
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", text):
        return float(text)
    return None


def _clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


_ID_CANDIDATES = ["Número de ID", "Numero de ID", "Nmero de ID", "ID", "Nombre de usuario", "DNI"]
_FIRST_CANDIDATES = ["Nombre"]
_LAST_CANDIDATES = ["Apellido(s)", "Apellidos", "Apellido"]
_GRADE_CANDIDATES = [
    "Calificación/10,00",
    "Calificacion/10,00",
    "Nota_Final",
    "Nota",
    "Calificación",
    "Calificacion",
    "Grade",
]


class FinalGradeCalculator:
    """Computes a weighted final grade across several exams (by file or by column)."""

    def __init__(
        self,
        cap_to_10: bool = True,
        id_col: Optional[str] = None,
        first_name_col: Optional[str] = None,
        last_name_col: Optional[str] = None,
    ) -> None:
        self.cap_to_10 = bool(cap_to_10)
        self.id_col = id_col
        self.first_name_col = first_name_col
        self.last_name_col = last_name_col
        self.result_df: Optional[pd.DataFrame] = None

    @staticmethod
    def _identity_key(id_value: Any, first: Any, last: Any) -> str:
        ident = normalize_id(id_value)
        if ident:
            return f"id::{ident}"
        return f"name::{_normalize(first)}::{_normalize(last)}"

    @staticmethod
    def _resolve_column(columns: Sequence[str], overrides: Sequence[Any], candidates: Sequence[str]) -> Optional[str]:
        """Usa el nombre indicado solo si existe en *este* fichero; si no, autodetecta con los candidatos."""
        explicit = [str(o).strip() for o in overrides if o and str(o).strip()]
        return _find_column(columns, [*explicit, *candidates])

    @staticmethod
    def _unique_labels(sources: Sequence[Dict[str, Any]]) -> List[str]:
        """Etiqueta única por fichero: dos ficheros con el mismo nombre no pueden compartir columna."""
        stems = [Path(str(s["path"])).stem for s in sources]
        default_counts: Dict[str, int] = {}
        for source, stem in zip(sources, stems):
            if not source.get("label"):
                default_counts[stem] = default_counts.get(stem, 0) + 1

        labels: List[str] = []
        used = set()
        for source, stem in zip(sources, stems):
            label = str(source.get("label") or "").strip()
            if not label:
                label = stem
                parent = Path(str(source["path"])).parent.name
                if default_counts.get(stem, 0) > 1 and parent:
                    # Mismo nombre de fichero en carpetas distintas (p. ej. parcial1/ y parcial2/).
                    label = f"{parent}_{stem}"
            base, suffix = label, 2
            while label in used:
                label = f"{base}_{suffix}"
                suffix += 1
            used.add(label)
            labels.append(label)
        return labels

    def compute_by_files(self, sources: Sequence[Dict[str, Any]]) -> pd.DataFrame:
        """Weights one grade column per file. ``sources`` items: ``{path, label?, weight?, grade_col?, id_col?}``.

        Column names given to the calculator (or per source) are used only in the files that contain them;
        other files are auto-detected. Rows without ID join the student with the same name in another file
        when that name belongs to exactly one ID. Repeated labels (e.g. two files with the same name in
        different folders) are made unique.
        """
        if not sources:
            raise ValueError("Debe indicar al menos un examen (fichero) para la nota final.")

        labels = self._unique_labels(sources)
        parsed = []
        for index, (source, label) in enumerate(zip(sources, labels)):
            path = source["path"]
            df = pd.read_excel(path)
            columns = list(df.columns)
            weight = float(source.get("weight", 1.0))
            id_col = self._resolve_column(columns, [source.get("id_col"), self.id_col], _ID_CANDIDATES)
            first_col = self._resolve_column(columns, [self.first_name_col], _FIRST_CANDIDATES)
            last_col = self._resolve_column(columns, [self.last_name_col], _LAST_CANDIDATES)
            grade_col = source.get("grade_col") or _find_column(columns, _GRADE_CANDIDATES)
            if grade_col is None:
                raise ValueError(
                    f"No se encontró una columna de nota en '{path}'. Indique 'grade_col' explícitamente."
                )
            parsed.append(
                {
                    "index": index,
                    "label": label,
                    "weight": weight,
                    "df": df,
                    "id_col": id_col,
                    "first_col": first_col,
                    "last_col": last_col,
                    "grade_col": grade_col,
                }
            )

        total_weight = sum(p["weight"] for p in parsed) or 1.0

        # 1) Leer todas las filas; 2) una fila sin ID se une al alumno con ese mismo nombre si este
        #    corresponde a un único ID (si el nombre es ambiguo, la fila queda aparte).
        entries = []
        ids_by_name: Dict[str, set] = {}
        for p in parsed:
            for _, row in p["df"].iterrows():
                ident = normalize_id(row.get(p["id_col"], "")) if p["id_col"] else ""
                first = row.get(p["first_col"], "") if p["first_col"] else ""
                last = row.get(p["last_col"], "") if p["last_col"] else ""
                name_key = f"{_normalize(_clean(first))}::{_normalize(_clean(last))}"
                if ident and name_key != "::":
                    ids_by_name.setdefault(name_key, set()).add(ident)
                entries.append((p, row, ident, first, last, name_key))

        registry: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for p, row, ident, first, last, name_key in entries:
            if not ident and len(ids_by_name.get(name_key, ())) == 1:
                ident = next(iter(ids_by_name[name_key]))
            key = self._identity_key(ident, _clean(first), _clean(last))
            if key in {"id::", "name::::"}:
                continue
            if key not in registry:
                registry[key] = {
                    "Número de ID": ident,
                    "Nombre": _clean(first),
                    "Apellido(s)": _clean(last),
                    "_grades": {},
                }
                order.append(key)
            record = registry[key]
            if not record["Número de ID"]:
                record["Número de ID"] = ident
            if not record["Nombre"]:
                record["Nombre"] = _clean(first)
            if not record["Apellido(s)"]:
                record["Apellido(s)"] = _clean(last)
            grade = _to_float_grade(row.get(p["grade_col"], ""))
            if grade is not None:
                record["_grades"][p["index"]] = grade

        rows_out = []
        for key in order:
            record = registry[key]
            final_grade = 0.0
            for p in parsed:
                grade = record["_grades"].get(p["index"])
                final_grade += (p["weight"] / total_weight) * (0.0 if grade is None else grade)
            if self.cap_to_10:
                final_grade = min(final_grade, 10.0)
            out_row: Dict[str, Any] = {
                "Número de ID": record["Número de ID"],
                "Nombre": record["Nombre"],
                "Apellido(s)": record["Apellido(s)"],
            }
            for p in parsed:
                grade = record["_grades"].get(p["index"])
                out_row[f"Nota_{p['label']}"] = "" if grade is None else round(grade, 4)
            out_row["Nota_Final"] = round(final_grade, 4)
            rows_out.append(out_row)

        self.result_df = pd.DataFrame(rows_out)
        return self.result_df

    def compute_by_columns(self, source_path: str, weights: Dict[str, float]) -> pd.DataFrame:
        """Weights several grade columns within a single XLSX. ``weights``: ``{column_name: weight}``."""
        if not weights:
            raise ValueError("Debe indicar al menos una columna con su peso para la nota final.")

        df = pd.read_excel(source_path)
        columns = list(df.columns)
        resolved: Dict[str, float] = {}
        for col_name, weight in weights.items():
            actual = col_name if col_name in df.columns else _find_column(columns, [col_name])
            if actual is None:
                raise ValueError(f"Columna '{col_name}' no encontrada en '{source_path}'.")
            resolved[actual] = float(weight)

        total_weight = sum(resolved.values()) or 1.0
        out_df = df.copy()
        final_grades = []
        for _, row in df.iterrows():
            value = 0.0
            for col, weight in resolved.items():
                grade = _to_float_grade(row.get(col, ""))
                value += (weight / total_weight) * (0.0 if grade is None else grade)
            if self.cap_to_10:
                value = min(value, 10.0)
            final_grades.append(round(value, 4))
        out_df["Nota_Final"] = final_grades

        self.result_df = out_df
        return out_df

    def export(self, output_path: str, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Writes ``df`` (or the last computed result) to ``output_path``."""
        result = self.result_df if df is None else df
        if result is None:
            raise ValueError("No hay nota final calculada para exportar.")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.to_excel(output_path, index=False)
        return result
