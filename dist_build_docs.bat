@echo off
REM build_docs.bat
REM Este script automatiza la generación de la documentación de pyexamgenerator.
REM Debe ser ejecutado desde la raíz del proyecto.

ECHO --- [Paso 1 de 3] Limpiando compilaciones anteriores...
IF EXIST docs\build rmdir /s /q docs\build
IF EXIST docs\source\api rmdir /s /q docs\source\api

ECHO.
ECHO --- [Paso 2 de 3] Generando archivos .rst de la API con sphinx-apidoc...
REM -o docs\source\api: Directorio de salida
REM pyexamgenerator: Paquete a documentar
sphinx-apidoc --force -o docs\source\api pyexamgenerator

ECHO.
ECHO --- [Paso 3 de 3] Construyendo la documentación HTML con Sphinx...
cd docs
call make.bat html
cd ..

ECHO.
ECHO --- Proceso completado ---
ECHO La documentacion HTML ha sido generada en: docs\build\html\index.html
PAUSE