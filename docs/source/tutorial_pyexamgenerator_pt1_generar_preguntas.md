# Uso de la pestaña "Generar Preguntas"

## Parte 2: Generando preguntas

Ahora vamos a realizar nuestro ejemplo práctico: generar preguntas de dos temas diferentes, la Ley de Prevención y el Reglamento de los Servicios de Prevención.

Asegúrate de tener ambos archivos en tu carpeta de trabajo: `RD 31-95 LPRL_fragmento.pdf` y `RD 39-97 RSP_fragmento.pdf`.

Puedes generar las preguntas de dos formas:

*   **Con API:** la aplicación se conecta directamente a la inteligencia artificial de Google Gemini, OpenAI (modelos de ChatGPT) o Anthropic (modelos de Claude) usando tu clave API. Es la forma más automática.
*   **Sin API:** la aplicación prepara las instrucciones (los "prompts") y tú las pegas en el chat de Google AI Studio, ChatGPT o Claude desde el navegador. No necesitas clave API.

Las secciones 1 a 3 son comunes a las dos formas. La Sección 4 explica la generación con API y la Sección 5, la generación sin API.

### Sección 1: Seleccionar/Editar tipo de prompt

Un "Prompt" son las instrucciones que le damos a la inteligencia artificial.

*   **Tipo de Prompt:** Este menú desplegable contiene plantillas de instrucciones. Como ambos documentos son de temática legal sobre prevención, la mejor opción es **PRL**.
    > **💡 Tip Pro: Prompts Personalizados**
    >
    > ¿Necesitas generar preguntas de Historia, Biología o Matemáticas? ¡Puedes crear tus propios prompts!
    >
    > *   **Añadir:** Haz clic en el botón "Añadir". Escribe un nombre (ej. "Historia") y las instrucciones para la IA (ej. "Genera preguntas sobre fechas clave...").
    > *   **Editar:** Selecciona un prompt existente (también **PRL** o **PM**) y haz clic en "Editar" para mejorarlo. La ventana se abre con el texto actual del prompt y los cambios se guardan de forma permanente.
    > *   **Guardar:** Al crear o editar, el programa genera automáticamente un archivo llamado `custom_prompts.json` **en la misma carpeta donde ejecutaste el programa**.
    > *   **Reutilizar:** La próxima vez que abras `pyexamgenerator` **desde esa misma carpeta**, el programa leerá el archivo `.json` y tus prompts personalizados aparecerán automáticamente en la lista. Si abres el programa en otra carpeta vacía, no aparecerán hasta que copies ese archivo allí.
    > *   **Formato:** No hace falta que expliques en tu prompt cómo debe responder la IA: la aplicación añade automáticamente a cada prompt las instrucciones de formato (una lista JSON con la pregunta, 4 opciones distintas, la letra de la respuesta correcta y el texto relevante). Tampoco pidas opciones del tipo "todas las anteriores" o "ninguna de las anteriores": las opciones se barajan al generar los exámenes y dejarían de tener sentido.
*   **Prompt Seleccionado:** Este cuadro muestra el texto del prompt elegido. Puedes modificarlo aquí para **una sola generación** (se usará tal cual, pero no se guarda); para guardar los cambios de forma permanente, usa el botón "Editar".
*   **Acción para nuestro ejemplo:** Selecciona **PRL** en el menú desplegable.

### Sección 2: Seleccionar archivos fuente

Aquí le decimos al programa qué documentos debe leer y cómo debe enviárselos a la IA.

*   **Botón "Seleccionar Archivos":** Haz clic en este botón para buscar archivos PDF (o imágenes) en tu ordenador.
*   **Acción para nuestro ejemplo:** En la ventana que se abre, busca tus archivos. Para seleccionar ambos a la vez, haz clic en el primero (`RD 31-95...`) y, **manteniendo pulsada la tecla `Ctrl`**, haz clic en el segundo (`RD 39-97...`). Luego, pulsa "Abrir". Verás las rutas de ambos archivos en el campo de texto, separadas por una coma.
    > Si vuelves a pulsar "Seleccionar Archivos", los nuevos archivos se **añaden** a la lista (sin repetir los que ya estaban). Para empezar de cero, borra antes el contenido del campo. Los nombres de archivo que contienen comas también funcionan.

