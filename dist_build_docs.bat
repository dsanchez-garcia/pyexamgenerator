@echo off
REM build_docs.bat
REM Este script automatiza la generación de la documentación de ExamGenerator.
REM Debe ser ejecutado desde la raíz del proyecto.

ECHO --- [Paso 1 de 3] Limpiando compilaciones anteriores...
REM Elimina el contenido de la carpeta de salida para asegurar una compilación limpia.
REM El flag /Q ejecuta la eliminación sin pedir confirmación.
IF EXIST docs\build rmdir /s /q docs\build

ECHO.
ECHO --- [Paso 2 de 3] Generando archivos .rst de la API con sphinx-apidoc...
REM Ejecuta sphinx-apidoc para generar/actualizar los archivos .rst desde el código fuente.
REM -o docs\source\api: Directorio de salida para los archivos .rst.
REM examgenerator: Ruta al paquete que se va a documentar.
REM --force: Sobrescribe los archivos existentes.
REM examgenerator/tests: Ruta a excluir (buena práctica para no documentar tests).
sphinx-apidoc --force -o docs\source\api examgenerator examgenerator/tests

ECHO.
ECHO --- [Paso 3 de 3] Construyendo la documentación HTML con Sphinx...
REM Cambia al directorio 'docs' y ejecuta el comando 'make html'.
cd docs
call make.bat html
cd ..

ECHO.
ECHO --- Proceso completado ---
ECHO La documentacion HTML ha sido generada en: docs\build\html\index.html
PAUSE