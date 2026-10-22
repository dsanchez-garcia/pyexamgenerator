# Arquitectura de pyexamgenerator

Referencia técnica para desarrolladores y agentes de IA. Describe el estado en la versión 0.3.0.
Las reglas de trabajo están en [`AGENTS.md`](../../AGENTS.md); la deuda técnica, en
[`TODO.md`](../../TODO.md).

> Esta carpeta (`docs/dev/`) **no** forma parte de la documentación de Sphinx/Read the Docs.

## Visión general

```
           PDFs / imágenes
                 │  QuestionGenerator (Gemini)
                 ▼
  <nombre>_pendiente_de_revisar.xlsx / .docx
                 │  revisión manual en Word → QuestionBankManager.generate_excel_from_docx
                 ▼
     preguntas revisadas .xlsx ──► QuestionBankManager.add_questions_without_duplicates
                                    / unify_question_banks
                 ▼
          BANCO PRINCIPAL .xlsx  ◄── registro de uso (update_bank_with_exam[s], update_excel=True)
                 │  ExamGenerator.generate_exam_from_excel
                 ▼
  examen_<asig>_<examen>_<curso>_<tipo>.docx       (alumno: preguntas + hoja de respuestas)
  examen_..._<tipo>_completo.docx / _completo.xlsx (profesor: con soluciones)
  examen_..._<tipo>.xml                            (Moodle XML, plantilla de corrección)
  [sesión de corrección .json/.pkl]
                 │  pyexamgenerator.grading.ExamCorrectionAPI
                 ▼
  calificaciones, incidencias OCR, asistencias, punto extra, nota final (.xlsx)
```

## Capas

| Capa | Módulos | Depende de |
|---|---|---|
| GUI | `main_app.py` (`ExamApp`), `gui_logic.py` (sin tkinter), `tooltip.py` | tkinter + toda la librería |
| Generación | `question_generator.py`, `question_bank_manager.py`, `exam_generator.py` | pandas, python-docx, google-genai, PyPDF2, PyMuPDF |
| Corrección | `grading/*` | pandas; OCR opcional (cv2, rapidocr) solo en `grading/extraction.py` |

La librería nunca importa `tkinter`. La GUI llama a la librería directamente desde los manejadores de
los botones.

## Módulos de generación

### `QuestionGenerator(api_key, model_name)` — `question_generator.py`

- Envuelve `google.genai.Client`.
- `generate_multiple_choice_questions(pdf_paths, prompt_type, ...)`: lee cada PDF como texto
  (PyPDF2) o como imágenes (PyMuPDF, `input_mode='image'`), lo trocea opcionalmente
  (`chunking_mode='pages'|'text_length'`, `pages_per_chunk`, `total_chunks`), construye el prompt
  (`_build_prompt`), llama a Gemini, analiza la respuesta (`_analyze_gemini_response`) y descarta
  preguntas demasiado parecidas a un banco existente (similitud de Jaccard).
- Escribe `<nombre>_pendiente_de_revisar.xlsx/.docx` y `<nombre>_similares_descartadas.docx`.
- `build_generation_prompts(...)`: mismos prompts sin llamar a la API (modo manual en AI Studio).
- `filter_generated_questions_duplicates(...)`: filtra preguntas externas contra un banco.
- Llamadas a Gemini en `_generate_content`: los errores temporales (429 y 5xx, leídos de
  `google.genai.errors.APIError.code`) se reintentan tras 2, 4 y 8 s (o la espera que sugiera la
  API, hasta 1 min). Excepciones públicas: `QuotaExceededError` (429 persistente),
  `ServiceOverloadedError` (5xx persistente) y `GeminiRequestError` (401/403 clave, 404 modelo
  retirado; sin reintentos). Los mensajes no nombran modelos concretos: Google los retira.
- Los «tipos de prompt» (p. ej. `PRL`, `PM`) los define la GUI
  (`ExamApp.load_default_prompt_types`) y los personalizados se guardan en `custom_prompts.json`.

### `QuestionBankManager()` — `question_bank_manager.py`

