@echo off
setlocal
REM build.bat
REM This script cleans old artifacts and builds the package for distribution.

ECHO --- [Step 1 of 3] Cleaning previous build artifacts...
REM Delete the contents of old build folders to ensure a clean build.
REM The /s flag is for subdirectories, and /q is for quiet mode (no confirmation).
IF EXIST dist rmdir /s /q dist
IF EXIST build rmdir /s /q build
FOR /d %%d IN (*.egg-info) DO rmdir /s /q "%%d"

ECHO.
ECHO --- [Step 2 of 3] Building the package using 'python -m build'...

REM Pick a reliable Python command: active venv -> local .\venv -> py launcher -> python in PATH.
set "PYTHON_EXE="
set "PYTHON_ARGS="

IF DEFINED VIRTUAL_ENV IF EXIST "%VIRTUAL_ENV%\Scripts\python.exe" (
    set "PYTHON_EXE=%VIRTUAL_ENV%\Scripts\python.exe"
)

IF NOT DEFINED PYTHON_EXE IF EXIST ".\venv\Scripts\python.exe" (
    set "PYTHON_EXE=.\venv\Scripts\python.exe"
)

IF NOT DEFINED PYTHON_EXE (
    where py >nul 2>&1
    IF NOT ERRORLEVEL 1 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3"
    )
)

IF NOT DEFINED PYTHON_EXE (
    where python >nul 2>&1
    IF NOT ERRORLEVEL 1 set "PYTHON_EXE=python"
)

IF NOT DEFINED PYTHON_EXE (
    ECHO ERROR: No valid Python interpreter was found.
    ECHO Activate your virtual environment or install Python 3.
    PAUSE
    EXIT /B 1
)

ECHO Using interpreter: %PYTHON_EXE% %PYTHON_ARGS%

"%PYTHON_EXE%" %PYTHON_ARGS% -m build --version >nul 2>&1
IF ERRORLEVEL 1 (
    ECHO The 'build' module is missing. Installing it...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade build
    IF ERRORLEVEL 1 (
        ECHO ERROR: Could not install the 'build' module.
        PAUSE
        EXIT /B 1
    )
)

"%PYTHON_EXE%" %PYTHON_ARGS% -m build
IF ERRORLEVEL 1 (
    ECHO ERROR: Build process failed.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO --- [Step 3 of 3] Verifying build results...
IF NOT EXIST dist (
    ECHO ERROR: The 'dist' directory was not created. The build may have failed.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO --- Process complete ---
ECHO The distribution files have been successfully created in the 'dist' directory.
PAUSE
endlocal
