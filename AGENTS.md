# AGENTS.md — Guía para agentes de IA

Instrucciones para agentes de programación (Claude Code, Codex, Copilot, Cursor, Gemini CLI…) y
para cualquier persona que contribuya. Es la fuente principal: `CLAUDE.md` la importa.

Documentación complementaria:

- [`docs/dev/ARCHITECTURE.md`](docs/dev/ARCHITECTURE.md): mapa de módulos, flujos de datos y esquema
  de los ficheros Excel/XML.
- [`docs/dev/DEVELOPMENT.md`](docs/dev/DEVELOPMENT.md): entorno, tests, documentación, flujo de
  trabajo con tareas y publicación de versiones.
- [`TODO.md`](TODO.md): tareas pendientes priorizadas con identificadores (`SEC-1`, `BUG-3`…).

## Qué es el proyecto

`pyexamgenerator` es una aplicación de escritorio (Tkinter) y librería Python para docentes que
cubre el ciclo completo de un examen tipo test:

1. **Generar preguntas** desde PDFs o imágenes con Google Gemini (`QuestionGenerator`).
2. **Gestionar bancos de preguntas** en Excel: revisar, fusionar, registrar uso (`QuestionBankManager`).
3. **Generar exámenes** en varias versiones barajadas → DOCX + XLSX + Moodle XML (`ExamGenerator`).
4. **Corregir**: OCR de hojas manuscritas, notas de Moodle, asistencias, punto extra y nota final
   (subpaquete `pyexamgenerator.grading`, fachada `ExamCorrectionAPI`).

Usuarios: profesorado universitario en España (Universidad de Cádiz). La interfaz, los mensajes, el
README, el CHANGELOG y los tutoriales están **en español**.

## Comandos esenciales

El desarrollo habitual es en **Windows** con un entorno virtual en `venv/` (Python 3.14).

```bash
# Tests (desde la raíz del repositorio)
venv/Scripts/python.exe -m pytest -q

# Un solo fichero o test
venv/Scripts/python.exe -m pytest tests/test_grading_unit.py -q
venv/Scripts/python.exe -m pytest -q -k "unify"

# Lint, formato y tipos (configuración en pyproject.toml; la CI exige los tres)
venv/Scripts/python.exe -m ruff check .
venv/Scripts/python.exe -m ruff format .
venv/Scripts/python.exe -m mypy

# Comprobar que el paquete se importa
venv/Scripts/python.exe -c "import pyexamgenerator as p; print(p.__version__, p.grading.HAS_OCR)"

# Lanzar la GUI (requiere pantalla; no lo hagas en entornos sin display)
venv/Scripts/python.exe -m pyexamgenerator.main_app
```

En Linux/macOS sustituye `venv/Scripts/python.exe` por `venv/bin/python`. Instalación de un entorno
nuevo: ver `docs/dev/DEVELOPMENT.md`.

`ruff check .` debe pasar (reglas `F` de pyflakes y `B` de bugbear) y el código está formateado
con `ruff format` (línea de 120, comillas tal como estén; los Markdown se excluyen): ejecútalo antes
de hacer commit. `pre-commit install` hace las dos cosas en cada commit y la CI las comprueba.

## Mapa del repositorio

