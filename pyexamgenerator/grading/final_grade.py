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
        ident = _clean(id_value)
        if ident:
            return f"id::{ident}"
        return f"name::{_normalize(first)}::{_normalize(last)}"

    def compute_by_files(self, sources: Sequence[Dict[str, Any]]) -> pd.DataFrame:
        """Weights one grade column per file. ``sources`` items: ``{path, label?, weight?, grade_col?, id_col?}``."""
        if not sources:
            raise ValueError("Debe indicar al menos un examen (fichero) para la nota final.")

        parsed = []
        for source in sources:
            path = source["path"]
            df = pd.read_excel(path)
            columns = list(df.columns)
            label = str(source.get("label") or Path(path).stem)
            weight = float(source.get("weight", 1.0))
            id_col = source.get("id_col") or self.id_col or _find_column(columns, _ID_CANDIDATES)
            first_col = self.first_name_col or _find_column(columns, _FIRST_CANDIDATES)
            last_col = self.last_name_col or _find_column(columns, _LAST_CANDIDATES)
            grade_col = source.get("grade_col") or _find_column(columns, _GRADE_CANDIDATES)
            if grade_col is None:
                raise ValueError(
                    f"No se encontró una columna de nota en '{path}'. Indique 'grade_col' explícitamente."
                )
            parsed.append(
                {
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

        registry: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for p in parsed:
            for _, row in p["df"].iterrows():
                id_value = row.get(p["id_col"], "") if p["id_col"] else ""
                first = row.get(p["first_col"], "") if p["first_col"] else ""
                last = row.get(p["last_col"], "") if p["last_col"] else ""
                key = self._identity_key(id_value, first, last)
                if key in {"id::", "name::::"}:
                    continue
                if key not in registry:
                    registry[key] = {
                        "Número de ID": _clean(id_value),
                        "Nombre": _clean(first),
                        "Apellido(s)": _clean(last),
                        "_grades": {},
                    }
                    order.append(key)
                record = registry[key]
                if not record["Número de ID"]:
                    record["Número de ID"] = _clean(id_value)
                if not record["Nombre"]:
                    record["Nombre"] = _clean(first)
                if not record["Apellido(s)"]:
                    record["Apellido(s)"] = _clean(last)
                grade = _to_float_grade(row.get(p["grade_col"], ""))
                if grade is not None:
                    record["_grades"][p["label"]] = grade

        rows_out = []
        for key in order:
            record = registry[key]
            final_grade = 0.0
            for p in parsed:
                grade = record["_grades"].get(p["label"])
                final_grade += (p["weight"] / total_weight) * (0.0 if grade is None else grade)
            if self.cap_to_10:
                final_grade = min(final_grade, 10.0)
            out_row: Dict[str, Any] = {
                "Número de ID": record["Número de ID"],
                "Nombre": record["Nombre"],
                "Apellido(s)": record["Apellido(s)"],
            }
            for p in parsed:
                grade = record["_grades"].get(p["label"])
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
