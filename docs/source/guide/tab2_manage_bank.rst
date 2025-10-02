Pestaña 2: Gestionar Banco de Preguntas
========================================

Esta pestaña es el puente entre las preguntas recién generadas y revisadas, y el banco de preguntas principal. Su propósito es consolidar y mantener la calidad del banco de preguntas a lo largo del tiempo.

.. image:: _static/tab2_manage_bank_full.png
   :alt: Vista completa de la pestaña Gestionar Banco de Preguntas

Flujo de Trabajo
----------------

1.  **Revisión Manual (Fuera de la App)**: Después de generar preguntas en la Pestaña 1, abre el archivo `.docx` resultante (ej. `banco_prueba_pendiente_de_revisar.docx`). Corrige cualquier error en los enunciados, las opciones, la respuesta correcta y, muy importante, cambia el **Estado** de "Pendiente de revisar" a "Aceptable" en las preguntas que consideres válidas.
2.  **Convertir DOCX a XLSX**: Usa la primera sección de esta pestaña para convertir tu `.docx` ya corregido a un formato `.xlsx` estructurado, especificando dónde quieres guardarlo.
3.  **Añadir al Banco Principal**: Usa la segunda sección para fusionar las preguntas del `.xlsx` recién creado con tu banco de preguntas maestro, evitando duplicados.

Secciones de la Interfaz
------------------------

Generar XLSX desde DOCX Revisado
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: _static/output_dir_manage_bank.png
   :alt: Sección para generar XLSX desde DOCX

Esta sección se utiliza para procesar el documento que has validado manualmente.

*   **Archivo DOCX Revisado**: Haz clic en "Seleccionar DOCX" para elegir el archivo `.docx` que has corregido.
*   **Directorio de Salida (XLSX)**: Especifica la carpeta donde se guardará el nuevo archivo Excel. Si se deja en blanco, se usará la misma carpeta donde se encuentra el archivo DOCX de entrada.
*   **Nombre del Nuevo Archivo XLSX**: Especifica un nombre para el archivo Excel que se creará. Si lo dejas en blanco, se usará el mismo nombre que el del archivo DOCX.
*   **Botón "Guardar XLSX Revisado"**: Inicia la conversión del documento de Word a una tabla de Excel estructurada.

Añadir Preguntas Existentes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Esta es la función principal para hacer crecer tu banco de preguntas.

*   **Banco Existente**: Selecciona el archivo `.xlsx` que funciona como tu banco de preguntas maestro.
*   **Archivo a Añadir**: Selecciona el archivo `.xlsx` que contiene las nuevas preguntas que deseas importar (normalmente, el que generaste en el paso anterior).
*   **Criterio de Duplicado**: Define cómo de estricta será la comprobación para evitar añadir preguntas repetidas:
    *   **Pregunta Única (ignorar respuestas)**: Una pregunta se considera duplicada si su enunciado ya existe en el banco, sin importar si las respuestas son diferentes.
    *   **Pregunta y Respuestas Iguales**: Una pregunta solo se considera duplicada si tanto el enunciado como todas sus opciones de respuesta coinciden exactamente con una ya existente.
*   **Filtro de Estado**: Permite controlar qué preguntas del archivo de origen se importarán:
    *   **Añadir todas las preguntas**: Se intentarán añadir todas las preguntas, sin importar su estado.
    *   **Añadir solo con estado 'Aceptable'**: Opción recomendada. Solo se importarán las preguntas que hayas marcado como "Aceptable" durante tu revisión manual.
*   **Botón "Añadir Preguntas sin Duplicados"**: Inicia el proceso de fusión. La aplicación comparará cada pregunta del "Archivo a Añadir" con el "Banco Existente" y solo añadirá las que no sean duplicadas, según los criterios que hayas establecido.