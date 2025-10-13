# Changelog

Todas las novedades de este proyecto están documentadas en este archivo.

## [0.1.0] - 2025-10-13

### ¡Lanzamiento Inicial! 🎉

Esta es la primera versión pública de ExamGenerator.

### Añadido
- Interfaz gráfica completa con tres pestañas para un flujo de trabajo integral.
- **Generación de Preguntas:**
    - Conexión con la API de Google Gemini para generar preguntas desde PDFs.
    - Soporte para prompts personalizados y plantillas (PRL, PM).
    - Procesamiento de PDFs por fragmentos para documentos largos.
    - Filtro de similitud para evitar preguntas duplicadas.
- **Gestión de Banco de Preguntas:**
    - Conversión de preguntas revisadas en formato DOCX a XLSX.
    - Fusión de bancos de preguntas con control de duplicados y filtro por estado.
- **Generación de Exámenes:**
    - Creación de múltiples versiones de exámenes (Tipo A, Tipo B) con preguntas y respuestas barajadas.
    - Selección granular de preguntas por tema.
    - Generación de hojas de respuesta y versiones para el profesor.
    - Exportación a Moodle XML para auto-corrección.
- **Documentación:**
    - Tutoriales completos y documentación de la API generada con Sphinx.
- **Empaquetado:**
    - Paquete instalable a través de `pip` y comando `examgenerator` para un fácil acceso.
