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

"""Column names of the question bank and of the generated exams' XLSX (ARC-3).

The question bank is an Excel file that teachers review and edit by hand, and the exams written
from it (``..._completo.xlsx``) have the same columns. These names are a contract with every
existing bank: **never rename them**. Code refers to them through these constants instead of
repeating the literal (``tests/test_schema.py`` pins their values).

Example, in a script::

    import pandas as pd
    from pyexamgenerator import schema

    bank = pd.read_excel("banco.xlsx")
    by_topic = bank.groupby(schema.TOPIC)[schema.QUESTION].count()
"""

QUESTION_NUMBER = "Número de pregunta"
"""Question number. Not unique once banks are merged: do not use it as a key."""

TOPIC = "Tema"
"""Topic of the question (at first, taken from the source PDF's name)."""

STATUS = "Estado"
"""Review status: :data:`STATUS_PENDING` or :data:`STATUS_ACCEPTABLE` (compared ignoring case)."""

QUESTION = "Pregunta"
"""Question statement."""

ANSWER_A = "Respuesta A"
ANSWER_B = "Respuesta B"
ANSWER_C = "Respuesta C"
ANSWER_D = "Respuesta D"

CORRECT_ANSWER = "Respuesta correcta"
"""Letter of the correct answer (A-D in banks; lowercase in the generated exams)."""

RELEVANT_TEXT = "Texto relevante"
"""Excerpt of the source document that justifies the answer."""

TIMES_USED = "Veces usada en examen"
"""How many exams used the question: the sum of the per-exam usage columns."""

USAGE_SUFFIX = "_uso"
"""Suffix of the per-exam usage columns (``<label>_uso``, 1 if the question was in that exam)."""

STATUS_PENDING = "Pendiente de revisar"
"""Status of a question just generated."""

STATUS_ACCEPTABLE = "Aceptable"
"""Status of a reviewed question that can go into exams."""

ANSWER_COLUMNS = (ANSWER_A, ANSWER_B, ANSWER_C, ANSWER_D)
"""The four answer options, in order."""

BANK_COLUMNS = (QUESTION_NUMBER, TOPIC, STATUS, QUESTION, *ANSWER_COLUMNS, CORRECT_ANSWER, RELEVANT_TEXT)
"""Columns of a question bank, in their usual order (the usage columns come after them)."""


def answer_column(letter: str) -> str:
    """Column of the answer option ``letter`` (``"A"`` to ``"D"``): ``"Respuesta A"``..."""
    return f"Respuesta {letter}"


def usage_column(label: str) -> str:
    """Usage column of the exam ``label``: ``"<label>_uso"``."""
    return f"{label}{USAGE_SUFFIX}"
