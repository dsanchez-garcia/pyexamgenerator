# TODO — Mejoras pendientes de pyexamgenerator

Resultado de una revisión general del repositorio (2026-10-22, commit `ce8cc28`, versión 0.3.0).
Las referencias `archivo:línea` corresponden a ese commit y pueden desplazarse con el tiempo:
búscalas por nombre de función si no coinciden.

**Cómo usar este archivo (personas y agentes de IA):**

- Cada tarea tiene un identificador estable (`SEC-1`, `BUG-3`…). Cítalo en la rama, el commit y la
  entrada del `CHANGELOG.md` (p. ej. `fix(exam): re-leer el banco en cada generación (BUG-1)`).
- Una tarea = una rama = un PR pequeño, con test de regresión cuando sea un bug.
- Al terminar, marca la casilla `[x]` y añade el PR o commit al final de la línea. No borres tareas
  hechas hasta la siguiente versión publicada.
- Prioridad: **P0** = riesgo de seguridad o datos incorrectos para alumnos; **P1** = bug visible o
  bloqueo de infraestructura; **P2** = mantenibilidad; **P3** = pulido.
- Lee [`AGENTS.md`](AGENTS.md) antes de empezar cualquier tarea.

---

## 1. Seguridad y privacidad

- [x] **SEC-1 (P0)** `eval()` sobre la respuesta de Gemini — `pyexamgenerator/question_generator.py:444`.
  Un PDF con texto que manipule la respuesta del modelo puede ejecutar código Python en el equipo
  del usuario. Sustituir por `json.loads` (idealmente con `response_mime_type="application/json"` y
  un esquema en la llamada a Gemini) o, como mínimo, `ast.literal_eval`. Test con una respuesta
  maliciosa que no debe ejecutarse. — hecho en `7d7fabb`.
- [x] **SEC-2 (P0)** Carga de sesiones con `pickle.load` — `pyexamgenerator/grading/session.py:165,174`
  y botón «Cargar sesión» (`main_app.py:~1401`). Abrir un `.pkl` recibido de un tercero ejecuta
  código arbitrario, y al pasar una ruta sin extensión se prefiere el `.pkl` al `.json`. El JSON ya
  hace round-trip (`from_dict`): cargar JSON por defecto y dejar pickle tras un flag explícito
  (`trusted=True`) o eliminarlo. — hecho en `9161e7c`.
- [x] **SEC-3 (P1)** Clave de API en texto plano en `config.json` del directorio actual —
  `main_app.py:2149,2162`. Además se puede guardar el marcador `"TU_CLAVE_API"` como clave. Usar
  `keyring` o una carpeta de configuración por usuario (`platformdirs`) y rechazar el marcador.
  *Parcial (`dac098a`): ya no se guarda el marcador `TU_CLAVE_API` ni una clave vacía, y se ignora
  si una versión anterior lo guardó. Pendiente de decisión: dónde guardar la clave (keyring o
  carpeta de configuración por usuario).*
  *Decidido por el mantenedor (2026-10-22): almacén de credenciales del sistema con `keyring` (y,
  solo si no hay almacén, fichero en la carpeta de configuración del usuario); al arrancar se
  pregunta si mover la clave de un `config.json` antiguo; la librería también usa la clave
  guardada.* — hecho en la rama `fix/sec-3-clave-api` (`pyexamgenerator/credentials.py`).
- [x] **SEC-4 (P1)** Imágenes de alumnos copiadas al Escritorio por defecto —
  `grading/extraction.py:658`, `main_app.py:617` (`~/Desktop/pyexamgenerator_temp`). En Windows el
  Escritorio suele sincronizarse con OneDrive (datos personales en la nube, RGPD). Usar
  `tempfile.gettempdir()` y limpiar también `debug_dir` (`extraction.py:604`). — hecho en `9ae14f6`.
- [x] **SEC-5 (P2)** Añadir `SECURITY.md` con cómo reportar vulnerabilidades y una nota sobre datos
  personales de alumnos (no subir nunca xlsx reales, ni a issues). — hecho en `f59af25`. *Pendiente
  del mantenedor: activar «Private vulnerability reporting» en Settings → Code security.*

## 2. Bugs de corrección (datos incorrectos)

### Generación de exámenes y banco

- [x] **BUG-1 (P0)** `ExamGenerator` reutiliza el primer banco cargado — `exam_generator.py:861`
  (`if self.df is None`). La GUI mantiene una única instancia (`main_app.py:131`), así que una
  segunda generación con otro banco (o tras editar el Excel) usa datos viejos y, con
  `update_excel=True`, **sobrescribe el banco nuevo con el antiguo** (`:1233`). Re-leer siempre el
  banco (o cachear por ruta + `mtime`). — hecho en `d41d15f`.