```
pyexamgenerator/
  __init__.py              versión (__version__, fuente única) + API pública
  question_generator.py    QuestionGenerator: PDFs/imágenes → preguntas con Gemini
  question_bank_manager.py QuestionBankManager: DOCX revisado ↔ XLSX, fusión, uso, unificación
  _text.py                 helpers compartidos: strip_accents, safe_filename_part
  schema.py                nombres de columna del banco (schema.QUESTION…): úsalos, no repitas el literal
  exam_generator.py        ExamGenerator: banco XLSX → exámenes DOCX/XLSX/Moodle XML
  main_app.py              punto de entrada del comando `pyexamgenerator`: reexporta ExamApp y main()
  gui/                     la GUI Tkinter (ARC-1): app.py (ExamApp: ventana, menús, estado, tareas en
                           segundo plano) y una clase por pestaña que recibe la app: questions_tab.py,
                           bank_tab.py, exam_tab.py, grading_tab.py; _dialogs.py (messagebox)
  gui_logic.py             lógica de la GUI sin tkinter: interpretar los campos, avisos (se prueba sin pantalla)
  credentials.py           clave de API de Gemini: GEMINI_API_KEY o almacén de credenciales (keyring)
  user_config.py           carpeta de configuración del usuario (prompts, plantilla): nunca el CWD
  tooltip.py               ToolTip para la GUI
  grading/                 corrección de exámenes (ver ARCHITECTURE.md)
    api.py                 ExamCorrectionAPI + dataclasses *Config
    _ids.py                normalize_id: comparar IDs de alumno (úsalo siempre)
    _paths.py              prepare_output_path: rutas de salida (las absolutas se respetan)
    _text.py               normalize_key, find_column, clean_text, parse_decimal: reglas comunes (úsalas)
    _names.py              match_name: nombre escrito → alumno, solo coincidencias seguras (úsalo)
    _topics.py             topic_key: tema de una sesión o cuestionario (justificaciones y PIR)
    settings.py            grading_settings.json: grupos, temas, regla PIR, columnas de Moodle (úsalo)
    extraction.py          OCR de las hojas (único módulo que importa cv2/numpy/rapidocr)
    image_grading.py       ImageExamGrader: hojas escaneadas → notas (usa el OCR de extraction)
    attendance.py          justificaciones de faltas; pir_bonus.py y theory_bonus.py, el punto extra
    graders.py, integrations.py, final_grade.py, comparison.py, data.py, session.py
tests/                     pytest; todos los datos se generan en tmp_path
.github/workflows/         CI: pytest (Ubuntu/Windows, con y sin [grading]) + sphinx -W
docs/source/               Sphinx + MyST (Read the Docs); tutoriales en Markdown, API autogenerada
docs/dev/                  documentación para desarrolladores y agentes (fuera de Sphinx)
examples/                  PDF de ejemplo de los tutoriales (no se empaquetan)
pyproject.toml             empaquetado (PEP 621; extras [grading] OCR, [dev], [docs]) y config. de pytest
*.bat, add_user_path.ps1   scripts de Windows para build, docs, subida a PyPI e instalación
```

## Reglas del proyecto

### Idioma y estilo

- **Texto visible para el usuario** (GUI, `messagebox`, excepciones que llegan al usuario, nombres de
  columnas de Excel, README, CHANGELOG, tutoriales): **español**.
- **Código**: identificadores y docstrings preferentemente en inglés (estilo Google, que procesa
  `sphinx.ext.napoleon`). Hay código mezclado; al tocar una función, sigue el idioma que ya usa y no
  traduzcas código que no estás cambiando.
- Los **nombres de columna** de Excel son contrato con los usuarios y con Moodle (`'Pregunta'`,
  `'Respuesta A'`…`'Respuesta D'`, `'Respuesta correcta'`, `'Estado'`, `'Tema'`,
  `'Número de pregunta'`, `'Veces usada en examen'`, `'<etiqueta>_uso'`, `'Número de ID'`…). **No los
  renombres**: rompería bancos existentes. Ver `docs/dev/ARCHITECTURE.md`. En el código, las columnas
  del banco y de los exámenes se escriben con las constantes de `pyexamgenerator/schema.py`
  (`schema.QUESTION`, `schema.ANSWER_COLUMNS`, `schema.usage_column(etiqueta)`…), no con el literal;
  `tests/test_schema.py` fija sus valores.
- El código debe funcionar en la versión mínima declarada en `pyproject.toml` (**Python 3.10**): puedes
  usar `X | Y`, `match` y `tuple[...]`, pero no funciones de 3.11 o posteriores (`tomllib`,
  `ExceptionGroup`/`except*`, `typing.Self`, `enum.StrEnum`, `datetime.UTC`). La CI ejecuta la suite
  en 3.10. Si cambias la versión mínima, actualiza a la vez `pyproject.toml` (`requires-python` y
  clasificadores), `tox.ini`, `.readthedocs.yaml`, la CI y el README.
- Comentarios: la densidad y el tono del código existente. Cabecera de licencia GPL en los módulos
  principales: consérvala.

### Límites de arquitectura (no romper)

