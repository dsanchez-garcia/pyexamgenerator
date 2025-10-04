# archivo: merge_question_banks.py

from examgenerator.question_bank_manager import QuestionBankManager
import os

# --- Configuración ---
# Cambia estas rutas a tus archivos reales
EXISTING_BANK_PATH = "ruta/a/tu/banco_principal.xlsx"
REVIEWED_QUESTIONS_PATH = "ruta/a/tus/preguntas_a_anadir.xlsx"
FINAL_OUTPUT_PATH = "ruta/a/tu/banco_principal_actualizado.xlsx" # Dónde guardar el resultado final

# --- Opciones de Fusión (¡Aquí está el poder del scripting!) ---
# Criterio para duplicados:
# Opción 1: Solo el enunciado de la pregunta debe ser único
DUPLICATE_CRITERIA = ['Pregunta']
# Opción 2: El enunciado Y TODAS las respuestas deben ser idénticas para ser un duplicado
# DUPLICATE_CRITERIA = ['Pregunta', 'Respuesta A', 'Respuesta B', 'Respuesta C', 'Respuesta D']

# Filtro de estado:
# Opción True: Solo añadir preguntas con la columna 'Estado' igual a 'Aceptable'
ADD_ONLY_ACCEPTABLE = True
# Opción False: Añadir todas las preguntas del archivo, sin importar su estado
# ADD_ONLY_ACCEPTABLE = False

# --- Lógica del Script ---

def main():
    print("--- Iniciando la fusión de bancos de preguntas ---")

    # 1. Verificar que los archivos de entrada existen
    if not os.path.exists(EXISTING_BANK_PATH) or not os.path.exists(REVIEWED_QUESTIONS_PATH):
        print("Error: Uno o ambos archivos de entrada no se encontraron.")
        return

    # 2. Crear una instancia del gestor
    manager = QuestionBankManager()

    print(f"Banco principal: {EXISTING_BANK_PATH}")
    print(f"Preguntas a añadir: {REVIEWED_QUESTIONS_PATH}")
    print(f"Criterio de duplicado: {'Solo enunciado' if len(DUPLICATE_CRITERIA) == 1 else 'Enunciado y respuestas'}")
    print(f"Añadir solo 'Aceptables': {ADD_ONLY_ACCEPTABLE}")

    try:
        # 3. Llamar a la función para añadir preguntas (sin guardar aún)
        # Esta función devuelve el número de preguntas añadidas y el DataFrame actualizado
        added_count, updated_df = manager.add_questions_without_duplicates(
            existing_bank_path=EXISTING_BANK_PATH,
            reviewed_questions_path=REVIEWED_QUESTIONS_PATH,
            duplicate_check_columns=DUPLICATE_CRITERIA,
            add_only_acceptable=ADD_ONLY_ACCEPTABLE
        )

        # 4. Procesar el resultado
        if added_count == -1:
            print("\n--- La fusión falló debido a un error al leer los archivos. ---")
            return
        
        if added_count > 0:
            print(f"\nSe encontraron {added_count} preguntas nuevas para añadir.")
            
            # 5. Guardar el DataFrame actualizado en un nuevo archivo
            print(f"Guardando el banco de preguntas actualizado en: {FINAL_OUTPUT_PATH}")
            saved_path = manager.save_dataframe_to_excel(
                df=updated_df,
                filepath=FINAL_OUTPUT_PATH,
                overwrite=True # Sobrescribir si el archivo de salida ya existe
            )
            if saved_path:
                print("\n--- ¡Fusión y guardado completados con éxito! ---")
            else:
                print("\n--- Error al guardar el archivo final. ---")
        else:
            print("\n--- No se encontraron preguntas nuevas para añadir. El banco principal no ha cambiado. ---")

    except Exception as e:
        print(f"\nOcurrió un error inesperado durante el proceso: {e}")

if __name__ == "__main__":
    main()