- DOCX revisado → DataFrame/XLSX: `read_questions_from_docx`, `generate_excel_from_docx`.
- Fusión sin duplicados: `add_questions_without_duplicates(existing_bank_path,
  reviewed_questions_path, duplicate_check_columns, add_only_acceptable)`.
- Unificación de N bancos: `unify_question_banks(...)` con criterio `enunciado` o
  `enunciado_y_respuestas` (respuestas comparadas como conjunto).
- Registro de uso: `update_bank_with_exam(...)`, `update_bank_with_exams(bank_path, exams, ...)` →
  columna `<etiqueta>_uso` (sin tildes) + recálculo de `Veces usada en examen`. Etiquetas derivables
  del nombre del fichero con `label_from_filename(path, delimiter, parts)`.
- `save_dataframe_to_excel(df, filepath, overwrite)`.

### `ExamGenerator()` — `exam_generator.py`

- `generate_exam_from_excel(bank_excel_path, output_dir, subject, exam, course, num_exams | exam_names,
  selection_method, questions_per_topic | total_questions + total_distribution, export_moodle_xml,
  update_excel, template_docx_path, session_output_path, check, review_callback, ...)`:
  1. Lee el banco (en cada llamada) y filtra `Estado == "aceptable"`
     (sin distinguir mayúsculas); si no hay ninguna, `NoAcceptableQuestionsError`.
     Tras seleccionar, exige que cada pregunta tenga `Respuesta correcta` A-D (acepta `B)`, ` b `,
     `(c)`); si no, `ValueError` con las preguntas afectadas.
  2. Selecciona preguntas: `azar`, `primeras` o `menos usadas`; por tema, número fijo o total
     (`equitativo`/`azar`).
  3. Para cada tipo construye una variante barajada con un **orden canónico único**
     (`_build_exam_variant_df`) que se reutiliza en DOCX, hoja de respuestas y XML.
  4. Escribe los DOCX (alumno: cabecera con huecos de identificación, hoja de respuestas en página
     impar con columna `NC`; profesor: `_completo`), el `_completo.xlsx` y el XML de Moodle.
  5. Opcionalmente actualiza el uso en el banco y escribe una sesión de corrección.
- `generate_moodle_xml_from_existing_exam_xlsx(...)`: XML a partir de un `_completo.xlsx`.
- `check=True` genera una previsualización y pide confirmación con `review_callback(ruta)`; sin
  callback, pregunta por consola solo desde un terminal (si no, `ValueError` antes de generar).
- `suggest_moodle_config(...)`: nombres de cuestionario/categoría coherentes con lo que espera
  `grading`.
- Penalizaciones de Moodle normalizadas a fracciones válidas (`_MOODLE_GRADE_OPTIONS_PERCENT`).

## Esquema del banco de preguntas (XLSX)

Columnas, en este orden habitual:

| Columna | Contenido |
|---|---|
| `Número de pregunta` | entero; **no** es único tras fusionar bancos (no lo uses como clave) |
| `Tema` | nombre del tema; inicialmente derivado del nombre del PDF |
| `Estado` | `Pendiente de revisar` o `Aceptable` (comparación sin distinguir mayúsculas) |
| `Pregunta` | enunciado |
| `Respuesta A` … `Respuesta D` | opciones |
| `Respuesta correcta` | letra (`A`–`D` en bancos; minúscula en los exámenes generados) |
| `Texto relevante` | fragmento del documento fuente |
| `Veces usada en examen` | suma de las columnas `*_uso` |
| `<etiqueta>_uso` | 0/1 por examen registrado; etiqueta sin tildes |

Los nombres de columna son contrato con los usuarios: no los cambies. Si necesitas referirte a ellos
en código nuevo, considera crear las constantes de `pyexamgenerator/schema.py` (`ARC-3`).

## Subpaquete `grading`

### Fachada y configuración — `grading/api.py`

`ExamCorrectionAPI` es la entrada única (la usa la GUI). Cada flujo es un método que recibe un
dataclass de configuración y, opcionalmente, `export_steps_dir` para volcar xlsx intermedios
numerados y un `manifest.json`. Los resultados se guardan en `api.results` y en una
`GradingSession`.

