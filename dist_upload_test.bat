@echo off
setlocal
REM dist_upload_test.bat
REM Este script sube las distribuciones del paquete al repositorio de PRUEBAS (TestPyPI).
REM Asume que el archivo .pypirc está correctamente configurado.

ECHO --- [Paso 1 de 2] Verificando que el directorio 'dist' existe...
IF NOT EXIST dist (
    ECHO ERROR: El directorio 'dist' no fue encontrado.
    ECHO Por favor, construye el paquete primero ejecutando: dist_build_package.bat
    PAUSE
    EXIT /B 1
)

IF NOT EXIST "dist\*" (
    ECHO ERROR: El directorio 'dist' esta vacio. No hay archivos para subir.
    ECHO Ejecuta primero: dist_build_package.bat
    PAUSE
    EXIT /B 1
)

REM Selecciona un Python fiable para evitar colisiones con otros ejecutables en PATH.
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
    ECHO ERROR: No se encontro un interprete Python valido.
    ECHO Activa el entorno virtual o instala Python 3.
    PAUSE
    EXIT /B 1
)

"%PYTHON_EXE%" %PYTHON_ARGS% -m twine --version >nul 2>&1
IF ERRORLEVEL 1 (
    ECHO El modulo 'twine' no esta instalado. Instalando...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade twine
    IF ERRORLEVEL 1 (
        ECHO ERROR: No se pudo instalar 'twine'.
        PAUSE
        EXIT /B 1
    )
)

ECHO.
ECHO Archivos detectados para subir:
dir /b dist

choice /M "Confirmas subir estos archivos a TestPyPI"
IF ERRORLEVEL 2 (
    ECHO Operacion cancelada por el usuario.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO --- [Paso 2 de 2] Subiendo distribuciones a TestPyPI...
"%PYTHON_EXE%" %PYTHON_ARGS% -m twine upload --repository testpypi dist/*
IF ERRORLEVEL 1 (
    ECHO ERROR: Fallo la subida a TestPyPI.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO --- Proceso completado ---
ECHO Revisa tu paquete en: https://test.pypi.org/project/pyexamgenerator/
PAUSE
endlocal
