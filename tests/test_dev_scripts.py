"""Scripts de Windows del repositorio (DEV-3): añadir la carpeta Scripts al PATH de usuario.

Las pruebas de `add_user_path.ps1` solo se ejecutan en Windows y siempre con `-WhatIf`: leen el
PATH de usuario, nunca lo modifican.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADD_USER_PATH = ROOT / "add_user_path.ps1"

windows_only = pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None, reason="Solo en Windows (PowerShell)."
)


def test_install_script_does_not_truncate_the_path_with_setx():
    """`setx` trunca el PATH a 1.024 caracteres: con un PATH largo se perdían entradas."""
    lines = (ROOT / "install_current_version.bat").read_text(encoding="utf-8").lower().splitlines()
    commands = [line.strip() for line in lines if not line.strip().startswith(("::", "rem "))]

    assert not [line for line in commands if line.startswith("setx")]
    assert any("add_user_path.ps1" in line for line in commands)


def _user_path():
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        try:
            return winreg.QueryValueEx(key, "Path")  # (raw value, registry type)
        except FileNotFoundError:
            return None


def _what_if(folder):
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ADD_USER_PATH),
            "-Folder",
            folder,
            "-WhatIf",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@windows_only
def test_adding_a_folder_with_whatif_only_reports_it():
    before = _user_path()

    output = _what_if(r"C:\pyexamgenerator-test\Scripts")

    assert r"C:\pyexamgenerator-test\Scripts" in output
    assert "PATH de usuario (" in output
    assert _user_path() == before


@windows_only
def test_a_folder_already_in_the_path_is_not_added_twice():
    current = _user_path()
    entries = [e for e in (current[0] if current else "").split(";") if e.strip() and "%" not in e]
    if not entries:
        pytest.skip("El PATH de usuario no tiene entradas sin variables.")

    # Same folder written differently: other case and a trailing backslash.
    output = _what_if(entries[0].upper().rstrip("\\") + "\\")

    assert "ya existe" in output
    assert _user_path() == current
