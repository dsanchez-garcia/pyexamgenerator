"""Compare and optionally overwrite results (grades or attendance) against a previous version.

Both grades and attendance are plain student-keyed tables, so a single comparator handles them:
it matches rows by student (ID, falling back to normalized name), reports what changed / was added /
was removed in the chosen value columns, and can produce a **merged** table where the new values
overwrite the previous ones (optionally adding students that only appear in the new file).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
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


def _clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _as_float(value: Any) -> Optional[float]:
    if pd.isna(value):
        return None
    text = str(value).strip().replace(",", ".")
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", text):
        return float(text)
    return None


def _values_differ(old: Any, new: Any) -> bool:
    """True if two cell values differ, comparing numerically when both look like numbers."""
    old_f, new_f = _as_float(old), _as_float(new)
    if old_f is not None and new_f is not None:
        return abs(old_f - new_f) > 1e-9
    return _clean(old) != _clean(new)


_ID_CANDIDATES = ["Número de ID", "Numero de ID", "Nmero de ID", "ID", "Nombre de usuario", "DNI"]
_FIRST_CANDIDATES = ["Nombre"]
_LAST_CANDIDATES = ["Apellido(s)", "Apellidos", "Apellido"]
_EMAIL_CANDIDATES = ["Dirección de correo", "Direccion de correo", "Correo", "Email"]


@dataclass
class ComparisonResult:
    """Outcome of comparing two result tables.

    Attributes:
        changes_df: One row per (student, column) that changed, with old and new values.
        only_in_existing_df: Students present only in the previous file.
        only_in_new_df: Students present only in the new file.
        merged_df: The combined table (new overwrites previous) when overwrite was requested, else None.
        summary: Counts (changed cells, changed students, added, removed, common, value columns).
        value_columns: The columns that were compared.
    """

    changes_df: pd.DataFrame
    only_in_existing_df: pd.DataFrame
    only_in_new_df: pd.DataFrame
    merged_df: Optional[pd.DataFrame]
    summary: Dict[str, int]
    value_columns: List[str] = field(default_factory=list)


class ResultComparator:
    """Compares (and optionally overwrites) a results table against a previous version."""

    def __init__(
        self,
        id_col: Optional[str] = None,
        first_name_col: Optional[str] = None,
        last_name_col: Optional[str] = None,
    ) -> None:
        self.id_col = id_col
        self.first_name_col = first_name_col
        self.last_name_col = last_name_col

    def _resolve_keys(self, columns: Sequence[str]):
        id_col = self.id_col if (self.id_col and self.id_col in columns) else _find_column(columns, _ID_CANDIDATES)
        first_col = self.first_name_col if (self.first_name_col and self.first_name_col in columns) else _find_column(columns, _FIRST_CANDIDATES)
        last_col = self.last_name_col if (self.last_name_col and self.last_name_col in columns) else _find_column(columns, _LAST_CANDIDATES)
        return id_col, first_col, last_col

    @staticmethod
    def _row_key(row: pd.Series, id_col, first_col, last_col) -> str:
        ident = _clean(row.get(id_col, "")) if id_col else ""
        if ident:
            return f"id::{ident}"
        first = _normalize(row.get(first_col, "")) if first_col else ""
        last = _normalize(row.get(last_col, "")) if last_col else ""
        key = f"name::{first}::{last}"
        return "" if key == "name::::" else key

    @staticmethod
    def _identity_fields(row: pd.Series, id_col, first_col, last_col) -> Dict[str, str]:
        return {
            "Número de ID": _clean(row.get(id_col, "")) if id_col else "",
            "Nombre": _clean(row.get(first_col, "")) if first_col else "",
            "Apellido(s)": _clean(row.get(last_col, "")) if last_col else "",
        }

    def compare(
        self,
        existing_path: str,
        new_path: str,
        value_cols: Optional[Sequence[str]] = None,
        overwrite: bool = False,
        add_new_rows: bool = True,
    ) -> ComparisonResult:
        """Compares ``new_path`` against ``existing_path`` and optionally builds a merged table.

        Args:
            existing_path: Previous results XLSX.
            new_path: Newly computed results XLSX.
            value_cols: Columns to compare. If None, uses the columns common to both files that are not
                identity columns (ID / name / email).
            overwrite: If True, build ``merged_df`` where the new values overwrite the previous ones.
            add_new_rows: When overwriting, also append students present only in the new file.
        """
        existing = pd.read_excel(existing_path)
        new = pd.read_excel(new_path)
        existing_cols, new_cols = list(existing.columns), list(new.columns)

        e_id, e_first, e_last = self._resolve_keys(existing_cols)
        n_id, n_first, n_last = self._resolve_keys(new_cols)

        identity_cols = set(filter(None, [
            e_id, e_first, e_last, _find_column(existing_cols, _EMAIL_CANDIDATES),
        ]))
        if value_cols:
            resolved_value_cols = []
            for col in value_cols:
                actual = col if col in existing.columns or col in new.columns else _find_column(existing_cols, [col]) or _find_column(new_cols, [col])
                if actual:
                    resolved_value_cols.append(actual)
            value_columns = resolved_value_cols
        else:
            new_set = set(new_cols)
            value_columns = [c for c in existing_cols if c in new_set and c not in identity_cols]

        existing_index: Dict[str, int] = {}
        for idx, row in existing.iterrows():
            key = self._row_key(row, e_id, e_first, e_last)
            if key:
                existing_index.setdefault(key, idx)
        new_index: Dict[str, int] = {}
        for idx, row in new.iterrows():
            key = self._row_key(row, n_id, n_first, n_last)
            if key:
                new_index.setdefault(key, idx)

        existing_keys = set(existing_index)
        new_keys = set(new_index)
        common = existing_keys & new_keys
        only_existing = existing_keys - new_keys
        only_new = new_keys - existing_keys

        changes: List[Dict[str, Any]] = []
        changed_students = set()
        for key in sorted(common):
            existing_row = existing.loc[existing_index[key]]
            new_row = new.loc[new_index[key]]
            for col in value_columns:
                old_value = existing_row.get(col, "")
                new_value = new_row.get(col, "")
                if _values_differ(old_value, new_value):
                    changed_students.add(key)
                    record = self._identity_fields(existing_row, e_id, e_first, e_last)
                    record.update({
                        "Columna": col,
                        "Valor_Anterior": _clean(old_value),
                        "Valor_Nuevo": _clean(new_value),
                    })
                    changes.append(record)

        changes_df = pd.DataFrame(
            changes,
            columns=["Número de ID", "Nombre", "Apellido(s)", "Columna", "Valor_Anterior", "Valor_Nuevo"],
        )
        only_existing_df = existing.loc[[existing_index[k] for k in sorted(only_existing)]].reset_index(drop=True)
        only_new_df = new.loc[[new_index[k] for k in sorted(only_new)]].reset_index(drop=True)

        merged_df: Optional[pd.DataFrame] = None
        if overwrite:
            merged_df = existing.copy()
            for col in value_columns:
                if col not in merged_df.columns:
                    merged_df[col] = pd.NA
            for key in common:
                new_row = new.loc[new_index[key]]
                for col in value_columns:
                    if col in new.columns:
                        merged_df.at[existing_index[key], col] = new_row.get(col)
            if add_new_rows and only_new:
                extra = new.loc[[new_index[k] for k in sorted(only_new)]]
                merged_df = pd.concat([merged_df, extra], ignore_index=True)

        summary = {
            "changed_cells": len(changes),
            "changed_students": len(changed_students),
            "added": len(only_new),
            "removed": len(only_existing),
            "common": len(common),
            "value_columns": len(value_columns),
        }
        return ComparisonResult(
            changes_df=changes_df,
            only_in_existing_df=only_existing_df,
            only_in_new_df=only_new_df,
            merged_df=merged_df,
            summary=summary,
            value_columns=list(value_columns),
        )

    @staticmethod
    def export_report(result: ComparisonResult, output_path: str) -> str:
        """Writes the comparison (changes / only-existing / only-new) to a multi-sheet XLSX."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(output_path) as writer:
            (result.changes_df if not result.changes_df.empty
             else pd.DataFrame(columns=["Número de ID", "Nombre", "Apellido(s)", "Columna", "Valor_Anterior", "Valor_Nuevo"])
             ).to_excel(writer, sheet_name="Cambios", index=False)
            result.only_in_existing_df.to_excel(writer, sheet_name="Solo_en_existente", index=False)
            result.only_in_new_df.to_excel(writer, sheet_name="Solo_en_nuevo", index=False)
        return output_path

    @staticmethod
    def export_merged(result: ComparisonResult, output_path: str) -> str:
        """Writes the merged (overwritten) table to ``output_path``."""
        if result.merged_df is None:
            raise ValueError("No hay tabla combinada: ejecuta compare(..., overwrite=True).")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.merged_df.to_excel(output_path, index=False)
        return output_path
