# Cómo contribuir a pyexamgenerator

Gracias por tu interés. Esta guía resume lo imprescindible; los detalles están en
[`docs/dev/DEVELOPMENT.md`](docs/dev/DEVELOPMENT.md) (entorno, tests, documentación, publicación) y
en [`AGENTS.md`](AGENTS.md) (reglas del proyecto, también para agentes de IA).

## Informar de un problema

Abre un *issue* en GitHub describiendo qué hiciste, qué esperabas y qué ocurrió (con el mensaje de
error completo: los diálogos de la aplicación tienen un botón **Copiar**).

> **Nunca adjuntes datos reales de alumnos** (nombres, DNI/NIE, correos, notas, escaneos de hojas de
> respuestas) ni tu clave de API. Si necesitas un ejemplo, crea un fichero pequeño con datos
> inventados que reproduzca el problema.

## Proponer cambios

1. Elige una tarea de [`TODO.md`](TODO.md) o abre antes un *issue* para comentarla.
2. Crea una rama desde `master` (`fix/...`, `feat/...`, `docs/...`, `test/...`).
3. Escribe primero un test que reproduzca el problema (con datos sintéticos en `tmp_path`) y después
   el arreglo mínimo.
4. Ejecuta toda la suite: `python -m pytest -q`.
5. Añade una entrada en `CHANGELOG.md`, bajo `## [Unreleased]`, en español.
6. Si la tarea venía de `TODO.md`, márcala y cita su identificador en el commit
   (p. ej. `fix(exam): ... (BUG-3)`).
7. Abre un *pull request* contra `master` rellenando la plantilla.

## Estilo

- Textos para el usuario (GUI, mensajes, documentación), en español; identificadores y docstrings,
  preferentemente en inglés, siguiendo el código que rodea al cambio.
- No renombres columnas de los Excel (`Pregunta`, `Respuesta A`, `Número de ID`…): son el formato de
  los bancos y de las exportaciones de Moodle que ya usan los docentes.
- No reformatees ficheros completos: limita el diff a lo que cambias.

## Licencia

Al contribuir aceptas que tu aportación se publique bajo la licencia del proyecto,
GPL-3.0-or-later.