*   **Modo de entrada:**
    *   **`text`:** extrae el texto del PDF y lo incluye en el prompt. Es el modo recomendado para documentos con texto seleccionable. En este modo solo se admiten archivos PDF.
    *   **`image`:** envía las páginas como imágenes al modelo. Úsalo cuando la maquetación, las tablas o los esquemas sean relevantes, o cuando el PDF no tenga texto extraíble (por ejemplo, un documento escaneado). El modelo elegido debe admitir imágenes y puede tardar más.
    *   **`pdf`:** adjunta el propio archivo PDF (o, si procesas por fragmentos, un PDF con las páginas de cada fragmento) para que el modelo lea el documento directamente. También sirve para PDFs escaneados.
    *   Los tres modos funcionan con los tres proveedores (Gemini, OpenAI y Anthropic) y también sin API: en los modos `image` y `pdf` tendrás que adjuntar en el chat el archivo que te indique la aplicación (ver la Sección 5).
*   **Acción para nuestro ejemplo:** Nuestros PDFs tienen texto seleccionable, así que **deja el modo `text`**.

### Sección 3: Configuración de generación

Esta es la parte más importante, donde personalizamos la tarea.

*   **Preguntas objetivo por PDF/fragmento:**
    *   **Qué es:** El número de preguntas que quieres que la IA intente crear **por cada PDF** que has seleccionado (o por cada fragmento, si activas el procesamiento por fragmentos).
    *   **Acción para nuestro ejemplo:** Borra el valor que haya y escribe **`3`**. El programa intentará generar 3 preguntas del primer PDF y 3 del segundo, para un total de 6 preguntas.

*   **Nombre Archivo Salida:**
    *   **Qué es:** El nombre base que tendrán los archivos que se generen. Si lo dejas vacío, se usará `preguntas`.
    *   **Acción para nuestro ejemplo:** Escribe un nombre que represente el contenido, como **`preguntas_PRL_varias`**.

*   **Modo de Procesamiento:**
    *   **Procesar PDF por fragmentos:** Si marcas esta casilla, el programa no enviará el PDF completo a la IA de una sola vez. En su lugar, lo dividirá en fragmentos más pequeños. Es ideal para documentos muy largos (más de 20-30 páginas) para asegurar que la IA lee y extrae información de todas las partes del texto.
    *   **Páginas por fragmento:** Este campo (que se activa al marcar la casilla) te permite decidir cuántas páginas tendrá cada fragmento. Por ejemplo, si pones `5`, la IA trabajará con las páginas 1-5, luego 6-10, y así sucesivamente.
    *   **Modo de fragmentación y total de fragmentos:** Puedes dividir por **páginas** (`pages`) o por **longitud de texto** (`text_length`, solo en modo `text`). Si prefieres controlar el número de llamadas, indica el **total de fragmentos**; si lo dejas vacío, se usa el tamaño configurado para cada fragmento.
    *   **Incluir el documento completo como contexto en cada fragmento (modo 'text'):** Esta casilla se activa al marcar "Procesar PDF por fragmentos" y viene marcada por defecto. Si está marcada, cada prompt incluye, además de su fragmento, el texto completo del PDF para que la IA tenga una visión general del tema (las preguntas se siguen basando solo en el fragmento). Los prompts son mucho más largos, así que desmárcala para ahorrar tokens o si vas a copiar los prompts a mano en un chat web.
    *   En modo `text`, los fragmentos sin texto extraíble (por ejemplo, páginas escaneadas) se omiten y el programa avisa de que uses el modo `image` o `pdf`.
    *   **Acción para nuestro ejemplo:** Nuestros PDFs son cortos, así que **deja la casilla DESMARCADA**.

