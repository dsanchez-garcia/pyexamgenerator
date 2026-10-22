# Parte 4: Corregir Exámenes (subpaquete `grading`)

El subpaquete `pyexamgenerator.grading` corrige exámenes de teoría y cierra el ciclo
**generar → corregir**: usa como plantilla de respuestas correctas el mismo **Moodle XML** que
produce el generador (`ExamGenerator.generate_moodle_xml`).

## Instalación del extra de OCR

La corrección de hojas **manuscritas** usa OCR (dependencia pesada y opcional):

```bash
pip install pyexamgenerator[grading]
```

Según la versión de Python se instala el backend adecuado automáticamente: `rapidocr` en
Python ≥ 3.13 (incl. 3.14) o `rapidocr-onnxruntime` en versiones anteriores. Sin el extra, todo lo
que **no** es OCR sigue funcionando y `pyexamgenerator.grading.HAS_OCR` vale `False`.

## Cómo funciona el módulo, en pocas palabras

El módulo `grading` parte de una idea sencilla: **un examen es una tabla de alumnos con valores**
(sus respuestas, sus notas, sus asistencias). Todo lo demás consiste en construir esa tabla, cruzarla
con otras y dejarla en la forma que Moodle espera.

El **hilo conductor** es la matrícula. Primero se fusionan los listados de los distintos grupos
(`EnrollmentMerger`) en un único *roster* que actúa de "fuente de la verdad": de él salen el nombre
oficial, el número de ID y el correo de cada alumno, y a él se reconducen todas las notas. Cuando una
hoja manuscrita o un correo no traen el ID, el sistema empareja por nombre; por eso es importante
que la matrícula esté completa. Un **correo de justificación** o una fila de un **xlsx de
respuestas** solo se asignan si coinciden con seguridad: por la dirección de correo, por el **mismo
nombre** en cualquier orden y sin importar tildes ni mayúsculas («GARCÍA LÓPEZ, MARÍA»), o con el
**único alumno** que contiene todas sus palabras («María García» si no hay otra María García). Un
nombre solo *parecido* no se asigna, porque el parecido no distingue una errata de otra persona
(«Mario» y «María»): queda para revisar, con el alumno más parecido como candidato. Las hojas
manuscritas del OCR sí se emparejan por aproximación, porque el nombre está escrito a mano; si no
encuentra al alumno, la hoja sale en la tabla de incidencias (`MISSING_ID`).

A partir de ahí, **las notas pueden entrar por dos caminos**. Si tienes las hojas en papel, el OCR
(`ImageExamGrader`) lee las marcas, detecta el **tipo de examen** (1A, 1B…) usando como plantilla de
respuestas correctas el **mismo Moodle XML** que generó el propio programa, y produce una nota sobre
10 más una **tabla de incidencias** con lo que no pudo resolver solo. Si las respuestas ya están
digitalizadas (por ejemplo en un cuestionario de Moodle), se corrige directamente desde ese xlsx
(`ExamGrader`). En ambos casos el resultado es la misma columna de calificación.

Esas notas se **integran** sobre el libro de calificaciones de teoría (`OcrGradeIntegrator`):
cada alumno se localiza por ID o por nombre y su nota aterriza en la columna del cuestionario que le
corresponde según su grupo y tipo de examen. El objetivo es que, al final, el profesor tenga un único
xlsx con las columnas en el sitio donde Moodle las espera.

La **asistencia y el punto extra** son una capa **aparte y opcional** (ver siguiente apartado). Y
como todas las piezas trabajan sobre tablas de alumnos, cualquier resultado se puede **comparar con
una versión anterior y sobrescribir** (apartado *Comparar y sobrescribir resultados*).

Cada clase guarda sus *inputs* y *outputs* como atributos, y la fachada `ExamCorrectionAPI` orquesta
los pasos y puede dejar constancia de todo en una **sesión reanudable** (`GradingSession`).

### Corregir sin contar la asistencia

La corrección del examen y el cómputo de la asistencia son **independientes**. La nota del examen sale
de las respuestas (OCR o xlsx) y de la plantilla XML; **no necesita** ni asistencias, ni horario, ni
justificaciones. Esos ficheros solo intervienen en el **punto extra** (`AbsenceJustificationManager` +
`TheoryBonusApplier`), que es una bonificación opcional.

Por tanto, si en tu asignatura la asistencia **no es obligatoria** (o simplemente no quieres contarla),
basta con ejecutar los pasos de **corregir** e **integrar** y omitir el de asistencia:

- **En la interfaz:** usa solo las secciones *"1. Corregir examen(es)"* y *"3. Integrar notas"*. Deja
  la sección *"2. Asistencia + justificaciones"* sin tocar. La nota final no depende de ella.
