### Parte 7: Usando la Pestaña "Generar Exámenes"

Esta pestaña es tu imprenta personal de exámenes. Aquí tomarás las preguntas que has generado y curado, y las convertirás en documentos de examen completos, con múltiples versiones, hojas de respuesta y mucho más.

Para nuestro ejemplo, vamos a crear un examen de 5 preguntas (2 del tema `PRL - LPRL` y 3 del tema `PRL - RSP`), generando dos versiones diferentes (Tipo A y Tipo B).

#### Sección 1: Archivo Excel de Preguntas

*   **Qué es:** El punto de partida. Aquí debes seleccionar tu banco de preguntas principal, el archivo maestro que contiene todas tus preguntas aprobadas de todos los temas.
*   **Acción para nuestro ejemplo:** Haz clic en **"Seleccionar Archivo"** y elige tu archivo **`banco_principal.xlsx`** (el que actualizamos en la pestaña anterior).

#### Sección 2: Datos del Examen

Esta sección define la cabecera y la información básica que aparecerá en el examen.

*   **Asignatura:** El nombre de la materia.
    *   **Acción:** Escribe `Prevención de Riesgos Laborales`.
*   **Curso:** El año académico.
    *   **Acción:** Escribe `2024-2025`.
*   **Nombre del Examen:** El título del examen (ej. "Parcial 1", "Examen Final").
    *   **Acción:** Escribe `Examen Temas LPRL y RSP`.
*   **Número de Exámenes a Generar:** ¿Cuántas versiones diferentes del examen quieres crear? Cada versión tendrá las mismas preguntas, pero en un orden diferente y con las respuestas también barajadas.
    *   **Acción:** Escribe `2`.
*   **Nombres de los Exámenes (separados por coma):** Si quieres nombres específicos para cada versión (ej. "Modelo A", "Recuperación"), escríbelos aquí.
    *   **Acción:** Escribe `Tipo A,Tipo B`.

#### Sección 3: Selección de Preguntas por Tema

Aquí es donde decides exactamente qué preguntas incluir en tu examen. Tienes un control total.

*   **Seleccionar cantidad por tema:** Esta opción te muestra una lista de todos los temas disponibles en tu banco de preguntas y te permite elegir cuántas preguntas quieres de cada uno. Es muy visual e intuitiva.
*   **Mismo número de preguntas por tema:** Una opción rápida si quieres, por ejemplo, 2 preguntas de cada tema sin tener que especificarlo uno por uno.
*   **Diccionario de preguntas por tema:** La opción más potente para scripting, pero también útil aquí. Escribes directamente tu selección en formato `NombreDelTema:Cantidad`.
*   **Acción para nuestro ejemplo:**
    1.  Haz clic en la opción **"Seleccionar cantidad por tema"**.
    2.  Al seleccionar tu archivo Excel, la aplicación cargará automáticamente los temas. Verás dos filas en el área de selección: **`PRL - LPRL`** y **`PRL - RSP`**.
    3.  En el pequeño cuadro numérico (Spinbox) al lado de **`PRL - LPRL`**, selecciona **`2`**.
    4.  En el cuadro numérico al lado de **`PRL - RSP`**, selecciona **`3`**.
    Esto le dice al programa que cree un examen con 2 preguntas de la Ley y 3 del Reglamento.

#### Sección 4: Método de Selección

Una vez que le has dicho al programa *cuántas* preguntas quieres de cada tema, aquí le dices *cómo* debe elegirlas.

*   **azar:** El programa seleccionará las preguntas de forma completamente aleatoria de entre todas las disponibles para ese tema. **Esta es la mejor opción para crear exámenes justos y diferentes cada vez.**
*   **primeras:** Seleccionará las primeras preguntas que encuentre en el archivo Excel para ese tema.
*   **menos usadas:** Una función avanzada muy útil. El programa lleva un registro de cuántas veces se ha usado cada pregunta en exámenes anteriores y elegirá las que se hayan usado menos. ¡Perfecto para asegurar que todo el temario se evalúa a lo largo del tiempo!
*   **Acción para nuestro ejemplo:** Selecciona **"azar"** en el menú desplegable.