- [x] **BUG-2 (P0)** El registro de uso empareja por `Número de pregunta`, que no es único —
  `exam_generator.py:1202-1206`. `add_questions_without_duplicates` (`question_bank_manager.py:186`)
  y `unify_question_banks` (`:653`) concatenan sin renumerar. Una pregunta puede marcar varias filas.
  Emparejar por enunciado (como hace `QuestionBankManager`) o renumerar al fusionar. — hecho en `d41d15f`.
- [x] **BUG-3 (P1)** Ruta de banco sin carpeta (`"banco.xlsx"`) rompe la generación —
  `exam_generator.py:986-988`, `question_bank_manager.py:738-741`: `os.makedirs('')` lanza
  `FileNotFoundError`. Usar `os.path.dirname(os.path.abspath(p))`. — hecho en `f40b1b3`.
- [x] **BUG-4 (P1)** Exportación Moodle falla con respuestas numéricas o vacías —
  `exam_generator.py:678-699` con `xml_use_answer_text=True`: `TypeError: cannot serialize 25`.
  Convertir a `str()` y NaN a `''`. — hecho en `f40b1b3`.
- [x] **BUG-5 (P1)** `menos usadas` lanza `KeyError` si el banco no tiene `Veces usada en examen` —
  `exam_generator.py:368`. Tratar la columna ausente como 0. — hecho en `f40b1b3`.
- [x] **BUG-6 (P1)** Dos esquemas de nombre para la columna `<etiqueta>_uso` —
  `exam_generator.py:189` (sustituye tildes por `_`) vs `question_bank_manager.py:202-210` (las
  elimina). Registrar el mismo examen por ambas vías duplica columnas y el conteo. Un único helper. — hecho en `8111c5b`.
- [x] **BUG-7 (P1)** Lectura de DOCX revisado frágil — `question_bank_manager.py:54-92`:
  `split(":")[1]` corta enunciados con `:`; `.replace("A)", "")` borra `A)` dentro del texto;
  la variable `state` no se usa y se pierden párrafos de continuación; un `except` amplio devuelve
  `None` para todo el archivo. Usar `split(":", 1)` y quitar solo el prefijo. — hecho en `8111c5b`.
- [x] **BUG-8 (P1)** Respuesta correcta en formato inesperado (`"B)"`, `"b "`) provoca `KeyError` o
  deja la pregunta sin respuesta correcta en Moodle sin avisar — `exam_generator.py:161-178`.
  Normalizar a `[A-D]` y avisar/lanzar si no hay coincidencia. — hecho en `f40b1b3`.
- [x] **BUG-9 (P2)** Una pregunta mal formada descarta toda la respuesta de Gemini —
  `question_generator.py:456-473` (`IndexError`/`AttributeError` no capturados por pregunta). — hecho en `7d7fabb`.
- [x] **BUG-10 (P2)** `generate_excel_from_docx` devuelve una ruta distinta de la que escribe —
  `question_bank_manager.py:778-781`. Devolver lo que devuelve `save_dataframe_to_excel`. — hecho en `8111c5b`.
- [x] **BUG-11 (P2)** Nombres de archivo de examen sin sanear — `exam_generator.py:1002`.
  `/`, `:` o `?` en asignatura/examen rompen en Windows; `None` produce `examen_None_...`. — hecho en `e7a49a1`.
- [x] **BUG-12 (P2)** Categoría Moodle con `" -"` final en el XML pero no en
  `suggest_moodle_config` — `exam_generator.py:649-655` vs `:108-113`. Un único helper. — hecho en `e7a49a1`.
- [x] **BUG-13 (P3)** Placeholders `{{...}}` de la plantilla DOCX partidos entre *runs* de Word no se
  sustituyen, y una plantilla inexistente se ignora en silencio — `exam_generator.py:1256-1271`. — hecho en `e7a49a1`.
- [x] **BUG-14 (P3)** `output_filename` por defecto genera
  `preguntas_pendiente_de_revisar_pendiente_de_revisar.xlsx` — `question_generator.py:1022`;
  `split('.pdf')` sensible a mayúsculas en `question_generator.py:125` (usar `os.path.splitext`). — hecho en `e7a49a1`.

### Corrección (`grading`)

- [x] **GRD-1 (P0)** El punto extra PIR se concede a todos si no casa ninguna sesión —
  `grading/attendance.py:1496-1502`: `all([])` es `True`. Exigir `topics` no vacío (la otra ruta ya
  lo hace en `:742`). — hecho en `5a8b9e1`.