- **En scripting:** llama únicamente a `grade_from_images` (o `grade_from_excel`) y, si lo necesitas,
  a `integrate_ocr_grades`; no llames a `process_absence_justifications` ni a `apply_theory_bonus`.

```python
from pyexamgenerator.grading import ExamCorrectionAPI, ImageGradingConfig

api = ExamCorrectionAPI(default_output_dir="salida")
# Solo corrección: ni asistencia, ni horario, ni justificaciones.
api.grade_from_images(ImageGradingConfig(
    xml_paths=["examen_1A.xml", "examen_1B.xml"],
    image_paths=["hoja1.jpg", "hoja2.jpg"],
    enrollment_path="matriculados.xlsx",
    output_grades="calificaciones.xlsx",
))
```

Con `default_output_dir`, los nombres de salida relativos (como `calificaciones.xlsx`) se guardan en
esa carpeta; si indicas una ruta absoluta, se respeta.

Si más adelante decides **sí** contar la asistencia, ejecuta ese paso por separado y cruza el
resultado con las notas; al estar desacoplado, puedes incorporarlo o descartarlo sin rehacer la
corrección.

## Flujo de corrección

1. **Matriculados** (`EnrollmentMerger`): fusiona los listados de matrícula.
2. **Identificación de respuestas** (`ImageExamGrader`): OCR de las hojas, detección del tipo de
   examen y nota sobre 10. Genera la **tabla de incidencias** para revisión manual.
3. **Integración de notas OCR en teoría** (`OcrGradeIntegrator`). Si la nota de una hoja sustituye
   a una nota distinta que el alumno ya tenía (por ejemplo, porque también hizo el cuestionario en
   Moodle, o porque la hoja es de otra persona), se aplica igualmente y queda la incidencia
   `OVERWRITTEN_GRADE` en `incidencias_integracion_ocr.xlsx` para que la revises.
4. **Asistencias + justificaciones + cuestionarios** en modo `extremo`
   (`AbsenceJustificationManager`).
5. **Punto extra PIR** (`TheoryBonusApplier`): aplica `+1` (con tope en 10) a quien cumple
   asistencia y cuestionarios. Ambas reglas se pueden cambiar en scripts: los puntos con
   `bonus_points` y la nota mínima de los cuestionarios en cada tema (7,5) con `min_quiz_grade`
   (en `TheoryBonusConfig`, `AbsenceJustificationConfig` o `FullPipelineConfig`).
6. **Reporte por tema** (`TheoryTopicReporter`): notas de cuestionarios por tema y obtención del
   punto extra.

Salidas (3 tablas): incidencias de identificación, cuestionarios + punto extra y calificaciones de
teoría (más `incidencias_integracion_ocr.xlsx` si la integración tiene incidencias). Los ficheros
intermedios van a la carpeta `_intermedios`, que se borra al terminar, también si hay un error.

