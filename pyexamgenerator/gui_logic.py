"""GUI logic that does not need Tk: reading what the user types in the fields and composing messages.

It lives apart from ``main_app.py`` so it can be tested without a display. Nothing here imports
``tkinter``; the window reads its widgets and passes the text to these functions.
"""

import math
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional


def split_paths(text: Optional[str]) -> List[str]:
    """Splits a list of paths separated by ';' (a ',' can be part of a file name).

    A list typed by hand with ',' is still accepted when every piece is an existing file.
    """
    parts = [p.strip() for p in str(text or "").replace("\n", ";").split(";") if p.strip()]
    if len(parts) == 1 and "," in parts[0] and not os.path.exists(parts[0]):
        comma_parts = [p.strip() for p in parts[0].split(",") if p.strip()]
        if comma_parts and all(os.path.exists(p) for p in comma_parts):
            return comma_parts
    return parts


def _parse_number(text: str) -> float:
    """A number with ',' or '.' as decimal separator; ValueError for anything else ('nan' and 'inf' too)."""
    value = float(str(text).strip().replace(",", "."))
    if not math.isfinite(value):
        raise ValueError(f"No es un número: {text!r}")
    return value


def parse_penalty(raw_penalty: Optional[str], default: float = -25.0) -> float:
    """Penalty typed in the exam tab, with ',' or '.' as decimal separator (``default`` if empty)."""
    cleaned = (raw_penalty or "").strip()
    if not cleaned:
        return default
    return _parse_number(cleaned)


def parse_weight(text: str, owner: str) -> float:
    """Parses a weight (>= 0) written with ',' or '.' as decimal separator; ValueError with a clear message."""
    try:
        weight = _parse_number(text)
    except ValueError:
        raise ValueError(f"Peso no válido para '{owner}': '{str(text).strip()}'. Usa un número, p. ej. 0,4.") from None
    if weight < 0:
        raise ValueError(f"El peso de '{owner}' no puede ser negativo: '{str(text).strip()}'.")
    return weight


def parse_final_grade_files(text: Optional[str]) -> List[Dict[str, Any]]:
    """Exams of the weighted final grade: ``path|weight|label ; ...`` (weight and label optional)."""
    sources = []
    for item in str(text or "").replace("\n", ";").split(";"):
        item = item.strip()
        if not item:
            continue
        parts = [p.strip() for p in item.split("|")]
        source: Dict[str, Any] = {"path": parts[0]}
        if len(parts) > 1 and parts[1]:
            source["weight"] = parse_weight(parts[1], parts[0])
        if len(parts) > 2 and parts[2]:
            source["label"] = parts[2]
        sources.append(source)
    return sources


def parse_column_weights(text: Optional[str]) -> Dict[str, float]:
    """Columns of the weighted final grade: ``Column|weight ; ...`` (items without '|' are skipped)."""
    weights = {}
    for item in str(text or "").replace("\n", ";").split(";"):
        item = item.strip()
        if not item or "|" not in item:
            continue
        col, weight = item.rsplit("|", 1)
        weights[col.strip()] = parse_weight(weight, col.strip())
    return weights


def parse_forced_types(raw_text: Optional[str]) -> Dict[str, str]:
    """Exam type forced per image: ``image=TYPE`` separated by ';', ',' or new lines."""
    forced: Dict[str, str] = {}
    normalized = str(raw_text or "").replace("\n", ";").replace(",", ";")
    for item in normalized.split(";"):
        chunk = item.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        key = name.strip()
        exam_type = value.strip().upper()
        if key and exam_type:
            forced[key] = exam_type
    return forced


def parse_exam_names(text: Optional[str]) -> Optional[List[str]]:
    """Names of the exam versions, separated by ',' (None if there are none).

    Empty names are skipped: a trailing comma ('1A, 1B,') used to add a version without a name.
    """
    names = [name.strip() for name in str(text or "").split(',') if name.strip()]
    return names or None


