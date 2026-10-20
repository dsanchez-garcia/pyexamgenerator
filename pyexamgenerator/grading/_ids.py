"""Normalización compartida de identificadores de alumno (Número de ID, DNI, ID_Oficial...).

pandas lee una columna numérica de IDs con alguna celda vacía como ``float64`` (``11111111`` pasa a
``11111111.0``) y las celdas vacías como ``NaN``, que ``str()`` convierte en el texto ``'nan'``.
Si cada módulo construye sus claves con ``str(valor)``, el mismo alumno no coincide entre ficheros
y todos los alumnos sin ID comparten la clave ``'nan'``. Todas las claves de alumno deben usar
:func:`normalize_id`.
"""

from __future__ import annotations

import math
import numbers
import re
from typing import Any

import pandas as pd

# Textos que representan una celda vacía tras pasar por pandas/Excel.
_EMPTY_ID_TEXTS = {"", "nan", "none", "<na>", "nat"}


def normalize_id(value: Any) -> str:
    """Devuelve el ID como texto normalizado, o ``''`` si está vacío.

    - ``None``, ``NaN``, ``pd.NA``, ``''`` y los textos ``'nan'``/``'none'``/``'<na>'``/``'nat'``
      se consideran vacíos.
    - Los números enteros (``12345678`` o ``12345678.0``) y los textos ``'12345678.0'`` pasan a
      ``'12345678'``.
    - Cualquier otro texto se conserva tal cual (sin espacios exteriores), incluidos los ceros a
      la izquierda (``'001234'``).
    """
    if value is None or isinstance(value, bool):
        return "" if value is None else str(value)
    if isinstance(value, numbers.Integral):
        return str(int(value))
    if isinstance(value, numbers.Real):
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return ""
        if number.is_integer():
            return str(int(number))
        return str(value).strip()
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    text = str(value).strip()
    if text.lower() in _EMPTY_ID_TEXTS:
        return ""
    # Excel/pandas pueden devolver IDs enteros como texto "12345.0".
    if re.fullmatch(r"[-+]?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def is_empty_id(value: Any) -> bool:
    """True si ``value`` no contiene un ID utilizable (ver :func:`normalize_id`)."""
    return normalize_id(value) == ""