- [x] **GRD-2 (P0)** Columnas de asistencia limitadas a 2026 — `grading/attendance.py:187`
  (`"2026" in text`). A partir de 2027 no se detecta ninguna columna. Detectar por
  `_parse_attendance_date(col) is not None`. — hecho en `5a8b9e1`.
- [x] **GRD-3 (P0)** IDs leídos como float dividen a un alumno en dos filas —
  `grading/final_grade.py:100`, `grading/comparison.py:140-141`, `grading/data.py:108,184`,
  `grading/attendance.py:432,528`: `read_excel` sin `dtype` → `"12345678.0"` y ceros iniciales
  perdidos. Leer con `dtype=object` y un único `normalize_id()` (reutilizar
  `OcrGradeIntegrator._normalize_id`). — hecho en `cdceb49` y `c81276a`.
- [x] **GRD-4 (P0)** Deduplicación fusiona a todos los alumnos sin ID — `grading/integrations.py:335`.
  Deduplicar solo filas con ID no vacío. — hecho en `cdceb49`.
- [x] **GRD-5 (P1)** Marcas de tiempo falsas en la corrección desde Excel — `grading/graders.py:82-84`
  escribe `"20 de abril de 2026 17:05"` y una duración fija en todas las filas. — hecho en `929e4f6`.
- [x] **GRD-6 (P1)** Modo `extremo` + emparejamiento difuso pueden justificar faltas al alumno
  equivocado — `grading/attendance.py:1037-1051`, `:410` (`cutoff=0.55`); `graders.py:56`
  (`cutoff=0.6`) asigna la nota al nombre más parecido en silencio. Subir umbrales, respetar
  `message_class` y reportar coincidencias < 0.9 como incidencias.
  *Decidido por el mantenedor (2026-10-22): ningún umbral separa una errata de otra persona
  («Mario»/«María» puntúan 0,94), así que solo se asignan coincidencias seguras (correo, mismo nombre
  en cualquier orden, o el único alumno que contiene todas las palabras) y el resto se informa con
  el candidato más parecido; el modo extremo no cuenta los correos clasificados como
  `no_justifica`; `ExamGrader` usa las mismas reglas con un fichero de incidencias.* — hecho en la
  rama `fix/grd-6-emparejamiento-seguro` (`grading/_names.py`).
- [x] **GRD-7 (P1)** Índice vs posición en el emparejamiento OCR — `grading/extraction.py:282-293`
  (`best_idx` de `iterrows()` usado con `.iloc`); `:295` fija `"Número de ID"` en vez de
  `self.id_col`. — hecho en `9ae14f6`.
- [x] **GRD-8 (P1)** Una imagen ilegible aborta todo el lote OCR — `grading/extraction.py:703,759`;
  `prompt_missing_type=True` por defecto llama a `input()` (bloquea fuera de terminal). — hecho en `9ae14f6`.
- [x] **GRD-9 (P2)** Nombres compuestos rompen la búsqueda de justificaciones —
  `grading/attendance.py:1046-1049,1063-1066` («María José García» → `maria_josegarcia`). — hecho en `45dd6f5`.
- [x] **GRD-10 (P2)** Detección de temas distinta entre PIR (`"ley 31_95"`, `attendance.py:1269`) y
  asistencia (`ley3195`, `:239`). — hecho en `59fa202` (`_topic_key`).
- [x] **GRD-11 (P2)** Reglas del bonus ignoran la config — `attendance.py:1836` (solo `T02..T11`),
  `:1764` (+1.0 fijo), `:742,746` (7.5 fijo) frente a `bonus_points`/`min_quiz_grade`. — hecho en
  `0ab8970`. *La GUI aún no expone estos dos valores (usa los de por defecto).*
- [x] **GRD-12 (P2)** `_name_match` fija `Nombre`/`Apellido(s)` — `grading/integrations.py:615-622`;
  `:865` sobrescribe una nota Moodle existente sin incidencia.
  *Parcial (`45dd6f5`): `_name_match` usa las columnas detectadas y exige nombre y apellidos (con
  `Apellidos` emparejaba solo por el nombre de pila). Completado en `2d669ed`: incidencia
  `OVERWRITTEN_GRADE` cuando el OCR sustituye a una nota distinta.*
- [x] **GRD-13 (P2)** La fachada relee todos los ficheros aunque no se exporten pasos —
  `grading/api.py:429-461,568-574,645,675,777`; `cfg.xlsx_files` se itera dos veces (falla con
  generadores). — hecho en `1bccd2c`.
