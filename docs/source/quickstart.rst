Configuración Inicial: Tu Clave API
===================================

Antes de poder generar preguntas, es imprescindible configurar tu clave de API de Google Gemini.

Obtención de la Clave
---------------------

1.  Navega a `Google AI Studio <https://ai.google.dev/gemini-api/docs/api-key>`_.
2.  Inicia sesión con tu cuenta de Google.
3.  Haz clic en el botón **"Get API key"** y sigue las instrucciones para crear una nueva clave.
4.  Copia la clave generada. Es una cadena larga de caracteres.

Configuración en la Aplicación
------------------------------

.. image:: _static/api_key_setup.png
   :alt: Configuración de la clave API en la aplicación

1.  Abre la aplicación `examgenerator`.
2.  Ve a la pestaña **"Generar Preguntas"**.
3.  Localiza la sección **"Configuración de API y Modelo"**.
4.  Pega tu clave en el campo **"Clave API de Gemini"**.
5.  Haz clic en el botón **"Guardar Clave"**.

La clave se guardará de forma segura en un archivo `config.json` en tu directorio local, por lo que no necesitarás volver a introducirla en futuras sesiones. Esta clave SOLO será necesaria para generar preguntas, no para las otras pestañas para gestionar el banco y generar los exámenes.