@echo off
setlocal EnableExtensions

:: Se sitúa en la raíz del proyecto (donde está este .bat)
cd /d "%~dp0"

set "SCRIPT_NAME=%~nx0"
set "MODE=user"
set "UPGRADE_PIP=0"
set "DRY_RUN=0"
set "ADD_PATH=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--system" (
    set "MODE=system"
    shift
    goto parse_args
)
if /I "%~1"=="--user" (
    set "MODE=user"
    shift
    goto parse_args
)
if /I "%~1"=="--upgrade-pip" (
    set "UPGRADE_PIP=1"
    shift
    goto parse_args
)
if /I "%~1"=="--dry-run" (
    set "DRY_RUN=1"
    shift
    goto parse_args
)
if /I "%~1"=="--add-path" (
    set "ADD_PATH=1"
    shift
    goto parse_args
)
if /I "%~1"=="-h" goto :help
if /I "%~1"=="--help" goto :help

echo Opcion no reconocida: %~1
goto :help

:args_done
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>nul && set "PY_CMD=python"
)

if not defined PY_CMD (
    echo ERROR: No se encontro Python en PATH.
    echo Instala Python 3.8+ y marca "Add Python to PATH".
    exit /b 1
)

set "PIP_ARGS="
if /I "%MODE%"=="user" set "PIP_ARGS=--user"

set "TARGET_SCRIPTS="
if /I "%MODE%"=="user" for /f "delims=" %%I in ('%PY_CMD% -c "import os,site,sys; print(os.path.join(site.USER_BASE, 'Python{}{}'.format(sys.version_info[0], sys.version_info[1]), 'Scripts'))"') do set "TARGET_SCRIPTS=%%I"
if /I not "%MODE%"=="user" for /f "delims=" %%I in ('%PY_CMD% -c "import sysconfig; print(sysconfig.get_path('scripts'))"') do set "TARGET_SCRIPTS=%%I"

echo ==========================================================
echo Instalando pyexamgenerator desde el codigo actual
echo Modo de instalacion: %MODE%
echo Python: %PY_CMD%
echo ==========================================================

if "%DRY_RUN%"=="1" (
    echo [DRY-RUN] No se ejecuta ninguna instalacion.
    if "%UPGRADE_PIP%"=="1" echo [DRY-RUN] call %PY_CMD% -m pip install --upgrade pip
    echo [DRY-RUN] call %PY_CMD% -m pip install --upgrade %PIP_ARGS% .
    if "%ADD_PATH%"=="1" (
        if /I "%MODE%"=="user" (
            echo [DRY-RUN] Se agregaria al PATH de usuario: %TARGET_SCRIPTS%
        ) else (
            echo [DRY-RUN] --add-path solo aplica a instalaciones --user.
        )
    )
    exit /b 0
)

if "%UPGRADE_PIP%"=="1" (
    call %PY_CMD% -m pip install --upgrade pip
    if errorlevel 1 goto :error
)

call %PY_CMD% -m pip install --upgrade %PIP_ARGS% .
if errorlevel 1 goto :error

echo.
echo Instalacion completada.
echo Puedes ejecutar: pyexamgenerator

if /I "%MODE%"=="user" (
    if defined TARGET_SCRIPTS (
        if "%ADD_PATH%"=="1" (
            echo Actualizando PATH de usuario con: %TARGET_SCRIPTS%
            call :add_user_path "%TARGET_SCRIPTS%"
        ) else (
            echo Si el comando no se reconoce, anade esta ruta al PATH:
            echo %TARGET_SCRIPTS%
            echo (o ejecuta este script con --add-path)
        )
    )
) else (
    if "%ADD_PATH%"=="1" (
        echo AVISO: --add-path solo aplica a instalaciones --user.
    )
)

exit /b 0

:help
echo Uso:
echo   %SCRIPT_NAME% [--user ^| --system] [--upgrade-pip] [--dry-run] [--add-path]
echo.
echo Opciones:
echo   --user        Instala para el usuario actual (por defecto).
echo   --system      Instala a nivel del Python activo (puede requerir permisos).
echo   --upgrade-pip Actualiza pip antes de instalar.
echo   --dry-run     Muestra comandos sin ejecutarlos.
echo   --add-path    Agrega la carpeta Scripts de usuario al PATH (solo --user).
exit /b 1

:error
echo.
echo ERROR: Fallo durante la instalacion.
echo Revisa el mensaje de pip para mas detalles.
exit /b 1

:add_user_path
set "PATH_TO_ADD=%~1"
if "%PATH_TO_ADD%"=="" exit /b 0

set "USER_PATH="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul ^| findstr /R /C:"^[ ]*Path[ ]*REG_"') do set "USER_PATH=%%B"

echo ;%USER_PATH%; | findstr /I /C:";%PATH_TO_ADD%;" >nul
if not errorlevel 1 (
    echo La ruta ya existe en el PATH de usuario.
    set "PATH=%PATH%;%PATH_TO_ADD%"
    exit /b 0
)

if defined USER_PATH (
    set "NEW_USER_PATH=%USER_PATH%;%PATH_TO_ADD%"
) else (
    set "NEW_USER_PATH=%PATH_TO_ADD%"
)

setx Path "%NEW_USER_PATH%" >nul
if errorlevel 1 (
    echo AVISO: No se pudo actualizar el PATH de usuario automaticamente.
    echo Agrega manualmente esta ruta al PATH:
    echo %PATH_TO_ADD%
    exit /b 0
)

set "PATH=%PATH%;%PATH_TO_ADD%"
echo PATH de usuario actualizado. Abre una nueva terminal para verlo.
exit /b 0