- **El OCR es opcional.** Solo `grading/extraction.py` puede importar `cv2`, `numpy` (como
  dependencia OCR) o `rapidocr*` a nivel de módulo; `grading/image_grading.py` depende de él.
  `grading/__init__.py` importa los dos dentro de `try/except ImportError` y expone `HAS_OCR`. Cualquier otro módulo debe funcionar sin el extra
  `[grading]`. Los tests de OCR usan `pytest.importorskip`.
- **La librería no debe depender de la GUI.** Nada en `question_generator.py`,
  `question_bank_manager.py`, `exam_generator.py` ni `grading/` importa `tkinter`. La lógica nueva
  va en la librería; `main_app.py` y `gui/` solo leen widgets, llaman a la librería y muestran resultados. Lo que
  sea propio de la GUI pero no necesite Tk (interpretar el texto de un campo, componer un aviso) va
  en `gui_logic.py`, con tests en `tests/test_gui_logic.py`.
- **No añadas `input()` ni prompts interactivos** a la librería: usa callbacks opcionales (como
  `usage_warning_callback` o `review_callback` en `ExamGenerator`, `exam_type_callback` en el OCR).
  Sin callback, solo se pregunta por consola desde un terminal (`pyexamgenerator/_console.py`).
- **Mensajes con `logging`, no con `print`:** cada módulo de la librería usa
  `logger = logging.getLogger(__name__)` (`info` para el progreso, `warning` y `error` para avisos y
  fallos). `print` solo queda en la interacción por consola y en los `main()` de línea de órdenes,
  que llaman a `_console.log_to_console()`, como la GUI. `tests/test_logging.py` lo comprueba.
- **Tkinter desde hilos:** nunca leas variables (`*.get()`) ni toques widgets fuera del hilo
  principal. Lee los valores antes de lanzar el hilo y devuelve resultados con `root.after(0, ...)`.
  Para tareas largas usa `ExamApp._run_in_background` (corrección: `_grad_run_async`, una tarea a la
  vez); si el hilo necesita preguntar al usuario, `_call_in_main_thread` muestra el diálogo en el
  hilo principal. `test_gui_smoke.py` comprueba que ningún hilo lee variables Tk.
- `ExamCorrectionAPI` es la fachada pública de `grading`: cada flujo recibe un dataclass `*Config`.
  Si añades un flujo, añade su `Config`, su método en la fachada, regístralo en la sesión
  (`session.record_workflow`) y expórtalo en `grading/__init__.py` (`__all__`).
- La API pública del paquete está en `pyexamgenerator/__init__.py` y `grading/__init__.py`. Cambiar
  una firma pública es un cambio incompatible: evítalo o deja compatibilidad hacia atrás.

### Seguridad y datos personales

- **Nunca** subas a git, a issues, a logs ni a la salida de un test datos reales de alumnos
  (nombres, DNI/NIE, correos, notas, escaneos). `.gitignore` excluye `*.xlsx`, `*.docx`, `*.xml`,
  `*.jpg`, `outputs/`, `_intermedios/`; no lo debilites sin excepciones acotadas a `tests/fixtures/`.
- Carpetas locales que **no debes leer, modificar ni versionar**: `prueba_error/` (datos de
  pruebas manuales), `deposito_rodin/`, `onedrive_backup` (enlace simbólico a OneDrive), `venv/`,
  `build/`, `dist/`, `.tox/`.
- **Nunca** llames a la API real de Gemini en tests: `tests/conftest.py` ya sustituye
  `google.genai.Client` en todos los tests; para simular respuestas, asigna un cliente falso a
  `generator.client`. No uses ni imprimas `GEMINI_API_KEY`; no leas `config.json`. Tampoco leas ni
  escribas la clave guardada en el almacén de credenciales del sistema: `tests/conftest.py` lo
  sustituye en todos los tests por uno en memoria (y la carpeta de configuración del usuario por
  una temporal).
- No uses `eval`, `exec` ni `pickle.load` sobre contenido externo (respuestas del modelo, ficheros
  del usuario). Las respuestas de Gemini se analizan con `QuestionGenerator._parse_question_literal`
  y las sesiones solo leen pickle con `allow_pickle=True`.

### Acciones que requieren confirmación del mantenedor

No ejecutes sin que el usuario lo pida explícitamente:

- `dist_upload.bat` / `dist_upload_test.bat` (publican en PyPI/TestPyPI) ni `twine upload`.
- `sync_branch.bat` (borra ficheros no versionados con `git clean -fd`, tras pedir confirmación) ni
  `install_current_version.bat --add-path` (modifica el PATH del usuario).
- `git push`, crear tags de versión, cambiar `__version__`, `CITATION.cff` o `.zenodo.json`.
- Subir la versión mínima de Python o añadir dependencias obligatorias (las pesadas van en extras).

## Definición de «hecho»

Antes de dar una tarea por terminada:

1. `pytest` pasa completo (indica cuántos tests pasan/se saltan; los de OCR se saltan sin `[grading]`).
2. Hay test nuevo para cada bug corregido o comportamiento añadido, con datos sintéticos creados en
   `tmp_path` (ver ejemplos en `tests/test_grading_unit.py` y `tests/test_bank_usage.py`).
3. `CHANGELOG.md`: entrada bajo `## [Unreleased]` en la sección adecuada (`### Añadido`,
   `### Cambiado`, `### Arreglado`), en español, con el formato de las entradas existentes
   (**negrita** + descripción, nombres de API entre comillas invertidas).
4. Si cambia algo visible para el usuario: actualiza README y/o el tutorial correspondiente en
   `docs/source/`. Read the Docs compila con `fail_on_warning: true`: todo `.md` nuevo en
   `docs/source/` debe estar en un `toctree`.
5. Si la tarea venía de `TODO.md`, marca su casilla y cita su identificador en el commit.
6. Mensajes de commit estilo *Conventional Commits* con ámbito, como en el historial:
   `feat(grading): ...`, `fix(exam): ...`, `docs: ...`, `test: ...`, `refactor(gui): ...`.

## Trampas conocidas

- `random` se usa para barajar: fija la semilla (`random.seed(...)`) en los tests que comparan orden.
- Los Excel de Moodle tienen IDs con ceros iniciales y, si hay huecos, pandas lee los numéricos como
  float (`12345678.0`). Compara IDs siempre con `pyexamgenerator.grading._ids.normalize_id` y, si
  necesitas conservar ceros iniciales, lee con `dtype=object`.
- Columnas de Moodle con nombres en español y, a veces, *mojibake* (`"Nmero de ID"`); busca columnas
  y lee notas con `pyexamgenerator.grading._text` (`find_column`, `normalize_key`, `parse_decimal`),
  que todos los módulos de `grading` comparten. No escribas otra copia con reglas distintas. Los
  nombres de esas columnas, los grupos (`GIM`…), los temas con nombre (`LPRL`…) y la regla PIR salen
  de `grading/settings.py` (`moodle_columns("id")`, `current_settings()`): no los escribas como
  literales, o la configuración del usuario no los cambiará.
- Para asignar un nombre escrito a un alumno de la matrícula usa `grading._names.match_name`, no un
  umbral de parecido (`difflib`): «Mario» y «María» puntúan 0,94 y el parecido asignaría la nota o
  la justificación a otra persona. Lo que no se asigne con seguridad debe acabar en un informe de
  incidencias, nunca en silencio.
- Los tipos de examen pueden ser `A`/`B` o `1A`/`1B`; el tipo se infiere del sufijo del nombre del
  XML (`..._1A.xml`).
- La GUI tiene pruebas de humo en `tests/test_gui_smoke.py`: construyen la ventana real sin mostrarla
  y se saltan donde no hay pantalla (la CI de Linux las ejecuta con `xvfb-run`). Usa su fixture `app`: crea una sola raíz
  Tk por módulo (crear `tk.Tk()` varias veces en un proceso falla de forma intermitente en Windows con
  «Can't find a usable tk.tcl») y registra los diálogos en `app.shown_messages` en lugar de quedarse
  bloqueada en ellos. Las pestañas están en `app.questions_tab`, `app.bank_tab`, `app.exam_tab` y
  `app.grading_tab`. Si cambias `gui/`, ejecútalas y describe lo que no pudiste probar a mano.
- Si editas ficheros con un script (heredoc de Python en Bash), cuidado con las barras invertidas:
  `\n` o `\b` pueden acabar como saltos de línea o caracteres de control dentro del código. Prefiere la
  herramienta de edición y compila después (`pytest tests/test_package_smoke.py`).
