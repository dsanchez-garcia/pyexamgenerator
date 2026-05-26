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

:: 1. Limpieza de archivos basura (sin borrar este script)
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
