### Parte 4: El Toque Humano - Revisar y Aprobar las Preguntas

Antes de usar la siguiente pestaña, hay un paso vital que ocurre fuera de la aplicación: **tu revisión experta**. La IA es una herramienta fantástica, pero tú eres quien garantiza la calidad.

1.  **Abre el Archivo de Word:** Ve a tu carpeta de trabajo y abre el archivo que generamos en el paso anterior: `preguntas_LPRL_pendiente_de_revisar.docx`.

2.  **Revisa y Corrige:** Lee cada pregunta, sus opciones y la respuesta correcta.
    *   ¿Hay algún error gramatical? ¡Corrígelo!
    *   ¿Podría una opción ser más clara? ¡Mejórala!
    *   ¿La respuesta marcada como correcta es realmente la correcta según el texto? Si no, cambia la letra en la línea "Respuesta correcta:".

3.  **¡El Paso Clave! Cambia el Estado:** Para cada pregunta que consideres que está lista para ser usada en un examen, busca la línea `Estado: Pendiente de revisar` y cámbiala por `Estado: Aceptable`. Esto es como ponerle un sello de aprobación.

4.  **Guarda el Archivo:** Una vez que hayas revisado y aprobado tus preguntas, guarda el documento. Te recomiendo usar "Guardar como..." y darle un nombre nuevo para no confundirte, por ejemplo: **`preguntas_LPRL_REVISADO.docx`**.

Ahora que tenemos nuestro documento de Word revisado y aprobado, estamos listos para volver a ExamGenerator.

### Parte 5: Usando la Pestaña "Gestionar Banco de Preguntas"

Esta pestaña es tu centro de control para mantener y hacer crecer tu colección de preguntas. Se divide en dos grandes tareas.

#### Tarea 1: Generar un Archivo Excel (XLSX) desde tu Word Revisado

El programa no puede trabajar directamente con un archivo de Word. Primero, necesitamos convertir nuestro `.docx` revisado de nuevo a un formato de datos estructurado que la aplicación entienda: un archivo de Excel (`.xlsx`).

*   **Archivo DOCX Revisado:**
    *   **Qué es:** Aquí le indicas al programa dónde está el archivo de Word que acabas de revisar y guardar.
    *   **Acción para nuestro ejemplo:** Haz clic en el botón **"Seleccionar DOCX"** y elige tu archivo **`preguntas_LPRL_REVISADO.docx`**.

*   **Directorio de Salida (XLSX):**
    *   **Qué es:** La carpeta donde se guardará el nuevo archivo de Excel.
    *   **Acción para nuestro ejemplo:** Déjalo **en blanco**. Se guardará en tu carpeta de trabajo actual.

*   **Nombre del Nuevo Archivo XLSX:**
    *   **Qué es:** El nombre que quieres darle al archivo de Excel que se va a crear.
    *   **Acción para nuestro ejemplo:** Escribe un nombre descriptivo, como **`preguntas_LPRL_aceptadas`**. No necesitas añadir `.xlsx`, el programa lo hará por ti.

*   **Botón "Guardar XLSX Revisado":**
    *   **Qué es:** El botón que inicia la conversión.
    *   **Acción para nuestro ejemplo:** Haz clic en él. En un instante, la aplicación leerá tu documento de Word y creará un archivo `preguntas_LPRL_aceptadas.xlsx` en tu carpeta de trabajo.

¡Felicidades! Has convertido con éxito tus preguntas revisadas a un formato de datos limpio.

#### Tarea 2: Añadir tus Nuevas Preguntas al Banco Principal

Ahora vamos a fusionar las preguntas que acabamos de crear con tu colección principal de preguntas (tu "banco").

*   **Banco Existente:**
    *   **Qué es:** Este es tu archivo maestro, el Excel que contiene todas las preguntas que has acumulado y aprobado a lo largo del tiempo.
    *   **Acción para nuestro ejemplo:**
        *   Si es tu primera vez, no tendrás este archivo. ¡No hay problema! Crea un archivo de Excel en blanco y guárdalo como **`banco_principal.xlsx`**. Luego, haz clic en **"Seleccionar"** y elígelo.
        *   Si ya tienes un banco, selecciónalo aquí.

*   **Archivo a Añadir:**
    *   **Qué es:** El archivo de Excel con las nuevas preguntas que quieres añadir a tu banco principal.
    *   **Acción para nuestro ejemplo:** Haz clic en **"Seleccionar"** y elige el archivo que creamos en la tarea anterior: **`preguntas_LPRL_aceptadas.xlsx`**.

*   **Criterio de Duplicado:**
    *   **Qué es:** Le dice al programa cómo decidir si una pregunta nueva ya existe en tu banco principal. Es una regla para evitar repeticiones.
    *   **Pregunta Única (ignorar respuestas):** Elige esta opción si consideras que una pregunta es un duplicado solo si el **texto del enunciado** es idéntico. Es útil si quieres tener la misma pregunta con diferentes opciones de respuesta en tu banco.
    *   **Pregunta y Respuestas Iguales:** Esta es una comprobación más estricta. Una pregunta se considera duplicada solo si tanto el **enunciado como todas las opciones de respuesta** son idénticos a una pregunta que ya existe.
    *   **Acción para nuestro ejemplo:** Para mantener un banco de alta calidad, elegiremos la opción más estricta: **"Pregunta y Respuestas Iguales"**.

*   **Filtro de Estado:**
    *   **Qué es:** Te permite elegir qué preguntas del "Archivo a Añadir" quieres importar.
    *   **Añadir todas las preguntas:** Importará todas las preguntas del archivo, sin importar si su estado es "Aceptable" o "Pendiente de revisar".
    *   **Añadir solo con estado 'Aceptable':** Esta es la opción recomendada. Solo importará las preguntas a las que les pusimos el sello de "Aceptable" en el archivo de Word. Es tu control de calidad final.
    *   **Acción para nuestro ejemplo:** Haz clic en **"Añadir solo con estado 'Aceptable'"**.

*   **Botón "Añadir Preguntas sin Duplicados":**
    *   **Qué es:** El botón final que inicia el proceso de fusión.
    *   **Acción para nuestro ejemplo:** Haz clic en él.

### Parte 6: El Resultado - Tu Banco de Preguntas Actualizado

Después de hacer clic en el botón, la aplicación analizará ambos archivos y te mostrará una ventana emergente informándote cuántas preguntas nuevas (no duplicadas y con estado "Aceptable") ha encontrado.

Luego, te preguntará cómo quieres guardar el resultado. Tienes tres opciones:
*   **Sí:** Sobrescribe tu `banco_principal.xlsx` con la nueva versión que incluye las preguntas añadidas.
*   **No:** Te permite guardar el resultado como un archivo nuevo (por ejemplo, `banco_principal_actualizado.xlsx`). **Esta es la opción más segura si quieres conservar una copia de seguridad.**
*   **Cancelar:** Aborta la operación de guardado.

**Acción para nuestro ejemplo:** Haz clic en **"No"** y guarda el archivo como `banco_principal_v2.xlsx`.

¡Y ya está! Ve a tu carpeta de trabajo y abre tu nuevo archivo de Excel. Verás que ahora contiene las 4 preguntas de la LPRL que generamos, revisamos y añadimos. Tu banco de preguntas ha crecido, ¡y todo de forma organizada y sin duplicados