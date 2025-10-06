# ExamGenerator

ExamGenerator es una suite de aplicaciones de escritorio construida con Python y Tkinter para automatizar y simplificar el ciclo completo de creación de exámenes. Permite generar preguntas a partir de documentos PDF utilizando la IA de Google Gemini, gestionar un banco centralizado de preguntas y producir exámenes en múltiples formatos.

## Características Principales

-   **Generación de Preguntas con IA**: Utiliza la API de Google Gemini para crear preguntas de opción múltiple a partir de documentos PDF.
-   **Gestión de Bancos de Preguntas**: Importa, fusiona y gestiona preguntas en formato Excel, evitando duplicados.
-   **Creación de Exámenes Personalizados**: Genera múltiples versiones de un examen (ej. Tipo A, Tipo B) con preguntas y respuestas barajadas.
-   **Exportación Múltiple**: Guarda los exámenes en formato `.docx` profesional y en formato XML para auto-corrección en Moodle.
-   **Interfaz Gráfica Intuitiva**: Todas las funcionalidades son accesibles a través de una interfaz de usuario fácil de usar.

## Instalación

### Requisitos Previos

-   **Python 3.8 o superior**. Durante la instalación de Python, asegúrate de marcar la casilla "Add Python to PATH".

### Instalación del Paquete

Puedes instalar ExamGenerator directamente desde PyPI usando pip. Abre tu terminal o línea de comandos y ejecuta:

```bash
pip install examgenerator
```

## Configuración Inicial: La Clave de API

Antes del primer uso, necesitas tu propia clave de API de Google Gemini.

1.  **Obtén tu clave de API** siguiendo las instrucciones oficiales en la [documentación de Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key).
2.  **Configura la clave**. Tienes dos opciones:

    *   **(Recomendado) Usar una Variable de Entorno:** Es el método más seguro. Crea una variable de entorno llamada `GEMINI_API_KEY` con el valor de tu clave. La aplicación la detectará automáticamente al iniciarse.
    *   **(Alternativa) Guardar en la Aplicación:**
        *   Abre la aplicación `examgenerator`.
        *   Ve a la pestaña **"Generar Preguntas"**.
        *   Introduce tu clave en el campo **"Clave API de Gemini"**.
        *   Haz clic en el botón **"Guardar Clave"**. La clave se guardará en un archivo `config.json` local.

## Uso mediante la interfaz

Una vez instalado, puedes lanzar la aplicación desde tu terminal con el siguiente comando:

```bash
examgenerator
```
Se recomienda ejecutar este comando desde la carpeta donde vayas a trabajar (donde tengas tus PDFs y donde quieras que se guarden los archivos generados).

### Flujo de Trabajo Completo

El proceso de uso de la aplicación se divide en tres fases principales, cada una correspondiente a una pestaña de la interfaz.

#### Fase 1: Generar Preguntas (Pestaña "Generar Preguntas")

Aquí es donde se crea el contenido inicial a partir de tus documentos.

1.  **Selecciona un Prompt**: Elige una plantilla de instrucciones para la IA (ej. "PRL") o crea la tuya propia.
2.  **Selecciona los PDFs**: Haz clic en "Seleccionar PDFs" para elegir los documentos que servirán como fuente de conocimiento.
3.  **Configura la Generación**:
    *   Define cuántas **preguntas objetivo** quieres por cada PDF.
    *   (Opcional) Activa el **filtro de duplicados** seleccionando tu banco de preguntas principal para evitar generar preguntas repetidas.
4.  **Carga y Selecciona un Modelo**: Haz clic en **"Cargar Modelos"** y selecciona uno de la tabla (ej. `gemini-1.5-flash`).
5.  **Genera**: Haz clic en **"Generar Preguntas"**. La aplicación creará un archivo `.xlsx` y un `.docx` con las nuevas preguntas, marcadas como "pendiente de revisar".

#### Fase 2: Gestionar el Banco de Preguntas (Pestaña "Gestionar Banco de Preguntas")

