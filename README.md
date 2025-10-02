# ExamGenerator

ExamGenerator es una suite de aplicaciones de escritorio construida con Python y Tkinter para automatizar y simplificar el ciclo completo de creación de exámenes. Permite generar preguntas a partir de documentos PDF utilizando la IA de Google Gemini, gestionar un banco centralizado de preguntas y producir exámenes en múltiples formatos.

![Aquí puedes poner una captura de pantalla de la aplicación](ruta/a/tu/captura.png)

## Características Principales

-   **Generación de Preguntas con IA**: Utiliza la API de Google Gemini para crear preguntas de opción múltiple a partir de documentos PDF.
-   **Gestión de Bancos de Preguntas**: Importa, fusiona y gestiona preguntas en formato Excel, evitando duplicados.
-   **Creación de Exámenes Personalizados**: Genera múltiples versiones de un examen (ej. Tipo A, Tipo B) con preguntas y respuestas barajadas.
-   **Exportación Múltiple**: Guarda los exámenes en formato `.docx` profesional y en formato XML compatible con Moodle.
-   **Interfaz Gráfica Intuitiva**: Todas las funcionalidades son accesibles a través de una interfaz de usuario fácil de usar.

## Instalación

Puedes instalar ExamGenerator directamente desde PyPI usando pip:

```bash
pip install examgenerator
```

## Uso

Una vez instalado, puedes lanzar la aplicación desde tu terminal con el siguiente comando:

```bash
examgenerator
```

### Configuración Inicial: Obtener la Clave de API

Antes del primer uso, necesitas tu propia clave de API de Google Gemini.

1.  **Obtén tu clave de API** siguiendo las instrucciones oficiales en la [documentación de Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key).
2.  Abre la aplicación `examgenerator`.
3.  Ve a la pestaña **"Generar Preguntas"**.
4.  En la sección "Configuración de API y Modelo", introduce tu clave en el campo **"Clave API de Gemini"**.
5.  Haz clic en el botón **"Guardar Clave"**. La clave se guardará en un archivo `config.json` local y no tendrás que volver a introducirla.

### Flujo de Trabajo Básico

El proceso de uso de la aplicación se divide en tres fases principales, cada una correspondiente a una pestaña de la interfaz.

#### Fase 1: Generar Preguntas (Pestaña "Generar Preguntas")

Aquí es donde se crea el contenido inicial.

1.  **Selecciona un Prompt**: Elige una plantilla de instrucciones para la IA (ej. "PRL") o crea la tuya propia con los botones "Añadir/Editar".
2.  **Selecciona los PDFs**: Haz clic en "Seleccionar PDFs" para elegir los documentos que servirán como fuente de conocimiento.
3.  **Configura la Generación**:
    *   Define cuántas **preguntas objetivo** quieres por cada PDF.
    *   Activa el **filtro de duplicados** seleccionando tu banco de preguntas principal para evitar generar preguntas repetidas.
    *   Ajusta el **umbral de similitud** para controlar qué tan estricto es el filtro.
4.  **Genera**: Haz clic en **"Generar Preguntas"**. La aplicación creará un archivo `.xlsx` y un `.docx` con las nuevas preguntas, marcadas como "pendiente de revisar".

#### Fase 2: Gestionar el Banco de Preguntas (Pestaña "Gestionar Banco de Preguntas")

Este es el paso de control de calidad y consolidación.

1.  **Revisión Manual (Fuera de la App)**: Abre el archivo `.docx` generado en la fase anterior. Corrige los enunciados, las respuestas, el estado (cambia "Pendiente de revisar" a "Aceptable"), etc. y guarda los cambios.
2.  **Convertir DOCX a XLSX**:
    *   En la sección "Generar XLSX desde DOCX revisado", selecciona el archivo `.docx` que acabas de corregir.
    *   Haz clic en **"Guardar XLSX Revisado"** para crear una versión en Excel limpia y estructurada.
3.  **Añadir al Banco Principal**:
    *   En la sección "Añadir Preguntas Existentes", selecciona tu **Banco Existente** principal y el **Archivo a Añadir** (el `.xlsx` que acabas de crear).
    *   Elige si quieres añadir todas las preguntas o **solo las que tienen estado "Aceptable"**.
    *   Haz clic en **"Añadir Preguntas sin Duplicados"** para fusionar las nuevas preguntas validadas en tu banco maestro.

#### Fase 3: Generar Exámenes (Pestaña "Generar Exámenes")

Con un banco de preguntas robusto y validado, ya puedes crear los exámenes finales.

1.  **Selecciona el Banco**: Elige tu archivo `.xlsx` del banco de preguntas principal.
2.  **Define los Datos del Examen**: Rellena los campos de Asignatura, Curso, Nombre del Examen, y el número de versiones que deseas (ej. 2 para un Tipo A y Tipo B).
3.  **Configura la Selección de Preguntas**:
    *   Elige cómo quieres componer el examen: especificando el número de preguntas por cada tema, un número fijo para todos los temas, o mediante un diccionario.
    *   Selecciona el **método de selección** (`azar`, `primeras`, `menos usadas`).
4.  **Actualizar Uso (Recomendado)**: Marca la casilla **"Actualizar Archivo Excel con Uso"**. Esto añadirá una columna en tu banco para registrar qué preguntas se han usado en este examen, lo cual es vital para el método de selección "menos usadas".
5.  **Genera**: Haz clic en **"Generar Exámenes"** para producir los documentos `.docx` finales, listos para imprimir.

## Licencia

Este proyecto está bajo la Licencia Pública General de GNU (GPLv3). Consulta el archivo `LICENSE` para más detalles.