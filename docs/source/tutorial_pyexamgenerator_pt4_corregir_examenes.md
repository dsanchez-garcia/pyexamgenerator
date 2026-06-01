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

## Flujo de corrección

1. **Matriculados** (`EnrollmentMerger`): fusiona los listados de matrícula.
2. **Identificación de respuestas** (`ImageExamGrader`): OCR de las hojas, detección del tipo de
   examen y nota sobre 10. Genera la **tabla de incidencias** para revisión manual.
3. **Integración de notas OCR en teoría** (`OcrGradeIntegrator`).
4. **Asistencias + justificaciones + cuestionarios** en modo `extremo`
   (`AbsenceJustificationManager`).
5. **Punto extra PIR** (`TheoryBonusApplier`): aplica `+1` (con tope en 10) a quien cumple
   asistencia y cuestionarios.
6. **Reporte por tema** (`TheoryTopicReporter`): notas de cuestionarios por tema y obtención del
   punto extra.

Salidas (3 tablas): incidencias de identificación, cuestionarios + punto extra y calificaciones de
teoría.

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
   digitalizadas.
3. **Asistencia + justificaciones (opcional):** paso aparte; útil cuando la asistencia **no es
   obligatoria** en la asignatura. Solo se usa para cruzar/descartar y no condiciona la corrección.
4. **Integrar notas** (Moodle + OCR).
5. **Punto extra / teoría.**
6. **Nota final ponderada** (ver más abajo).
7. **Sesión:** guardar/cargar para retomar el trabajo.

Se mantiene además un botón **"Pipeline completo"** que ejecuta todos los pasos de una pasada (como
antes). Cada acción corre en segundo plano y deja sus resultados en la carpeta de salida.

## Sesión reanudable (retomar más tarde)

`GradingSession` guarda una sesión en **dos ficheros equivalentes**: `.pkl` (recarga exacta) y
`.json` (legible). Sirve, por ejemplo, para conocer las rutas de los exámenes generados y corregirlos
después sin volver a indicarlas. Al generar exámenes puedes escribir la sesión (campo *"Sesión de
corrección"* de la pestaña Generar Exámenes, o el parámetro `session_output_path`); en la pestaña
Corregir Exámenes, **Cargar sesión** rellena rutas y columnas (incluidos los XML de los exámenes
generados).

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

## Nombres recomendados para Moodle

Para que las columnas del xlsx exportado de Moodle sean reconocibles por el corrector, usa el botón
**"Sugerir nombres Moodle"** (pestaña Generar Exámenes) o `ExamGenerator.suggest_moodle_config(...)`,
que propone el nombre del cuestionario, la categoría y la columna esperada (p. ej.
`Cuestionario:GIM Parcial 1_Tipo 1A (Real)`).

## Identificación manual del resto

Las marcas dudosas y los alumnos no identificados automáticamente (p. ej. un nombre manuscrito
ilegible) aparecen en la **tabla de incidencias**. Para resolverlas de forma asistida, ejecuta el
paso de OCR con `interactive_review=True`: el sistema abre cada imagen y pide confirmar.
