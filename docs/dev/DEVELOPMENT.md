# Guía de desarrollo

Cómo preparar el entorno, ejecutar los tests, compilar la documentación y publicar versiones.
Pensada para personas y agentes de IA; las reglas obligatorias están en
[`AGENTS.md`](../../AGENTS.md).

## Entorno

Requisitos: Python 3.10+ (desarrollo habitual en 3.14 sobre Windows) y git.

```bash
python -m venv venv
venv/Scripts/python.exe -m pip install --upgrade pip
venv/Scripts/python.exe -m pip install -e ".[grading]"
venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

- `-e` instala en modo editable: los cambios en `pyexamgenerator/` se usan sin reinstalar.
- El extra `[grading]` instala el OCR. Sin él, el paquete funciona y los tests de OCR se saltan.
- En Linux/macOS usa `venv/bin/python`. La GUI necesita Tk (`python3-tk` en Debian/Ubuntu).

## Tests

```bash
venv/Scripts/python.exe -m pytest -q                      # todo
venv/Scripts/python.exe -m pytest tests/test_v030_features.py -q
venv/Scripts/python.exe -m pytest -q -k "final_grade"     # por nombre
venv/Scripts/python.exe -m tox                            # matriz py310 / py314 (tox.ini)
```

Estado a 2026-10-22: 169 tests pasan en Windows con Python 3.14 y `[grading]` (incluidas las
pruebas de la GUI, que necesitan pantalla). La CI (`.github/workflows/tests.yml`) repite la suite en
Ubuntu (con pantalla virtual `xvfb`) y Windows, con y sin el extra; sin `[grading]` se saltan las
pruebas de OCR. `pytest.ini` limita la recogida a `tests/` y muestra el motivo de cada test saltado.

Convenciones para tests nuevos:

- pytest con funciones simples (sin clases), un fichero por área.
- Datos sintéticos creados en `tmp_path` con pandas/python-docx; nunca datos reales de alumnos.
- Sin red: `tests/conftest.py` sustituye `google.genai.Client` en todos los tests por un cliente que
  falla si se le pide algo. Para simular respuestas de Gemini, asigna tu propio cliente falso a
  `generator.client` (ver `tests/test_question_generator_flow.py`).
- Tests de OCR: `pytest.importorskip("cv2")` o comprobar `grading.HAS_OCR`.
- Barajados: fija `random.seed(...)`.
- Para bugs: el test debe fallar antes del arreglo y pasar después.

## Documentación (Sphinx / Read the Docs)

- Fuentes en `docs/source/` (MyST Markdown para tutoriales, reStructuredText para índices y API).
- La API se genera con `sphinx-apidoc` (`dist_build_docs.bat` regenera `docs/source/api/`).
- Read the Docs usa `.readthedocs.yaml` con `fail_on_warning: true`: cualquier aviso rompe la
  publicación. Compila localmente con avisos como errores antes de proponer cambios en la doc:

```bash
venv/Scripts/python.exe -m sphinx -W -b html docs/source docs/build/html
```

- Las imágenes/GIF de los tutoriales están en `docs/source/_static/gifs/`.
- `docs/dev/` (esta carpeta) queda fuera de Sphinx a propósito.

## Flujo de trabajo con tareas

1. Elige una tarea de [`TODO.md`](../../TODO.md) (respeta el «Orden de trabajo sugerido» salvo
   indicación del mantenedor).
2. Crea una rama desde `master`: `fix/bug-1-cache-banco`, `feat/...`, `docs/...`, `test/...`.
3. Escribe primero el test que reproduce el problema; después el arreglo mínimo.
4. Ejecuta toda la suite.
5. Actualiza `CHANGELOG.md` (`## [Unreleased]`) y, si procede, README/tutoriales.
6. Marca la casilla en `TODO.md` con el identificador.
7. Commit con *Conventional Commits* (`fix(exam): re-leer el banco en cada generación (BUG-1)`).
8. PR contra `master` con: qué cambia, por qué, cómo se ha probado y qué no se ha podido probar
   (p. ej. la GUI).

Una tarea por PR. Las refactorizaciones grandes (`ARC-1`, `ARC-5`) se hacen en pasos pequeños que
mantengan los tests en verde, sin mezclar cambios funcionales.

## Publicar una versión (solo el mantenedor)

1. Mover las entradas de `## [Unreleased]` a `## [X.Y.Z] - AAAA-MM-DD` en `CHANGELOG.md`.
2. Actualizar la versión en `pyexamgenerator/__init__.py`, `CITATION.cff` (`version`,
   `date-released`) y `.zenodo.json` (`version`, `publication_date`, URL del tag).
3. `dist_build_package.bat` → comprobar `dist/`.
4. `dist_upload_test.bat` (TestPyPI) → instalar y probar en un entorno limpio.
5. `dist_upload.bat` (PyPI), tag `vX.Y.Z`, release en GitHub (Zenodo genera el DOI).

## Scripts de Windows en la raíz

| Script | Qué hace | ¿Seguro para un agente? |
|---|---|---|
| `dist_build_package.bat` | borra `dist/`, `build/`, `*.egg-info` y ejecuta `python -m build` | sí, si se pide |
| `dist_build_docs.bat` | regenera `docs/source/api/` y compila HTML | sí (acaba en `PAUSE`) |
| `dist_upload_test.bat` / `dist_upload.bat` | suben a TestPyPI / PyPI | **no** sin orden explícita |
| `install_current_version.bat` | `pip install` del código actual; `--add-path` modifica el PATH | **no** sin orden explícita |
| `sync_branch.bat` | lista y, tras confirmar, borra lo no versionado (`git clean -fd`); checkout + pull | **no** sin orden explícita |

Los scripts terminan con `PAUSE`: en un entorno no interactivo, ejecuta los comandos equivalentes
directamente en lugar del `.bat`.
