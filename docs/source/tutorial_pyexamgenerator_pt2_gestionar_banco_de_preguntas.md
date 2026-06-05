# Uso de la pestaña "Gestionar Banco de Preguntas"

## Parte 4: Revisar y aprobar las preguntas

Antes de usar la siguiente pestaña, hay un paso vital que ocurre fuera de la aplicación: **tu revisión experta**. La IA es una herramienta fantástica, pero tú eres quien garantiza la calidad.

1.  **Abre el Archivo de Word:** Ve a tu carpeta de trabajo y abre el archivo `preguntas_PRL_varias_pendiente_de_revisar.docx`.

2.  **Revisa y Corrige:** Lee cada una de las 6 preguntas, sus opciones y la respuesta correcta.
    *   ¿Hay algún error gramatical? ¡Corrígelo!
    *   ¿Podría una opción ser más clara? ¡Mejórala!
    *   ¿La respuesta marcada como correcta es realmente la correcta según el texto? Si no, cambia la letra en la línea "Respuesta correcta:".

3.  **¡El Paso Clave! Cambia el Estado:** Para cada pregunta que consideres que está lista para ser usada en un examen, busca la línea `Estado: Pendiente de revisar` y cámbiala por `Estado: Aceptable`. **No te preocupes por el nombre del tema en este paso, lo ajustaremos más eficientemente después.**

4.  **Guarda el Archivo:** Una vez que hayas revisado y aprobado tus preguntas, usa "Guardar como..." y dale un nombre nuevo para no confundirte, por ejemplo: **`preguntas_PRL_varias_revisadas.docx`**.

Ahora que tenemos nuestro documento de Word revisado y aprobado, estamos listos para volver a pyexamgenerator.

![](/_static/gifs/parte4_v01.gif)

## Parte 5: Usando la pestaña "Gestionar Banco de Preguntas"

Esta pestaña es tu centro de control para mantener y hacer crecer tu colección de preguntas.

### Tarea 1: Generar un archivo Excel (XLSX) desde tu Word revisado

El programa no puede trabajar directamente con un archivo de Word. Primero, necesitamos convertir nuestro `.docx` revisado de nuevo a un formato de datos estructurado que la aplicación entienda: un archivo de Excel (`.xlsx`).

*   **Archivo DOCX Revisado:**
    *   **Acción:** Haz clic en el botón **"Seleccionar DOCX"** y elige tu archivo **`preguntas_PRL_varias_revisadas.docx`**.

*   **Directorio de Salida (XLSX):**
    *   **Acción:** Déjalo **en blanco**. Se guardará en tu carpeta de trabajo actual.

*   **Nombre del Nuevo Archivo XLSX:**
    *   **Acción:** Escribe un nombre descriptivo, como **`preguntas_PRL_varias_aceptadas`**.

*   **Botón "Guardar XLSX Revisado":**
    *   **Acción:** Haz clic en él. En un instante, la aplicación leerá tu documento de Word y creará un archivo `preguntas_PRL_varias_aceptadas.xlsx` en tu carpeta de trabajo.

![](/_static/gifs/parte5_tarea1_v01.gif)

### Tarea 1.5: Organizar los nombres de los temas

Ahora tenemos un archivo Excel limpio con nuestras preguntas aprobadas. Antes de fusionarlo, vamos a darle los nombres de tema definitivos.

1.  **Abre el Archivo de Excel:** Ve a tu carpeta de trabajo y abre el archivo que acabamos de crear: **`preguntas_PRL_varias_aceptadas.xlsx`**.
2.  **Edita la Columna "Tema":**
    *   Para las preguntas que vinieron del `RD 31-95...`, reemplaza el nombre largo del archivo en la columna **Tema** por **`PRL - LPRL`**.
    *   Para las preguntas que vinieron del `RD 39-97...`, reemplaza el nombre largo del archivo por **`PRL - RSP`**.
3.  **Guarda y Cierra** el archivo de Excel.

Ten en cuenta que este paso es opcional. Si desde el principio, hubiéramos llamado a los pdfs "Tema 1.pdf" y "Tema 2.pdf", no haría falta modificarlos en el archivo Excel.

¡Perfecto! Ahora tienes un lote de preguntas de alta calidad, revisadas y perfectamente organizadas por temas, listas para ser añadidas a tu colección principal.

![](/_static/gifs/parte5_tarea1.5_v01.gif)

### Tarea 2: Añadir tus nuevas preguntas al banco principal

Ahora vamos a fusionar las preguntas de nuestros dos nuevos temas con tu colección principal de preguntas (tu "banco").

*   **Banco Existente:**
    *   **Acción:** Haz clic en **"Seleccionar"** y elige tu archivo maestro, **`banco_principal.xlsx`**.

*   **Archivo a Añadir:**
    *   **Acción:** Haz clic en **"Seleccionar"** y elige el archivo que acabamos de editar: **`preguntas_PRL_varias_aceptadas.xlsx`**.

*   **Criterio de Duplicado:**
    *   **Acción:** Elige **"Pregunta y Respuestas Iguales"** para la comprobación más estricta.

