"""Shared normalization of student identifiers ('Número de ID') for the grading workflows.

pandas reads an integer ID column as float as soon as one cell is blank (``12345678`` becomes
``12345678.0``), so comparing raw ``str(value)`` splits one student into two keys. Every module that
matches students by ID should go through :func:`normalize_id`.
"""

import re

import pandas as pd


def normalize_id(value) -> str:
    """Returns a canonical text form of a student ID ('' when missing).

    Integer-like floats (``12345.0``) and their text form (``"12345.0"``) become ``"12345"``; textual
    IDs are kept as-is so leading zeros (``"001234"``) are preserved.
    """
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).strip()

    text = str(value).strip()
    if not text:
        return ""
    if text.lower() in {"nan", "none", "<na>"}:
        return ""
    # Excel/pandas may surface integer-like IDs as e.g. "12345.0".
    if re.fullmatch(r"[-+]?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text