*   **Máx. intentos por fragmento:**
    *   **Qué es:** A veces, la IA no genera el número exacto de preguntas a la primera. Este número le dice cuántas veces puede volver a intentarlo para alcanzar el objetivo. Solo se usa en la generación con API.
    *   **Acción para nuestro ejemplo:** El valor por defecto, **`3`**, es perfecto. No necesitas cambiarlo.

*   **Filtro de Duplicados:**
    *   **Qué es:** Una potente herramienta para evitar añadir preguntas repetidas a un banco que ya existe. Funciona tanto con API como sin API.
    *   **Banco Existente a Consultar:** Aquí seleccionarías tu archivo Excel principal de preguntas.
    *   **Activar filtro de similitud:** Si la marcas, la aplicación comparará el enunciado de cada nueva pregunta generada con los de todas las preguntas de tu banco existente. La comparación no distingue mayúsculas ni tildes.
    *   **Umbral de similitud:** Define la sensibilidad del filtro usando el **Índice de Jaccard** (comparación de palabras compartidas).
        *   **¿Cómo funciona?** Un valor de **1.0** significa que la pregunta solo se descartará si es *idéntica* palabra por palabra a una existente. Un valor de **0.8** (recomendado) significa que si la nueva pregunta comparte el 80% de las palabras con una existente (es decir, es muy parecida aunque cambie alguna palabra), se considerará duplicada y se descartará.
    *   **Acción para nuestro ejemplo:** Como estamos creando nuestro primer banco, **dejaremos todos estos campos vacíos y las casillas desmarcadas**.

*   **Inclusión de Banco en Prompt:**
    *   **Qué es:** Le da "ejemplos" a la IA de las preguntas que ya tienes para que intente ser más original y no repetir conceptos.
    *   **Alcance:** Le dice a la IA si debe fijarse en las preguntas del mismo tema o en todas las preguntas de tu banco.
    *   **Contenido:** Le dice a la IA si los ejemplos deben incluir solo el enunciado o también las respuestas.
    *   **Acción para nuestro ejemplo:** Como no estamos usando un banco existente, **ignoraremos esta sección**.