Este es el paso de control de calidad y consolidación.

1.  **Revisión Manual (Fuera de la App)**:
    *   Abre el archivo `.docx` generado en la fase anterior.
    *   Corrige los enunciados, las respuestas y, lo más importante, cambia el estado de las preguntas que apruebes de "Pendiente de revisar" a "Aceptable".
    *   Guarda el documento revisado (ej. `preguntas_revisadas.docx`).
2.  **Convertir DOCX a XLSX**:
    *   En la sección "Generar XLSX desde DOCX revisado", selecciona el archivo `.docx` que acabas de corregir.
    *   Dale un nombre al nuevo archivo Excel y haz clic en **"Guardar XLSX Revisado"**.
3.  **Organizar Temas (Opcional pero Recomendado)**:
    *   Abre el nuevo archivo `.xlsx` que acabas de crear.
    *   En la columna "Tema", reemplaza los nombres de archivo por nombres de tema más cortos y descriptivos (ej. "PRL - LPRL").
4.  **Añadir al Banco Principal**:
    *   En la sección "Añadir Preguntas Existentes", selecciona tu **Banco Existente** principal y el **Archivo a Añadir** (el `.xlsx` que acabas de organizar).
    *   Elige añadir **solo las que tienen estado "Aceptable"**.
    *   Haz clic en **"Añadir Preguntas sin Duplicados"** para fusionar las nuevas preguntas validadas en tu banco maestro.

#### Fase 3: Generar Exámenes (Pestaña "Generar Exámenes")

Con un banco de preguntas robusto y validado, ya puedes crear los exámenes finales.

1.  **Selecciona el Banco**: Elige tu archivo `.xlsx` del banco de preguntas principal.
2.  **Define los Datos del Examen**: Rellena los campos de Asignatura, Curso, Nombre del Examen, y el número de versiones que deseas (ej. 2 para un Tipo A y Tipo B).
3.  **Configura la Selección de Preguntas**:
    *   Elige cómo quieres componer el examen: especificando el número de preguntas por cada tema, un número fijo para todos los temas, etc.
    *   Selecciona el **método de selección** (`azar`, `primeras`, `menos usadas`).
4.  **Actualizar Uso (Recomendado)**: Marca la casilla **"Actualizar Archivo Excel con Uso"**. Esto registrará qué preguntas se han usado, lo cual es vital para el método de selección "menos usadas".
5.  **Exportar a Moodle (Opcional)**: Marca la casilla para generar un archivo `.xml` que automatiza la corrección en Moodle.
6.  **Genera**: Haz clic en **"Generar Exámenes"** para producir los documentos `.docx` finales, listos para imprimir, y los archivos `.xml` si se seleccionó.

### Documentación Completa

Para una guía visual y más detallada de cada paso, incluyendo GIFs animados de cada proceso, consulta los **tutoriales completos** en la documentación oficial:
PENDIENTE-DE-REEMPLAZAR
-   [Tutorial Parte 1: Generar Preguntas](URL_A_TU_DOCUMENTACION/tutorial_generar_preguntas.html)
-   [Tutorial Parte 2: Gestionar el Banco de Preguntas](URL_A_TU_DOCUMENTACION/tutorial_gestionar_banco.html)
-   [Tutorial Parte 3: Generar Exámenes](URL_A_TU_DOCUMENTACION/tutorial_generar_examenes.html)

*(Nota: Deberás reemplazar `URL_A_TU_DOCUMENTACION` con el enlace a tu documentación una vez que la publiques, por ejemplo, en GitHub Pages o Read the Docs).*

## Uso Avanzado: Scripting y Automatización

Además de la interfaz gráfica, todos los componentes de ExamGenerator están diseñados para ser utilizados en scripts de Python. Esto te permite automatizar la generación de preguntas, la gestión de bancos y la creación de exámenes, ideal para procesos por lotes o para integrar ExamGenerator en otros sistemas.

A continuación se muestran ejemplos de uso para cada uno de los módulos principales.

### 1. Generar Preguntas con `QuestionGenerator`

