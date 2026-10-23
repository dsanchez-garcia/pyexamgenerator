# Guía de desarrollo

Cómo preparar el entorno, ejecutar los tests, compilar la documentación y publicar versiones.
Pensada para personas y agentes de IA; las reglas obligatorias están en
[`AGENTS.md`](../../AGENTS.md).

## Entorno

Requisitos: Python 3.10+ (desarrollo habitual en 3.14 sobre Windows) y git.

```bash
python -m venv venv
venv/Scripts/python.exe -m pip install --upgrade pip
venv/Scripts/python.exe -m pip install -e ".[dev,docs,grading]"
```

- `-e` instala en modo editable: los cambios en `pyexamgenerator/` se usan sin reinstalar.
- Extras (definidos en `pyproject.toml`): `[dev]` tests y empaquetado (pytest, tox, build, twine),
  `[docs]` Sphinx y `[grading]` el OCR. Sin `[grading]`, el paquete funciona y los tests de OCR se
  saltan.
- En Linux/macOS usa `venv/bin/python`. La GUI necesita Tk (`python3-tk` en Debian/Ubuntu).

## Tests

```bash
venv/Scripts/python.exe -m pytest -q                      # todo
venv/Scripts/python.exe -m pytest tests/test_bank_usage.py -q
venv/Scripts/python.exe -m pytest -q -k "final_grade"     # por nombre
venv/Scripts/python.exe -m tox                            # matriz py310 / py314 (tox.ini)
venv/Scripts/python.exe -m ruff check .                   # lint (reglas en pyproject.toml)
venv/Scripts/python.exe -m ruff format .                  # formato (comillas tal como estén)
venv/Scripts/python.exe -m mypy                           # tipos (módulos en [tool.mypy])
```

La CI también ejecuta `ruff check` (reglas `F` de pyflakes y `B` de bugbear), `ruff format
--check` y `mypy` en modo no estricto sobre los módulos listados en `[tool.mypy]` de `pyproject.toml`
(están todos los del paquete: añade ahí los módulos nuevos). Para revisar y formatear en cada commit:
`venv/Scripts/pre-commit.exe install` (configuración en `.pre-commit-config.yaml`).

El commit que formateó todo el código está en `.git-blame-ignore-revs`: GitHub lo salta en la vista
*blame*; en local, `git config blame.ignoreRevsFile .git-blame-ignore-revs`.

Estado a 2026-10-22: 234 tests pasan en Windows con Python 3.14 y `[grading]` (incluidas las
pruebas de la GUI, que necesitan pantalla). La CI (`.github/workflows/tests.yml`) repite la suite en
Ubuntu (con pantalla virtual `xvfb`) y Windows, con y sin el extra; sin `[grading]` se saltan las
pruebas de OCR. La sección `[tool.pytest.ini_options]` de `pyproject.toml` limita la recogida a
`tests/` y muestra el motivo de cada test saltado.

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

- Read the Docs y el job `sphinx -W` de la CI (Python 3.10) instalan las versiones fijadas en
  `docs/requirements.txt`; el extra `[docs]` solo fija mínimos. Si una actualización de Sphinx o del
  tema introduce avisos, se corrigen al cambiar esas versiones, no por sorpresa en una publicación.
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
   `tests/test_release_metadata.py` falla si alguno no coincide (también con la fecha del
   `CHANGELOG.md`): ejecuta la suite antes de seguir.
3. `dist_build_package.bat` → comprobar `dist/`.
4. `dist_upload_test.bat` (TestPyPI) → instalar y probar en un entorno limpio.
5. `dist_upload.bat` (PyPI), tag `vX.Y.Z`, release en GitHub (Zenodo genera el DOI).

## Scripts de Windows en la raíz

| Script | Qué hace | ¿Seguro para un agente? |
|---|---|---|
| `dist_build_package.bat` | borra `dist/`, `build/`, `*.egg-info` y ejecuta `python -m build` | sí, si se pide |
| `dist_build_docs.bat` | regenera `docs/source/api/` y compila HTML | sí (acaba en `PAUSE`) |
| `dist_upload_test.bat` / `dist_upload.bat` | suben a TestPyPI / PyPI | **no** sin orden explícita |
| `install_current_version.bat` | `pip install` del código actual; `--add-path` añade la carpeta `Scripts` al PATH de usuario con `add_user_path.ps1` | **no** sin orden explícita (`--dry-run` no cambia nada) |
| `sync_branch.bat` | lista y, tras confirmar, borra lo no versionado (`git clean -fd`); checkout + pull | **no** sin orden explícita |

Los scripts terminan con `PAUSE`: en un entorno no interactivo, ejecuta los comandos equivalentes
directamente en lugar del `.bat`.

`add_user_path.ps1` sustituye a `setx Path`, que trunca el PATH a 1.024 caracteres: conserva el
resto del PATH de usuario tal cual (también las entradas con `%USERPROFILE%`) y no toca el del
sistema. Con `-WhatIf` solo informa de lo que haría.

En Linux/macOS no hay equivalentes de los `.bat`: usa los comandos directamente
(`python -m pip install .`, `python -m build`, `python -m twine upload dist/*`…). `pip` indica la
carpeta de los ejecutables si no está en el PATH (habitualmente `~/.local/bin`).