- [x] **GRD-14 (P2)** `_resolve_output_path` descarta rutas absolutas explícitas
  (`grading/api.py:232`); `run_moodle_plus_ocr_pipeline` muta los config del llamador (`:523-529`).
  *Parcial (`37de35a`): `run_moodle_plus_ocr_pipeline` ya no modifica los config. Falta respetar
  rutas absolutas (hay que cambiar también las clases de trabajo, que hacen lo mismo).
  Completado en `1bccd2c` (`grading/_paths.py`).*
- [x] **GRD-15 (P2)** «Sobrescribir en su sitio» sin copia de seguridad (`grading/api.py:750`) y
  `comparison.py:213` reemplaza valores por NaN cuando el fichero nuevo tiene celdas vacías. — hecho en `37de35a`.
- [x] **GRD-16 (P2)** Dos ficheros con el mismo nombre en carpetas distintas colisionan en la nota
  final — `grading/final_grade.py:102`. — hecho en `37de35a`.
- [x] **GRD-17 (P3)** `grade_from_images`, `merge_enrollment_sources`, `calculate_pir_bonus` y
  `export_theory_topic_reports` no llaman a `session.record_workflow` (sesiones incompletas). — hecho en `37de35a`.

## 3. GUI (`main_app.py`)

- [x] **GUI-1 (P1)** Métodos definidos dos veces (gana la segunda copia): `save_prompt_types`
  (344/370), `add_edit_prompt_type` (380/468), `delete_prompt_type` (429/516),
  `update_prompt_type_options` (448/531). Bug visible: «Editar» abre el prompt vacío. Borrar la
  segunda copia (468-539). — hecho en `0fa3771`.
- [x] **GUI-2 (P1)** Variables Tkinter leídas desde hilos de trabajo — `main_app.py` ~1100-1537
  (`self.grad_*_var.get()` dentro de `work()`). Leer todo en el hilo principal antes de lanzar el
  hilo y devolver resultados solo con `root.after`. — hecho en `393881d`.
- [x] **GUI-3 (P1)** Operaciones largas bloquean la ventana: generación con Gemini (`:2328`), carga
  de modelos (`:2000`), generación de exámenes (`:3413`). Los botones de corrección no se
  deshabilitan: dos clics en «Pipeline completo» lanzan dos hilos sobre la misma carpeta
  `_intermedios` (`:1602`). Un helper común «deshabilitar → hilo → rehabilitar en `finally`».
  *Parcial (`80735e8`): solo una tarea de corrección a la vez. Completado en `da5b678`
  (`_run_in_background`): Gemini, la carga de modelos y la generación de exámenes en un hilo.*
- [x] **GUI-4 (P2)** Elegir ficheros dos veces concatena rutas sin separador (`:2199`) y separar por
  `,` rompe nombres de Windows con comas (`:2221`). — hecho en `063ec17`.
- [x] **GUI-5 (P2)** `float()`/`read_excel` fuera de `try` (`:1056,1069,1294,1301,3371,3386`): el
  error solo sale por consola. — hecho en `063ec17`.
- [x] **GUI-6 (P2)** El binding de la rueda del ratón rompe el scroll de `Treeview`/`Text` internos
  (`:1667-1672,1978,2788`). — hecho en `dc0dc50`.
- [x] **GUI-7 (P2)** `run_grading` (`:1453-1623`) reimplementa el pipeline completo a mano; moverlo a
  `ExamCorrectionAPI.run_full_pipeline(cfg)` y limpiar `_intermedios` en `finally`. — hecho en `393881d`.
- [x] **GUI-8 (P2)** `tooltip.py:50-51` registra manejadores `<Unmap>`/`<Destroy>` en la ventana
  raíz por cada tooltip (nunca se eliminan). Enlazar solo al widget. — hecho en `6cccdbc`.
- [x] **GUI-9 (P3)** Parcheo global de `messagebox.show*` (`:248-250`); usar un método envoltorio.
  — hecho en `650f9a5` (un `messagebox` propio del módulo de la GUI).
- [x] **GUI-10 (P3)** Valores por defecto de prueba en la UI («Asignatura de Prueba», «Prueba GUI»,
  `La/ruta/del/banco...`, `:142-158`); la GUI llama a un método privado `_usage_column_name`
  (`:3604`). — hecho en `19ee139`.

## 4. Arquitectura y mantenibilidad

- [ ] **ARC-1 (P2)** `main_app.py` (3.900 líneas, una clase con ~120 métodos). Dividir por pestaña
  (`gui/question_tab.py`, `gui/bank_tab.py`, `gui/exam_tab.py`, `gui/grading_tab.py`) y extraer la
  lógica pura a `gui_logic.py` testeable (parsers de pesos, penalización, preguntas por tema,
  mapeos de plantilla/sesión, constructor de avisos OCR).
  *Parcial (`3694d52`): `pyexamgenerator/gui_logic.py` (sin tkinter) con los parsers de los campos
  y los avisos de la integración OCR; los mapeos de plantilla/sesión quedan en `ExamApp` porque
  enlazan variables Tk (`0375766`). Falta dividir `main_app.py` por pestañas (conviene acordar
  antes la estructura del subpaquete `gui/`).*