def parse_questions_per_topic(text: Optional[str]) -> Dict[str, int]:
    """``Topic:count`` pairs separated by ','; ValueError if one is not written that way.

    The count is what follows the last ':', so a topic may contain ':' ('Tema 1: Leyes:2'); it must
    be a whole number >= 0. Empty items (a trailing comma) are skipped.
    """
    questions_per_topic: Dict[str, int] = {}
    for item in str(text or "").split(','):
        if not item.strip():
            continue
        topic, separator, quantity = item.strip().rpartition(':')
        count = int(quantity.strip())
        if not separator or not topic.strip() or count < 0:
            raise ValueError(f"Se esperaba 'Tema:número' y se ha encontrado {item.strip()!r}.")
        questions_per_topic[topic.strip()] = count
    return questions_per_topic


def integration_warnings(summary: Any, incidents_path: str) -> List[str]:
    """Warnings for the summary of an OCR integration (summary rows removed, blocked OCR rows)."""
    if not isinstance(summary, dict):
        return []
    warning_msgs: List[str] = []
    removed_summary_rows = int(summary.get("general_summary_rows_removed", 0) or 0)
    if removed_summary_rows > 0:
        warning_msgs.append(
            "Se eliminaron automáticamente "
            f"{removed_summary_rows} fila(s) de promedio/resumen "
            "en las notas de teoría antes de integrar OCR."
        )
    blocked = [
        ("blocked_missing_identity", "Sin identidad (ID o nombre+apellidos)"),
        ("blocked_unmatched", "Alumno no encontrado en teoría"),
        ("blocked_missing_target", "Sin columna destino en teoría"),
        ("blocked_missing_grade", "Sin nota OCR válida"),
    ]
    parts = [
        f"- {label}: {int(summary.get(key, 0) or 0)}"
        for key, label in blocked if int(summary.get(key, 0) or 0) > 0
    ]
    if parts:
        warning_msgs.append(
            "Durante la integración se bloquearon filas OCR:\n"
            + "\n".join(parts)
            + f"\nRevisa: {incidents_path}"
        )
    overwritten = int(summary.get("grades_overwritten", 0) or 0)
    if overwritten > 0:
        warning_msgs.append(
            f"La nota OCR sustituyó a una nota distinta que ya había en teoría en {overwritten} alumno(s); "
            "comprueba que cada hoja es de ese alumno.\n"
            f"Revisa: {incidents_path}"
        )
    return warning_msgs


def justification_warnings(summary_rows: Iterable[Mapping[str, Any]], review_hint: str) -> List[str]:
    """Warnings for the justification emails that justify nothing (GRD-6).

    ``summary_rows`` are the rows of ``justificaciones_resumen.xlsx``: emails not assigned to any
    student (``Revisar``) and emails of a student that do not look like a justification
    (``Cuenta_Para_Justificar``). ``review_hint`` tells where to look.
    """
    rows = list(summary_rows)
    unassigned = sum(1 for row in rows if row.get("Revisar") == "si")
    not_counted = sum(1 for row in rows if row.get("Revisar") == "no" and row.get("Cuenta_Para_Justificar") == "no")
    warnings: List[str] = []
    if unassigned:
        warnings.append(
            f"{unassigned} correo(s) de justificación no se han asignado a ningún alumno: el remitente no "
            "coincide con la matrícula (ni por correo ni por nombre) o encaja con varios alumnos. No "
            "justifican faltas hasta que corrijas el remitente en el Excel de justificaciones.\n"
            f"{review_hint}"
        )
    if not_counted:
        warnings.append(
            f"{not_counted} correo(s) de alumnos no justifican faltas porque no parecen una justificación "
            f"(consultas, agradecimientos…).\n{review_hint}"
        )
    return warnings


def answer_grading_warnings(incidents: int, incidents_path: str) -> List[str]:
    """Warning for the rows of an answers file not graded or repeated (GRD-6)."""
    if not incidents:
        return []
    return [
        f"{incidents} fila(s) del fichero de respuestas tienen incidencias: un nombre que no coincide con "
        "la matrícula o que encaja con varios alumnos (esas filas no se han corregido), o dos filas del "
        f"mismo alumno.\nRevisa: {incidents_path}"
    ]
