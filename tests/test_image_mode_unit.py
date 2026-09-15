from pyexamgenerator.question_generator import QuestionGenerator


def test_is_image_path_detects_supported_extensions():
    assert QuestionGenerator._is_image_path("a.png")
    assert QuestionGenerator._is_image_path("a.JPG")
    assert not QuestionGenerator._is_image_path("a.pdf")


def test_group_items_into_total_chunks_balances_items():
    items = [{"i": i} for i in range(5)]
    chunks = QuestionGenerator._group_items_into_total_chunks(items, 2)
    lengths = [len(chunk) for chunk in chunks]

    assert lengths == [3, 2]


def test_group_items_by_chunk_size_creates_expected_groups():
    items = [{"i": i} for i in range(5)]
    chunks = QuestionGenerator._group_items_by_chunk_size(items, 2)
    lengths = [len(chunk) for chunk in chunks]

    assert lengths == [2, 2, 1]


def test_build_generation_prompts_image_mode_returns_prompt_without_api_calls():
    generator = QuestionGenerator(api_key="dummy", model_name="models/gemini-2.5-flash")
    prompts_df = generator.build_generation_prompts(
        pdf_paths=["Tema Imagen 01.pdf"],
        prompt_type="PRL",
        input_mode="image",
        include_similar_questions_in_prompt=False,
    )

    assert len(prompts_df) == 1
    prompt_text = prompts_df.iloc[0]["Prompt"]
    assert "imágenes adjuntas" in prompt_text.lower()

