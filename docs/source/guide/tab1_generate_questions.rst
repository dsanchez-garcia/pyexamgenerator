Pestaña 1: Generar Preguntas
============================

Esta es la pestaña principal para la creación de nuevo contenido. Aquí se le indica a la IA qué tipo de preguntas generar y a partir de qué material.

.. image:: _static/tab1_generate_questions_full.png
   :alt: Vista completa de la pestaña Generar Preguntas

Flujo de Trabajo
----------------

1.  **Selecciona un Prompt**: Elige una plantilla de instrucciones para la IA o crea una nueva.
2.  **Selecciona los PDFs**: Elige los documentos que servirán como fuente de conocimiento.
3.  **Configura la Generación**: Ajusta los parámetros como el número de preguntas, el modo de procesamiento y los filtros.
4.  **Define el Directorio de Salida**: Especifica dónde se guardarán los archivos generados.
5.  **Genera**: Inicia el proceso y espera los archivos de salida.

Secciones de la Interfaz
------------------------

Seleccionar/Editar Tipo de Prompt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*   **Tipo de Prompt**: Menú desplegable para seleccionar una plantilla de instrucciones. Define el estilo y las reglas de las preguntas (ej. "PRL" para Prevención de Riesgos Laborales).
*   **Botones de Gestión**:
    *   **Añadir**: Abre una ventana para crear un nuevo tipo de prompt personalizado.
    *   **Editar**: Permite modificar el texto del prompt actualmente seleccionado.
    *   **Eliminar**: Borra un prompt personalizado (los predeterminados no se pueden eliminar).

Seleccionar Archivos PDF
~~~~~~~~~~~~~~~~~~~~~~~~

*   **Campo de Archivos PDF**: Muestra las rutas de los archivos seleccionados.
*   **Botón "Seleccionar PDFs"**: Abre un explorador de archivos para elegir uno o más documentos `.pdf`.

Configuración de Generación
~~~~~~~~~~~~~~~~~~~~~~~~~~~

*   **Preguntas objetivo por PDF/fragmento**: Define cuántas preguntas válidas se desea obtener por cada PDF o fragmento.
*   **Nombre Archivo Salida**: Nombre base que tendrán los archivos generados (ej. `banco_prueba`).
*   **Modo de Procesamiento**:
    *   **Checkbox "Procesar PDF por fragmentos"**: Si se activa, el PDF se divide en partes más pequeñas. Esencial para documentos largos.
    *   **Páginas por fragmento**: Define el tamaño de cada fragmento.
*   **Máx. intentos por fragmento**: Número de veces que la aplicación reintentará la generación si no se alcanza el objetivo.

Filtro de Duplicados
~~~~~~~~~~~~~~~~~~~~

*   **Banco Existente a Consultar**: Selecciona el archivo `.xlsx` del banco principal para evitar generar preguntas repetidas.
*   **Checkbox "Activar filtro de similitud"**: Activa el filtro que compara cada pregunta nueva con las existentes.
*   **Umbral de similitud**: Controla la rigurosidad del filtro (0.0 a 1.0). Un valor más alto requiere que las preguntas sean más parecidas para ser descartadas.

Inclusión de Banco en Prompt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ayuda a la IA a no repetirse mostrándole ejemplos.

*   **Alcance**: Define si se usan como ejemplo preguntas del mismo tema o de todo el banco.
*   **Contenido**: Define si los ejemplos incluyen solo el enunciado o también las respuestas.

Configuración de API y Modelo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*   **Modelo de Gemini**: Permite elegir la versión del modelo de IA. Útil para gestionar cuotas o probar diferentes capacidades.
*   **Clave API de Gemini**: Campo para introducir y guardar tu clave de API.

**Directorio de Salida**
~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: _static/output_dir_gen_questions.png
   :alt: Sección para definir el directorio de salida

Esta sección te permite especificar en qué carpeta se guardarán los archivos generados.

*   **Campo de Directorio**: Puedes pegar una ruta directamente en este campo.
*   **Botón "Seleccionar..."**: Abre un explorador de archivos para que puedas elegir una carpeta de forma visual.
*   **Comportamiento por defecto**: Si dejas este campo en blanco, todos los archivos de salida (el `.xlsx` con las preguntas aceptadas, el `.docx` de revisión y el informe de preguntas descartadas) se guardarán en la misma carpeta desde la que se está ejecutando la aplicación.

**Iniciar la Generación**
~~~~~~~~~~~~~~~~~~~~~~~~~

*   **Botón "Generar Preguntas"**: Una vez configurado todo, este botón inicia el proceso. La barra de estado en la parte inferior de la ventana te informará del progreso.