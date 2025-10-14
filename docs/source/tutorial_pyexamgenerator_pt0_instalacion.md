# Instalación e iniciación del programa

¡Bienvenido a pyexamgenerator! Esta guía te enseñará a usar la aplicación para convertir automáticamente un documento PDF en un banco de preguntas de examen. No necesitas saber nada de programación, solo sigue los pasos.

## Parte 0: Antes de empezar (instalación una sola vez)

Antes de poder usar la aplicación, necesitamos prepararlo todo. Esto solo se hace una vez.

1.  **Instalar Python:** Si no lo tienes, descarga e instala Python desde su web oficial: [python.org](https://www.python.org/downloads/). Durante la instalación, **asegúrate de marcar la casilla que dice "Add Python to PATH"**. Esto es muy importante.

2.  **Instalar pyexamgenerator:** Abre la **Línea de Comandos** de Windows (busca `cmd` en el menú de Inicio). En la ventana negra que aparece, escribe el siguiente comando y presiona Enter.
    ```
    pip install pyexamgenerator
    ```
    Este único comando instalará la aplicación y todas sus dependencias automáticamente.

3.  **Conseguir tu Clave API de Gemini:** La "Clave API" es como una contraseña personal que te da acceso a la inteligencia artificial de Google.
    *   Puedes conseguir una gratis siguiendo las instrucciones de Google. En la aplicación, hemos añadido un atajo para ayudarte: ve al menú **Ayuda > Configurar API Key (Ayuda)...** para abrir la guía oficial.
    *   Una vez que tengas tu clave, la forma más fácil y segura de usarla es configurarla como una "variable de entorno" (`GEMINI_API_KEY`). El enlace de ayuda te explica cómo hacerlo. Si sigues esos pasos, ¡la aplicación la detectará automáticamente!

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