*   **Proveedor de IA, Clave API y Modelo:** (solo para la generación con API; si vas a trabajar sin API, puedes saltarte este apartado)
    *   **Proveedor:** Elige **Google Gemini (AI Studio)**, **OpenAI (ChatGPT)** o **Anthropic (Claude)**. La aplicación recuerda la clave y el modelo de cada proveedor por separado. Debajo de los campos verás de dónde se ha cargado la clave (variable de entorno o `config.json`) y, si falta la librería del proveedor, el comando para instalarla (por ejemplo, `pip install pyexamgenerator[openai]`).
    *   **Clave API:** Si configuraste la variable de entorno del proveedor (`GEMINI_API_KEY`, `OPENAI_API_KEY` o `ANTHROPIC_API_KEY`), la aplicación ya la habrá detectado. Si no, pega aquí tu clave (se muestra oculta con asteriscos).
        *   **Botón "Guardar Clave":** Guarda la clave del proveedor seleccionado, junto con el modelo elegido, en el archivo `config.json` de la carpeta donde ejecutaste el programa. Si existe la variable de entorno, esta tiene prioridad.
        *   **Botón "Obtener clave...":** Abre en el navegador la página del proveedor donde se crean las claves.
    *   **Modelo:** Desplegable con modelos sugeridos para el proveedor elegido. También puedes escribir directamente el identificador de cualquier otro modelo. Las sugerencias son:

        | Proveedor | Modelos sugeridos |
        | --- | --- |
        | Google Gemini | `gemini-flash-latest`, `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-pro-latest` |
        | OpenAI | `gpt-6.1-sol`, `gpt-6-luna`, `gpt-6-astra` |
        | Anthropic | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-fable-5-1` |

    *   **Botón "Cargar Modelos":** Haz clic en este botón para que la aplicación use tu clave y obtenga la lista de los "cerebros" de IA disponibles en el proveedor seleccionado. Es la mejor forma de saber qué modelos puedes usar con tu clave.
    *   **Tabla de Modelos:** Después de cargar, la tabla se llenará con los modelos y sus detalles. Te explicamos las columnas (según el proveedor, algunas pueden aparecer vacías o como `N/A`):
        *   **Nombre Técnico:** El nombre "oficial" que usa el programa para comunicarse con la IA.
        *   **Nombre:** Un nombre más amigable y fácil de leer.
        *   **Versión:** La versión específica del modelo.
        *   **Tokens Entrada/Salida:** Piensa en esto como la "memoria" o la capacidad de la IA. Números más altos significan que puede procesar documentos más largos y generar respuestas más extensas de una sola vez.
        *   **Descripción:** Una breve explicación del modelo (o información como su fecha de publicación).
    *   Al hacer clic en una fila de la tabla, ese modelo pasa al campo **"Modelo"**.
    *   **Acción para nuestro ejemplo:** Elige el proveedor **Google Gemini (AI Studio)** y el modelo **`gemini-flash-latest`** (un modelo "Flash"), que es rápido y económico.

*   **Imprimir respuesta cruda del modelo (depuración):**
    *   **Qué es:** Esta es una opción para usuarios avanzados o para cuando algo no funciona bien. Si la marcas, en la ventana negra de la línea de comandos (la que usaste para iniciar el programa) se imprimirá el texto exacto que devuelve la IA, sin ningún formato. Es útil para diagnosticar problemas.
    *   **Acción para nuestro ejemplo:** Para un uso normal, **deja esta casilla DESMARCADA**.

*   **Directorio de Salida:**
    *   **Qué es:** La carpeta donde se guardarán los archivos generados.
    *   **Acción para nuestro ejemplo:** Puedes dejar este campo **en blanco**. Como iniciamos la aplicación desde nuestra carpeta de trabajo, los archivos se guardarán allí automáticamente.

### Sección 4: ¡A generar! (con API)

Ya está todo configurado.

*   **Botón "Generar Preguntas":** Haz clic en este botón, dentro del recuadro **"Generar con API"**.
*   **¿Qué pasará ahora?:** La generación se realiza en segundo plano, así que la ventana sigue respondiendo mientras tanto. En la barra de estado de la parte inferior verás el progreso (archivo, fragmento e intento en curso). Cuando termine, aparecerá una ventana emergente con el número de preguntas guardadas y la lista de archivos creados.
*   **Botón "Cancelar":** Si quieres detener la generación, pulsa **"Cancelar"**. El programa se detendrá en cuanto termine la petición en curso y guardará las preguntas obtenidas hasta ese momento.
*   **Si algo falla:** La aplicación muestra un mensaje que explica el problema y cómo solucionarlo: clave API no válida, límite de uso o cuota excedida (espera unos minutos o cambia a un modelo más ligero, como uno "Flash"), servidores saturados (inténtalo más tarde o con otro modelo), modelo no disponible (pulsa "Cargar Modelos" y elige uno de la lista) o librería del proveedor sin instalar (te indica el comando `pip` necesario). Si el error ocurre a mitad del proceso, **las preguntas generadas hasta ese momento se guardan** igualmente.

> Nota: la animación se grabó con una versión anterior de la pestaña, que solo admitía Gemini. Los pasos son los mismos, aunque algunos controles han cambiado de nombre o de sitio.

![](/_static/gifs/parte2-3_v01_parte2.gif)

### Sección 5: Generar sin API (Google AI Studio, ChatGPT o Claude en el navegador)

Si no tienes clave API (o no quieres consumir la cuota de la API), puedes usar el chat de Google AI Studio, ChatGPT o Claude en el navegador. La aplicación prepara un prompt por cada PDF (o por cada fragmento) con la configuración de las secciones 1 a 3, tú lo pegas en el chat y luego pegas la respuesta en la aplicación. Al final se generan **los mismos archivos de revisión** que con la API.

1.  **Abre el asistente:** En el recuadro **"Generar sin API (Google AI Studio, ChatGPT o Claude en el navegador)"**, haz clic en **"Preparar prompts sin API..."**. Se abrirá la ventana **"Generar preguntas sin API (copiar y pegar en el chat)"**.
2.  **Elige el chat:** En **"Chat de destino"**, selecciona **Google AI Studio**, **ChatGPT** o **Claude** (aparece preseleccionado el del proveedor elegido en la pestaña) y pulsa **"Abrir chat en el navegador"**. Debajo verás consejos específicos para el chat elegido.
3.  **Elige un prompt:** La tabla muestra un prompt por PDF o fragmento, con su tema, sus páginas, el archivo que hay que adjuntar (columna **"Adjuntar"**, solo en los modos `image` y `pdf`), su longitud y su estado. Haz clic en una fila para ver su prompt en el recuadro **"1. Prompt: cópialo y pégalo en el chat"**.
4.  **Copia el prompt en el chat:** Pulsa **"Copiar prompt"**, inicia una **conversación nueva** en el chat y pega el prompt. En los modos `image` y `pdf`, adjunta también el archivo indicado en la columna **"Adjuntar"**; el botón **"Abrir carpeta del adjunto"** abre la carpeta donde está. Si procesas el PDF por fragmentos, la aplicación guarda el PDF de cada fragmento en la carpeta `<nombre>_adjuntos`, dentro del directorio de salida.
5.  **Copia la respuesta:** El chat responderá con un bloque de código ```` ```json ```` que contiene las preguntas. Cópialo con el botón de copiar del propio bloque de código (o del mensaje).
6.  **Pega la respuesta:** En el recuadro **"2. Respuesta del chat: pégala aquí"**, pulsa **"Pegar del portapapeles"** (también puedes usar **"Cargar desde archivo..."** con un `.txt`, `.md` o `.json`). Pulsa **"Comprobar respuesta"** para saber cuántas preguntas válidas contiene; la columna **"Estado"** de la tabla se actualiza. **"Borrar"** vacía la respuesta de ese prompt.
7.  **¿Respuesta cortada o quieres más preguntas?** Pulsa **"Copiar petición de continuación"**, pégala en la misma conversación del chat y pega la nueva respuesta **debajo** de la anterior (el botón "Pegar del portapapeles" la añade al final). Se aprovechan todas las preguntas completas de todos los bloques.
8.  **Repite** los pasos 3 a 7 con cada fila de la tabla.
9.  **Guarda las preguntas:** Pulsa **"3. Guardar preguntas (Excel + DOCX)"**. La aplicación analiza todas las respuestas, aplica el filtro de similitud si lo configuraste en la Sección 3 y crea los mismos archivos que la generación con API (ver la Parte 3). Si algún prompt no tiene respuesta, te preguntará si quieres guardar igualmente las disponibles.