- [x] **ARC-2 (P2)** Código de pestaña con scroll copiado 4 veces (`:582,1646,2385,2758`) y
  guardado/carga de plantilla y sesión con listas de campos duplicadas (`:3821-3913`, `:1354-1443`).
  *Parcial (`dc0dc50`): la rueda del ratón de dos pestañas usa un único helper (`_bind_page_scroll`).*
  — hecho en `0375766` (`_create_scrollable_tab` y un mapa de campos para guardar y cargar).
- [ ] **ARC-3 (P2)** Nombres de columna repetidos como literales en todos los módulos (`'Pregunta'`,
  `'Respuesta A'`, `'Estado'`, `'Veces usada en examen'`, `'_uso'`, `'Número de ID'`…). Crear
  `pyexamgenerator/schema.py` con constantes y usarlo en todas partes.
- [x] **ARC-4 (P2)** Helpers duplicados en `grading` con reglas ligeramente distintas (`_normalize`,
  `_find_column`, `_parse_grade`, `_clean` en `data.py`, `comparison.py`, `final_grade.py`,
  `integrations.py`, `attendance.py`, `extraction.py`). Unificar en `grading/_text.py`. — hecho en
  `27023c8` (de paso, las filas sin ID ni nombre ya no cuentan como un alumno en la nota final ni en
  la comparación).
- [ ] **ARC-5 (P2)** Módulos de `grading` que son concatenaciones de ficheros antiguos (imports a
  mitad de fichero, bloques `if __name__ == "__main__"` intermedios en `integrations.py:1108`,
  `extraction.py:841`). Dividir `attendance.py` (1.890 líneas) y `extraction.py` (1.590).
  *Nota: `extraction.py` también define dos veces las funciones de módulo `_parse_args` y `main`
  (restos de la concatenación); gana la segunda.*
  *Parcial (`d1c6542`): quitados los imports repetidos a mitad de fichero. `d1f1dbb`: eliminada la
  primera copia de `_parse_args`/`main` (al ejecutar el módulo corrían las dos), los imports que
  quedaban a mitad de fichero suben a la cabecera y cada bloque `__main__` queda al final. Falta
  dividir `attendance.py` y `extraction.py` (conviene acordar antes los módulos nuevos y mantener
  las rutas de import actuales).*
- [ ] **ARC-6 (P2)** `generate_exam_from_excel` ≈ 450 líneas y 26 parámetros. Introducir un
  `ExamConfig` (dataclass) y separar selección / construcción de variantes / escritura.
- [x] **ARC-7 (P2)** `input()` en código de librería — `exam_generator.py:965` (`check=True`, solo
  acepta exactamente `"sí"`), `grading/extraction.py:1030,1265`. Sustituir por callbacks, como
  `usage_warning_callback`. — hecho en `b53bbcd` (la consola queda como opción por defecto en un
  terminal, en `_console.py`).
- [ ] **ARC-8 (P2)** 134 `print()` y 0 usos de `logging`. Introducir `logging.getLogger(__name__)` en
  la librería; la GUI puede añadir un handler.
- [x] **ARC-9 (P2)** ~34 `except Exception`/`except:` que tragan errores (p. ej.
  `exam_generator.py:436,1236`). Revisar uno a uno.
  *Parcial (`9d9fb12`): revisados los de la librería; corregidos los que daban resultados
  incorrectos en silencio (banco ilegible, uso no registrado, banco de duplicados ilegible). Quedan
  los de `main_app.py` (casi todos informan al usuario) y pasar los `print` a `logging` (ARC-8).*
  — hecho en `ac8e865` (los de `main_app.py`: solo la lista de temas se tragaba los errores; pasar
  los `print` a `logging` sigue en ARC-8).
- [ ] **ARC-10 (P2)** Valores institucionales fijos en código (grupos `GIM`, `GITI-GIE-GIEI`, regla
  PIR, temas `LPRL`/`RSP`, columnas mojibake `"Nmero de ID"`). Moverlos a configuración.
- [x] **ARC-11 (P2)** `QuestionGenerator`: errores de cuota/sobrecarga detectados por subcadena
  (`"429"`, `question_generator.py:980,994`) y `time.sleep(1)` fijo. Usar
  `google.genai.errors.APIError.code` y reintentos con backoff exponencial. — hecho en `f61113a`
  (y `GeminiRequestError` para 401/403/404).
