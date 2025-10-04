# archivo: create_simple_exam.py

from examgenerator.exam_generator import ExamGenerator
import os

# --- Configuración ---
BANK_FILE_PATH = "ruta/a/tu/banco_principal.xlsx"
OUTPUT_DIRECTORY = "examenes_generados"

# --- Metadatos del Examen ---
SUBJECT = "Calidad, Seguridad y Protección Ambiental"
EXAM_NAME = "Parcial 1"
COURSE = "24-25"

# --- Lógica del Script ---

def main():
    print("--- Iniciando la generación de exámenes ---")

    # 1. Verificar que el banco de preguntas existe
    if not os.path.exists(BANK_FILE_PATH):
        print(f"Error: El archivo del banco de preguntas no se encontró en '{BANK_FILE_PATH}'")
        return

    # 2. Crear una instancia del generador de exámenes
    exam_gen = ExamGenerator()

    try:
        # 3. Llamar al método principal con la configuración básica
        # Al no especificar 'questions_per_topic', se usarán todas las preguntas 'Aceptables'.
        # Al no especificar 'exam_names', se usarán nombres genéricos (Tipo 1, Tipo 2, etc.).
        exam_gen.generate_exam_from_excel(
            bank_excel_path=BANK_FILE_PATH,
            output_dir=OUTPUT_DIRECTORY,
            subject=SUBJECT,
            exam=EXAM_NAME,
            course=COURSE,
            num_exams=2, # Generará 'Tipo 1' y 'Tipo 2'
            selection_method="azar" # Selecciona preguntas aleatoriamente
        )

        print("\n--- ¡Generación de exámenes completada con éxito! ---")
        print(f"Los archivos han sido guardados en la carpeta: '{OUTPUT_DIRECTORY}'")

    except Exception as e:
        print(f"\nOcurrió un error inesperado durante la generación: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()