> **¿Prefieres trabajar en varias sesiones o desde Excel?** En el asistente, el botón **"Exportar prompts y respuestas (Excel + TXT)..."** guarda `<nombre>_prompts.xlsx` (un prompt por fila, con una columna **"Respuesta"** que incluye las respuestas ya pegadas) y una carpeta `<nombre>_prompts/` con un archivo `.txt` por prompt. Más adelante, pega cada respuesta en la columna **"Respuesta"** del Excel (o, si es muy larga, la ruta a un `.txt` que la contenga) y, en la pestaña "Generar Preguntas", pulsa **"Importar respuestas desde Excel de prompts..."**. Se crearán los archivos de revisión en el **Directorio de Salida** (o, si está vacío, en la carpeta del Excel) con el **Nombre Archivo Salida** indicado, aplicando el filtro de duplicados si está configurado.

> **💡 Consejos para los chats web**
>
> *   Inicia una **conversación nueva para cada prompt**.
> *   Pide como mucho **10-15 preguntas por mensaje** (campo "Preguntas objetivo por PDF/fragmento") para evitar respuestas cortadas.
> *   Copia la respuesta con el **botón de copiar del bloque de código**, para no perder ningún carácter.
> *   **Google AI Studio:** en *Run settings* puedes activar *Structured output* y pegar el esquema que copia el botón **"Copiar esquema JSON"** para recibir un JSON limpio.
> *   **ChatGPT y Claude** pueden convertir un texto pegado muy largo en un archivo adjunto; es normal. En Claude, si el adjunto llegase vacío, guarda el prompt en un `.txt` y súbelo.
> *   Los **planes gratuitos** de los chats tienen límites de archivos subidos y de uso. Con documentos largos, usa fragmentos pequeños o el modo `text`, y desmarca "Incluir el documento completo como contexto en cada fragmento (modo 'text')" para acortar los prompts.