| Método | Config | Clase de trabajo |
|---|---|---|
| `grade_from_excel` | `ExcelGradingConfig` | `graders.ExamGrader` |
| `grade_from_images` | `ImageGradingConfig` | `extraction.ImageExamGrader` / `AnswerSheetExtractor` (OCR) |
| `integrate_moodle_grades` | `MoodleIntegrationConfig` | `integrations.MoodleGradeIntegrator` |
| `integrate_ocr_grades` | `OCRIntegrationConfig` | `integrations.OcrGradeIntegrator` |
| `run_moodle_plus_ocr_pipeline` | las dos anteriores | ambos integradores |
| `run_full_pipeline` | `FullPipelineConfig` | matrícula → OCR → integración → asistencias → punto extra → informe (el «Pipeline completo» de la GUI; borra `_intermedios` también tras un error) |
| `merge_enrollment_sources` | `EnrollmentMergeConfig` | `data.EnrollmentMerger` |
| `process_absence_justifications` | `AbsenceJustificationConfig` | `attendance.AbsenceJustificationManager` |
| `calculate_pir_bonus` | `PIRBonusConfig` | `attendance.PIRBonusCalculator` |
| `apply_theory_bonus` | `TheoryBonusConfig` | `attendance.TheoryBonusApplier` |
| `export_theory_topic_reports` | `TheoryTopicReportConfig` | `attendance.TheoryTopicReporter` |
| `compute_final_grade` | `FinalGradeConfig` | `final_grade.FinalGradeCalculator` |
| `compare_results` | `ComparisonConfig` | `comparison.ResultComparator` |
| `save_session` / `load_session` | — | `session.GradingSession` |

Las clases de trabajo guardan sus entradas y salidas como atributos para poder inspeccionarlas.
`data.SharedExamDataStore` cachea lecturas de Excel/XML compartidas.

- **Rutas de salida:** un nombre relativo se escribe en la carpeta de salida (`output_dir` del
  config o `default_output_dir` de la fachada; solo se conserva el nombre del fichero) y una ruta
  absoluta se respeta. Fachada y clases de trabajo usan el mismo helper,
  `grading/_paths.py: prepare_output_path`.
- **Texto, columnas y notas:** todos los módulos usan las mismas reglas de `grading/_text.py`:
  `normalize_key` (sin tildes, mayúsculas ni signos; celda vacía → `''`), `find_column` (busca una
  columna entre varios nombres posibles, también con *mojibake*), `clean_text` y `parse_decimal`
  (nota con coma o punto decimal; `None` si no es un número). Las clases conservan sus nombres
  privados (`_normalize`, `_find_column`…) como alias.
- **`export_steps_dir`:** las entradas solo se vuelven a leer para exportarlas cuando se pide
  (`_export_step_input`).

### Flujo de datos de corrección

1. **Matrícula:** varios xlsx (por grupo) → lista única de alumnos (`EnrollmentMerger`).
2. **Respuestas:** desde Excel o desde OCR de escaneos.
3. **Corrección:** contra el Moodle XML del tipo; el tipo se infiere del sufijo del fichero
   (`..._1A.xml`, `..._A.xml`) o se fuerza por imagen (`forced_type_by_image`); el alumno puede
   forzarse con `forced_student_by_image`.
4. **Integración:** notas de Moodle (columnas `Cuestionario:..._Tipo X (Real)`) + notas OCR. Modo
   unión (por defecto) o estricto (`append_unmatched_students`); incidencias en
   `incidencias_integracion_ocr.xlsx`: filas bloqueadas y notas OCR que sustituyen a una nota
   distinta que ya existía (`OVERWRITTEN_GRADE`, se aplican igualmente).
5. **Asistencia y bonus:** asistencias + correos de justificación + cuestionarios → punto extra PIR.
6. **Nota final** ponderada (por fichero o por columnas) y **comparación** con una versión previa.

### Columnas de entrada típicas (exportaciones de Moodle, en español)

`Apellido(s)`, `Nombre`, `Número de ID`, `Dirección de correo`, `Grupo`, `Calificación/10,00`,
`Cuestionario:<nombre> (Real)`. Los IDs pueden tener ceros iniciales: léelos como texto.