#### Sección 5: Estilo del Documento

Aquí personalizas el aspecto visual de tu examen en el archivo de Word.

*   **Márgenes (Superior, Inferior, Izquierdo, Derecho):** Define el espacio en blanco alrededor de la página, en pulgadas. Los valores por defecto suelen funcionar bien.
*   **Tamaño de Fuente:** El tamaño del texto de las preguntas y respuestas.
*   **Instrucciones Hoja de Respuestas:** El texto que aparecerá justo encima de la tabla de respuestas para guiar al alumno.
*   **Acción para nuestro ejemplo:** En "Instrucciones Hoja de Respuestas", escribe: `Marque con una "X" la casilla correspondiente a la respuesta correcta. No se permiten tachaduras.`

#### Sección 6: Configuración para Moodle

¡Una de las funciones más potentes! Si usas la plataforma online Moodle, ExamGenerator puede crear un archivo especial para que subas las preguntas del examen directamente a tu curso.

*   **Exportar a Moodle XML:** Marca esta casilla para activar la exportación.
*   **Penalización (-%):** En Moodle, puedes hacer que las respuestas incorrectas resten puntos. Aquí indicas el porcentaje negativo (ej. `-25` para que un error reste un 25% del valor de la pregunta).
*   **Texto Adicional Moodle XML:** Un texto extra para organizar tus preguntas dentro de Moodle.
*   **Acción para nuestro ejemplo:** **Deja la casilla desmarcada por ahora**.

#### Sección 7: Actualizar Archivo Excel con Uso

*   **Qué es:** Si marcas esta casilla, después de generar el examen, el programa abrirá tu `banco_principal.xlsx` y anotará qué preguntas se han utilizado y en qué examen. Esto alimenta la función "menos usadas" que vimos antes.
*   **Acción para nuestro ejemplo:** **Marca la casilla "Actualizar Archivo Excel con Uso"**. Es una buena práctica para mantener tu banco de preguntas siempre al día.

#### Sección 8: Directorio de Salida y ¡Generar!

*   **Directorio de Salida para Exámenes:** La carpeta donde se guardarán todos los archivos del examen.
*   **Acción para nuestro ejemplo:** Déjalo **en blanco** para que se guarden en tu carpeta de trabajo.
*   **Botón "Generar Exámenes":** ¡El momento de la verdad! Haz clic en este botón.

### Parte 8: ¡Tus Exámenes Están Listos!

Ve a tu carpeta de trabajo. Verás que se han creado varios archivos:

*   **`examen_Prevención de Riesgos Laborales_Examen Temas LPRL y RSP_24-25_Tipo A.docx`**: El examen para el alumno, listo para imprimir. Incluye la cabecera, las 5 preguntas seleccionadas al azar (2 de un tema, 3 del otro), y una hoja de datos y respuestas al final.
*   **`examen_..._Tipo B.docx`**: La segunda versión del examen. Contiene las mismas 5 preguntas, pero en un orden diferente y con las opciones de respuesta también barajadas.
*   **`examen_..._Tipo A_completo.docx`**: Una versión para el profesor. Es igual que el examen del alumno, pero cada pregunta incluye la respuesta correcta y el tema al que pertenece. ¡Perfecto para corregir!
*   **`examen_..._Tipo B_completo.docx`**: La versión del profesor para el Tipo B.
*   **`examen_..._Tipo A_completo.xlsx`** y **`..._Tipo B_completo.xlsx`**: Archivos de Excel con los datos exactos de cada examen.

Además, si abres tu archivo `banco_principal.xlsx`, verás que se ha añadido una nueva columna (`Examen Temas LPRL y RSP_24-25_uso`) y que la columna `Veces usada en examen` se ha actualizado para las 5 preguntas que se incluyeron en el examen.

¡Felicidades! Has completado todo el ciclo: desde múltiples PDFs en bruto hasta un examen multi-tema profesional y listo para entregar, manteniendo tu banco de preguntas actualizado automáticamente.