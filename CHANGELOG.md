# Changelog

Todas las novedades de este proyecto están documentadas en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto se adhiere al [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Añadido
- **Comparar y sobrescribir resultados:** Nuevo `pyexamgenerator.grading.ResultComparator` (+ `ComparisonConfig` y `ExamCorrectionAPI.compare_results`) para comparar unas calificaciones o asistencias con una versión previa —emparejando alumnos por ID o nombre— y obtener un informe de celdas cambiadas, altas y bajas; opcionalmente **combina sobrescribiendo** con los valores nuevos (en un fichero aparte o reemplazando el existente en su sitio). Sección **"Comparar / sobrescribir resultados"** en la GUI y método en scripting.
- **Sesión de corrección reanudable (pickle + JSON):** Nuevo `pyexamgenerator.grading.GradingSession` que guarda en `.pkl` (round-trip exacto) y `.json` (legible y equivalente) las rutas de los exámenes generados, las entradas/columnas de corrección, la configuración de cada flujo y un resumen de resultados. `ExamGenerator.generate_exam_from_excel(...)` admite `session_output_path` para escribir la sesión con las rutas de los exámenes; `ExamCorrectionAPI` gana `save_session`/`load_session` y registra cada flujo. La GUI permite **Guardar/Cargar sesión** (rellena rutas y columnas, incl. los XML de los exámenes generados) y la pestaña Generar Exámenes puede escribir la sesión.
- **Nota final ponderada (varios exámenes):** Nuevo `FinalGradeCalculator` y `FinalGradeConfig` + `ExamCorrectionAPI.compute_final_grade(...)` con dos modos: **por fichero** (un peso por examen, emparejando alumnos por ID/nombre) y **por columnas** (ponderar columnas de un único xlsx); pesos normalizados y tope a 10 opcional. Sección propia en la GUI.
- **Sugerencias de nombres Moodle:** `ExamGenerator.suggest_moodle_config(...)` propone nombres de cuestionario, categoría y la columna esperada en el xlsx exportado, casando con las convenciones que parsea el corrector. Botón **"Sugerir nombres Moodle"** en la pestaña Generar Exámenes.
- **Patrón estructurado del correo de justificación:** `AbsenceJustificationManager` reconoce la plantilla (Día `mm/dd/aaaa` —tolerando `dd/mm`—, Nº Tema/Práctica, Grupo `GIM`/`GITI-GIE-GIEI`, Grupo de prácticas `MC1`…, Motivo); cuando está presente manda sobre la heurística y se vuelca en columnas nuevas `Justif_Fecha`, `Justif_Tema_Practica`, `Justif_Grupo`, `Justif_Subgrupo_Practicas`, `Justif_Motivo`.
- **Columnas de entrada definibles por el usuario:** `AbsenceJustificationConfig`/`AbsenceJustificationManager` aceptan nombres de columna explícitos (`first_name_col`, `last_name_col`, `id_col`, `email_col`, `subject_col`, `message_col`) que tienen prioridad sobre la detección automática; la GUI añade una sección **"Mapeo de columnas"** compartida.
- **Nuevas pruebas de corrección:** `tests/test_grading_session_and_grades.py` (round-trip de sesión, sugerencias Moodle, patrón de justificación, nota final por fichero/columnas con tope, columnas personalizadas en `ExamGrader`, y comparación/sobrescritura de resultados).
- **Documentación narrativa del módulo `grading`:** El tutorial de corrección explica de forma narrativa cómo funciona el módulo y cómo **corregir sin contar la asistencia** (pasos desacoplados; el punto extra es opcional).
- **Selección por número total de preguntas:** `ExamGenerator.generate_exam_from_excel(...)` admite `total_questions` y `total_distribution` (`equitativo` o `azar`). En modo `equitativo` reparte el total entre los temas de la forma más igualada posible (los primeros temas reciben una pregunta más cuando el total no es divisible y se redistribuye el excedente si un tema no tiene suficientes preguntas); en modo `azar` elige el total del banco completo sin tener en cuenta el tema. La pestaña **Generar Exámenes** incorpora la opción "Número total de preguntas" con su selector de reparto, incluida en las plantillas de configuración.
- **Actualizar banco con examen existente:** Nuevo método `QuestionBankManager.update_bank_with_exam(...)` y su sección en la pestaña **Gestionar Banco de Preguntas**. Empareja por enunciado las preguntas de un examen ya generado (el `*_completo.xlsx`) con el banco, marca su uso en una columna `<etiqueta>_uso` y recalcula `Veces usada en examen`, cerrando el ciclo de uso fuera del momento de generación.
- **Unificar varios bancos en uno definitivo:** Nuevo método `QuestionBankManager.unify_question_banks(...)` y su sección **"Unificar Bancos de Preguntas"** en la pestaña Gestionar Banco. Combina N bancos de una vez eliminando duplicados con criterio elegible: **solo enunciado** (`enunciado`/`pregunta_unica`) o **enunciado + respuestas** (`enunciado_y_respuestas`/`pregunta_respuestas`). En el segundo modo las respuestas se comparan como **conjunto** (independiente del orden), de modo que un mismo enunciado con respuestas distintas se conserva como preguntas diferentes y una mera reordenación de las mismas respuestas se trata como duplicado. El primer banco tiene prioridad cuando una pregunta aparece en varios; devuelve además estadísticas (leídas, únicas, duplicados, errores).
- **Nuevas pruebas automáticas:** `tests/test_v030_features.py` valida el reparto equitativo (par/impar y con temas cortos), la selección por total (`equitativo`/`azar`), el arranque de la hoja de respuestas en página impar, la ausencia de línea en blanco entre preguntas, la actualización del banco desde un examen y la unificación de varios bancos (solo enunciado / enunciado + respuestas como conjunto).
- **Identificación manual del alumno por imagen (OCR):** Nuevo parámetro `forced_student_by_image={imagen: "Número de ID" | nombre}` en `ImageExamGrader`/`AnswerSheetExtractor` (y en `ImageGradingConfig`/`ExamCorrectionAPI.grade_from_images`). Permite asignar a mano el alumno de una hoja cuyo nombre manuscrito el OCR no puede leer (incidencia `MISSING_ID`); resuelve el identificador contra la matrícula por `Número de ID`, por nombre completo normalizado o por coincidencia aproximada, y la asignación manual prevalece sobre el OCR.
- **Subpaquete de corrección `pyexamgenerator.grading`:** Integra el flujo completo de corrección de exámenes (antes proyecto `examgrader`), cerrando el ciclo *generar → corregir*. Incluye:
  - OCR de hojas de respuestas manuscritas (`ImageExamGrader`, `AnswerSheetExtractor`) con identificación de marcas y detección del tipo de examen, usando como plantilla el **Moodle XML** que produce el propio generador.
  - Corrección desde Excel/Moodle e integración de notas OCR (`ExamGrader`, `MoodleGradeIntegrator`, `OcrGradeIntegrator`).
  - Cruce de asistencias + justificaciones de faltas + cuestionarios en modo `extremo` (`AbsenceJustificationManager`) y cálculo del **punto extra PIR** (`TheoryBonusApplier`, `TheoryTopicReporter`).
  - Fachada `ExamCorrectionAPI` y clases con estado (guardan inputs/outputs como atributos) para inspección/reuso.
- **Pestaña "Corregir Exámenes" en la GUI:** Nueva pestaña en `main_app.py` que ejecuta el pipeline en segundo plano y genera 3 tablas (incidencias de identificación, cuestionarios + punto extra y calificaciones de teoría).
- **OCR como extra opcional `[grading]`:** `pip install pyexamgenerator[grading]`. Doble backend según la versión de Python: `rapidocr` (≥3.13, incl. 3.14) o `rapidocr-onnxruntime` (<3.13). Sin el extra, todo lo que no es OCR sigue funcionando y `pyexamgenerator.grading.HAS_OCR` vale `False`.
- **Soporte de Python 3.13 y 3.14:** Clasificadores y backend OCR nuevo para esas versiones.
- **Pruebas del subpaquete de corrección:** `tests/test_grading_unit.py` (fusión de matriculados, punto extra y reporte por tema; OCR tras `importorskip`).
- **Prompts sin API (modo manual):** Nuevo método `build_generation_prompts(...)` en `QuestionGenerator` para preparar prompts listos para usar en Google AI Studio/Gemini sin llamadas a la API.
- **Filtrado de duplicados post-generación:** Nuevo método `filter_generated_questions_duplicates(...)` en `QuestionGenerator` para filtrar preguntas externas contra un banco existente.
- **XML de Moodle configurable:** Se añade opción para exportar XML con enunciado y respuestas completas (`xml_use_answer_text=True`), manteniendo por defecto el modo compatible de letras `a/b/c/d`.
- **Plantilla DOCX en generación de exámenes:** Se soporta `template_docx_path` y reemplazo de placeholders `{{subject}}`, `{{exam}}`, `{{course}}`, `{{exam_type}}` cuando estén presentes.
- **Plantillas de configuración en GUI (Generar Exámenes):** Se añaden acciones para guardar/cargar la configuración de la pestaña en JSON con prioridad local (`./exam_generation_template.json`) y fallback central (`%APPDATA%\pyexamgenerator\exam_generation_template.json`).
- **Nuevas pruebas automáticas:** Nuevo archivo `tests/test_v023_features.py` para validar estado case-insensitive, XML no blanco y placeholders de plantilla DOCX.
- **Entrada multimodal por imágenes con Gemini:** `QuestionGenerator.generate_multiple_choice_questions(...)` añade `input_mode` con soporte `image` para generar preguntas a partir de imágenes o de páginas PDF renderizadas como imagen.
- **Soporte de imágenes en prompts manuales:** `QuestionGenerator.build_generation_prompts(...)` añade `input_mode` para preparar prompts orientados a flujo visual (AI Studio/Gemini web).
- **Dependencia para renderizado visual de PDFs:** Se incorpora `PyMuPDF` en `setup.py` para convertir páginas PDF en imágenes cuando se usa `input_mode='image'`.
- **Nuevas pruebas unitarias de modo visual:** Nuevo archivo `tests/test_image_mode_unit.py` para validar utilidades de agrupación y flujo básico de prompts en `input_mode='image'`.
- **Prueba unitaria para validar numeración canónica** y coherencia de la respuesta correcta tras el barajado de opciones.
- **Prueba de integración** usando el fixture real `prueba_error/examen_CSP_Q-PA_25-26.xlsx` para verificar coherencia entre tabla de respuestas en DOCX y preguntas en XML.

### Cambiado
- **Pestaña "Corregir Exámenes" por secciones independientes:** En lugar de un único botón que exigía todos los ficheros, ahora hay secciones con botón propio (corregir desde imágenes/OCR o desde respuestas Moodle, asistencia + justificaciones **opcional**, integrar notas, punto extra y nota final ponderada), además de mapeo de columnas y guardar/cargar sesión. Se mantiene un botón **"Pipeline completo"** para ejecutar todo de una pasada.
- **Hoja de respuestas en página impar:** En el DOCX del alumno, la hoja de respuestas (datos del alumno + tabla) ahora comienza en una **página impar** mediante un salto de sección `oddPage`, de modo que al imprimir a doble cara queda como una hoja física independiente sin salir del mismo documento que el examen.
- **Sin línea en blanco entre preguntas:** Se elimina el salto de línea final de cada pregunta en los DOCX (alumno y profesor); el espaciado del estilo de párrafo ya separa cada pregunta de la siguiente.
- **Generación por fragmentos más flexible:** Se añade soporte para elegir el modo de fragmentación con `chunking_mode` (`pages` o `text_length`) y para definir `total_chunks` además de `pages_per_chunk`.
- **Flujo GUI de generación de preguntas ampliado:** La pestaña **Generar Preguntas** incluye controles para `total_chunks`, `chunking_mode` y para incluir/excluir preguntas similares del banco dentro del prompt.
- **Modo de entrada configurable para generación:** La pestaña **Generar Preguntas** permite elegir entre `text` (extracción de texto de PDF) e `image` (análisis visual multimodal con Gemini).

### Arreglado
- **Integración de notas OCR en formato *quiz-totals*:** `OcrGradeIntegrator` no conseguía volcar las notas manuscritas cuando un mismo tipo de examen existía en varios grupos (p. ej. `GIM` y `GITI-GIE-GIEI`), porque el mapa `Número de ID → grupo` no casaba con el índice del fichero de Moodle (`Nombre de usuario`). Ahora desambigua usando el `Grupo_Principal` que viene en la propia fila OCR, de modo que las notas aterrizan en la columna de cuestionario correcta.
- **Estado case-insensitive:** El filtro de preguntas con estado "Aceptable" ahora acepta variantes como "aceptable" en generación de exámenes y en fusión de bancos.
- **Tooltips persistentes en GUI:** Se corrige el comportamiento de tooltips que podían quedar visibles al salir del widget o cerrar la aplicación, reforzando la destrucción y el manejo de eventos de cierre.
- **Orden canónico único por tipo:** Generación de exámenes con un orden canónico por tipo, reutilizado en enunciados, hoja de respuestas y exportación XML de Moodle.
- La tabla de la hoja de respuestas muestra la numeración `01..N` de forma consistente.
- Los nombres de pregunta en XML (`Pregunta 01`, `Pregunta 02`, ...) usan dos dígitos para mantener homogeneidad visual y trazabilidad con la hoja de respuestas.

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