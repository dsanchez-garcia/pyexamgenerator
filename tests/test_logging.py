"""Mensajes de la librería con `logging` en lugar de `print` (ARC-8).

La librería registra sus mensajes de progreso y avisos; los puntos de entrada (la GUI y los comandos
`python -m pyexamgenerator.grading...`) los muestran en la consola con `log_to_console`. Los scripts
deciden qué ven configurando `logging`.
"""

import ast
import logging
import os
import subprocess
import sys
from pathlib import Path

import pyexamgenerator
from pyexamgenerator.question_generator import QuestionGenerator

PACKAGE = Path(pyexamgenerator.__file__).parent
# print() is their interface: interactive console questions and command-line entry points.
CONSOLE_FUNCTIONS = {"_ask_exam_type_in_console", "_ask_review_in_console", "_run_interactive_review", "main"}


def _prints_outside_console_functions(path):
    found = []

    def visit(node, function):
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function
            is_print = isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "print"
            if is_print and function not in CONSOLE_FUNCTIONS:
                found.append(f"{path.name}:{child.lineno} ({function})")
            visit(child, name)

    visit(ast.parse(path.read_text(encoding="utf-8")), None)
    return found


def test_library_modules_log_instead_of_printing():
    """ARC-8: había 134 `print()` en la librería y ningún uso de `logging`."""
    modules = [p for p in PACKAGE.rglob("*.py") if p.name != "_console.py"]

    found = [hit for path in modules for hit in _prints_outside_console_functions(path)]

    assert found == []


def test_library_messages_go_to_the_log_not_to_stdout(capsys, caplog):
    with caplog.at_level(logging.INFO, logger="pyexamgenerator"):
        QuestionGenerator(api_key="dummy", model_name="models/test")

    assert capsys.readouterr().out == ""
    assert [(r.name, r.levelname) for r in caplog.records] == [("pyexamgenerator.question_generator", "INFO")]
    assert "models/test" in caplog.records[0].getMessage()


def test_log_to_console_shows_the_messages_on_stdout_as_plain_text():
    code = (
        "import logging\n"
        "from pyexamgenerator._console import log_to_console\n"
        "log_to_console()\n"
        "logging.getLogger('pyexamgenerator.prueba').info('Generando exámenes...')\n"
        "logging.getLogger('pyexamgenerator.prueba').debug('detalle que no se ve')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Generando exámenes...\n"