## Parte 3: Revisa tus resultados

Ve a tu carpeta de trabajo. Dentro, encontrarás dos archivos nuevos (se crean igual con API que sin API):

1.  **`preguntas_PRL_varias_pendiente_de_revisar.xlsx` (Archivo de Excel):** El banco de preguntas en formato de datos. La columna "Tema" toma el nombre de cada archivo fuente sin su extensión (por ejemplo, `RD 31-95 LPRL_fragmento`).
2.  **`preguntas_PRL_varias_pendiente_de_revisar.docx` (Archivo de Word):** **¡Este es el archivo importante para ti!** Ábrelo. Verás un total de 6 preguntas (3 de cada PDF), cada una con sus opciones, la respuesta correcta y el "Texto relevante" que justifica la respuesta.

Según el caso, también pueden aparecer:

3.  **`preguntas_PRL_varias_similares_descartadas.docx`:** Solo si usaste el filtro de duplicados y se descartó alguna pregunta. Para cada una indica el porcentaje de similitud y la pregunta del banco con la que coincide.
4.  **`preguntas_PRL_varias_no_validas.xlsx`:** Solo si alguna parte de la respuesta de la IA no se pudo aprovechar. Indica el tema, el fragmento de la respuesta y el **motivo**. Estas preguntas no se aceptan en silencio; se consideran no válidas cuando:
    *   les falta el enunciado;
    *   no tienen **4 opciones distintas** y no vacías (dos opciones iguales harían ambigua la respuesta correcta al barajarlas);
    *   la **respuesta correcta** falta, es ambigua o no es válida. Se acepta la letra (A, B, C o D), expresiones como "Opción B" o el texto de una de las opciones, pero se rechazan los números como `1` o `"2"`, porque no se sabe si cuentan desde 0 o desde 1;
    *   o la respuesta no contenía ninguna pregunta en formato JSON reconocible.

Además, las preguntas repetidas (mismo tema, mismo enunciado y mismas opciones, aunque estén en otro orden) que aparezcan en varios fragmentos o intentos se descartan automáticamente. Las preguntas con el mismo enunciado pero opciones distintas (por ejemplo, "Señala la afirmación correcta") se conservan.

**Tu siguiente paso sería leer este archivo de Word, corregir cualquier error que veas, y prepararlo para añadirlo a tu banco de preguntas principal, ¡pero eso lo veremos en el tutorial de la siguiente pestaña!**

¡Felicidades! Has usado con éxito la inteligencia artificial para automatizar la creación de preguntas de examen a partir de múltiples fuentes.

![](/_static/gifs/parte2-3_v01_parte3.gif)
