# archivo: convert_docx_to_xlsx.py

from examgenerator.question_bank_manager import QuestionBankManager
import os

# --- Configuración ---
# Cambia estas rutas a tus archivos reales
REVISED_DOCX_PATH = "ruta/a/tus/preguntas_revisadas.docx"
OUTPUT_XLSX_FILENAME = "preguntas_revisadas_desde_script.xlsx"
OUTPUT_DIRECTORY = "bancos_convertidos" # Opcional, si no se especifica, se guarda en la misma carpeta que el DOCX

# --- Lógica del Script ---

def main():
    print("--- Iniciando la conversión de DOCX a XLSX ---")

    # 1. Verificar que el archivo de entrada existe
    if not os.path.exists(REVISED_DOCX_PATH):
        print(f"Error: El archivo de entrada no se encontró en '{REVISED_DOCX_PATH}'")
        return

    # 2. Crear una instancia del gestor
    manager = QuestionBankManager()

    # 3. Llamar a la función de conversión
    print(f"Leyendo preguntas desde: {REVISED_DOCX_PATH}")
    print(f"Se guardará como: {os.path.join(OUTPUT_DIRECTORY, OUTPUT_XLSX_FILENAME)}")
    
    try:
        # Esta función lee el DOCX y guarda el XLSX en un solo paso
        saved_path = manager.generate_excel_from_docx(
            docx_path=REVISED_DOCX_PATH,
            excel_output_filename=OUTPUT_XLSX_FILENAME,
            output_dir=OUTPUT_DIRECTORY
        )

        # 4. Comprobar el resultado
        if saved_path:
            print("\n--- ¡Conversión completada con éxito! ---")
            print(f"Archivo XLSX guardado en: {saved_path}")
        else:
            print("\n--- La conversión falló. ---")
            print("Revisa la consola para ver posibles mensajes de error del gestor.")

    except Exception as e:
        print(f"\nOcurrió un error inesperado durante el proceso: {e}")

if __name__ == "__main__":
    main()