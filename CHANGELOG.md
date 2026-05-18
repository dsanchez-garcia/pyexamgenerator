# Changelog

Todas las novedades de este proyecto están documentadas en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto se adhiere al [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Arreglado
- Generación de exámenes con orden canónico único por tipo, reutilizado en enunciados, hoja de respuestas y exportación XML de Moodle.
- La tabla de la hoja de respuestas muestra la numeración `01..N` de forma consistente.
- Los nombres de pregunta en XML (`Pregunta 01`, `Pregunta 02`, ...) usan dos dígitos para mantener homogeneidad visual y trazabilidad con la hoja de respuestas.

### Añadido
- Prueba unitaria para validar numeración canónica y coherencia de la respuesta correcta tras el barajado de opciones.
- Prueba de integración usando el fixture real `prueba_error/examen_CSP_Q-PA_25-26.xlsx` para verificar coherencia entre tabla de respuestas en DOCX y preguntas en XML.

## [0.2.2] - 2026-01-08

### Arreglado
- **Corrección en Guardado de API Key:** Se ha corregido un error (`TypeError`) que ocurría al intentar guardar la clave de API antes de seleccionar un modelo. Ahora el botón "Guardar Clave" simplemente guarda la credencial sin intentar inicializar el generador prematuramente.

## [0.2.1] - 2026-01-03

### Cambiado
- **Migración de Librería de Google:** Se ha sustituido la dependencia `google-generativeai` (deprecada) por la nueva librería oficial `google-genai`. Esto asegura la compatibilidad futura y elimina las advertencias de `FutureWarning` al ejecutar la aplicación.
- Actualizada la lógica de conexión y generación de contenido en `QuestionGenerator` para usar el nuevo cliente `genai.Client`.
- Actualizado el método de listado de modelos en la interfaz gráfica para adaptarse a la estructura de objetos de la nueva API de Google, mejorando la robustez al obtener atributos como límites de tokens.

### Arreglado
- Solucionado un error de compatibilidad en Python 3.9 relacionado con `importlib.metadata` al obtener la versión del paquete en la interfaz gráfica. Ahora la versión se importa directamente desde el paquete.

## [0.2.0] - 2024-10-06

### Añadido
- **Manejo de Errores Mejorado:**
    - La aplicación ahora detecta si se excede la cuota de la API de Gemini (Error 429) y muestra un mensaje de ayuda con sugerencias, como esperar o cambiar a un modelo más económico (ej. 'Flash').
    - Se ha añadido una comprobación para detectar si no hay preguntas con estado "Aceptable" en el banco antes de generar un examen, mostrando un error claro en lugar de fallar.
- **API Pública Simplificada:** Las clases principales (`ExamGenerator`, `QuestionGenerator`, `QuestionBankManager`) y las excepciones personalizadas (`QuotaExceededError`, `NoAcceptableQuestionsError`) ahora se pueden importar directamente desde el paquete `pyexamgenerator`, facilitando su uso en scripts.

### Cambiado
- **BREAKING CHANGE: Renombrado Completo del Proyecto:** El nombre del proyecto ha sido unificado a `pyexamgenerator` en todas sus facetas para mejorar la consistencia y evitar conflictos de nombres en PyPI.
    - El nombre del paquete en PyPI es ahora `pyexamgenerator`.
    - El comando para ejecutar la aplicación es ahora `pyexamgenerator`.
    - El paquete interno de Python ha sido renombrado a `pyexamgenerator`.

## [0.1.0] - 2024-10-05

### ¡Lanzamiento Inicial! 🎉

Esta es la primera versión pública de `pyexamgenerator`.

### Añadido
- Interfaz gráfica completa con tres pestañas para un flujo de trabajo integral.
- **Generación de Preguntas:**
    - Conexión con la API de Google Gemini para generar preguntas desde PDFs.
    - Soporte para prompts personalizados y plantillas (PRL, PM).
    - Procesamiento de PDFs por fragmentos para documentos largos.
    - Filtro de similitud para evitar preguntas duplicadas.
- **Gestión de Banco de Preguntas:**
    - Conversión de preguntas revisadas en formato DOCX a XLSX.
    - Fusión de bancos de preguntas con control de duplicados y filtro por estado.
- **Generación de Exámenes:**
    - Creación de múltiples versiones de exámenes (Tipo A, Tipo B) con preguntas y respuestas barajadas.
    - Selección granular de preguntas por tema.
    - Generación de hojas de respuesta y versiones para el profesor.
    - Exportación a Moodle XML para auto-corrección.
- **Documentación:**
    - Tutoriales completos y documentación de la API generada con Sphinx.
- **Empaquetado:**
    - Paquete instalable a través de `pip` y comando `examgenerator` para un fácil acceso.