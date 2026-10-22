# Changelog

Todas las novedades de este proyecto están documentadas en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto se adhiere al [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Añadido
- **Integración continua:** workflow de GitHub Actions (`.github/workflows/tests.yml`) que ejecuta `pytest` en Ubuntu y Windows (Python 3.10 y 3.14, con y sin el extra `[grading]`) y compila la documentación con `sphinx -W`, igual que Read the Docs.
- **Nuevas pruebas de regresión:** análisis seguro de la respuesta de Gemini, carga de sesiones, relectura del banco y registro de uso, punto extra PIR, columnas de asistencia, normalización de IDs y compilación de todos los módulos del paquete (incluida la GUI).
- **Pruebas de humo de la GUI:** `tests/test_gui_smoke.py` construye la ventana real de la aplicación (sin mostrarla) y prueba el diálogo de prompts y el guardado de la clave de API. Se saltan donde no hay pantalla para Tk.
- **Más pruebas de regresión:** generación con datos reales (respuestas numéricas o vacías, letras como `B)`), lectura del DOCX revisado, nombres de columnas de uso, matrícula y asistencias con IDs vacíos o numéricos, y flujo OCR con hojas ilegibles o sin tipo de examen.
- **Pruebas del flujo de generación de preguntas** con un cliente de Gemini simulado (sin llamadas a la API), de los ficheros de examen (nombres, categoría de Moodle, plantillas) y de la fachada de corrección.
- **La CI prueba la GUI también en Linux** (pantalla virtual `xvfb`), y `pytest.ini` limita la recogida de tests a `tests/`.
- **Guía de contribución y plantillas:** `CONTRIBUTING.md`, plantilla de *pull request* y de informe de error (con el aviso de no adjuntar datos de alumnos), enlazadas desde el README.
- **Pipeline completo en la librería:** `ExamCorrectionAPI.run_full_pipeline(FullPipelineConfig)` hace lo mismo que el botón «Pipeline completo» de la GUI (matrícula, OCR, integración de notas, asistencias, punto extra e informe de cuestionarios), con un `progress_callback` opcional para informar del avance. La GUI lo usa.
- **Política de seguridad:** `SECURITY.md` explica cómo informar en privado de una vulnerabilidad y resume cómo trata la aplicación los datos de los alumnos (qué se procesa en local, qué se envía a Gemini, clave de API, temporales y sesiones).
- **`QuestionBankManager.usage_column_name`:** nombre público del método que calcula la columna `<etiqueta>_uso` (se mantiene `_usage_column_name` como alias).
- **Más pruebas:** la GUI en segundo plano (Gemini, modelos, exámenes), las lecturas de la interfaz desde los hilos, la rueda del ratón y los tooltips; el pipeline completo; rutas de salida absolutas; coherencia de la versión entre `__init__.py`, `CITATION.cff`, `.zenodo.json` y `CHANGELOG.md`. `tests/conftest.py` sustituye el cliente de Gemini en todos los tests, de modo que ninguno puede llamar a la API real.
- **Lint con ruff:** la CI comprueba el código con `ruff` (de momento, las reglas de pyflakes) y `.pre-commit-config.yaml` permite hacerlo en cada commit (`pre-commit install`). La configuración está en `pyproject.toml`.
- **`GeminiRequestError`:** nueva excepción pública para los errores de Gemini que no se arreglan reintentando: clave no válida o sin permiso (401/403) y modelo inexistente o retirado (404). Con un modelo retirado, el mensaje sugiere los modelos disponibles para tu clave.
- **Callbacks en lugar de `input()`:** `review_callback` en `ExamGenerator.generate_exam_from_excel(check=True)` y `exam_type_callback` / `review_callback` en el OCR (`ImageExamGrader.grade_from_images`, `ImageGradingConfig`), para preguntar al usuario desde una GUI o un notebook.
- **Reglas del punto extra configurables:** `min_quiz_grade` (nota mínima de los cuestionarios en cada tema; `AbsenceJustificationConfig`, `FullPipelineConfig`) y `bonus_points` (puntos que se suman; `TheoryBonusConfig`, `FullPipelineConfig`, `TheoryBonusApplier`). Los valores por defecto no cambian (7,5 y +1).

### Cambiado
- **INCOMPATIBLE: Python 3.10 o superior.** La versión mínima pasa de 3.8 a 3.10: Python 3.8 y 3.9 ya no tienen soporte y la librería `google-genai` exige 3.10 en sus versiones actuales (en 3.8 ni siquiera se podía instalar). Se actualizan `python_requires` y los clasificadores, `tox.ini`, Read the Docs y la CI (que prueba 3.10 y 3.14). Con Python 3.9, la última versión utilizable es la 0.3.0.
- **OCR: una hoja problemática ya no detiene la corrección:** si una imagen no se puede leer o no se puede deducir su tipo de examen, la hoja se omite y aparece en las incidencias con severidad alta (`UNREADABLE_IMAGE` / `EXAM_TYPE_UNRESOLVED`); el resto de hojas se corrige. `ExamCorrectionAPI` expone siempre las incidencias en `results["ocr_incidents"]` y, sin un terminal interactivo, nunca pregunta el tipo con `input()`.
- **Carpeta temporal del OCR:** por defecto se usa la carpeta temporal del sistema (`pyexamgenerator_temp`) en lugar del Escritorio, que a menudo se sincroniza con la nube y estas copias son escaneos de alumnos.
- **`QuestionGenerator` sin clave explícita:** `api_key` es opcional y se toma de `GEMINI_API_KEY` (el ejemplo del README `QuestionGenerator(model_name=...)` ya funciona); `model_name` sigue siendo obligatorio.
- **Columna de uso de la generación sin tildes:** `<examen>_<curso>_uso` elimina las tildes como ya hacía el registro de uso del banco (`Evaluacion`, no `Evaluaci_n`). Si el banco ya tiene la columna con el nombre antiguo, se reutiliza.
- **Respuesta correcta inválida:** si una pregunta seleccionada no tiene una letra válida (A-D) en `Respuesta correcta`, la generación se detiene con un error que la identifica, en lugar de producir un examen sin respuesta correcta. Se aceptan variantes como `B)`, ` b ` o `(c)`.
- **"Menos usadas" con celdas vacías:** una celda vacía en `Veces usada en examen` cuenta como 0 usos.
- **Categoría de Moodle sin guion final:** el XML usa `$course$/top/Examen Parcial - A` (antes `... - A -`), igual que la sugerencia de "Sugerir nombres Moodle". Si hay texto adicional, sigue añadiéndose con ` - `.
- **Nombres de fichero de los exámenes:** los caracteres no válidos (`/ \ : * ? " < > |`) de la asignatura o el examen se sustituyen por `-`, y un dato ausente ya no escribe `None`.
- **Plantillas DOCX:** una ruta de plantilla inexistente detiene la generación con un error (antes se usaba un documento en blanco sin avisar), y la cabecera de la plantilla se conserva: la línea de identificación del alumno se añade debajo en lugar de sustituirla.
- **Lista de ficheros fuente en la GUI separada por `;`:** los nombres pueden contener comas; al volver a seleccionar ficheros se añaden a la lista sin duplicados.
- **Combinar resultados «en su sitio»:** antes de sobrescribir se guarda una copia con fecha y hora del fichero anterior, y una celda vacía en el fichero nuevo ya no borra el valor anterior.
- **Una sola tarea de corrección a la vez** en la GUI: un segundo clic mientras otra está en marcha muestra un aviso.
- **Nombre de salida por defecto de `generate_multiple_choice_questions`:** `preguntas_pendiente_de_revisar.xlsx` (antes repetía el sufijo).
- **Dependencias:** ya no se instalan `ttkwidgets` ni `importlib-metadata`, que no se usaban.
- **`sync_branch.bat`:** lista los ficheros no versionados y pide confirmación antes de borrarlos con `git clean`.
- **Sesiones de corrección: JSON primero, pickle solo con permiso:** `GradingSession.load(...)` y `ExamCorrectionAPI.load_session(...)` usan siempre el `.json` y solo leen un `.pkl` (sin su `.json`) con `allow_pickle=True`, porque deserializar un pickle puede ejecutar código. La GUI pide confirmación antes de abrir un `.pkl`.
- **Documentación para desarrolladores y agentes de IA:** `AGENTS.md`, `CLAUDE.md`, `docs/dev/` y `TODO.md` con la revisión priorizada del repositorio.
- **La ventana ya no se queda congelada:** la generación de preguntas con Gemini, la carga de la lista de modelos y la generación de exámenes se ejecutan en segundo plano; el botón que las lanza queda deshabilitado hasta que terminan. La alerta de uso de preguntas sigue preguntando antes de continuar.
- **Campos de «Generar Exámenes» sin valores de prueba:** la asignatura, el examen, el curso, el banco, las instrucciones de la hoja de respuestas y el texto adicional de la categoría de Moodle empiezan vacíos. Antes venían con «Asignatura de Prueba», «Prueba GUI»… y, si no se cambiaban, acababan en los exámenes (por ejemplo, «Prueba GUI» en la hoja de respuestas). El nombre de salida por defecto de «Generar Preguntas» es `preguntas` (antes `banco_prueba`).
- **Integración de notas OCR: aviso al sustituir una nota existente:** si la nota de una hoja sustituye a una nota distinta que el alumno ya tenía en teoría (por ejemplo, porque también hizo el cuestionario en Moodle, o porque la hoja es de otra persona), la nota OCR se sigue aplicando pero queda la incidencia `OVERWRITTEN_GRADE` (severidad media) en `incidencias_integracion_ocr.xlsx`, el resumen cuenta `grades_overwritten` y la GUI lo avisa.
- **Rutas de salida absolutas en `grading`:** una ruta de salida absoluta se respeta aunque haya una carpeta de salida; antes el fichero acababa en esa carpeta. Los nombres relativos siguen guardándose en la carpeta de salida.
- **`.gitignore`:** ignora las cachés de herramientas (pytest, tox, ruff, mypy), `prueba_error/` y `deposito_rodin/`, y permite versionar ficheros de prueba sintéticos en `tests/fixtures/`.
- **Empaquetado con `pyproject.toml`:** sustituye a `setup.py`, `pytest.ini` y `requirements-dev.txt` (PEP 621), con los mismos metadatos y dependencias; la versión sigue en `pyexamgenerator/__init__.py`. Nuevos extras `[dev]` (tests, lint y publicación) y `[docs]`: el entorno de desarrollo se instala con `pip install -e ".[dev,docs,grading]"`. La licencia figura como expresión SPDX (`License-Expression: GPL-3.0-or-later`).
- **Versiones fijadas para la documentación:** Read the Docs y la CI compilan con Sphinx 8.1.3, sphinx-rtd-theme 3.1.0, MyST 4.0.1 y docutils 0.21.2, para que una versión nueva no rompa la publicación por sorpresa.
- **Tests reorganizados por funcionalidad:** `test_v023_features.py` y `test_v030_features.py` se reparten en `test_exam_question_selection.py`, `test_exam_docx_layout.py`, `test_moodle_xml.py`, `test_bank_usage.py` y `test_bank_merge_and_unify.py`.
- **Reintentos ante errores temporales de Gemini:** el límite de solicitudes (429) y los servidores saturados o no disponibles (5xx) se reintentan con esperas crecientes (2, 4 y 8 s, o la que indique la API, hasta 1 minuto) antes de avisar. Se detectan por el código de error de la API en lugar de buscar texto en el mensaje, y desaparece la pausa fija de 1 s tras cada respuesta.
- **Mensajes sin modelos concretos:** las sugerencias ya no recomiendan `gemini-2.5-flash` (desde septiembre de 2026 solo lo pueden usar quienes ya lo usaban); remiten a la lista de «Cargar Modelos». El README y el tutorial, igual.
- **Previsualización (`check=True`) fuera de un terminal:** sin `review_callback`, un error claro antes de generar nada (antes `input()` se quedaba esperando o fallaba). En la consola se acepta sí/si/s/yes.
- **Informe por tema del punto extra:** además de LPRL, RSP y T02..T11, incluye cualquier otro tema que aparezca en las columnas de clase (antes, un tema 1 o 12 se perdía).

### Arreglado
- **Seguridad: la respuesta de Gemini ya no se ejecuta con `eval`:** se analiza con `ast.literal_eval` (o `json.loads`), de modo que un PDF que manipule la salida del modelo no puede ejecutar código. Además, una pregunta mal formada (menos de cuatro opciones, respuesta no textual) ya no descarta el resto de preguntas de la misma respuesta.
- **El generador de exámenes reutilizaba el primer banco cargado:** `ExamGenerator.generate_exam_from_excel(...)` vuelve a leer el banco en cada llamada. Antes, en la GUI, una segunda generación usaba el banco anterior y, con "Actualizar Excel", podía sobrescribir el banco nuevo con el antiguo.
- **Registro de uso con números de pregunta repetidos:** al actualizar el uso se marcan exactamente las filas seleccionadas, en lugar de todas las que compartían `Número de pregunta` (habitual tras fusionar bancos).
- **Punto extra PIR concedido a todos:** si ninguna sesión de asistencia casaba con el horario, todos los alumnos recibían el punto extra; ahora no se concede y se emite un aviso.
- **Asistencias a partir de 2027:** las columnas de asistencia solo se reconocían si contenían "2026"; ahora se acepta cualquier año.
- **Alumnos partidos en dos filas por el ID:** la nota final y la comparación de resultados emparejan `12345678` y `12345678.0` (columna leída como número con huecos) como el mismo alumno.
- **Deduplicación de notas de Moodle:** `MoodleGradeIntegrator.integrate_grades(deduplicate_by_id=True)` ya no fusiona en una sola fila a todos los alumnos sin `Número de ID`.
- **Test de integración independiente de datos locales:** `tests/test_exam_order_integration.py` genera su banco sintético en lugar de depender de `prueba_error/` (no versionado).
- **Asistencia o justificación aplicada al alumno equivocado:** un `Número de ID` vacío se convertía en el texto `nan` y todos los alumnos sin ID compartían la misma clave; en modo extremo, la justificación de uno podía aplicarse a otros. La matrícula fusionada tampoco duplica ya a un alumno por `12345678` frente a `12345678.0`.
- **OCR asignaba la hoja a otro alumno:** con una matrícula ordenada o filtrada, el emparejamiento por nombre devolvía la fila de otra posición. Los IDs oficiales ya no salen como `nan` ni con `.0`.
- **Generación con un banco sin carpeta:** indicar `banco.xlsx` sin ruta hacía fallar la generación (y la conversión DOCX→XLSX).
- **Moodle XML con respuestas numéricas o vacías:** con `xml_use_answer_text=True` la exportación fallaba; ahora se escriben como texto (`25`, no `25.0`). Los DOCX tampoco muestran `nan` en celdas vacías.
- **"Menos usadas" en un banco nuevo:** fallaba si el banco aún no tenía la columna `Veces usada en examen`.
- **Lectura del DOCX revisado:** el enunciado se cortaba en el segundo `:` (p. ej. `Según la Ley 31/1995: ...`), `A)` se borraba también dentro del texto de la respuesta, se perdían los párrafos de continuación y una línea `Pregunta N` sin `:` hacía fallar todo el fichero.
- **`add_reviewed_questions_to_existing_excel`** devolvía una ruta distinta de la del fichero que escribía.
- **Corrección desde Excel con fechas inventadas:** `ExamGrader` escribía "20 de abril de 2026 17:05" y una duración fija en todas las filas; esas columnas quedan vacías.
- **"Editar" tipo de prompt abría el texto vacío:** había métodos duplicados en la GUI y se usaba la copia defectuosa; además, renombrar un prompt propio ya no deja el nombre antiguo.
- **Clave de API:** «Guardar Clave» ya no guarda el marcador `TU_CLAVE_API` ni muestra dos avisos seguidos.
- **Nota OCR asignada a otro alumno con el mismo nombre de pila:** si los ficheros usaban la columna `Apellidos` (sin `(s)`), la integración comparaba apellidos vacíos y emparejaba solo por el nombre; ahora usa las columnas detectadas y exige nombre y apellidos.
- **Justificaciones de alumnos con nombre compuesto:** ya no dependen de que coincida el ID (`María José García` se partía como `María` + `José García`).
- **Nota final con dos ficheros del mismo nombre** (en carpetas distintas): reciben etiquetas distintas (`notas`, `notas (2)`); antes la nota del segundo se contaba dos veces.
- **`run_moodle_plus_ocr_pipeline`** ya no modifica los objetos de configuración que recibe, y todos los flujos de corrección (OCR, matrícula, punto extra PIR, informes por tema) quedan registrados en la sesión.
- **Marcadores de plantilla partidos o en la cabecera:** `{{subject}}` y demás se sustituyen aunque Word los haya partido en varios fragmentos con formato, y también en cabeceras y pies de página.
- **Tema de los ficheros `.PDF` (en mayúsculas) e imágenes:** el tema ya no conserva la extensión.
- **Errores de entrada en la GUI:** un peso no numérico en la nota final o un banco ilegible (o bloqueado por Excel) al listar los temas muestran un mensaje en lugar de fallar solo en la consola.
- **Compatibilidad con pandas futuro:** al combinar resultados, asignar decimales a una columna leída como entera ya no genera el aviso que en próximas versiones de pandas será un error.
- **Corrección desde la GUI y campos de la interfaz:** las tareas de corrección leían campos de la ventana (carpeta de salida, matriculados, horario, columna de nota…) desde su hilo de trabajo, algo que Tkinter no admite de forma segura y que podía mezclar valores si se editaba un campo durante la tarea. Ahora se leen todos antes de empezar.
- **«Pipeline completo» deja ficheros con datos de alumnos tras un error:** la carpeta `_intermedios` (matrícula fusionada, notas OCR, teoría integrada) solo se borraba si todo iba bien; ahora se borra siempre.
- **Rueda del ratón:** la tabla de modelos, el texto del prompt y la tabla de exámenes a registrar vuelven a desplazarse con la rueda (la página se quedaba con todos los eventos).
- **Ventana lenta al cambiar de pestaña o al cerrarse:** cada tooltip enlazaba sus manejadores a la ventana entera, y se ejecutaban (tooltips × widgets) veces en cada evento. Ahora hay un solo manejador por ventana.
- **Fachada de corrección:** sin `export_steps_dir`, ya no vuelve a leer todos los ficheros de entrada, y `MoodleIntegrationConfig(xlsx_files=...)` acepta un generador (antes la integración fallaba con «No XLSX files were provided»).
- **Previsualización de exámenes (`check=True`):** si no se podía borrar el examen de previsualización, el mensaje decía que se había borrado; ahora informa del error.
- **Modelo retirado o clave no válida en la generación de preguntas:** se repetía la llamada fallida en cada intento de cada fragmento y el resultado era «no se generaron preguntas» sin explicación; ahora se detiene al primer error con un mensaje que dice qué cambiar.
- **Temas en el punto extra PIR:** «Ley 31/95» o «RD 39/97» con barra (y «Ley 31/1995») se reconocen igual que en el análisis de asistencia; antes el cálculo PIR solo aceptaba «Ley 31_95» y la sesión se ignoraba. Un texto como «Sistema 3» ya no se toma por «Tema 3».
- **Sesiones de corrección con callbacks en el config:** al guardar la sesión, los callbacks se omiten; antes se copiaban en profundidad (con un método de la GUI, la ventana entera) y la grabación fallaba.

## [0.3.0] - 2026-09-15

### Añadido
- **Modo unión/estricto en integración OCR (GUI + API):** la sección de integración en la pestaña **Corregir Exámenes** incorpora un check para elegir entre **unir** (añadir alumnos OCR no presentes en teoría) o **modo estricto** (bloquear no emparejados). La preferencia se guarda/carga en la sesión de corrección (`append_unmatched_ocr`) y se propaga a `OCRIntegrationConfig.append_unmatched_students`.
- **Reporte de incidencias de integración OCR:** `OcrGradeIntegrator` expone `last_integration_summary` y `last_integration_incidents_df`, `ExamCorrectionAPI.integrate_ocr_grades(...)` guarda el resumen en `results["ocr_integration_summary"]` y exporta `incidencias_integracion_ocr.xlsx` cuando hay filas bloqueadas.
- **Cobertura de pruebas para integración OCR y preservación de ID:** se añaden casos en `tests/test_grading_unit.py` y `tests/test_grading_session_and_grades.py` para validar modo unión/estricto, eliminación de filas resumen, exportación de incidencias y conservación de IDs con ceros iniciales.
- **Popups copiables en la GUI:** los cuadros `showinfo`, `showwarning` y `showerror` ahora se muestran con texto seleccionable/copiable (botón **"Copiar"** y atajo `Ctrl+C`), útil para pegar errores completos en incidencias o soporte.
- **Tabla para tipos forzados por imagen (OCR):** en **Corregir Exámenes**, además del campo de texto `imagen=tipo`, ahora se puede abrir una tabla con columnas **Imagen / Tipo asignado / Ruta** para asignar el tipo por fila desde el botón **"Asignar tipos en tabla..."**.
- **Generar XML Moodle desde un examen XLSX existente:** Nuevo método `ExamGenerator.generate_moodle_xml_from_existing_exam_xlsx(...)` para convertir directamente un `*_completo.xlsx` en XML de Moodle sin volver a generar el examen completo.
- **Conversión XLSX→XML en la pestaña Generar Exámenes:** La GUI añade la sección **"Generar Moodle XML desde XLSX de Examen"** (selección de `*_completo.xlsx`, ruta XML de salida opcional, penalización, texto extra de categoría y modo de XML no blanco).
- **Alerta por preguntas muy usadas al generar exámenes:** La pestaña **Generar Exámenes** avisa, por defecto, cuando alguna pregunta seleccionada supera 3 usos en `Veces usada en examen`; el umbral es configurable, la alerta se puede desactivar y la configuración se guarda/carga con la plantilla de la pestaña.
- **Identificación del alumno en cada página:** El DOCX del alumno incluye en la cabecera repetida de cada página huecos para Nombre, Apellidos, DNI/NIE y Firma, además de conservar la tabla de datos de la hoja de respuestas.
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
- **Actualizar banco con varios exámenes a la vez:** Nuevo método `QuestionBankManager.update_bank_with_exams(bank_path, exams, ...)` que registra el uso de **múltiples** exámenes en una sola pasada, dando a cada uno su propia etiqueta (cada examen genera su columna `<etiqueta>_uso` y al final se recalcula `Veces usada en examen`). Acepta cada examen como ruta, tupla `(ruta, etiqueta)` o dict `{"path", "label"}`; los exámenes ilegibles se omiten e informan en las estadísticas devueltas. La sección de la pestaña **Gestionar Banco de Preguntas** pasa a llamarse **"Actualizar Banco con Exámenes Existentes"** e incorpora una lista donde se añaden varios exámenes y se edita la etiqueta de cada uno (doble clic o botón "Editar etiqueta").
- **Etiquetas de uso sin tildes:** al construir la columna `<etiqueta>_uso` ahora se eliminan los acentos/diacríticos antes de sanear el nombre (p. ej. `Evaluación` → `Evaluacion`), evitando que las letras acentuadas se convirtieran en `_` (antes salía `Evaluaci_n`). La pestaña muestra además una columna **"Columna en XLSX"** con el nombre real que se escribirá.
- **Etiqueta automática desde el nombre del archivo:** nuevo método `QuestionBankManager.label_from_filename(path, delimiter, parts, join_with)` y parámetros `label_delimiter`/`label_parts` en `update_bank_with_exam(s)`. Permite **partir el nombre del archivo** por un delimitador (p. ej. `_`) y **quedarse con las partes elegidas** (índices 1-based, rangos `a:b` e índices negativos desde el final, p. ej. `"2:3, -4:-2"`). En la GUI se configura con los campos **"Delimitador"** y **"Partes a conservar"** y el botón **"Aplicar a la lista"**.
- **Unificar varios bancos en uno definitivo:** Nuevo método `QuestionBankManager.unify_question_banks(...)` y su sección **"Unificar Bancos de Preguntas"** en la pestaña Gestionar Banco. Combina N bancos de una vez eliminando duplicados con criterio elegible: **solo enunciado** (`enunciado`/`pregunta_unica`) o **enunciado + respuestas** (`enunciado_y_respuestas`/`pregunta_respuestas`). En el segundo modo las respuestas se comparan como **conjunto** (independiente del orden), de modo que un mismo enunciado con respuestas distintas se conserva como preguntas diferentes y una mera reordenación de las mismas respuestas se trata como duplicado. El primer banco tiene prioridad cuando una pregunta aparece en varios; devuelve además estadísticas (leídas, únicas, duplicados, errores).
- **Nuevas pruebas automáticas:** `tests/test_v030_features.py` valida el reparto equitativo (par/impar y con temas cortos), la selección por total (`equitativo`/`azar`), el arranque de la hoja de respuestas en página impar, la ausencia de línea en blanco entre preguntas, la actualización del banco desde un examen (uno y **varios** con etiqueta), la eliminación de tildes en la columna de uso y la **etiqueta automática** desde el nombre del archivo, el **layout del DOCX del alumno** (columnas desiguales en *Datos del alumno* y hoja de respuestas centrada con columna **NC** y contenido centrado) y la unificación de varios bancos (solo enunciado / enunciado + respuestas como conjunto).
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
- **Modo unión por defecto en integración OCR:** `OCRIntegrationConfig.append_unmatched_students` pasa a `True` por defecto para reflejar el flujo habitual (teoría Moodle + manuscritos OCR), añadiendo filas OCR no presentes en teoría salvo que se active explícitamente el modo estricto.
- **Penalización Moodle con decimales en GUI:** El campo de penalización ahora admite valores decimales (con coma o punto), tanto en la generación normal de exámenes como en la conversión de XLSX existente a XML.
- **Ubicación de la conversión XLSX→XML:** La opción de generar XML desde un `*_completo.xlsx` se mueve a la pestaña **Generar Exámenes** para centralizar el flujo de exportación a Moodle.
- **Enunciados navegables en Word:** Los enunciados de pregunta de los DOCX generados se escriben como `Heading 2`, manteniendo el aspecto compacto de fuente normal en negrita, para que aparezcan en el panel de navegación de Word.
- **Pestaña "Corregir Exámenes" por secciones independientes:** En lugar de un único botón que exigía todos los ficheros, ahora hay secciones con botón propio (corregir desde imágenes/OCR o desde respuestas Moodle, asistencia + justificaciones **opcional**, integrar notas, punto extra y nota final ponderada), además de mapeo de columnas y guardar/cargar sesión. Se mantiene un botón **"Pipeline completo"** para ejecutar todo de una pasada.
- **Hoja de respuestas en página impar:** En el DOCX del alumno, la hoja de respuestas (datos del alumno + tabla) ahora comienza en una **página impar** mediante un salto de sección `oddPage`, de modo que al imprimir a doble cara queda como una hoja física independiente sin salir del mismo documento que el examen.
- **Columna "NC" en la hoja de respuestas:** La tabla de respuestas del DOCX del alumno incorpora una quinta columna de opción **NC** (no contestada) para que el alumno marque explícitamente que deja la pregunta sin contestar, en lugar de dejarla en blanco. El OCR de corrección ya reconocía esta columna.
- **Tabla de respuestas centrada y compacta:** La tabla de respuestas del DOCX del alumno ahora se **centra** en la página, con columnas de opción de **1 cm** (la columna *Pregunta* se ajusta a su contenido) y el **contenido centrado** horizontal y verticalmente.
- **Datos del alumno con columnas desiguales:** En la tabla *Datos del alumno* del DOCX, la columna de etiquetas (Nombre, Apellidos, DNI/NIE, Firma) se estrecha y la columna de datos ocupa el resto del ancho de la página, dejando más espacio para escribir.
- **Sin línea en blanco entre preguntas:** Se elimina el salto de línea final de cada pregunta en los DOCX (alumno y profesor); el espaciado del estilo de párrafo ya separa cada pregunta de la siguiente.
- **Generación por fragmentos más flexible:** Se añade soporte para elegir el modo de fragmentación con `chunking_mode` (`pages` o `text_length`) y para definir `total_chunks` además de `pages_per_chunk`.
- **Flujo GUI de generación de preguntas ampliado:** La pestaña **Generar Preguntas** incluye controles para `total_chunks`, `chunking_mode` y para incluir/excluir preguntas similares del banco dentro del prompt.
- **Modo de entrada configurable para generación:** La pestaña **Generar Preguntas** permite elegir entre `text` (extracción de texto de PDF) e `image` (análisis visual multimodal con Gemini).

### Arreglado
- **Limpieza automática de filas de promedio/resumen antes de integrar OCR:** `OcrGradeIntegrator` elimina filas no pertenecientes a alumnos (p. ej. `Promedio general`) en el xlsx general, tanto en formato clásico como en formato de totales de cuestionario, y lo refleja en el contador `general_summary_rows_removed`.
- **Conservación de IDs con ceros iniciales en integraciones de notas:** la lectura de Excel evita la inferencia que perdía ceros a la izquierda (`001234 -> 1234`) y `_normalize_id` mantiene el valor textual del identificador en las salidas integradas.
- **Avisos de incidencias más claros en GUI:** al corregir OCR o integrar teoría+OCR, la interfaz muestra avisos específicos cuando hay incidencias OCR, filas bloqueadas en integración o filas resumen eliminadas automáticamente.
- **Ultimo recurso OCR con carpeta temporal configurable:** cuando fallan `cv2.imread(...)` y el fallback `np.fromfile + cv2.imdecode`, `AnswerSheetExtractor` copia la imagen a una carpeta temporal configurable y reintenta desde ahi; por defecto usa `~/Desktop/pyexamgenerator_temp` y limpia las copias al terminar. La GUI de **Corregir Exámenes** añade el campo **"Carpeta temp OCR (fallback)"**.
- **Tipo de examen único en OCR:** si el OCR no detecta el tipo en una hoja, pero solo hay una plantilla XML cargada (por ejemplo, solo `A`), `ImageExamGrader` usa automáticamente ese único tipo en lugar de fallar con *"Could not determine exam type"*.
- **Tipos forzados por nombre o ruta en OCR:** `ImageExamGrader` ahora acepta claves de `forced_type_by_image` tanto por nombre de archivo como por ruta completa (normalizando barras y mayúsculas/minúsculas), lo que evita colisiones cuando hay imágenes con el mismo nombre en carpetas distintas.
- **Lectura de imágenes OCR en rutas Windows con Unicode:** `AnswerSheetExtractor` añade un fallback `np.fromfile + cv2.imdecode` cuando `cv2.imread(...)` falla, evitando errores *"Could not read image"* en rutas con acentos/caracteres especiales (p. ej. carpetas de OneDrive).
- **Tipos de examen con letra sola (`A`, `B`) en corrección:** la inferencia del tipo desde XML y el parseo de columnas Moodle en integración (`Cuestionario:..._Tipo A (Real)`) aceptan ahora tanto formatos `A/B` como `1A/1B`.
- **Fracciones de penalización compatibles con Moodle:** Al exportar XML, las penalizaciones se ajustan automáticamente a opciones válidas de Moodle (p. ej., `-33` se normaliza a `-33.3333333`) para evitar omisión de preguntas al importar.
- **Scroll con rueda en pestañas largas de GUI:** Se corrige la rueda del ratón para que desplace aunque el cursor esté sobre campos o controles internos en **Gestionar Banco de Preguntas** y **Generar Preguntas**.
- **Columna de uso del `*_completo.xlsx`:** El XLSX generado junto al examen ahora añade al final la columna de uso del examen actual (`<examen>_<curso>_uso`) con valor `1` en todas sus filas, en lugar de dejar visibles valores históricos heredados del banco para las preguntas seleccionadas.
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