### Dependencia opcional de OCR

- `pip install pyexamgenerator[grading]` instala `rapidocr` (Python ≥ 3.13) o
  `rapidocr-onnxruntime` (< 3.13) junto con numpy/opencv compatibles (ver `pyproject.toml`).
- Solo `grading/extraction.py` importa esas librerías; `grading/__init__.py` lo protege con
  `try/except ImportError` y expone `HAS_OCR`.
- `docs/source/conf.py` simula `cv2`/`rapidocr*` con `autodoc_mock_imports` para Read the Docs.

## GUI — `main_app.py`

- Una clase `ExamApp(root)`; `main()` crea `tk.Tk()` y lanza `mainloop()` (entry point de consola
  `pyexamgenerator`).
- `__init__` carga la clave (`GEMINI_API_KEY` → `config.json`), crea ~70 variables Tkinter y
  construye las pestañas: `create_question_tab`, `create_manage_bank_tab`, `create_exam_tab`,
  `create_grading_tab`, y el menú «Ayuda».
- Hilos: las tareas largas se ejecutan fuera del hilo de la interfaz. Generación con Gemini, carga
  de modelos y generación de exámenes usan `_run_in_background` (deshabilita el botón, ejecuta en
  un hilo y llama a `on_success`/`on_error` en el hilo principal); la corrección usa
  `_grad_run_async`, con una sola tarea a la vez (`_grad_try_start_job` / `_grad_finish_job`), y
  «Pipeline completo» delega en `ExamCorrectionAPI.run_full_pipeline`. Todos los valores de la
  interfaz se leen antes de lanzar el hilo; un diálogo pedido desde un hilo (la alerta de uso de
  preguntas) se muestra con `_call_in_main_thread`. Los hilos devuelven resultados con
  `root.after`, que exige el `mainloop` en marcha (en los tests, ver `_run_in_mainloop` en
  `test_gui_smoke.py`). Cada generación de exámenes usa su propio `ExamGenerator`, porque la
  instancia guarda estado mientras trabaja (`ARC-13`).
- Desplazamiento: las cuatro pestañas se crean con `_create_scrollable_tab` y, al final de su
  construcción, `_bind_page_scroll` enlaza la rueda del ratón en todos sus widgets salvo los que se
  desplazan solos (tablas, textos).
- Tooltips (`tooltip.py`): un único manejador por ventana oculta los tooltips visibles al ocultarla
  o cerrarla.
- Lo que el usuario escribe en los campos se interpreta en `gui_logic.py` (no importa tkinter; se
  prueba sin pantalla en `test_gui_logic.py`): listas de rutas separadas por `;` (`split_paths`; los
  nombres de fichero pueden contener comas), penalización, pesos de la nota final, tipos forzados por
  imagen, nombres de examen y preguntas por tema.
- Guardar y cargar la plantilla de exámenes y la sesión de corrección usan un único mapa de campos
  (`_exam_template_fields`, `_grad_session_fields`, `_grad_column_fields`).
- Los `messagebox.show*` se sustituyen por diálogos con texto copiable.
- Ficheros persistidos:

| Fichero | Ubicación | Contenido |
|---|---|---|
| `config.json` | directorio actual | clave de API (texto plano, `SEC-3`) |
| copias temporales del OCR | `<temp del sistema>/pyexamgenerator_temp` (configurable) | solo si falla la lectura directa; se borran al terminar |
| `custom_prompts.json` | directorio actual | prompts personalizados |
| `exam_generation_template.json` | directorio actual → `%APPDATA%\pyexamgenerator` | plantilla de la pestaña de exámenes |
| sesión `.json` + `.pkl` | ruta elegida por el usuario | sesión de corrección (se carga el `.json`; el `.pkl` solo con `allow_pickle=True`) |

## Tests