*   **Filtro de Estado:**
    *   **Acción:** Elige **"Añadir solo con estado 'Aceptable'"**. Esto asegura que solo las preguntas que has aprobado personalmente entren en tu banco principal.

*   **Botón "Añadir Preguntas sin Duplicados":**
    *   **Acción:** Haz clic en él.

Después de hacer clic en el botón, la aplicación analizará ambos archivos y te mostrará una ventana emergente informándote cuántas preguntas nuevas (no duplicadas y con estado "Aceptable") ha encontrado.

Luego, te preguntará cómo quieres guardar el resultado. Tienes tres opciones:
*   **Sí:** Sobrescribe tu `banco_principal.xlsx` con la nueva versión que incluye las preguntas añadidas.
*   **No:** Te permite guardar el resultado como un archivo nuevo.
*   **Cancelar:** Aborta la operación de guardado.

**Acción para nuestro ejemplo:** Haz clic en **"Sí"** para actualizar directamente tu banco principal.

¡Y ya está! Ve a tu carpeta de trabajo y abre tu archivo `banco_principal.xlsx`. Verás que ahora contiene las 6 preguntas de los temas **`PRL - LPRL`** y **`PRL - RSP`** que generamos, revisamos y añadimos. Tu banco de preguntas ha crecido, ¡y todo de forma organizada y sin duplicados

![](/_static/gifs/parte5_tarea2_v01.gif)

### Tarea 3: Actualizar el banco con uno o varios exámenes ya generados

Si marcaste **"Actualizar Archivo Excel con Uso"** al generar un examen, el banco ya queda al día. Pero si generaste exámenes sin esa opción (o lo hiciste desde otro equipo o en otra sesión), puedes registrar su uso *a posteriori* con la sección **"Actualizar Banco con Exámenes Existentes"**. Puedes registrar **varios exámenes de una sola vez**, dándole a cada uno su propia etiqueta.

*   **Banco a Actualizar:**
    *   **Acción:** Haz clic en **"Seleccionar"** y elige tu archivo maestro, **`banco_principal.xlsx`**.

*   **Exámenes a registrar:**
    *   **Acción:** Haz clic en **"Añadir..."** y elige uno o varios archivos **`..._completo.xlsx`** que produjo la pestaña *Generar Exámenes* (cada uno contiene las preguntas que se usaron en ese examen). Cada examen aparece en la lista con tres columnas: el **archivo**, su **etiqueta** y la **"Columna en XLSX"** que realmente se escribirá (sin tildes ni caracteres especiales; por ejemplo `Evaluación` se guardará como `Evaluacion`, no como `Evaluaci_n`).
    *   **Editar la etiqueta:** Haz **doble clic** sobre una fila (o selecciónala y pulsa **"Editar etiqueta"**) y escribe el nombre para su columna de uso, por ejemplo **`Parcial1_24-25`**. Cada examen tendrá su propia columna `<etiqueta>_uso`.
    *   **Quitar / Limpiar:** Usa **"Quitar"** para eliminar el examen seleccionado o **"Limpiar"** para vaciar la lista.

*   **Etiqueta automática (desde el nombre del archivo):** si tus archivos tienen nombres largos y descriptivos, puedes generar las etiquetas automáticamente en lugar de escribirlas a mano:
    *   **Delimitador:** el carácter por el que se parte el nombre del archivo (por defecto **`_`**).
    *   **Partes a conservar:** qué trozos quieres conservar, indicados por su posición. Se numeran desde **1** (la primera parte); admite **rangos** `a:b` (ambos incluidos) e **índices negativos** contados desde el final (`-1` es la última parte). Por ejemplo, para `examen_Prevención_Industrial_de_Riesgos_..._25_26_1A_completo.xlsx`, la expresión **`2:3, -4:-2`** produce la etiqueta `Prevención_Industrial_25_26_1A`. Si lo dejas en blanco, se usa el nombre completo del archivo.
    *   **Botón "Aplicar a la lista":** recalcula la etiqueta de **todos** los exámenes de la lista con el delimitador y las partes indicados. (Los exámenes que añadas después también tomarán su etiqueta inicial con esa misma configuración.) Puedes seguir ajustando cualquier etiqueta a mano con "Editar etiqueta".

*   **Botón "Actualizar Banco con Exámenes":**
    *   **Acción:** Haz clic en él. La aplicación empareja por enunciado las preguntas de **cada** examen con las del banco (el orden de las respuestas se baraja en el examen, por eso el cruce se hace por el texto de la pregunta), marca cada pregunta usada en la columna `<etiqueta>_uso` correspondiente y recalcula la columna `Veces usada en examen` sumando todas las columnas de uso. Te mostrará un resumen con las coincidencias de cada examen y después te preguntará si quieres sobrescribir el banco o guardar una copia, igual que en la Tarea 2.

Esto alimenta la opción **"menos usadas"** de la pestaña *Generar Exámenes*, manteniendo el reparto de preguntas equilibrado a lo largo del curso.