Todo este flujo está disponible en una sola llamada (es lo que ejecuta el botón *"Pipeline
completo"* de la interfaz):

```python
from pyexamgenerator.grading import ExamCorrectionAPI, FullPipelineConfig

api = ExamCorrectionAPI()
teoria = api.run_full_pipeline(
    FullPipelineConfig(
        enrollment_paths=["GIM.xlsx", "GITI-GIE-GIEI.xlsx"],
        xml_paths=["examen_1A.xml", "examen_1B.xml"],
        image_paths=["hoja1.jpg", "hoja2.jpg"],
        theory_xlsx_path="teoria_moodle.xlsx",
        attendance_xlsx_path="asistencias.xlsx",
        schedule_xlsx_path="horario.xlsx",
        justifications_xlsx_path="justificaciones.xlsx",
        quizzes_xlsx_path="cuestionarios.xlsx",
        output_dir="salida",
    ),
    progress_callback=print,  # opcional: avisa al empezar cada paso
)
print(api.results["full_pipeline_outputs"])  # rutas de las tablas generadas
```

## Uso como librería

```python
from pyexamgenerator.grading import (
    EnrollmentMerger, ImageExamGrader, OcrGradeIntegrator,
    AbsenceJustificationManager, TheoryBonusApplier, TheoryTopicReporter,
)

# 1. Matriculados
merger = EnrollmentMerger(["GIM.xlsx", "GITI-GIE-GIEI.xlsx"])
merger.export("matriculados.xlsx")

# 2. OCR de hojas manuscritas
grader = ImageExamGrader(xml_paths=["examen_1A.xml", "examen_1B.xml"],
                         enrollment_path="matriculados.xlsx", aggressive_recovery=True)
answers, grades, audit = grader.grade_from_images(
    image_paths=["hoja1.jpg", "hoja2.jpg"],
    output_answers="respuestas.xlsx", output_grades="notas_ocr.xlsx",
    output_incidents="incidencias.xlsx", prompt_missing_type=False,
)

# 3..6. Integración, asistencias, punto extra y reporte (ver ejemplo completo).
```

Cada clase guarda sus *inputs* y *outputs* como atributos (p. ej. `merger.merged_df`,
`grader.enrollment_df`, `bonus.grade_columns`) para inspeccionarlos o reutilizarlos.

## Uso desde la interfaz gráfica

La pestaña **Corregir Exámenes** está dividida en **secciones independientes**, cada una con su
propio botón, para que ejecutes solo el paso que necesites:

1. **Datos comunes** y **Mapeo de columnas:** matriculados, plantillas XML, carpeta de salida y los
   nombres de columna de tus xlsx (Nº de ID, Nombre, Apellidos, Correo, Nota total, y Remitente /
   Asunto / Mensaje de las justificaciones). Si tus ficheros usan otros nombres, indícalos aquí.
2. **Corregir examen(es):** desde **imágenes** (OCR) o desde un xlsx de **respuestas** ya
   digitalizadas. En el segundo caso, las filas cuyo nombre no coincide con un único alumno no se
   corrigen y, junto con dos filas del mismo alumno, aparecen en
   `incidencias_correccion_respuestas.xlsx` con el alumno más parecido; la aplicación lo avisa.
3. **Asistencia + justificaciones (opcional):** paso aparte; útil cuando la asistencia **no es
   obligatoria** en la asignatura. Solo se usa para cruzar/descartar y no condiciona la corrección.
4. **Integrar notas** (Moodle + OCR).
5. **Punto extra / teoría.**
6. **Nota final ponderada** (ver más abajo).
7. **Comparar / sobrescribir resultados** (ver más abajo).
8. **Sesión:** guardar/cargar para retomar el trabajo.

Se mantiene además un botón **"Pipeline completo"** que ejecuta todos los pasos de una pasada (como
antes; usa `ExamCorrectionAPI.run_full_pipeline`). Cada acción corre en segundo plano y deja sus
resultados en la carpeta de salida; solo se ejecuta una tarea de corrección a la vez.

## Sesión reanudable (retomar más tarde)

`GradingSession` guarda una sesión en **dos ficheros equivalentes**: `.pkl` (recarga exacta) y
`.json` (legible). Sirve, por ejemplo, para conocer las rutas de los exámenes generados y corregirlos
después sin volver a indicarlas. Al generar exámenes puedes escribir la sesión (campo *"Sesión de
corrección"* de la pestaña Generar Exámenes, o el parámetro `session_output_path`); en la pestaña
Corregir Exámenes, **Cargar sesión** rellena rutas y columnas (incluidos los XML de los exámenes
generados).

Al cargar, siempre se usa el `.json`. Abrir un `.pkl` puede ejecutar código, así que solo se lee si
no existe el `.json` y lo autorizas expresamente (en la GUI, confirmando el aviso; en scripts, con
`GradingSession.load(ruta, allow_pickle=True)`). Hazlo únicamente con sesiones creadas por ti, nunca
con ficheros recibidos de terceros.

```python
from pyexamgenerator.grading import GradingSession

session = GradingSession.load("sesion_correccion.json")
print(session.generated_xml_paths())        # rutas de los XML generados
print(session.grading_inputs)               # entradas y mapeo de columnas
```

## Nota final ponderada (varios exámenes)

`FinalGradeCalculator` (o `ExamCorrectionAPI.compute_final_grade`) combina varios exámenes con los
pesos que definas. Dos modos: **por fichero** (un peso por examen, emparejando alumnos por ID o
nombre) y **por columnas** (ponderar columnas de un único xlsx). Los pesos se normalizan y la nota
final puede topar en 10.

```python
from pyexamgenerator.grading import ExamCorrectionAPI, FinalGradeConfig

api = ExamCorrectionAPI(default_output_dir="salida")
api.compute_final_grade(FinalGradeConfig(
    mode="by_file",
    sources=[
        {"path": "teoria.xlsx", "label": "Teoría", "weight": 0.6},
        {"path": "practicas.xlsx", "label": "Prácticas", "weight": 0.4},
    ],
    output_path="calificaciones_finales_ponderadas.xlsx",
    cap_to_10=True,
))
```

## Comparar y sobrescribir resultados

Cuando ya tienes unas calificaciones (o unas asistencias) y vuelves a generarlas —por una corrección
posterior, una incidencia resuelta, una nota revisada—, conviene saber **qué ha cambiado** respecto a
la versión anterior antes de pisarla. `ResultComparator` (o `ExamCorrectionAPI.compare_results`) hace
justo eso: empareja a los alumnos por **ID** (o por nombre si no hay ID) y produce un informe con las
**celdas que cambian**, los alumnos que **solo están en la versión nueva** y los que **solo están en la
anterior**. Como ambos —calificaciones y asistencias— son tablas de alumnos, sirve para los dos.

Opcionalmente combina las dos versiones **sobrescribiendo** con los valores nuevos: actualiza las
celdas de los alumnos coincidentes, conserva los que solo estaban antes y (si quieres) añade los
nuevos. Puedes escribir el resultado en un fichero aparte o **reemplazar el fichero existente** en su
sitio.

- **En la interfaz:** sección *"6. Comparar / sobrescribir resultados"*: elige el fichero existente y
  el nuevo, opcionalmente las columnas a comparar (vacío = todas las comunes), y pulsa
  **"Comparar (solo informe)"** o **"Comparar y combinar (sobrescribir)"**. La casilla *"Reemplazar el
  fichero existente"* escribe el resultado combinado sobre el fichero anterior (pide confirmación).
- **En scripting:**

```python
from pyexamgenerator.grading import ExamCorrectionAPI, ComparisonConfig

api = ExamCorrectionAPI(default_output_dir="salida")
result = api.compare_results(ComparisonConfig(
    existing_path="calificaciones_anteriores.xlsx",
    new_path="calificaciones_nuevas.xlsx",
    value_cols=[],          # vacío = todas las columnas comunes (no identificativas)
    overwrite=True,         # genera la tabla combinada (nuevo sobre anterior)
    add_new_rows=True,      # añade alumnos que solo aparecen en la nueva
    merged_in_place=False,  # True = reemplaza el fichero existente
))
print(result.summary)       # {'changed_cells': ..., 'added': ..., 'removed': ..., ...}
print(result.changes_df)    # detalle: Columna, Valor_Anterior, Valor_Nuevo por alumno
```

## Patrón del correo de justificación

Si las justificaciones siguen esta plantilla, el corrector extrae los campos y los vuelca en columnas
(`Justif_Fecha`, `Justif_Tema_Practica`, `Justif_Grupo`, `Justif_Subgrupo_Practicas`, `Justif_Motivo`),
tomándolos como **autoritativos** sobre la heurística de texto:

```
Día de la falta (formato mm/dd/aaaa):
Nº Tema/Práctica a la que se ha faltado:
Grupo (GIM o GITI-GIE-GIEI):
Grupo de prácticas (MC1, etc):
Motivo de la ausencia:
```

La fecha se interpreta como `mm/dd/aaaa` (se tolera `dd/mm/aaaa` cuando el primer número es > 12).

### Qué correos justifican faltas

En el modo `extremo` (el que usan la aplicación y el pipeline completo), un correo asignado a un
alumno justifica **todas** sus faltas, salvo que su texto no parezca una justificación: una consulta,
una duda sobre el examen o un agradecimiento (`Mensaje_Clasificacion = no_justifica`) no justifican
nada. En el modo `normal` se aplica la misma regla, pero solo a las faltas claras.

`justificaciones_resumen.xlsx` tiene tres columnas para revisarlo:

- `Revisar = si`: el correo no se ha asignado a ningún alumno (el remitente no coincide con la
  matrícula o encaja con varios alumnos). `Candidato_Mas_Parecido` indica el alumno más parecido.
  Si es él, corrige el remitente en el Excel de justificaciones (nombre completo o su correo de la
  matrícula) y vuelve a ejecutar.
- `Cuenta_Para_Justificar`: `si` si el correo justifica faltas; `no` si no está asignado o no parece
  una justificación.

La aplicación avisa al terminar si hay correos sin asignar o que no cuentan.

## Nombres recomendados para Moodle

Para que las columnas del xlsx exportado de Moodle sean reconocibles por el corrector, usa el botón
**"Sugerir nombres Moodle"** (pestaña Generar Exámenes) o `ExamGenerator.suggest_moodle_config(...)`,
que propone el nombre del cuestionario, la categoría y la columna esperada (p. ej.
`Cuestionario:GIM Parcial 1_Tipo 1A (Real)`).

## Identificación manual del resto

Las marcas dudosas y los alumnos no identificados automáticamente (p. ej. un nombre manuscrito
ilegible) aparecen en la **tabla de incidencias**. Para resolverlas de forma asistida, ejecuta el
paso de OCR con `interactive_review=True`: el sistema abre cada imagen y pide confirmar.
