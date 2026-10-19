# pyexamgenerator: A tool for generating exams from PDF files using AI.
# Copyright (C) 2024 Daniel Sánchez-García

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Robust parsing of the questions returned by a language model.

The same parser is used for answers obtained through an API (Gemini, OpenAI,
Anthropic) and for answers copied by hand from a web chat (Google AI Studio,
ChatGPT, Claude). It accepts, among others:

* a JSON array of objects (the format requested by the prompts),
* the same array inside a Markdown code block (```json ... ```), as produced
  by the "copy" button of the web chats, even split across several blocks or
  messages ("continúa"),
* an object that wraps the list (``{"preguntas": [...]}``),
* the legacy format of previous versions (one Python dictionary per paragraph),
* truncated answers: every complete question is recovered.

The model output is never executed: only ``json`` and ``ast.literal_eval`` are
used to decode it.
"""

import ast
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

#: Letters used for the four answer options.
OPTION_LETTERS = ("A", "B", "C", "D")

#: JSON Schema of an answer, accepted by the structured-output modes of the Gemini,
#: OpenAI and Anthropic APIs (root object, ASCII keys, no array-length limits) and by the
#: "Structured output" option of Google AI Studio. The parser maps these keys to the
#: Spanish column names; the number of options is validated in code.
QUESTIONS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "preguntas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pregunta": {"type": "string"},
                    "opciones": {"type": "array", "items": {"type": "string"}},
                    "respuesta_correcta": {"type": "string", "enum": list(OPTION_LETTERS)},
                    "texto_relevante": {"type": "string"},
                },
                "required": ["pregunta", "opciones", "respuesta_correcta", "texto_relevante"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["preguntas"],
    "additionalProperties": False,
}

_QUESTION_KEY = "Pregunta"
_OPTIONS_KEY = "Opciones"
_ANSWER_KEY = "Respuesta correcta"
_RELEVANT_TEXT_KEY = "Texto relevante"

# Normalised alias -> canonical key.
_KEY_ALIASES = {
    "pregunta": _QUESTION_KEY,
    "enunciado": _QUESTION_KEY,
    "question": _QUESTION_KEY,
    "question text": _QUESTION_KEY,
    "stem": _QUESTION_KEY,
    "opciones": _OPTIONS_KEY,
    "opciones de respuesta": _OPTIONS_KEY,
    "respuestas": _OPTIONS_KEY,
    "alternativas": _OPTIONS_KEY,
    "options": _OPTIONS_KEY,
    "choices": _OPTIONS_KEY,
    "answers": _OPTIONS_KEY,
    "respuesta correcta": _ANSWER_KEY,
    "respuestacorrecta": _ANSWER_KEY,
    "correcta": _ANSWER_KEY,
    "opcion correcta": _ANSWER_KEY,
    "solucion": _ANSWER_KEY,
    "correct answer": _ANSWER_KEY,
    "correct option": _ANSWER_KEY,
    "correct": _ANSWER_KEY,
    "answer": _ANSWER_KEY,
    "texto relevante": _RELEVANT_TEXT_KEY,
    "textorelevante": _RELEVANT_TEXT_KEY,
    "justificacion": _RELEVANT_TEXT_KEY,
    "explicacion": _RELEVANT_TEXT_KEY,
    "fuente": _RELEVANT_TEXT_KEY,
    "cita": _RELEVANT_TEXT_KEY,
    "relevant text": _RELEVANT_TEXT_KEY,
    "source text": _RELEVANT_TEXT_KEY,
    "explanation": _RELEVANT_TEXT_KEY,
    "justification": _RELEVANT_TEXT_KEY,
    "evidence": _RELEVANT_TEXT_KEY,
}

# Keys of a wrapper object that may contain the list of questions.
_LIST_WRAPPER_KEYS = ("preguntas", "questions", "items", "data", "resultado", "results")

_FENCED_BLOCK_RE = re.compile(r"```[^\n`]*\n(.*?)(?:```|\Z)", re.DOTALL)
_QUESTION_PREFIX_RE = re.compile(r"^\s*pregunta\s*\d+\s*[:.)-]\s*", re.IGNORECASE)
_OPTION_LABEL_RE = re.compile(r"^\s*[\(\[]?([A-Da-d])\s*[\)\]\.:\-]\s*")
_ANSWER_LETTER_RE = re.compile(
    r"^\s*(?:la\s+)?(?:opci[oó]n|respuesta|letra|option|answer)?\s*[:\-]?\s*[\(\[]?([A-Da-d])[\)\]]?(?=$|[\s\.\):,;-])"
)


def _normalize_key(key: Any) -> str:
    text = unicodedata.normalize("NFKD", str(key))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[_\-]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _normalize_for_compare(text: Any) -> str:
    return re.sub(r"\s+", " ", _normalize_key(text)).strip(" .")


def _repair_json(text: str) -> str:
    """Fixes the most common deviations from strict JSON (outside strings)."""
    text = text.replace("“", '"').replace("”", '"')
    out = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        matched = False
        for py_literal, json_literal in (("True", "true"), ("False", "false"), ("None", "null")):
            if text.startswith(py_literal, i) and not (i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_")):
                end = i + len(py_literal)
                if end >= len(text) or not (text[end].isalnum() or text[end] == "_"):
                    out.append(json_literal)
                    i = end
                    matched = True
                    break
        if matched:
            continue
        out.append(ch)
        i += 1
    repaired = "".join(out)
    # Trailing commas before a closing bracket.
    return re.sub(r",\s*([\]}])", r"\1", repaired)


def _loads(text: str) -> Optional[Any]:
    """Decodes JSON or a Python literal without executing any code."""
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text, strict=False)
    except (ValueError, TypeError):
        pass
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        pass
    try:
        return json.loads(_repair_json(text), strict=False)
    except (ValueError, TypeError):
        return None


def _find_matching_brace(text: str, start: int) -> int:
    """Returns the index of the ``}`` closing the ``{`` at ``start`` or -1."""
    depth = 0
    quote = None
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _canonical_items(obj: Any) -> List[Dict]:
    """Extracts the dictionaries that look like questions from a decoded value."""
    if isinstance(obj, list):
        items: List[Dict] = []
        for element in obj:
            items.extend(_canonical_items(element))
        return items
    if isinstance(obj, dict):
        normalized_keys = {_normalize_key(k) for k in obj}
        if any(_KEY_ALIASES.get(k) == _QUESTION_KEY for k in normalized_keys):
            return [obj]
        for key, value in obj.items():
            if _normalize_key(key) in _LIST_WRAPPER_KEYS and isinstance(value, (list, dict)):
                return _canonical_items(value)
        # Single wrapper with an arbitrary name: {"tema 1": [...]}.
        nested = [v for v in obj.values() if isinstance(v, list)]
        if len(nested) == 1:
            return _canonical_items(nested[0])
    return []


def _scan_objects(text: str) -> List[Dict]:
    """Finds every balanced ``{...}`` that decodes to a question (or a list of them)."""
    items: List[Dict] = []
    i = 0
    while i < len(text):
        start = text.find("{", i)
        if start == -1:
            break
        end = _find_matching_brace(text, start)
        if end == -1:
            i = start + 1
            continue
        found = _canonical_items(_loads(text[start:end + 1]))
        if found:
            items.extend(found)
            i = end + 1
        else:
            i = start + 1
    return items


def extract_question_dicts(response_text: str) -> List[Dict]:
    """
    Extracts the raw question dictionaries contained in a model answer.

    Args:
        response_text (str): Text returned by the model or pasted by the user.

    Returns:
        List[Dict]: Raw dictionaries (keys as written by the model), in order.
    """
    if not response_text or not str(response_text).strip():
        return []
    text = str(response_text).lstrip("﻿")

    fenced_blocks = [block for block in _FENCED_BLOCK_RE.findall(text) if block.strip()]
    if fenced_blocks:
        items: List[Dict] = []
        for block in fenced_blocks:
            decoded = _canonical_items(_loads(block))
            items.extend(decoded if decoded else _scan_objects(block))
        if items:
            return items

    decoded = _canonical_items(_loads(text))
    if decoded:
        return decoded

    # Arrays embedded in surrounding prose: "Aquí tienes las preguntas: [...]".
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if 0 <= first_bracket < last_bracket:
        decoded = _canonical_items(_loads(text[first_bracket:last_bracket + 1]))
        if decoded:
            return decoded

    return _scan_objects(text)


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_to_text(v) for v in value if _to_text(v))
    return str(value).strip()


def _extract_options(raw: Dict[str, Any], canonical: Dict[str, Any]) -> List[str]:
    options = canonical.get(_OPTIONS_KEY)
    if isinstance(options, dict):
        by_letter = {}
        for key, value in options.items():
            match = re.match(r"^\s*[\(\[]?([A-Da-d])[\)\]\.:]?\s*$", str(key))
            if match:
                by_letter[match.group(1).upper()] = value
        if by_letter:
            options = [by_letter.get(letter, "") for letter in OPTION_LETTERS if letter in by_letter]
        else:
            options = list(options.values())
    if isinstance(options, str):
        lines = [line for line in options.splitlines() if line.strip()]
        options = lines if len(lines) > 1 else [options]
    if not isinstance(options, (list, tuple)):
        # Separate keys: "Respuesta A", "Opción B", "A", "a)".
        by_letter = {}
        for key, value in raw.items():
            match = re.match(r"^(?:respuesta|opcion|option|answer)?\s*([a-d])\)?$", _normalize_key(key))
            if match:
                by_letter[match.group(1).upper()] = value
        options = [by_letter[letter] for letter in OPTION_LETTERS if letter in by_letter]

    cleaned = [_to_text(option) for option in options]
    # Remove "A) ", "b. "... only when every option carries its expected label.
    labels = [_OPTION_LABEL_RE.match(option) for option in cleaned]
    if cleaned and all(
        match and match.group(1).upper() == OPTION_LETTERS[idx]
        for idx, match in enumerate(labels[:len(OPTION_LETTERS)])
    ) and len(cleaned) <= len(OPTION_LETTERS):
        cleaned = [option[match.end():].strip() for option, match in zip(cleaned, labels)]
    return cleaned


def _resolve_answer_letter(answer: Any, options: List[str]) -> Optional[str]:
    if isinstance(answer, bool) or answer is None:
        return None
    if isinstance(answer, (list, tuple)):
        return _resolve_answer_letter(answer[0], options) if len(answer) == 1 else None
    if isinstance(answer, (int, float)):
        # A number is ambiguous (0- or 1-based index): it is rejected and reported.
        return None
    text = _to_text(answer)
    if not text:
        return None
    valid_letters = OPTION_LETTERS[:len(options)]

    def match_option_text() -> Optional[str]:
        normalized_answer = _normalize_for_compare(text)
        for idx, option in enumerate(options):
            if normalized_answer and normalized_answer == _normalize_for_compare(option):
                return OPTION_LETTERS[idx]
        return None

    # The full text of an option ("A partir de 50 trabajadores") must not be read as a letter.
    if len(text) > 3:
        by_text = match_option_text()
        if by_text:
            return by_text
    match = _ANSWER_LETTER_RE.match(text)
    if match and match.group(1).upper() in valid_letters:
        return match.group(1).upper()
    by_text = match_option_text()
    if by_text:
        return by_text
    # Short sentences such as "La correcta es la B".
    if len(text) <= 40:
        letters = set(re.findall(r"(?<![A-Za-zÁÉÍÓÚáéíóúÑñ])([A-D])(?![A-Za-zÁÉÍÓÚáéíóúÑñ])", text))
        if len(letters) == 1:
            letter = letters.pop()
            if letter in valid_letters:
                return letter
    return None


def normalize_question(raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Converts a raw dictionary into the canonical question format.

    Returns:
        Tuple[Optional[Dict], Optional[str]]: ``(question, None)`` when valid,
        where ``question`` has the keys ``Pregunta``, ``Opciones`` (4 strings),
        ``Respuesta correcta`` (letter A-D) and ``Texto relevante``; or
        ``(None, reason)`` when the question cannot be used.
    """
    if not isinstance(raw, dict):
        return None, "No es un objeto con clave/valor."

    canonical: Dict[str, Any] = {}
    for key, value in raw.items():
        target = _KEY_ALIASES.get(_normalize_key(key))
        if target and target not in canonical:
            canonical[target] = value

    statement = _QUESTION_PREFIX_RE.sub("", _to_text(canonical.get(_QUESTION_KEY)), count=1).strip()
    if not statement:
        return None, "Falta el enunciado de la pregunta."

    options = _extract_options(raw, canonical)
    if len(options) != len(OPTION_LETTERS) or any(not option for option in options):
        return None, (
            f"Se esperaban {len(OPTION_LETTERS)} opciones no vacías y se encontraron "
            f"{len([o for o in options if o])}."
        )

    if len({_normalize_for_compare(option) for option in options}) != len(options):
        return None, "Hay opciones repetidas: la respuesta correcta sería ambigua al barajar."

    letter = _resolve_answer_letter(canonical.get(_ANSWER_KEY), options)
    if letter is None:
        return None, f"Respuesta correcta no válida: {_to_text(canonical.get(_ANSWER_KEY))!r}."

    return {
        _QUESTION_KEY: statement,
        _OPTIONS_KEY: options,
        _ANSWER_KEY: letter,
        _RELEVANT_TEXT_KEY: _to_text(canonical.get(_RELEVANT_TEXT_KEY)),
    }, None


def parse_questions_response(response_text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Parses a model answer into canonical questions.

    Args:
        response_text (str): Text returned by the model or pasted from a web chat.

    Returns:
        Tuple[List[Dict], List[Dict]]: ``(questions, errors)``. ``questions`` are
        canonical dictionaries (see :func:`normalize_question`) without repeated
        statements; ``errors`` lists the discarded fragments as
        ``{"Fragmento": ..., "Motivo": ...}``.
    """
    questions: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    seen_statements = set()
    for raw in extract_question_dicts(response_text):
        question, reason = normalize_question(raw)
        if question is None:
            fragment = json.dumps(raw, ensure_ascii=False, default=str) if isinstance(raw, dict) else str(raw)
            errors.append({"Fragmento": fragment[:300], "Motivo": reason or "Formato no reconocido."})
            continue
        key = _normalize_for_compare(question[_QUESTION_KEY])
        if key in seen_statements:
            continue
        seen_statements.add(key)
        questions.append(question)
    return questions, errors
