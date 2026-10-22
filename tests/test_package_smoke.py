"""Comprobaciones mínimas de que todos los módulos del paquete son código Python válido.

La GUI (`main_app.py`) no tiene tests y no se importa en el resto de la suite; compilar cada
fichero detecta al menos errores de sintaxis sin necesitar pantalla ni Tk.
"""

import py_compile
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "pyexamgenerator"
MODULES = sorted(PACKAGE_DIR.rglob("*.py"))


@pytest.mark.parametrize("module_path", MODULES, ids=lambda p: str(p.relative_to(PACKAGE_DIR)))
def test_module_compiles(module_path):
    py_compile.compile(str(module_path), doraise=True)
