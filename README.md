# pyexamgenerator

[![DOI](https://zenodo.org/badge/1068439434.svg)](https://doi.org/10.5281/zenodo.17337856)
[![alt text](https://img.shields.io/readthedocs/pyexamgenerator/latest)](https://pyexamgenerator.readthedocs.io/es/latest/)

pyexamgenerator es una suite de aplicaciones de escritorio construida con Python y Tkinter para automatizar y simplificar el ciclo completo de los exámenes: generar preguntas a partir de documentos PDF con IA (Google Gemini, ChatGPT o Claude, con o sin clave de API), gestionar bancos centralizados, producir exámenes en múltiples formatos y corregirlos.

## Características Principales

-   **Generación de Preguntas con IA**: Crea preguntas de opción múltiple a partir de documentos PDF (o imágenes) usando la API de Google Gemini, la de OpenAI (modelos de ChatGPT) o la de Anthropic (modelos de Claude). El material se puede enviar como texto extraído, como imágenes de las páginas o como el propio PDF.
-   **Generación sin API**: Si no tienes clave de API, la aplicación prepara los prompts para que los pegues en Google AI Studio, ChatGPT o Claude desde el navegador y convierte las respuestas que copies en los mismos archivos de revisión.
-   **Gestión de Bancos de Preguntas**: Importa, fusiona y gestiona preguntas en formato Excel, evitando duplicados.
-   **Creación de Exámenes Personalizados**: Genera múltiples versiones de un examen (ej. Tipo A, Tipo B) con preguntas y respuestas barajadas.
-   **Exportación Múltiple**: Guarda los exámenes en formato `.docx` profesional y en formato XML para auto-corrección en Moodle.
-   **Corrección de Exámenes** (subpaquete `grading`): Cierra el ciclo *generar → corregir*. OCR de hojas de respuestas manuscritas, integración de notas, asistencias + justificaciones + cuestionarios y punto extra PIR. El OCR es un extra opcional: `pip install pyexamgenerator[grading]`.
-   **Interfaz Gráfica Intuitiva**: Todas las funcionalidades son accesibles a través de una interfaz de usuario fácil de usar.

## Instalación

### Requisitos Previos

-   **Python 3.9 o superior**. Durante la instalación de Python, asegúrate de marcar la casilla "Add Python to PATH".

### Instalación del Paquete

Puedes instalar pyexamgenerator directamente desde PyPI usando pip. Abre tu terminal o línea de comandos y ejecuta:

```bash
pip install pyexamgenerator
```

Esta instalación incluye todo lo necesario para generar preguntas con la API de Google Gemini y para el flujo sin API. Si quieres usar la API de OpenAI o la de Anthropic, instala además su librería con el extra correspondiente:

```bash
pip install pyexamgenerator[openai]     # API de OpenAI (modelos de ChatGPT)
pip install pyexamgenerator[anthropic]  # API de Anthropic (modelos de Claude)
pip install pyexamgenerator[ia]         # ambas
```

> En algunas terminales (por ejemplo, zsh en macOS) hay que poner el paquete entre comillas: `pip install "pyexamgenerator[ia]"`.

## Configuración Inicial: La Clave de API

La clave de API solo es necesaria para generar preguntas **con API**. Si prefieres no usarla, puedes trabajar **sin API**, copiando los prompts en Google AI Studio, ChatGPT o Claude desde el navegador (ver la Fase 1 más abajo).

1.  **Obtén tu clave de API** del proveedor que vayas a usar:

    | Proveedor | Dónde se crea la clave | Variable de entorno |
    | --- | --- | --- |
    | Google Gemini | [Google AI Studio](https://aistudio.google.com/app/apikey) (tiene un nivel gratuito con límites; consulta la [documentación de Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key)) | `GEMINI_API_KEY` (o `GOOGLE_API_KEY`) |
    | OpenAI (ChatGPT) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` |
    | Anthropic (Claude) | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) | `ANTHROPIC_API_KEY` |

    Ten en cuenta que el uso de la API de OpenAI y de la de Anthropic se factura aparte de las suscripciones de ChatGPT o de Claude.

2.  **Configura la clave**. Tienes dos opciones:

    *   **(Recomendado) Usar una Variable de Entorno:** Es el método más seguro. Crea la variable de entorno de tu proveedor (tabla anterior) con el valor de tu clave. La aplicación la detectará automáticamente al iniciarse y, si también hay una clave guardada con **"Guardar Clave"**, la variable de entorno tiene prioridad.
    *   **(Alternativa) Guardar en la Aplicación:**
        *   Abre la aplicación `pyexamgenerator`.
        *   Ve a la pestaña **"Generar Preguntas"**, sección **"Proveedor de IA, Clave API y Modelo"**.
        *   Elige el **"Proveedor"** e introduce tu clave en el campo **"Clave API"** (el botón **"Obtener clave..."** abre la página del proveedor donde se crean las claves).
        *   Haz clic en el botón **"Guardar Clave"**. La clave del proveedor seleccionado (junto con el modelo elegido) se guardará en el archivo `config.json` de tu carpeta de configuración de usuario, que es la misma sea cual sea la carpeta desde la que abras la aplicación:
            *   Windows: `%APPDATA%\pyexamgenerator\config.json` (normalmente `C:\Users\<usuario>\AppData\Roaming\pyexamgenerator\config.json`).
            *   macOS y Linux: `~/.config/pyexamgenerator/config.json`.
        *   La clave se guarda sin cifrar; donde el sistema lo permite, el archivo solo es accesible para tu usuario. No lo compartas ni lo copies a carpetas compartidas o sincronizadas en la nube.
        *   Las versiones anteriores guardaban `config.json` en la carpeta desde la que se ejecutaba la aplicación. Mientras no exista el nuevo archivo, la aplicación sigue leyendo el antiguo de la carpeta de trabajo, y la próxima vez que pulses **"Guardar Clave"** copia su contenido a la nueva ubicación. El archivo antiguo no se borra: elimínalo tú cuando ya no lo necesites.

    El menú **Ayuda > Configurar API Key (Ayuda)...** de la aplicación resume qué variable de entorno usa cada proveedor.

## Uso mediante la interfaz

Una vez instalado, puedes lanzar la aplicación desde tu terminal con el siguiente comando:

```bash
pyexamgenerator
```
Se recomienda ejecutar este comando desde la carpeta donde vayas a trabajar (donde tengas tus PDFs y donde quieras que se guarden los archivos generados).

### Flujo de Trabajo Completo

El proceso de uso de la aplicación se divide en tres fases principales, cada una correspondiente a una pestaña de la interfaz.

#### Fase 1: Generar Preguntas (Pestaña "Generar Preguntas")

Aquí es donde se crea el contenido inicial a partir de tus documentos.

1.  **Selecciona un Prompt**: Elige una plantilla de instrucciones para la IA (ej. "PRL") o crea la tuya propia. Puedes retocar el texto de **"Prompt Seleccionado"** para una sola generación; para guardarlo de forma permanente usa **"Editar"**.
2.  **Selecciona los Archivos Fuente**: Haz clic en **"Seleccionar Archivos"** para elegir los PDFs (o imágenes) que servirán como fuente de conocimiento y elige el **"Modo de entrada"**:
    *   `text`: extrae el texto del PDF y lo incluye en el prompt (recomendado para PDFs con texto seleccionable).
    *   `image`: envía las páginas como imágenes (útil con esquemas, tablas o PDFs escaneados).
    *   `pdf`: adjunta el propio PDF (o cada fragmento) como documento.
3.  **Configura la Generación**:
    *   Define cuántas **preguntas objetivo** quieres por cada PDF (o por cada fragmento, si activas **"Procesar PDF por fragmentos"**).
    *   (Opcional) Activa el **filtro de duplicados** seleccionando tu banco de preguntas principal para evitar generar preguntas repetidas.
4.  **Elige Proveedor, Clave y Modelo**: En la sección **"Proveedor de IA, Clave API y Modelo"**, selecciona el **"Proveedor"** (Google Gemini, OpenAI o Anthropic), comprueba la **"Clave API"** y elige un modelo en el desplegable **"Modelo"** (ej. `gemini-flash-latest`). También puedes pulsar **"Cargar Modelos"** para ver en la tabla los modelos disponibles para tu clave y seleccionar uno.
5.  **Genera**: Haz clic en **"Generar Preguntas"**. La generación se ejecuta en segundo plano (la ventana sigue respondiendo y la barra de estado muestra el progreso) y el botón **"Cancelar"** la detiene tras la petición en curso, guardando lo obtenido. La aplicación creará un archivo `.xlsx` y un `.docx` (`<nombre>_pendiente_de_revisar`) con las nuevas preguntas, marcadas como "Pendiente de revisar". Si procede, creará también `<nombre>_similares_descartadas.docx` (preguntas descartadas por el filtro de similitud) y `<nombre>_no_validas.xlsx` (respuestas del modelo que no se pudieron usar, con el motivo).

**¿Sin clave de API?** En lugar de los pasos 4 y 5, pulsa **"Preparar prompts sin API..."** en la sección **"Generar sin API (Google AI Studio, ChatGPT o Claude en el navegador)"**. Se abrirá un asistente con un prompt por PDF o fragmento: cópialo en el chat, pega la respuesta en el asistente y pulsa **"3. Guardar preguntas (Excel + DOCX)"** para obtener los mismos archivos de revisión.

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
-   [Tutorial Parte 0: Instalación e iniciación del programa](https://pyexamgenerator.readthedocs.io/es/latest/tutorial_pyexamgenerator_pt0_instalacion.html)
-   [Tutorial Parte 1: Generar Preguntas](https://pyexamgenerator.readthedocs.io/es/latest/tutorial_pyexamgenerator_pt1_generar_preguntas.html)
-   [Tutorial Parte 2: Gestionar el Banco de Preguntas](https://pyexamgenerator.readthedocs.io/es/latest/tutorial_pyexamgenerator_pt2_gestionar_banco_de_preguntas.html)
-   [Tutorial Parte 3: Generar Exámenes](https://pyexamgenerator.readthedocs.io/es/latest/tutorial_pyexamgenerator_pt3_generar_examenes.html)
-   [Tutorial Parte 4: Corregir Exámenes](https://pyexamgenerator.readthedocs.io/es/latest/tutorial_pyexamgenerator_pt4_corregir_examenes.html)


## Uso Avanzado: Scripting y Automatización

Además de la interfaz gráfica, todos los componentes de pyexamgenerator están diseñados para ser utilizados en scripts de Python. Esto te permite automatizar la generación de preguntas, la gestión de bancos y la creación de exámenes, ideal para procesos por lotes o para integrar pyexamgenerator en otros sistemas.

A continuación se muestran ejemplos de uso para cada uno de los módulos principales.

### 1. Generar Preguntas con `QuestionGenerator`

#### 1.1. Con API (Gemini, OpenAI o Anthropic)

Este script utiliza la IA para leer uno o más archivos PDF y generar un banco de preguntas, procesando cada página de forma individual para un análisis exhaustivo.

```python
# archivo: generar_preguntas.py

from pyexamgenerator import QuestionGenerator
from pyexamgenerator.ai_providers import AIProviderError

# --- Configuración ---
# Se recomienda configurar la API Key como una variable de entorno del proveedor:
# GEMINI_API_KEY (o GOOGLE_API_KEY), OPENAI_API_KEY o ANTHROPIC_API_KEY.
# Si no la tienes definida, pásala con QuestionGenerator(api_key="...", ...).

PDF_FILES = ['ruta/a/tu/TEMA_01.pdf', 'ruta/a/tu/TEMA_02.pdf']
OUTPUT_FILENAME = "banco_generado_script"
PROVIDER = "gemini"  # "gemini", "openai" o "anthropic"
MODEL_NAME = "gemini-flash-latest"  # O el modelo que prefieras del proveedor elegido

# --- Lógica del Script ---
if __name__ == '__main__':
    generator = QuestionGenerator(model_name=MODEL_NAME, provider=PROVIDER)

    print(f"Generando preguntas desde: {PDF_FILES}")

    try:
        questions_df = generator.generate_multiple_choice_questions(
            pdf_paths=PDF_FILES,
            prompt_type="PRL",
            output_filename=OUTPUT_FILENAME,
            generate_docx=True,
            input_mode="text",  # "text", "image" o "pdf"
            process_by_pages=True,  # Activar procesamiento por páginas
            num_questions_per_chunk_target=2, # Intentar generar 2 preguntas por página
            pages_per_chunk=1,  # Procesar cada página individualmente
        )
    except AIProviderError as e:
        # Clave no válida, cuota excedida, servidores saturados, modelo inexistente...
        # Las preguntas obtenidas antes del error ya se han guardado.
        print(f"\nError del proveedor de IA:\n{e}")
    else:
        if questions_df is not None and not questions_df.empty:
            print(f"\n¡Éxito! Se generaron {len(questions_df)} preguntas.")
            print(f"Archivos guardados: {list(generator.last_output_paths.values())}")
```

Para usar otro proveedor basta con cambiar `provider` y `model_name` (se admiten también los alias `"google"`, `"chatgpt"` o `"claude"`). Por ejemplo, con Claude y enviando el PDF como documento adjunto:

```python
from pyexamgenerator import QuestionGenerator

qg = QuestionGenerator(api_key="...", model_name="claude-opus-5-5", provider="anthropic")
qg.generate_multiple_choice_questions(["Tema 1.pdf"], prompt_type="PRL", num_questions_per_chunk_target=10,
                                      input_mode="pdf", output_filename="tema1")
```

> Recuerda instalar el extra del proveedor (`pip install pyexamgenerator[openai]`, `[anthropic]` o `[ia]`) para usar OpenAI o Anthropic.

#### 1.2. Sin API (Google AI Studio, ChatGPT o Claude en el navegador)

Sin clave de API puedes preparar los prompts, pegarlos tú mismo en el chat y convertir después las respuestas en los mismos archivos de revisión que genera la API:

```python
# archivo: generar_preguntas_sin_api.py

from pyexamgenerator import QuestionGenerator

qg = QuestionGenerator()  # No necesita clave ni modelo

# 1. Un prompt por PDF/fragmento (admite las mismas opciones de fragmentación que la generación con API)
prompts = qg.build_generation_prompts(["Tema 1.pdf"], prompt_type="PRL", input_mode="text")
qg.export_prompts(prompts, output_filename="tema1")   # tema1_prompts.xlsx + carpeta tema1_prompts/

# 2. Pega cada prompt en el chat y copia su respuesta en la columna 'Respuesta' del Excel
#    (o escribe en esa celda la ruta a un .txt con la respuesta).

# 3. Importa las respuestas: crea tema1_pendiente_de_revisar.xlsx/.docx y, si procede,
#    tema1_similares_descartadas.docx y tema1_no_validas.xlsx.
qg.import_questions_from_prompts_file("tema1_prompts.xlsx", output_filename="tema1")

# O directamente con el texto copiado del chat:
# qg.import_questions_from_responses({"Tema 1": texto_copiado_del_chat}, output_filename="tema1")
```

> Para aplicar el filtro de similitud al importar, añade `existing_bank_path="ruta/a/tu/banco_principal.xlsx"` (y, si quieres, `similarity_threshold`). En los modos `image` y `pdf`, la columna `Adjuntar` indica el archivo que hay que adjuntar en el chat junto con cada prompt; si procesas el PDF por fragmentos, pasa también `attachments_dir="carpeta"` a `build_generation_prompts` para que escriba allí el PDF de cada fragmento.

### 2. Gestionar el Banco de Preguntas con `QuestionBankManager`

#### 2.1. Convertir un DOCX Revisado a XLSX

Este script toma un archivo `.docx` que has revisado manualmente y lo convierte en un archivo `.xlsx` estructurado, listo para ser añadido a tu banco principal.

```python
# archivo: convertir_docx.py

from pyexamgenerator import QuestionBankManager
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

from pyexamgenerator import QuestionBankManager
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

#### 2.3. Registrar el uso de varios exámenes en el banco

Este script marca en el banco las preguntas usadas en uno o varios exámenes ya generados (los archivos `..._completo.xlsx`), dándole a cada examen su propia **etiqueta**. Cada examen genera una columna `<etiqueta>_uso` y, al final, se recalcula la columna agregada `Veces usada en examen` (que alimenta la selección por *"menos usadas"* al generar exámenes).

```python
# archivo: registrar_uso_examenes.py

from pyexamgenerator import QuestionBankManager

# --- Configuración ---
BANK_PATH = "ruta/a/tu/banco_principal.xlsx"
OUTPUT_PATH = "ruta/a/tu/banco_principal_actualizado.xlsx"

# Lista de exámenes con su etiqueta. Cada examen puede indicarse como:
#   - un dict {"path": ..., "label": ...},
#   - una tupla (ruta, etiqueta),
#   - o solo la ruta (la etiqueta se deriva del nombre del archivo).
EXAMS = [
    {"path": "ruta/a/examen_parcial1_completo.xlsx", "label": "Parcial1_24-25"},
    {"path": "ruta/a/examen_parcial2_completo.xlsx", "label": "Parcial2_24-25"},
    ("ruta/a/examen_recuperacion_completo.xlsx", "Recuperacion_24-25"),
    # Sin etiqueta: se derivará del nombre del archivo (ver label_delimiter/label_parts).
    "ruta/a/examen_Prevencion_Industrial_25_26_1A_completo.xlsx",
]

# --- Lógica del Script ---
if __name__ == "__main__":
    manager = QuestionBankManager()

    total_matched, updated_df, stats = manager.update_bank_with_exams(
        bank_path=BANK_PATH,
        exams=EXAMS,
        # Para los exámenes SIN etiqueta explícita, se deriva del nombre del archivo:
        # se parte por "_" y se conservan las partes 2:4 (1-based, admite rangos y negativos).
        label_delimiter="_",
        label_parts="2:4",
    )

    if total_matched == -1:
        print("Error: no se pudo leer el banco o faltan columnas para emparejar.")
    else:
        for exam in stats["exams"]:
            print(f"{exam['label']}: {exam['matched']} preguntas -> columna '{exam['column']}'")
        if stats["errors"]:
            print(f"Exámenes omitidos: {len(stats['errors'])}")
        print(f"\nTotal de usos registrados: {total_matched}")
        manager.save_dataframe_to_excel(df=updated_df, filepath=OUTPUT_PATH)
        print(f"Banco actualizado guardado en: {OUTPUT_PATH}")
```

> Las etiquetas se escriben en la columna `<etiqueta>_uso` **sin tildes** (p. ej. `Evaluación` → `Evaluacion`). Puedes previsualizar la etiqueta derivada de un nombre con `manager.label_from_filename(path, delimiter="_", parts="2:4")`.
>
> Para un único examen sigue disponible `manager.update_bank_with_exam(bank_path, exam_path, exam_label=...)`, que devuelve `(coincidencias, banco_actualizado)`.

### 3. Generar Exámenes con `pyexamgenerator`

#### 3.1. Crear un Examen Sencillo

Este script genera rápidamente dos versiones de un examen utilizando todas las preguntas disponibles de un banco.

```python
# archivo: crear_examen_simple.py

from pyexamgenerator import ExamGenerator
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
        num_exams=2,  # Generará 'Tipo 1' y 'Tipo 2'
        selection_method="azar"
    )
    print(f"\nExámenes simples generados en la carpeta: '{OUTPUT_DIRECTORY}'")
```

#### 3.2. Crear un Examen Personalizado y Completo

Este ejemplo muestra el poder de la personalización, definiendo la estructura exacta del examen, los nombres de las versiones, el estilo y las opciones de exportación.

```python
# archivo: crear_examen_personalizado.py

from pyexamgenerator import ExamGenerator
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
        check=False,  # Desactiva la previsualización interactiva
        verbose=True  # Muestra más información de progreso
    )
    print(
        f"\nExámenes personalizados generados en la carpeta: '{OUTPUT_DIRECTORY}'")
```

## Historial de Cambios

Para ver una lista detallada de los cambios, mejoras y correcciones de errores en cada versión, consulta el archivo [CHANGELOG.md](CHANGELOG.md).

## Contribución

Las contribuciones son bienvenidas. Si encuentras un error o tienes una idea para una nueva funcionalidad, por favor, abre un "issue" en el repositorio de GitHub.

## Licencia

Este proyecto está bajo la Licencia Pública General de GNU v3.0 o posterior (GPL-3.0-or-later). Consulta el archivo `LICENSE` para más detalles.