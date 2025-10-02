Pestaña 3: Generar Exámenes
===========================

Esta es la fase final del proceso. Con un banco de preguntas robusto y validado, esta pestaña te permite diseñar y generar los documentos de examen finales, listos para ser impresos y distribuidos.

.. image:: _static/tab3_generate_exams_full.png
   :alt: Vista completa de la pestaña Generar Exámenes

Flujo de Trabajo
----------------

1.  **Selecciona tu Banco de Preguntas**: Elige el archivo `.xlsx` que contiene todas tus preguntas aceptadas.
2.  **Define los Datos del Examen**: Especifica la asignatura, curso y nombre del examen.
3.  **Configura la Composición**: Decide cuántas preguntas quieres y de qué temas, y cómo deben ser seleccionadas.
4.  **Personaliza el Estilo**: Ajusta los márgenes y el tamaño de la fuente del documento final.
5.  **Elige Opciones de Salida**: Decide si quieres exportar a Moodle, actualizar el contador de uso y dónde guardar los archivos.
6.  **Genera**: Crea los archivos `.docx` del examen.

Secciones de la Interfaz
------------------------

Datos del Examen
~~~~~~~~~~~~~~~~

*   **Archivo Excel de Preguntas**: Elige tu banco de preguntas maestro.
*   **Asignatura, Curso, Nombre del Examen**: Información que aparecerá en la cabecera de los exámenes.
*   **Número de Exámenes a Generar**: Define cuántas versiones diferentes del examen se crearán (ej. 2 para un Tipo A y Tipo B).
*   **Nombres de los Exámenes**: Permite dar nombres específicos a cada versión (ej. `Tipo A,Tipo B`). Si se deja en blanco, se usarán nombres genéricos.

Selección de Preguntas por Tema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Esta sección ofrece una gran flexibilidad para componer tu examen.

*   **Métodos de Selección de Cantidad**:
    1.  **Seleccionar cantidad por tema**: Muestra una lista de todos los temas del Excel y te permite elegir un número específico de preguntas para cada uno.
    2.  **Mismo número de preguntas por tema**: Coge un número fijo de preguntas de todos los temas.
    3.  **Diccionario de preguntas por tema**: Formato de texto para usuarios avanzados (ej. `Tema 1:5,Tema 2:3`).
*   **Método de Selección de Preguntas**: Una vez definida la cantidad por tema, este menú decide *cuáles* preguntas se eligen:
    *   **azar**: Selecciona preguntas aleatoriamente.
    *   **primeras**: Coge las primeras N preguntas que encuentra para ese tema.
    *   **menos usadas**: Selecciona las preguntas que menos veces han aparecido en exámenes anteriores. Requiere que la opción "Actualizar Archivo Excel con Uso" esté activada.

Estilo del Documento
~~~~~~~~~~~~~~~~~~~~

*   **Márgenes y Tamaño de Fuente**: Permite personalizar el diseño del documento `.docx` final para ajustarlo a tus necesidades de impresión.
*   **Instrucciones Hoja de Respuestas**: Campo de texto libre para añadir cualquier instrucción para los alumnos en la hoja de respuestas.

Configuración para Moodle
~~~~~~~~~~~~~~~~~~~~~~~~~

*   **Checkbox "Exportar a Moodle XML"**: Si se marca, además del `.docx`, se genera un archivo `.xml` que se puede importar directamente en el banco de preguntas de Moodle.
*   **Penalización**: Define el porcentaje de penalización por respuesta incorrecta en Moodle.

Actualizar Archivo Excel con Uso
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*   **Checkbox "Actualizar Archivo Excel con Uso"**: **Opción muy recomendada.** Si se marca, después de generar el examen, el archivo Excel original se actualizará. Se añadirá una nueva columna para registrar qué preguntas se han usado en este examen y se recalculará la columna "Veces usada en examen". Esto es esencial para que el método de selección "menos usadas" funcione correctamente en el futuro.

**Directorio de Salida para Exámenes**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: _static/output_dir_generate_exams.png
   :alt: Sección para definir el directorio de salida de los exámenes

Esta sección te permite especificar en qué carpeta se guardarán los archivos de examen generados.

*   **Campo de Directorio**: Puedes pegar una ruta directamente en este campo.
*   **Botón "Seleccionar..."**: Abre un explorador de archivos para que puedas elegir una carpeta de forma visual.
*   **Comportamiento por defecto**: Si dejas este campo en blanco, todos los archivos de examen (`.docx`, `.xlsx` y `.xml`) se guardarán en la misma carpeta donde se encuentra tu banco de preguntas.