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

La aplicación incluye la pestaña **Corregir Exámenes**: selecciona los archivos de entrada
(matriculados, plantillas XML, imágenes, notas de teoría, asistencias, horario, justificaciones,
cuestionarios) y una carpeta de salida, y pulsa **Corregir**. El proceso se ejecuta en segundo
plano y genera las 3 tablas en la carpeta indicada.

## Identificación manual del resto

Las marcas dudosas y los alumnos no identificados automáticamente (p. ej. un nombre manuscrito
ilegible) aparecen en la **tabla de incidencias**. Para resolverlas de forma asistida, ejecuta el
paso de OCR con `interactive_review=True`: el sistema abre cada imagen y pide confirmar.
