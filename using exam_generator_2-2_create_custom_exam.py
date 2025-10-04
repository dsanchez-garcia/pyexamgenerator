# archivo: create_custom_exam.py

from examgenerator.exam_generator import ExamGenerator
import os
import pandas as pd # Necesario si quieres construir el dict de temas dinámicamente

# --- CONFIGURACIÓN GENERAL ---
BANK_FILE_PATH = "ruta/a/tu/banco_principal.xlsx"
OUTPUT_DIRECTORY = "examenes_personalizados"

# --- METADATOS DEL EXAMEN ---
EXAM_METADATA = {
    "subject": "Calidad, Seguridad y Protección Ambiental",
    "exam": "Examen Final",
    "course": "24-25"
}

# --- ESTRUCTURA Y SELECCIÓN DE PREGUNTAS ---
# Opción 1: Definir explícitamente la estructura del examen (la más común en scripting)
QUESTIONS_PER_TOPIC_CONFIG = {
    "TEMA 01_Introducción": 3,
    "TEMA 02_Marco normativo": 3,
    "TEMA 05_Inspecciones de seguridad": 5
}

# Opción 2: Mismo número de preguntas para todos los temas (construcción dinámica)
# Descomenta este bloque si quieres usar esta lógica
# try:
#     df_bank = pd.read_excel(BANK_FILE_PATH)
#     all_topics = df_bank['Tema'].unique()
#     QUESTIONS_PER_TOPIC_CONFIG = {topic: 2 for topic in all_topics} # 2 preguntas de cada tema
#     print("Configuración de preguntas generada dinámicamente:")
#     print(QUESTIONS_PER_TOPIC_CONFIG)
# except Exception as e:
#     print(f"No se pudo generar la configuración de temas dinámicamente: {e}")
#     QUESTIONS_PER_TOPIC_CONFIG = {}


SELECTION_CONFIG = {
    "selection_method": "menos usadas", # "azar", "primeras", "menos usadas"
    "exam_names": ["Modelo A", "Modelo B", "Modelo C"], # Nombres específicos para cada versión
}

# --- CONFIGURACIÓN DE ESTILO Y EXPORTACIÓN ---
STYLE_CONFIG = {
    "top_margin": 1.0,
    "bottom_margin": 1.0,
    "left_margin": 0.75,
    "right_margin": 0.75,
    "font_size": 10,
    "answer_sheet_instructions": "Marque con una 'X' la respuesta correcta. No se permiten tachaduras."
}

EXPORT_CONFIG = {
    "export_moodle_xml": True,
    "xml_cat_additional_text": "Examen Final 24-25",
    "penalty": -33, # Penalización del 33%
    "update_excel": True # Actualizará el banco con las estadísticas de uso
}

# --- LÓGICA DEL SCRIPT ---

def main():
    print("--- Iniciando la generación de exámenes personalizados ---")

    if not os.path.exists(BANK_FILE_PATH):
        print(f"Error: El archivo del banco de preguntas no se encontró en '{BANK_FILE_PATH}'")
        return

    exam_gen = ExamGenerator()

    try:
        # Usamos el operador ** para "desempaquetar" los diccionarios de configuración
        # en argumentos para la función. Esto mantiene el código muy limpio.
        exam_gen.generate_exam_from_excel(
            bank_excel_path=BANK_FILE_PATH,
            output_dir=OUTPUT_DIRECTORY,
            questions_per_topic=QUESTIONS_PER_TOPIC_CONFIG,
            
            **EXAM_METADATA,
            **SELECTION_CONFIG,
            **STYLE_CONFIG,
            **EXPORT_CONFIG,
            
            # Parámetros adicionales importantes para scripting
            check=False, # Desactiva la previsualización interactiva
            verbose=True # Muestra más información de progreso en la consola
        )

        print(f"\n--- ¡Generación de exámenes completada con éxito! ---")
        print(f"Los archivos han sido guardados en la carpeta: '{OUTPUT_DIRECTORY}'")

    except Exception as e:
        print(f"\nOcurrió un error inesperado durante la generación: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()