- [x] **ARC-12 (P2)** Ubicación de ficheros de configuración inconsistente (`config.json` y
  `custom_prompts.json` en CWD; plantilla en CWD → `%APPDATA%`, solo Windows). Un único
  `config_dir()` con `platformdirs`. Hay además un `pyexamgenerator/custom_prompts.json` suelto e
  ignorado dentro del paquete.
  *Decidido por el mantenedor (2026-10-22): una carpeta por usuario calculada sin dependencias
  (`%APPDATA%\pyexamgenerator`, `~/.config/pyexamgenerator`, `~/Library/Application Support/…`);
  al arrancar se pregunta si mover los ficheros de la carpeta actual (los prompts se combinan); menú
  «Abrir carpeta de configuración».* — hecho en la rama `refactor/carpeta-configuracion`
  (`pyexamgenerator/user_config.py`). El `pyexamgenerator/custom_prompts.json` suelto es un fichero
  local, ignorado por git: la aplicación ofrece moverlo si se abre desde esa carpeta.
- [x] **ARC-13 (P3)** Estado compartido en `self` (`self.text`, `self.quiz`, `self.page_texts`) hace
  que las instancias no sean reutilizables de forma segura. — hecho en `b6913cb`.

## 5. Dependencias, empaquetado y compatibilidad

- [x] **PKG-1 (P1)** `setup.py` declara `python_requires='>=3.8'`, pero
  `question_generator.py:594` usa `tuple[...]` (requiere 3.9): la app no arranca en 3.8. Además 3.8
  (EOL 2024-10) y 3.9 (EOL 2025-10) ya no tienen soporte. **Decisión pendiente del mantenedor:**
  subir el mínimo a 3.10 y actualizar clasificadores, `tox.ini`, `.readthedocs.yaml` (usa 3.9) y
  README.
  *Decidido por el mantenedor (2026-10-22): mínimo Python 3.10. Anotación corregida en `07e3e4d`;
  `setup.py`, `tox.ini`, `.readthedocs.yaml`, CI, README y guías actualizados en la rama
  `build/python-3.10`.*
- [x] **PKG-2 (P2)** Migrar `setup.py` → `pyproject.toml` (PEP 621) con extras `dev`, `docs`,
  `grading`; centralizar configuración de pytest y ruff. Mantener la versión única en
  `pyexamgenerator/__init__.py` (dinámica). — hecho en `16af861` (ruff en `d1c6542`).
- [x] **PKG-3 (P2)** `ttkwidgets` es dependencia obligatoria solo por un import no usado
  (`main_app.py:30`). Eliminar import y dependencia. Igual con `Document` (`:25`) y el fallback
  `importlib_metadata` (`:37-42`, y `importlib-metadata; python_version < "3.8"` en `setup.py`). — hecho en `2fd7db2`.
- [x] **PKG-4 (P2)** `PyPDF2` está deprecado (avisa en cada test). Migrar a `pypdf`.
  *Decidido por el mantenedor (2026-10-22): migrar a `pypdf`.* — hecho en la rama `build/pypdf`
  (`pypdf>=6.21.2`, la primera versión sin los avisos de seguridad publicados en octubre de 2026).
- [x] **PKG-5 (P2)** `requirements-dev.txt` duplica las dependencias de `setup.py`. Sustituir por
  `pip install -e .[dev,grading,docs]` cuando exista PKG-2. — hecho en `410a2f1`.
- [x] **PKG-6 (P2)** `docs/requirements.txt` sin versiones fijadas y RTD con `fail_on_warning: true`:
  una versión nueva de Sphinx puede romper la build. Fijar versiones. — hecho en `8f1d70b`.
- [x] **PKG-7 (P3)** La versión está en 3 sitios (`__init__.py`, `CITATION.cff`, `.zenodo.json`) más
  la fecha en `CHANGELOG.md`. Añadir un test que compruebe que coinciden (o un script de *bump*).
  — hecho en `ae5ba96`.
- [x] **PKG-8 (P3)** Modelos Gemini fijados en mensajes y docs (`gemini-2.5-flash/pro` en
  `question_generator.py:60,986,998`, README). Verificar vigencia y sacar la sugerencia de
  configuración o de `client.models.list()`. — hecho en `f61113a`: a 2026-10-22, `gemini-2.5-flash`
  solo lo pueden usar quienes ya lo usaban; los mensajes remiten a la lista de modelos y un 404
  sugiere los disponibles.

## 6. Tests y CI