Este script utiliza la IA para leer uno o más archivos PDF y generar un banco de preguntas, procesando cada página de forma individual para un análisis exhaustivo.

```python
# archivo: generar_preguntas.py

from examgenerator.question_generator import QuestionGenerator
import os

# --- Configuración ---
# Se recomienda configurar la API Key como una variable de entorno (GEMINI_API_KEY)
# api_key = os.getenv("GEMINI_API_KEY") 

PDF_FILES = ['ruta/a/tu/TEMA_01.pdf', 'ruta/a/tu/TEMA_02.pdf']
OUTPUT_FILENAME = "banco_generado_script"
MODEL_NAME = 'models/gemini-1.5-flash' # O el modelo que prefieras

# --- Lógica del Script ---
if __name__ == '__main__':
    # Asegúrate de pasar la API Key si no usas variables de entorno
    generator = QuestionGenerator(model_name=MODEL_NAME)
    
    print(f"Generando preguntas desde: {PDF_FILES}")
    
    questions_df = generator.generate_multiple_choice_questions(
        pdf_paths=PDF_FILES,
        prompt_type="PRL",
        output_filename=OUTPUT_FILENAME,
        generate_docx=True,
        process_by_pages=True,  # Activar procesamiento por páginas
        num_questions_per_chunk_target=2, # Intentar generar 2 preguntas por página
        pages_per_chunk=1,  # Procesar cada página individualmente
    )

    if questions_df is not None and not questions_df.empty:
        print(f"\n¡Éxito! Se generaron {len(questions_df)} preguntas.")
        print(f"Archivos guardados con el prefijo '{OUTPUT_FILENAME}'.")
```

### 2. Gestionar el Banco de Preguntas con `QuestionBankManager`

#### 2.1. Convertir un DOCX Revisado a XLSX

Este script toma un archivo `.docx` que has revisado manualmente y lo convierte en un archivo `.xlsx` estructurado, listo para ser añadido a tu banco principal.

```python
# archivo: convertir_docx.py

from examgenerator.question_bank_manager import QuestionBankManager
import os

# --- Configuración ---
REVISED_DOCX_PATH = "ruta/a/tus/preguntas_revisadas.docx"
OUTPUT_XLSX_FILENAME = "preguntas_revisadas_desde_script.xlsx"
OUTPUT_DIRECTORY = "bancos_convertidos"

# --- Lógica del Script ---
if __name__ == "__main__":
    manager = QuestionBankManager()
    
    saved_path = manager.generate_excel_from_docx(
        docx_path=REVISED_DOCX_PATH,
        excel_output_filename=OUTPUT_XLSX_FILENAME,
        output_dir=OUTPUT_DIRECTORY
    )

    if saved_path:
        print(f"\n¡Conversión completada! Archivo guardado en: {saved_path}")
```

#### 2.2. Fusionar Bancos de Preguntas (sin duplicados)

Este script añade las preguntas de un archivo Excel a tu banco principal, aplicando filtros para evitar duplicados y para importar solo las preguntas que has marcado como "Aceptable".

```python
# archivo: fusionar_bancos.py

from examgenerator.question_bank_manager import QuestionBankManager
import os

# --- Configuración ---
EXISTING_BANK_PATH = "ruta/a/tu/banco_principal.xlsx"
REVIEWED_QUESTIONS_PATH = "ruta/a/tus/preguntas_a_anadir.xlsx"
FINAL_OUTPUT_PATH = "ruta/a/tu/banco_principal_actualizado.xlsx"

# --- Opciones de Fusión ---
# Criterio estricto: una pregunta es duplicada si el enunciado Y las respuestas son idénticas
DUPLICATE_CRITERIA = ['Pregunta', 'Respuesta A', 'Respuesta B', 'Respuesta C', 'Respuesta D']
ADD_ONLY_ACCEPTABLE = True # Solo añadir preguntas con estado 'Aceptable'

# --- Lógica del Script ---
if __name__ == "__main__":
    manager = QuestionBankManager()

    added_count, updated_df = manager.add_questions_without_duplicates(
        existing_bank_path=EXISTING_BANK_PATH,
        reviewed_questions_path=REVIEWED_QUESTIONS_PATH,
        duplicate_check_columns=DUPLICATE_CRITERIA,
        add_only_acceptable=ADD_ONLY_ACCEPTABLE
    )

    if added_count > 0:
        print(f"\nSe añadieron {added_count} preguntas nuevas.")
        manager.save_dataframe_to_excel(df=updated_df, filepath=FINAL_OUTPUT_PATH)
        print(f"Banco de preguntas actualizado guardado en: {FINAL_OUTPUT_PATH}")
    elif added_count == 0:
        print("\nNo se encontraron preguntas nuevas para añadir.")
```

