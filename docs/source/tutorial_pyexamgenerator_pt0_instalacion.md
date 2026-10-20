# Instalación e iniciación del programa

¡Bienvenido a pyexamgenerator! Esta guía te enseñará a usar la aplicación para convertir automáticamente un documento PDF en un banco de preguntas de examen. No necesitas saber nada de programación, solo sigue los pasos.

## Parte 0: Antes de empezar (instalación una sola vez)

Antes de poder usar la aplicación, necesitamos prepararlo todo. Esto solo se hace una vez.

1.  **Instalar Python:** Si no lo tienes, descarga e instala Python (versión 3.9 o superior) desde su web oficial: [python.org](https://www.python.org/downloads/). Durante la instalación, **asegúrate de marcar la casilla que dice "Add Python to PATH"**. Esto es muy importante.

2.  **Instalar pyexamgenerator:** Abre la **Línea de Comandos** de Windows (busca `cmd` en el menú de Inicio). En la ventana negra que aparece, escribe el siguiente comando y presiona Enter.
    ```
    pip install pyexamgenerator
    ```
    Este único comando instalará la aplicación y todas sus dependencias automáticamente. Con él ya puedes generar preguntas con la IA de Google Gemini o **sin API** (copiando los prompts en el chat del navegador).

    Si además quieres generar preguntas con la API de **OpenAI** (modelos de ChatGPT) o de **Anthropic** (modelos de Claude), instala su librería con uno de estos comandos:
    ```
    pip install pyexamgenerator[openai]
    pip install pyexamgenerator[anthropic]
    pip install pyexamgenerator[ia]
    ```
    El último instala las dos. Si te olvidas, no pasa nada: la aplicación te avisará e indicará el comando que falta cuando elijas ese proveedor.

3.  **(Opcional) Conseguir una Clave API:** La "Clave API" es como una contraseña personal que da acceso a la inteligencia artificial de un proveedor. **Solo la necesitas para generar preguntas con API**; sin ella puedes usar el flujo **sin API**, en el que la aplicación prepara los prompts y tú los pegas en Google AI Studio, ChatGPT o Claude desde el navegador (lo verás en el tutorial de la pestaña "Generar Preguntas").
    *   **Google Gemini:** las claves se crean gratis en [Google AI Studio](https://aistudio.google.com/app/apikey) y la API tiene un nivel gratuito (con límites de uso). Es la opción más sencilla para empezar.
    *   **OpenAI (ChatGPT):** las claves se crean en [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
    *   **Anthropic (Claude):** las claves se crean en [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).
    *   Ten en cuenta que el uso de la API de OpenAI y de la de Anthropic se factura aparte de las suscripciones de ChatGPT o de Claude.
    *   En la aplicación tienes dos atajos: el menú **Ayuda > Obtener clave API del proveedor seleccionado...** (o el botón **"Obtener clave..."** de la pestaña "Generar Preguntas") abre la página donde se crean las claves, y el menú **Ayuda > Configurar API Key (Ayuda)...** resume qué variable de entorno usa cada proveedor y abre la guía oficial de Google para configurarla.
    *   Una vez que tengas tu clave, la forma más fácil y segura de usarla es configurarla como una "variable de entorno" con el nombre de tu proveedor: `GEMINI_API_KEY` (o `GOOGLE_API_KEY`) para Gemini, `OPENAI_API_KEY` para OpenAI y `ANTHROPIC_API_KEY` para Anthropic. En Windows puedes crearla desde la Línea de Comandos con `setx`, por ejemplo:
        ```
        setx GEMINI_API_KEY "pega_aqui_tu_clave"
        ```
        Cierra y vuelve a abrir la Línea de Comandos para que el cambio surta efecto. ¡La aplicación la detectará automáticamente al iniciarse! (Si prefieres no usar variables de entorno, también puedes pegar la clave en la aplicación y pulsar **"Guardar Clave"**; se guardará en un archivo `config.json` en tu carpeta de trabajo. Si existen las dos, la variable de entorno tiene prioridad.)

## Parte 1: Cómo iniciar pyexamgenerator

La forma más cómoda de trabajar es abrir la aplicación directamente en la carpeta donde tienes tus documentos.

1.  **Abre la Línea de Comandos en tu Carpeta de Trabajo:**
    *   Usa el Explorador de Archivos para ir a la carpeta donde tienes los PDFs que quieres usar (por ejemplo, `Mis Documentos\Examenes`).
    *   Haz clic en la barra de direcciones de la parte superior, borra la ruta que aparece, escribe `cmd` y presiona Enter.

2.  **Ejecuta el Comando:** En la ventana negra que se acaba de abrir, simplemente escribe el siguiente comando y presiona Enter:
    ```
    pyexamgenerator
    ```
¡Listo! La ventana de la aplicación pyexamgenerator debería aparecer en tu pantalla. Al iniciarla de esta forma, cualquier archivo que generes se guardará directamente en esta carpeta.

![](/_static/gifs/parte1_v00.gif)