- [x] **TST-1 (P1)** No hay CI. Añadir `.github/workflows/tests.yml`: pytest en Windows y Ubuntu,
  versiones mínima y máxima soportadas, con y sin extra `[grading]`; y un job de build de docs
  (`sphinx -W`). — hecho en `07e3e4d`.
- [x] **TST-2 (P1)** `tests/test_exam_order_integration.py` depende de
  `prueba_error/examen_CSP_Q-PA_25-26.xlsx`, que no está en git (`prueba_error/` y `*.xlsx` están
  ignorados): falla en un clon limpio. Generar el banco en `tmp_path` o versionar un fixture
  anonimizado en `tests/fixtures/` (con excepción `!tests/fixtures/**` en `.gitignore`). — hecho en `07e3e4d`.
- [x] **TST-3 (P2)** Sin tests: `QuestionGenerator._analyze_gemini_response`, `_build_prompt`,
  `generate_multiple_choice_questions` (con cliente simulado), `filter_generated_questions_duplicates`;
  `QuestionBankManager.read_questions_from_docx`, `generate_excel_from_docx`,
  `add_reviewed_questions_to_existing_excel`; `ExamGenerator` con `update_excel=True`, `check=True`,
  `primeras`, `menos usadas`, `questions_per_topic`, `NoAcceptableQuestionsError`.
  *Parcial: ya cubiertos `_analyze_gemini_response`, `generate_multiple_choice_questions` (cliente
  simulado), `read_questions_from_docx` (ida y vuelta), `add_reviewed_questions_to_existing_excel`,
  `update_excel=True`, `menos usadas`, `questions_per_topic`, plantillas DOCX y XML con respuestas
  numéricas o vacías, y el borrado de la previsualización con `check=True` (`d1c6542`).
  Completado en `5b8f42e` (filtro de duplicados, `primeras`, `NoAcceptableQuestionsError`) y
  `b53bbcd` (`check=True` con callback, consola y sin terminal).*
- [x] **TST-4 (P2)** Sin tests en `grading`: `PIRBonusCalculator` (incluido GRD-1),
  `AbsenceJustificationManager.analyze`, `MoodleGradeIntegrator.deduplicate_by_id` (GRD-4),
  `FinalGradeCalculator` con IDs mixtos/NaN (GRD-3), `export_steps_dir` + `manifest.json`,
  asistencia de 2027 (GRD-2). OCR: fixture sintético de hoja de respuestas con `RapidOCR` simulado.
  *Parcial: ya cubiertos el PIR sin sesiones, la deduplicación por ID, la nota final y la comparación
  con IDs float, la matrícula fusionada, las claves de justificación y el flujo OCR con hojas fallidas
  (extractor simulado), la detección de temas y la regla de cuestionarios del punto extra (`59fa202`,
  `0ab8970`), y `AbsenceJustificationManager.analyze` completo con `export_steps_dir` y
  `manifest.json` (`5410d6b`). Falta un fixture sintético de hoja de respuestas para el OCR.*
  — hecho en `ed07b5b` (hojas PNG sintéticas con un RapidOCR simulado, de la imagen a la nota).
- [x] **TST-5 (P2)** Sin tests de GUI. Tras ARC-1, testear `gui_logic.py` sin pantalla.
  *Parcial: `tests/test_gui_smoke.py` construye la ventana real (Windows y Linux con xvfb) y prueba
  prompts, clave de API, lista de ficheros, errores de entrada, la tarea única de corrección, las
  tareas en segundo plano, las lecturas desde hilos, la rueda del ratón y los tooltips. Falta
  extraer `gui_logic.py`.* — hecho en `3694d52` y `23d4b3b` (`tests/test_gui_logic.py`, sin
  pantalla).
- [x] **TST-6 (P3)** Añadir configuración de pytest (`testpaths = tests`, marcadores `ocr` e
  `integration`, `filterwarnings`). — hecho en `63e1da2`.
- [x] **TST-7 (P3)** Renombrar `test_v023_features.py` / `test_v030_features.py` por funcionalidad
  (`test_moodle_xml.py`, `test_bank_usage.py`…). `test_exam_order_integration.py` mezcla
  tabuladores con espacios.
  *Parcial (`07e3e4d`): `test_exam_order_integration.py` ya usa solo espacios. Completado en
  `c5d0bd6`: cinco ficheros por funcionalidad.*
- [x] **TST-8 (P3)** `tests/test_image_mode_unit.py:28` crea un `genai.Client` real con clave falsa;
  simularlo. — hecho en `092840c` (`tests/conftest.py`, para todos los tests).

## 7. Herramientas de desarrollo