### 3. Generar Exámenes con `ExamGenerator`

#### 3.1. Crear un Examen Sencillo

Este script genera rápidamente dos versiones de un examen utilizando todas las preguntas disponibles de un banco.

```python
# archivo: crear_examen_simple.py

from examgenerator.exam_generator import ExamGenerator
import os

# --- Configuración ---
BANK_FILE_PATH = "ruta/a/tu/banco_principal.xlsx"
OUTPUT_DIRECTORY = "examenes_generados"

# --- Lógica del Script ---
if __name__ == "__main__":
    exam_gen = ExamGenerator()
    exam_gen.generate_exam_from_excel(
        bank_excel_path=BANK_FILE_PATH,
        output_dir=OUTPUT_DIRECTORY,
        subject="Asignatura de Prueba",
        exam="Parcial 1",
        course="24-25",
        num_exams=2, # Generará 'Tipo 1' y 'Tipo 2'
        selection_method="azar"
    )
    print(f"\nExámenes simples generados en la carpeta: '{OUTPUT_DIRECTORY}'")
```

#### 3.2. Crear un Examen Personalizado y Completo

Este ejemplo muestra el poder de la personalización, definiendo la estructura exacta del examen, los nombres de las versiones, el estilo y las opciones de exportación.

```python
# archivo: crear_examen_personalizado.py

from examgenerator.exam_generator import ExamGenerator
import os

# --- Configuración ---
BANK_FILE_PATH = "ruta/a/tu/banco_principal.xlsx"
OUTPUT_DIRECTORY = "examenes_personalizados"

# Define la estructura: 3 preguntas del Tema 1 y 5 del Tema 5
QUESTIONS_PER_TOPIC_CONFIG = {
    "PRL - LPRL": 3,
    "PRL - RSP": 5
}

# --- Lógica del Script ---
if __name__ == "__main__":
    exam_gen = ExamGenerator()
    
    # Usamos diccionarios para una configuración limpia
    exam_gen.generate_exam_from_excel(
        bank_excel_path=BANK_FILE_PATH,
        output_dir=OUTPUT_DIRECTORY,
        questions_per_topic=QUESTIONS_PER_TOPIC_CONFIG,
        
        # Metadatos
        subject="Prevención de Riesgos Laborales",
        exam="Examen Final",
        course="24-25",
        
        # Selección y versiones
        selection_method="menos usadas",
        exam_names=["Modelo A", "Modelo B"],
        
        # Estilo y exportación
        answer_sheet_instructions="Marque con una 'X' la respuesta correcta.",
        export_moodle_xml=True,
        update_excel=True,
        
        # Opciones para scripting
        check=False, # Desactiva la previsualización interactiva
        verbose=True # Muestra más información de progreso
    )
    print(f"\nExámenes personalizados generados en la carpeta: '{OUTPUT_DIRECTORY}'")
```

## Contribución

Las contribuciones son bienvenidas. Si encuentras un error o tienes una idea para una nueva funcionalidad, por favor, abre un "issue" en el repositorio de GitHub.

## Licencia

Este proyecto está bajo la Licencia Pública General de GNU v3.0 o posterior (GPL-3.0-or-later). Consulta el archivo `LICENSE` para más detalles.