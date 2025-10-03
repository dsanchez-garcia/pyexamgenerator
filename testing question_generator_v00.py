from examgenerator.question_generator import QuestionGenerator
import os

my_api_key = os.environ.get("GEMINI_API_KEY")


if __name__ == '__main__':
    # api_key = "my api key"  # Reemplaza con tu API key de Gemini
    api_key = my_api_key

    # model_name = 'models/gemini-2.5-flash-lite-preview-06-17'
    # model_name = 'models/gemini-2.5-pro'
    # model_name = 'models/gemini-exp-1206' # No ha funcionado
    # model_name = 'models/gemini-pro-latest'
    # model_name = 'models/gemma-3-1b-it' # No ha funcionado
    model_name = 'models/gemini-robotics-er-1.5-preview'


    output = model_name.split('/')[-1]
    generator = QuestionGenerator(
        api_key=api_key,
        model_name=model_name
    )
    pdf_files = [
        'TEMA 05_Inspecciones de seguridad.pdf',
        # 'TEMA 08_Equipos de proteccion individual.pdf'
    ]

    # Ejemplo 1: Procesamiento normal (todo el texto a la vez)
    # questions_df = generator.generate_multiple_choice_questions(
    #     pdf_files,
    #     prompt_type="PRL",
    #     num_questions=2,
    #     output_filename="banco_de_preguntas",
    #     generate_docx=True
    # )

    # Ejemplo 3: Procesamiento por páginas
    questions_df_pages = generator.generate_multiple_choice_questions(
        pdf_files,
        prompt_type="PRL",
        # output_filename=model_name,
        # output_filename='gemini-2.5-flash-lite-preview-06-17',
        output_filename=output,
        generate_docx=True,
        process_by_pages=True,  # Activar procesamiento por páginas
        num_questions_per_chunk_target=1,
        pages_per_chunk=1,  # Procesar cada página individualmente
        # existing_bank_path="examen_PIR.xlsx"
    )

    # Ejemplo 4: Procesamiento por grupos de páginas
    # questions_df_page_groups = generator.generate_multiple_choice_questions(
    #     pdf_files,
    #     prompt_type="PRL",
    #     output_filename="banco_de_preguntas_grupos_paginas",
    #     generate_docx=True,
    #     process_by_pages=True,  # Activar procesamiento por páginas
    #     questions_per_page=3,  # Generar 3 preguntas por cada página
    #     pages_per_chunk=2  # Agrupar cada 2 páginas para procesarlas juntas
    # )

    # Puedes usar cualquiera de los DataFrames para inspeccionar las preguntas generadas
