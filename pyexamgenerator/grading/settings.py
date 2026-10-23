"""Values of the grading flows that depend on the institution (ARC-10).

The macro-groups of the students, the topics with a name of their own, the PIR bonus rule and the
column names of the Moodle exports default to those of the Universidad de Cádiz. To change them,
edit ``grading_settings.json`` in the user's configuration folder
(:func:`pyexamgenerator.user_config.config_dir`; the application opens it from «Ayuda»). Only the
keys present in the file change; the others keep their default::

    {
      "grupos": [
        {"nombre": "GIM", "codigo": "GIM", "en_nombre_de_fichero": ["GIM"]},
        {"nombre": "GITI-GIE-GIEI", "codigo": "GGG", "en_nombre_de_fichero": ["GITI", "GIE"]}
      ],
      "temas_con_nombre": {"LPRL": "\\\\bley\\\\s*31\\\\s*(?:19)?95\\\\b", "RSP": "\\\\brd\\\\s*39\\\\s*(?:19)?97\\\\b"},
      "pir": {"nota_minima_cuestionario": 7.5, "puntos": 1.0},
      "columnas_moodle": {
        "id": ["Número de ID", "Nmero de ID"],
        "nombre": ["Nombre"],
        "apellidos": ["Apellido(s)", "Apellidos", "Apellido"],
        "correo": ["Dirección de correo", "Direccin de correo"],
        "nota": ["Calificación/10,00", "Calificacin/10,00"]
      }
    }

- **grupos**: the groups of the subject, as Moodle names them in the quizzes (``Cuestionario <tema> -
  <grupo> (Real)``) and the session titles. ``codigo`` is their short code in the class columns of the
  attendance table, and ``en_nombre_de_fichero`` the texts that identify an enrollment file. When a
  text could match several groups, the longest name is tried first.
- **temas_con_nombre**: topics that are not called «Tema NN», with the regular expression that finds
  them in a session or quiz title (written in lowercase, without accents, words separated by spaces).
- **pir**: the minimum grade of every topic quiz and the points of the bonus, when a flow is not given
  other values.
- **columnas_moodle**: the names a Moodle export may give each column (the misspelt ones, like
  «Nmero de ID», come from exports with broken accents).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from pyexamgenerator import user_config
from pyexamgenerator.grading._text import normalize_key

SETTINGS_FILE = "grading_settings.json"


@dataclass(frozen=True)
class Group:
    """A macro-group of students: the groups of a subject that share sessions and quizzes."""

    name: str
    """As Moodle writes it in quiz names and session titles, e.g. 'GITI-GIE-GIEI'."""
    code: str
    """Short code in the class columns of the attendance table, e.g. 'GGG'."""
    file_markers: Tuple[str, ...]
    """Texts that identify the group in the name of an enrollment file, e.g. ('GITI', 'GIE')."""


DEFAULT_GROUPS = (
    Group("GIM", "GIM", ("GIM",)),
    Group("GITI-GIE-GIEI", "GGG", ("GITI", "GIE")),
)
DEFAULT_NAMED_TOPICS = (
    ("LPRL", r"\bley\s*31\s*(?:19)?95\b"),
    ("RSP", r"\brd\s*39\s*(?:19)?97\b"),
)
# Semantic column -> the names a Moodle export may give it.
DEFAULT_MOODLE_COLUMNS: Mapping[str, Tuple[str, ...]] = {
    "id": ("Número de ID", "Nmero de ID"),
    "first_name": ("Nombre",),
    "last_name": ("Apellido(s)", "Apellidos", "Apellido"),
    "email": ("Dirección de correo", "Direccin de correo"),
    "grade": ("Calificación/10,00", "Calificacin/10,00"),
}
# Keys of the JSON file (in Spanish: teachers edit it) -> keys of DEFAULT_MOODLE_COLUMNS.
_COLUMN_KEYS = {"id": "id", "nombre": "first_name", "apellidos": "last_name", "correo": "email", "nota": "grade"}


@dataclass(frozen=True)
class GradingSettings:
    """The institution-specific values of the grading flows (see the module documentation)."""

    groups: Tuple[Group, ...] = DEFAULT_GROUPS
    named_topics: Tuple[Tuple[str, str], ...] = DEFAULT_NAMED_TOPICS
    """``(name, regular expression)`` pairs, tried in order."""
    pir_min_quiz_grade: float = 7.5
    pir_bonus_points: float = 1.0
    moodle_columns: Mapping[str, Tuple[str, ...]] = field(default_factory=lambda: dict(DEFAULT_MOODLE_COLUMNS))

    @property
    def group_names(self) -> List[str]:
        """Group names in the configured order (the order of the output columns)."""
        return [group.name for group in self.groups]

    @property
    def groups_longest_first(self) -> List[Group]:
        """Groups in the order to recognise them: a longer name is more specific."""
        return sorted(self.groups, key=lambda group: len(group.name), reverse=True)

    @property
    def named_topic_names(self) -> List[str]:
        return [name for name, _pattern in self.named_topics]

    def to_json(self) -> Dict[str, Any]:
        """The settings with the keys of ``grading_settings.json``."""
        return {
            "grupos": [
                {"nombre": g.name, "codigo": g.code, "en_nombre_de_fichero": list(g.file_markers)} for g in self.groups
            ],
            "temas_con_nombre": dict(self.named_topics),
            "pir": {"nota_minima_cuestionario": self.pir_min_quiz_grade, "puntos": self.pir_bonus_points},
            "columnas_moodle": {key: list(self.moodle_columns[name]) for key, name in _COLUMN_KEYS.items()},
        }


def settings_path() -> Path:
    """Where the settings file is read from: ``grading_settings.json`` in the configuration folder."""
    return user_config.config_path(SETTINGS_FILE)


def _invalid(path: Path, problem: str) -> ValueError:
    return ValueError(f"La configuración de corrección «{path}» no es válida: {problem}")


def _text_list(value: Any, path: Path, what: str) -> Tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
        raise _invalid(path, f"{what} debe ser una lista de textos no vacía.")
    return tuple(v.strip() for v in value)


def _parse(data: Any, path: Path) -> GradingSettings:
    if not isinstance(data, dict):
        raise _invalid(path, "debe ser un objeto JSON ({...}).")
    unknown = sorted(set(data) - {"grupos", "temas_con_nombre", "pir", "columnas_moodle"})
    if unknown:
        raise _invalid(path, f"claves desconocidas: {', '.join(unknown)}.")
    settings = GradingSettings()

    if "grupos" in data:
        groups = data["grupos"]
        if not isinstance(groups, list) or not groups:
            raise _invalid(path, "«grupos» debe ser una lista no vacía.")
        parsed_groups = []
        for item in groups:
            if not isinstance(item, dict) or not isinstance(item.get("nombre"), str) or not item["nombre"].strip():
                raise _invalid(path, "cada grupo necesita un «nombre».")
            name = item["nombre"].strip()
            if not normalize_key(name):  # groups are recognised by the letters and digits of their name
                raise _invalid(path, f"el nombre del grupo «{name}» necesita letras o cifras.")
            # By default, the letters of the name ('GITI-GIE-GIEI' -> 'GITIGIEGIEI').
            code = item.get("codigo") or re.sub(r"[^A-Z]", "", normalize_key(name).upper())
            # The code goes into the class column names (C01_0303_T02_GIM__...), read back by the
            # per-topic report: letters only, and not the code of an unknown group.
            if not isinstance(code, str) or not re.fullmatch(r"[A-Z]+", code.strip()) or code.strip() == "GRP":
                raise _invalid(path, f"el «codigo» del grupo {name} debe tener solo letras mayúsculas (y no ser GRP).")
            markers = _text_list(item.get("en_nombre_de_fichero", [name]), path, f"«en_nombre_de_fichero» de {name}")
            parsed_groups.append(Group(name, code.strip(), markers))
        if len({normalize_key(g.name) for g in parsed_groups}) != len(parsed_groups):
            raise _invalid(path, "hay grupos repetidos.")
        settings = replace(settings, groups=tuple(parsed_groups))

    if "temas_con_nombre" in data:
        topics = data["temas_con_nombre"]
        if not isinstance(topics, dict):
            raise _invalid(path, "«temas_con_nombre» debe ser un objeto {\"nombre\": \"expresión regular\"}.")
        parsed_topics = []
        for name, pattern in topics.items():
            # Also part of the class column names: letters and then digits, and neither the code of
            # a numbered topic (T02) nor that of an unknown one (TOP).
            if not re.fullmatch(r"[A-Z]+\d*", name) or re.fullmatch(r"T\d{2}", name) or name == "TOP":
                raise _invalid(path, f"el tema «{name}» debe tener mayúsculas y, al final, cifras (no T02 ni TOP).")
            if not isinstance(pattern, str):
                raise _invalid(path, f"la expresión del tema {name} debe ser un texto.")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise _invalid(path, f"la expresión del tema {name} no es válida ({exc}).") from exc
            parsed_topics.append((name, pattern))
        settings = replace(settings, named_topics=tuple(parsed_topics))

    if "pir" in data:
        pir = data["pir"]
        if not isinstance(pir, dict) or set(pir) - {"nota_minima_cuestionario", "puntos"}:
            raise _invalid(path, "«pir» admite «nota_minima_cuestionario» y «puntos».")
        values = {"nota_minima_cuestionario": settings.pir_min_quiz_grade, "puntos": settings.pir_bonus_points}
        for key in values:
            if key in pir:
                value = pir[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10:
                    raise _invalid(path, f"«pir.{key}» debe ser un número entre 0 y 10.")
                values[key] = float(value)
        settings = replace(
            settings, pir_min_quiz_grade=values["nota_minima_cuestionario"], pir_bonus_points=values["puntos"]
        )

    if "columnas_moodle" in data:
        columns = data["columnas_moodle"]
        if not isinstance(columns, dict) or set(columns) - set(_COLUMN_KEYS):
            raise _invalid(path, f"«columnas_moodle» admite {', '.join(_COLUMN_KEYS)}.")
        merged = dict(settings.moodle_columns)
        for key, names in columns.items():
            merged[_COLUMN_KEYS[key]] = _text_list(names, path, f"«columnas_moodle.{key}»")
        settings = replace(settings, moodle_columns=merged)

    return settings


def load_settings(path: Optional[Path] = None) -> GradingSettings:
    """Reads the settings file (by default :func:`settings_path`); without it, the defaults.

    Raises:
        ValueError: If the file is not valid JSON or has values that cannot be used.
    """
    path = Path(path) if path is not None else settings_path()
    if not path.exists():
        return GradingSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _invalid(path, f"no se puede leer como JSON ({exc}).") from exc
    return _parse(data, path)


_cache: Dict[str, Any] = {}


def current_settings() -> GradingSettings:
    """:func:`load_settings` of the user's file, read again only when the file changes."""
    path = settings_path()
    try:
        stat = path.stat()
        stamp: Optional[Tuple[int, int]] = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        stamp = None
    key = (str(path), stamp)
    if _cache.get("key") != key:
        _cache["settings"] = load_settings(path)
        _cache["key"] = key
    return _cache["settings"]


def write_default_settings(path: Optional[Path] = None) -> Path:
    """Writes the default settings, to edit them, unless the file already exists. Returns its path."""
    path = Path(path) if path is not None else settings_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(GradingSettings().to_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def moodle_columns(column: str) -> Tuple[str, ...]:
    """Names a Moodle export may give ``column`` ('id', 'first_name', 'last_name', 'email', 'grade')."""
    return current_settings().moodle_columns[column]