| Fichero | Cubre |
|---|---|
| `test_exam_order_unit.py` | orden canónico y respuesta correcta tras barajar |
| `test_exam_order_integration.py` | DOCX vs XML con un banco sintético realista |
| `test_exam_generator_bank.py` | relectura del banco, registro de uso por fila y nombre de la columna de uso |
| `test_exam_generator_robustness.py` | banco sin carpeta, XML con respuestas numéricas o vacías, «menos usadas», letras como `B)` |
| `test_question_bank_docx.py` | lectura del DOCX revisado (ida y vuelta) y fusión de bancos |
| `test_question_generator_parsing.py` | análisis seguro de la respuesta de Gemini; `api_key` desde el entorno |
| `test_grading_bonus_and_attendance.py` | punto extra PIR y columnas de asistencia |
| `test_grading_ids.py` | `normalize_id`; nota final, comparación, matrícula y asistencias con IDs float o vacíos |
| `test_grading_ocr_robustness.py` | emparejamiento OCR, hojas ilegibles o sin tipo, carpeta temporal (requiere `[grading]`) |
| `test_grading_matching.py` | emparejamiento por nombre (justificaciones, integración OCR con `Apellidos`) y aviso de notas sustituidas |
| `test_grading_api_workflows.py` | fachada: configs sin efectos secundarios, combinar con copia, nota final con nombres repetidos, sesión, pipeline completo (OCR y asistencias simulados), rutas absolutas y lecturas solo para exportar pasos |
| `test_exam_generator_outputs.py` | nombres de fichero seguros, categoría de Moodle, plantillas DOCX (runs partidos, cabeceras) |
| `test_question_generator_flow.py` | flujo completo de generación con un cliente de Gemini simulado; troceo de PDF por páginas y generadores reutilizables |
| `test_question_generator_errors.py` | errores de Gemini: reintentos con espera (429/5xx), clave no válida, modelo retirado |
| `test_grading_attendance_flow.py` | justificaciones, punto extra en modo extremo y normal, `export_steps_dir` y `manifest.json` |
| `test_grading_ocr_sheet.py` | hojas de respuestas PNG sintéticas con RapidOCR simulado, de la imagen a la nota (requiere `[grading]`) |
| `test_grading_text_helpers.py` | reglas comunes de `grading/_text.py`; filas sin ID ni nombre en la nota final y la comparación |
| `test_gui_logic.py` | `gui_logic.py` sin pantalla: listas de rutas, penalización, pesos, tipos forzados, nombres de examen, preguntas por tema |
| `test_dev_scripts.py` | `install_current_version.bat` sin `setx`; `add_user_path.ps1` con `-WhatIf` (solo Windows) |
| `test_gui_smoke.py` | ventana real de la GUI: prompts, clave de API, lista de ficheros, errores de entrada, una sola tarea de corrección, variables Tk solo en el hilo principal, tareas en segundo plano, rueda del ratón, tooltips y valores por defecto (se salta sin pantalla; en la CI de Linux usa xvfb) |
| `test_package_smoke.py` | compila todos los módulos (incluida la GUI) |
| `test_release_metadata.py` | la versión y la fecha coinciden en `__init__.py`, `CITATION.cff`, `.zenodo.json` y `CHANGELOG.md` |
| `conftest.py` | sustituye `google.genai.Client` en todos los tests (ninguno puede llamar a Gemini) |
| `test_image_mode_unit.py` | utilidades de `input_mode='image'` |
| `test_exam_question_selection.py` | estado sin mayúsculas, reparto de un total de preguntas entre temas, alerta de uso |
| `test_exam_docx_layout.py` | maquetación del DOCX (hoja de respuestas, columna NC, cabecera) y marcadores de plantilla |
| `test_moodle_xml.py` | XML de Moodle: textos, penalizaciones válidas y XML desde un `_completo.xlsx` |
| `test_bank_usage.py` | registro de uso desde exámenes, etiquetas derivadas del nombre, columnas sin tildes |
| `test_bank_merge_and_unify.py` | añadir solo las aceptables y unificar bancos sin duplicados |
| `test_grading_unit.py` | matrícula, punto extra, reporte por tema, integración OCR; OCR con `importorskip` |
| `test_grading_session_and_grades.py` | sesión, sugerencias Moodle, justificaciones, nota final, comparación |

Huecos de cobertura conocidos: `TST-3`, `TST-4`, `TST-5` en `TODO.md`.
