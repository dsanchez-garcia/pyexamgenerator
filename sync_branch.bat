@echo off
setlocal
:: Se sitúa en la carpeta donde está el archivo (la raíz del proyecto)
cd /d "%~dp0"

set "BRANCH_NAME=%~1"
set "SCRIPT_NAME=%~nx0"

if "%BRANCH_NAME%"=="" (
    echo Error: Debes especificar el nombre de la rama.
    echo Uso: %SCRIPT_NAME% nombre_de_la_rama
    pause
    exit /b 1
)

echo ==========================================================
echo Sincronizando rama: %BRANCH_NAME% en la raiz
echo ==========================================================

:: 1. Limpieza de archivos no versionados (sin borrar este script). git clean los borra de forma
::    definitiva (no toca los ignorados por .gitignore): primero se listan y se pide confirmacion.
echo Archivos no versionados que se eliminarian:
git clean -nd -e "%SCRIPT_NAME%"
if errorlevel 1 goto :error
set "CONFIRM="
set /p "CONFIRM=Eliminarlos y continuar? (s/N): "
if /I not "%CONFIRM%"=="s" (
    echo Operacion cancelada. No se ha modificado nada.
    pause
    exit /b 1
)
git clean -fd -e "%SCRIPT_NAME%"
if errorlevel 1 goto :error

:: 2. Actualización de datos
git fetch --all
if errorlevel 1 goto :error

:: 3. Cambiar de rama y traer los cambios
git checkout "%BRANCH_NAME%"
if errorlevel 1 goto :error

git pull origin "%BRANCH_NAME%"
if errorlevel 1 goto :error

echo ==========================================================
echo PROCESO COMPLETADO
echo ==========================================================
pause
exit /b 0

:error
echo.
echo ==========================================================
echo ERROR: El proceso se detuvo por un fallo en Git.
echo ==========================================================
pause
exit /b 1
