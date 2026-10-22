"""Text, column and grade rules shared by the grading modules.

Moodle and the teachers' own workbooks write column names with or without accents, in any case and
sometimes with mojibake (``"Nmero de ID"``), and grades as numbers or as text with a decimal comma
(``"7,50"``). Every grading module compares and reads them with these helpers, so the same cell
means the same in all of them.
"""

import math
import re
import unicodedata
from typing import Any, Iterable, Optional

import pandas as pd

_DECIMAL = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _is_missing(value: Any) -> bool:
    """True for an empty cell: None, NaN, NaT or ``pd.NA``."""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):  # list-like values are never an empty cell
        return False


def normalize_text(value: Any) -> str:
    """Lower case without accents or surrounding spaces; punctuation is kept ('' for an empty cell)."""
    if _is_missing(value):
        return ""
    text = unicodedata.normalize("NFD", str(value).strip().lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_key(value: Any) -> str:
    """:func:`normalize_text` with only letters and digits: ``"Apellido(s)"`` → ``"apellidos"``."""
    return re.sub(r"[^a-z0-9]", "", normalize_text(value))


def find_column(columns: Iterable[Any], candidates: Iterable[Optional[str]]) -> Optional[str]:
    """First of ``candidates`` found in ``columns`` comparing with :func:`normalize_key`, or None.

    Empty candidates (None or '') are skipped.
    """
    by_key = {normalize_key(column): column for column in columns}
    for candidate in candidates:
        key = normalize_key(candidate)
        if key and key in by_key:
            return by_key[key]
    return None


def clean_text(value: Any) -> str:
    """The cell as text without surrounding spaces ('' for an empty cell)."""
    return "" if _is_missing(value) else str(value).strip()


def parse_decimal(value: Any) -> Optional[float]:
    """A grade as a float: a number, or text with a decimal comma or point (``"7,50"``, ``"-0,25"``).

    Empty cells, ``"-"`` and any other text (``"Ausente"``, ``"nan"``, ``"1e3"``) give None.
    """
    if isinstance(value, bool) or _is_missing(value):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip().replace(",", ".")
    return float(text) if _DECIMAL.fullmatch(text) else None