- [x] **DEV-1 (P2)** Sin linter/formateador. Añadir `ruff` (lint + format) con una configuración
  inicial permisiva y `pre-commit`. Aplicar el formateo en un PR aparte, sin cambios funcionales.
  *Análisis previo (2026-10-22, `ruff check --select F`): ningún nombre sin definir (F821); 18 imports
  repetidos por la concatenación de módulos de `grading` (ARC-5), 7 variables asignadas sin uso
  (restos de lógica sustituida, sin efecto) y 6 imports sin uso. Buen punto de partida: activar `F`.*
  — hecho en `d1c6542`: reglas `F` en la CI y pre-commit (además, un `except` repetido que daba un
  mensaje falso). *Pendiente: aplicar `ruff format` en un PR aparte y ampliar las reglas.*
  *`ruff format` aplicado en `5916315` (decidido por el mantenedor el 2026-10-22: comillas tal como
  estaban, Markdown excluidos; mismo AST antes y después); la CI y pre-commit lo exigen y el commit
  está en `.git-blame-ignore-revs`. Queda ampliar las reglas de lint.*
- [x] **DEV-2 (P3)** Tipado: añadir `mypy` (o `pyright`) en modo no estricto, empezando por
  `grading/api.py` y los dataclasses de configuración. — hecho en `b08fab8` (job `mypy` en la CI;
  ir añadiendo módulos a `[tool.mypy]`).
- [x] **DEV-3 (P3)** Scripts `.bat` solo para Windows; `install_current_version.bat --add-path` usa
  `setx Path`, que trunca el PATH a 1.024 caracteres. Considerar `py -m pip install -e .` y
  documentar el PATH manualmente, o usar PowerShell. — hecho en `ca7376e` (`add_user_path.ps1`;
  `docs/dev/DEVELOPMENT.md` indica qué usar en Linux/macOS).
- [x] **DEV-4 (P3)** `sync_branch.bat` ejecuta `git clean -fd` sin confirmación (borra ficheros no
  versionados que no estén ignorados). Pedir confirmación o eliminar el paso. — hecho en `f4c3851`.

## 8. Repositorio y documentación

- [x] **REPO-1 (P2)** `.gitignore`: faltan `.tox/`, `.pytest_cache/`, `docs/build/`, `.ruff_cache/`,
  `.mypy_cache/`; los patrones globales `*.xlsx`, `*.docx`, `*.xml`, `*.jpg` impedirán versionar
  fixtures de test (ver TST-2). Hay además un cambio sin commitear (`deposito_rodin/`). — hecho en
  `c622270` (con excepción acotada a `tests/fixtures/`).
- [x] **REPO-2 (P2)** `__init__.py` vacío en la raíz del repositorio convierte la raíz en paquete y
  puede confundir a pytest y a las herramientas. Eliminar. — hecho en `07e3e4d`.
- [x] **REPO-3 (P3)** PDFs de ejemplo en la raíz (`RD 31-95 LPRL*.pdf`, `RD 39-97 RSP*.pdf`, ~1 MB).
  Moverlos a `examples/` y enlazarlos desde los tutoriales. — hecho en `f905067`.
- [x] **REPO-4 (P2)** README: `QuestionGenerator(model_name=MODEL_NAME)` (`README.md:139`) lanza
  `TypeError` porque `api_key` es obligatorio y el código no lee `GEMINI_API_KEY`. Hacer
  `api_key: Optional[str] = None` con *fallback* a la variable de entorno (y test). — hecho en `9607102`.
- [x] **REPO-5 (P3)** Docstring de `generate_question_text` dice que devuelve 3 valores y devuelve 2
  (`exam_generator.py:439,520`); además muta su entrada. — hecho en `f40b1b3`.
- [x] **REPO-6 (P3)** Añadir `CONTRIBUTING.md` (o enlazar `docs/dev/DEVELOPMENT.md` desde el README)
  y plantillas de issue/PR en `.github/`. — hecho en la rama `fix/p2-correcciones`.
- [ ] **REPO-7 (P3)** Mezcla de idiomas en identificadores y comentarios (inglés/español). Fijar la
  convención documentada en `AGENTS.md` y aplicarla progresivamente, sin PRs masivos.

---

## Orden de trabajo sugerido

1. **Red de seguridad:** TST-2 → TST-1 (CI) → REPO-1/REPO-2 → PKG-1 (decidir versión mínima).
2. **P0 de seguridad y datos:** SEC-1, SEC-2, BUG-1, BUG-2, GRD-1, GRD-2, GRD-3, GRD-4 (cada uno con
   su test de regresión).
3. **P1 restantes**, empezando por GUI-1 (trivial) y BUG-3/4/5.
4. **Fundaciones de mantenibilidad:** PKG-2, DEV-1, ARC-3, ARC-8; después ARC-1 y ARC-5 por partes.
