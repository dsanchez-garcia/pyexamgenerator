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

# Comprobar que el paquete se importa
venv/Scripts/python.exe -c "import pyexamgenerator as p; print(p.__version__, p.grading.HAS_OCR)"

# Lanzar la GUI (requiere pantalla; no lo hagas en entornos sin display)
venv/Scripts/python.exe -m pyexamgenerator.main_app
```

En Linux/macOS sustituye `venv/Scripts/python.exe` por `venv/bin/python`. Instalación de un entorno
nuevo: ver `docs/dev/DEVELOPMENT.md`.

No hay linter ni formateador configurados todavía (ver `DEV-1` en `TODO.md`). No reformatees
ficheros enteros: limita el diff a lo que cambias.

## Mapa del repositorio

```
pyexamgenerator/
  __init__.py              versión (__version__, fuente única) + API pública
  question_generator.py    QuestionGenerator: PDFs/imágenes → preguntas con Gemini
  question_bank_manager.py QuestionBankManager: DOCX revisado ↔ XLSX, fusión, uso, unificación
  exam_generator.py        ExamGenerator: banco XLSX → exámenes DOCX/XLSX/Moodle XML
  main_app.py              GUI Tkinter (clase ExamApp, ~3.900 líneas) y entry point main()
  tooltip.py               ToolTip para la GUI
  grading/                 corrección de exámenes (ver ARCHITECTURE.md)
    api.py                 ExamCorrectionAPI + dataclasses *Config
    extraction.py          OCR (único módulo que importa cv2/numpy/rapidocr)
    graders.py, integrations.py, attendance.py, final_grade.py, comparison.py, data.py, session.py
tests/                     pytest; todos los datos se generan en tmp_path
.github/workflows/         CI: pytest (Ubuntu/Windows, con y sin [grading]) + sphinx -W
docs/source/               Sphinx + MyST (Read the Docs); tutoriales en Markdown, API autogenerada
docs/dev/                  documentación para desarrolladores y agentes (fuera de Sphinx)
setup.py                   empaquetado (extra opcional [grading] para OCR)
*.bat                      scripts de Windows para build, docs, subida a PyPI e instalación
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
  renombres**: rompería bancos existentes. Ver `docs/dev/ARCHITECTURE.md`.
- Anotaciones de tipo compatibles con la versión mínima declarada en `setup.py`: usa `typing.Tuple`,
  `Optional`, `Dict`… o añade `from __future__ import annotations`. No uses `X | Y`, `match` ni
  `tuple[...]` en tiempo de ejecución sin ese import (ver `PKG-1`).
- Comentarios: la densidad y el tono del código existente. Cabecera de licencia GPL en los módulos
  principales: consérvala.

### Límites de arquitectura (no romper)

- **El OCR es opcional.** Solo `grading/extraction.py` puede importar `cv2`, `numpy` (como
  dependencia OCR) o `rapidocr*` a nivel de módulo. `grading/__init__.py` lo importa dentro de
  `try/except ImportError` y expone `HAS_OCR`. Cualquier otro módulo debe funcionar sin el extra
  `[grading]`. Los tests de OCR usan `pytest.importorskip`.
- **La librería no debe depender de la GUI.** Nada en `question_generator.py`,
  `question_bank_manager.py`, `exam_generator.py` ni `grading/` importa `tkinter`. La lógica nueva
  va en la librería; `main_app.py` solo lee widgets, llama a la librería y muestra resultados.
- **No añadas `input()` ni prompts interactivos** a la librería: usa callbacks opcionales (como
  `usage_warning_callback` en `ExamGenerator`). Hay deuda existente (`ARC-7`).
- **Tkinter desde hilos:** nunca leas variables (`*.get()`) ni toques widgets fuera del hilo
  principal. Lee los valores antes de lanzar el hilo y devuelve resultados con `root.after(0, ...)`.
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
- **Nunca** llames a la API real de Gemini en tests: simula `google.genai.Client`. No uses ni
  imprimas `GEMINI_API_KEY`; no leas `config.json`.
- No uses `eval`, `exec` ni `pickle.load` sobre contenido externo (respuestas del modelo, ficheros
  del usuario). Las respuestas de Gemini se analizan con `QuestionGenerator._parse_question_literal`
  y las sesiones solo leen pickle con `allow_pickle=True`.

### Acciones que requieren confirmación del mantenedor

No ejecutes sin que el usuario lo pida explícitamente:

- `dist_upload.bat` / `dist_upload_test.bat` (publican en PyPI/TestPyPI) ni `twine upload`.
- `sync_branch.bat` (hace `git clean -fd`) ni `install_current_version.bat --add-path` (modifica el
  PATH del usuario).
- `git push`, crear tags de versión, cambiar `__version__`, `CITATION.cff` o `.zenodo.json`.
- Subir la versión mínima de Python o añadir dependencias obligatorias (las pesadas van en extras).

## Definición de «hecho»

Antes de dar una tarea por terminada:

1. `pytest` pasa completo (indica cuántos tests pasan/se saltan; los de OCR se saltan sin `[grading]`).
2. Hay test nuevo para cada bug corregido o comportamiento añadido, con datos sintéticos creados en
   `tmp_path` (ver ejemplos en `tests/test_grading_unit.py` y `tests/test_v030_features.py`).
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
- Columnas de Moodle con nombres en español y, a veces, *mojibake* (`"Nmero de ID"`); los helpers de
  `grading` buscan columnas de forma tolerante (`_find_column`). Reutilízalos.
- Los tipos de examen pueden ser `A`/`B` o `1A`/`1B`; el tipo se infiere del sufijo del nombre del
  XML (`..._1A.xml`).
- La GUI tiene pruebas de humo en `tests/test_gui_smoke.py`: construyen la ventana real sin mostrarla
  y se saltan donde no hay pantalla (p. ej. la CI de Linux). Usa su fixture `app`: crea una sola raíz
  Tk por módulo (crear `tk.Tk()` varias veces en un proceso falla de forma intermitente en Windows con
  «Can't find a usable tk.tcl») y registra los diálogos en `app.shown_messages` en lugar de quedarse
  bloqueada en ellos. Si cambias `main_app.py`, ejecútalas y describe lo que no pudiste probar a mano.
- Si editas ficheros con un script (heredoc de Python en Bash), cuidado con las barras invertidas:
  `\n` o `\b` pueden acabar como saltos de línea o caracteres de control dentro del código. Prefiere la
  herramienta de edición y compila después (`pytest tests/test_package_smoke.py`).
