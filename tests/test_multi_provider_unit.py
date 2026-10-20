"""Tests for the multi-provider generation (Gemini/OpenAI/Anthropic) and the manual (no API) workflow."""
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from pyexamgenerator.ai_providers import (
    AIProviderError,
    AnthropicClient,
    BaseAIClient,
    GeminiClient,
    InvalidAPIKeyError,
    InvalidRequestError,
    ModelNotFoundError,
    OpenAIClient,
    QuotaExceededError,
    ServiceOverloadedError,
    create_ai_client,
    get_api_key_from_env,
    resolve_provider,
)
from pyexamgenerator.question_bank_manager import QuestionBankManager
from pyexamgenerator.question_generator import QUESTION_COLUMNS, QuestionGenerator
from pyexamgenerator.question_parsing import QUESTIONS_JSON_SCHEMA, parse_questions_response

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PDF = PROJECT_ROOT / "RD 31-95 LPRL_fragmento.pdf"


def _question(statement, answer="B", options=None):
    return {
        "Pregunta": statement,
        "Opciones": options or ["uno", "dos", "tres", "cuatro"],
        "Respuesta correcta": answer,
        "Texto relevante": "texto",
    }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    json.dumps([_question("¿P?")]),
    "Aquí tienes:\n```json\n" + json.dumps([_question("¿P?")], ensure_ascii=False, indent=2) + "\n```\n¡Suerte!",
    json.dumps({"preguntas": [_question("¿P?")]}),
    "{'Pregunta': '¿P?', 'Opciones': ['uno', 'dos', 'tres', 'cuatro'], 'Respuesta correcta': 'b', "
    "'Texto relevante': None}",
    'Claro: [{"Pregunta": "¿P?", "Opciones": ["uno", "dos", "tres", "cuatro"], '
    '"Respuesta correcta": "B) dos", "Texto relevante": "texto",}]',
])
def test_parser_accepts_api_and_web_chat_formats(text):
    questions, errors = parse_questions_response(text)

    assert errors == []
    assert len(questions) == 1
    assert questions[0]["Pregunta"] == "¿P?"
    assert questions[0]["Opciones"] == ["uno", "dos", "tres", "cuatro"]
    assert questions[0]["Respuesta correcta"] == "B"


def test_parser_recovers_complete_questions_from_truncated_and_continued_answers():
    first = json.dumps([_question("P1"), _question("P2")])[:-40]  # cut inside the second question
    text = f"```json\n{first}\n```\nContinúo:\n```json\n{json.dumps([_question('P3', 'D')])}\n```"

    questions, _errors = parse_questions_response(text)

    assert [q["Pregunta"] for q in questions] == ["P1", "P3"]
    assert questions[1]["Respuesta correcta"] == "D"


def test_parser_handles_braces_and_blank_lines_inside_strings():
    text = json.dumps([_question("¿Qué significa {x}?\n\nExplica.")])

    questions, errors = parse_questions_response(text)

    assert errors == []
    assert questions[0]["Pregunta"].startswith("¿Qué significa {x}?")


def test_parser_normalizes_labels_aliases_and_answer_text():
    text = json.dumps([{
        "enunciado": "Pregunta 3: ¿Capital de Francia?",
        "opciones": {"a": "Madrid", "b": "París", "c": "Roma", "d": "Lisboa"},
        "respuesta_correcta": "París",
        "justificacion": ["París es", "la capital"],
    }, {
        "question": "Which?",
        "options": ["A) one", "B) two", "C) three", "D) four"],
        "correct_answer": "(d)",
    }])

    questions, errors = parse_questions_response(text)

    assert errors == []
    assert questions[0]["Pregunta"] == "¿Capital de Francia?"
    assert questions[0]["Respuesta correcta"] == "B"
    assert questions[0]["Texto relevante"] == "París es la capital"
    assert questions[1]["Opciones"] == ["one", "two", "three", "four"]
    assert questions[1]["Respuesta correcta"] == "D"


def test_parser_reports_invalid_questions_without_executing_code():
    text = json.dumps([
        _question("Tres opciones", options=["a", "b", "c"]),
        _question("Letra inválida", answer="E"),
        {"Pregunta": "__import__('os').system('echo hacked')", "Opciones": "x", "Respuesta correcta": "A"},
    ])

    questions, errors = parse_questions_response(text)

    assert questions == []
    assert len(errors) == 3
    assert all("Motivo" in error for error in errors)


def test_parser_rejects_ambiguous_numeric_answers_and_repeated_options():
    text = json.dumps([
        {**_question("Número"), "Respuesta correcta": 1},
        _question("Repetidas", options=["Sí", "No", "sí", "Quizá"]),
    ])

    questions, errors = parse_questions_response(text)

    assert questions == []
    assert [e["Motivo"].split()[0] for e in errors] == ["Respuesta", "Hay"]


def test_parser_answer_text_starting_with_letter_is_matched_by_option_text():
    options = ["Madrid", "A partir de 50 trabajadores", "Nunca", "Siempre"]
    questions, _ = parse_questions_response(json.dumps([_question("¿Cuándo?", "A partir de 50 trabajadores", options)]))

    assert questions[0]["Respuesta correcta"] == "B"


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
def test_resolve_provider_accepts_aliases_and_labels():
    assert resolve_provider(None) == "gemini"
    assert resolve_provider("Google AI Studio") == "gemini"
    assert resolve_provider("ChatGPT") == "openai"
    assert resolve_provider("Anthropic (Claude)") == "anthropic"
    with pytest.raises(ValueError):
        resolve_provider("otro")


def test_env_api_keys_per_provider(monkeypatch):
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")

    assert get_api_key_from_env("gemini") == "g-key"
    assert get_api_key_from_env("openai") is None
    assert get_api_key_from_env("claude") == "a-key"
    with pytest.raises(InvalidAPIKeyError):
        create_ai_client("openai", "TU_CLAVE_API", "gpt-5")


def test_gemini_client_sends_attachments_and_json_mode():
    calls = []

    def generate_content(model, contents, config):
        calls.append((model, contents, config))
        return SimpleNamespace(text="[]")

    sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    client = GeminiClient("key", "gemini-2.5-flash", sdk_client=sdk)

    client.generate("prompt", [{"bytes": b"%PDF", "mime_type": "application/pdf", "name": "a.pdf"}])

    model, contents, config = calls[0]
    assert model == "gemini-2.5-flash"
    assert contents[-1] == "prompt"
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == QUESTIONS_JSON_SCHEMA


def test_structured_output_falls_back_to_plain_text_when_rejected():
    calls = []

    class BadRequest(Exception):
        status_code = 400

    def create(**kwargs):
        calls.append(kwargs)
        if "text" in kwargs:
            raise BadRequest("response_format json_schema is not supported with this model")
        return SimpleNamespace(output_text="[]", status="completed")

    client = OpenAIClient("key", "old-model", sdk_client=SimpleNamespace(responses=SimpleNamespace(create=create)))

    assert client.generate("prompt") == "[]"
    assert client.generate("prompt") == "[]"
    assert ["text" in call for call in calls] == [True, False, False]
    assert client.structured_output is False


def test_invalid_gemini_key_reported_as_auth_error_without_disabling_structured_output():
    class GeminiBadKey(Exception):
        code = 400

    def generate_content(**_kwargs):
        raise GeminiBadKey("400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key.")

    sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    client = GeminiClient("bad", "gemini-flash-latest", sdk_client=sdk)

    with pytest.raises(InvalidAPIKeyError):
        client.generate("prompt")
    assert client.structured_output is True


def test_openai_client_uses_responses_api_with_files_and_images():
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output_text="[]", status="completed")

    sdk = SimpleNamespace(responses=SimpleNamespace(create=create))
    client = OpenAIClient("key", "gpt-5", sdk_client=sdk)

    client.generate("prompt", [
        {"bytes": b"%PDF", "mime_type": "application/pdf", "name": "a.pdf"},
        {"bytes": b"png", "mime_type": "image/png", "name": "a.png"},
    ])

    content = captured["input"][0]["content"]
    assert captured["model"] == "gpt-5"
    assert content[0]["type"] == "input_file" and content[0]["file_data"].startswith("data:application/pdf;base64,")
    assert content[1]["type"] == "input_image" and content[1]["image_url"].startswith("data:image/png;base64,")
    assert content[1]["detail"] == "auto"
    assert captured["text"]["format"]["type"] == "json_schema"
    assert content[2] == {"type": "input_text", "text": "prompt"}


def test_anthropic_client_streams_and_joins_text_blocks():
    captured = {}

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return SimpleNamespace(stop_reason="end_turn", content=[
                SimpleNamespace(type="text", text="[{"), SimpleNamespace(type="thinking", thinking="..."),
                SimpleNamespace(type="text", text="}]"),
            ])

    def stream(**kwargs):
        captured.update(kwargs)
        return Stream()

    sdk = SimpleNamespace(messages=SimpleNamespace(stream=stream))
    client = AnthropicClient("key", "claude-opus-5-5", temperature=0.2, sdk_client=sdk)

    text = client.generate("prompt", [{"bytes": b"%PDF", "mime_type": "application/pdf"}])

    assert text == "[{}]"
    assert captured["max_tokens"] == AnthropicClient.DEFAULT_MAX_OUTPUT_TOKENS
    assert "temperature" not in captured
    assert captured["output_config"]["format"]["schema"] == QUESTIONS_JSON_SCHEMA
    blocks = captured["messages"][0]["content"]
    assert blocks[0]["type"] == "document" and blocks[0]["source"]["media_type"] == "application/pdf"
    assert blocks[-1] == {"type": "text", "text": "prompt"}


@pytest.mark.parametrize("status, expected", [
    (401, InvalidAPIKeyError),
    (429, QuotaExceededError),
    (503, ServiceOverloadedError),
    (529, ServiceOverloadedError),
    (404, ModelNotFoundError),
    (400, InvalidRequestError),
    (413, InvalidRequestError),
])
def test_provider_errors_are_translated(status, expected):
    class FakeSDKError(Exception):
        status_code = status

    client = OpenAIClient("key", "gpt-5", sdk_client=SimpleNamespace())

    translated = client.translate_error(FakeSDKError("boom"))

    assert type(translated) is expected


# ---------------------------------------------------------------------------
# QuestionGenerator with a fake provider
# ---------------------------------------------------------------------------
class FakeClient(BaseAIClient):
    provider = "anthropic"

    def __init__(self, answers):
        super().__init__("key", "fake-model", sdk_client=object())
        self.answers = list(answers)
        self.calls = []

    def _generate(self, client, prompt, attachments, structured):
        self.calls.append((prompt, attachments))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
@pytest.mark.parametrize("input_mode, mime_type", [("text", None), ("image", "image/png"), ("pdf", "application/pdf")])
def test_generation_with_any_provider_and_input_mode(tmp_path, input_mode, mime_type):
    answers = [f"```json\n{json.dumps([_question(f'P{i}a'), _question(f'P{i}b')])}\n```" for i in range(10)]
    fake = FakeClient(answers)
    generator = QuestionGenerator(ai_client=fake)

    df = generator.generate_multiple_choice_questions(
        [str(SAMPLE_PDF)], "PRL", num_questions_per_chunk_target=2, output_dir=str(tmp_path),
        output_filename="out", input_mode=input_mode, process_by_pages=True, pages_per_chunk=2,
    )

    assert len(df) == 2 * len(fake.calls)
    assert list(df.columns[:len(QUESTION_COLUMNS) + 1]) == ["Número de pregunta", *QUESTION_COLUMNS]
    if mime_type:
        assert all(att["mime_type"] == mime_type for _prompt, atts in fake.calls for att in atts)
    else:
        assert all(atts == [] for _prompt, atts in fake.calls)
    assert (tmp_path / "out_pendiente_de_revisar.xlsx").exists()


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
def test_generation_saves_partial_results_before_quota_error(tmp_path):
    fake = FakeClient([json.dumps([_question("P1"), _question("P2")]), QuotaExceededError("cuota")])
    generator = QuestionGenerator(ai_client=fake)

    with pytest.raises(QuotaExceededError):
        generator.generate_multiple_choice_questions(
            [str(SAMPLE_PDF)], "PRL", num_questions_per_chunk_target=2, output_dir=str(tmp_path),
            output_filename="partial", process_by_pages=True, pages_per_chunk=1,
        )

    saved = pd.read_excel(tmp_path / "partial_pendiente_de_revisar.xlsx")
    assert saved["Pregunta"].tolist() == ["P1", "P2"]


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
def test_generation_can_be_cancelled(tmp_path):
    import threading

    cancel = threading.Event()
    fake = FakeClient([json.dumps([_question("P1"), _question("P2")])] * 5)
    generator = QuestionGenerator(ai_client=fake)

    def progress(message):
        if "Intento 1:" in message:
            cancel.set()

    df = generator.generate_multiple_choice_questions(
        [str(SAMPLE_PDF)], "PRL", num_questions_per_chunk_target=2, output_dir=str(tmp_path),
        process_by_pages=True, pages_per_chunk=1, progress_callback=progress, cancel_event=cancel,
    )

    assert generator.cancelled
    assert len(fake.calls) == 1
    assert len(df) == 2


def test_generator_without_api_key_builds_prompts_for_web_chats():
    generator = QuestionGenerator()  # no key, no SDK client needed

    prompts_df = generator.build_generation_prompts(
        pdf_paths=["Tema 01.pdf"], prompt_type="PRL", input_mode="pdf", include_similar_questions_in_prompt=False,
    )

    prompt = prompts_df.iloc[0]["Prompt"]
    assert prompts_df.iloc[0]["Tema"] == "Tema 01"
    assert prompts_df.iloc[0]["Adjuntar"] == "Tema 01.pdf"
    assert "```json" in prompt
    assert "Tema 01.pdf" in prompt


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
def test_manual_round_trip_export_prompts_and_import_answers(tmp_path):
    generator = QuestionGenerator()
    prompts_df = generator.build_generation_prompts(
        [str(SAMPLE_PDF)], "PRL", input_mode="pdf", process_by_pages=True, pages_per_chunk=3,
        attachments_dir=str(tmp_path / "adjuntos"),
    )
    assert len(prompts_df) == 2
    assert all(Path(path).exists() for path in prompts_df["Adjuntar"])

    paths = generator.export_prompts(prompts_df, output_dir=str(tmp_path), output_filename="manual")
    sheet = pd.read_excel(paths["xlsx"], dtype=str)
    assert len(list(Path(paths["folder"]).glob("*.txt"))) == 2
    sheet.loc[0, "Respuesta"] = "```json\n" + json.dumps([_question("Manual 1"), _question("Mal", "Z")]) + "\n```"
    (tmp_path / "respuesta2.txt").write_text(json.dumps([_question("Manual 2", "D")]), encoding="utf-8")
    sheet.loc[1, "Respuesta"] = "respuesta2.txt"
    sheet.to_excel(paths["xlsx"], index=False)

    df = generator.import_questions_from_prompts_file(paths["xlsx"], output_dir=str(tmp_path), output_filename="imp")

    assert df["Pregunta"].tolist() == ["Manual 1", "Manual 2"]
    assert (tmp_path / "imp_no_validas.xlsx").exists()
    # The DOCX for review keeps the format read by the bank manager.
    reread = QuestionBankManager().read_questions_from_docx(str(tmp_path / "imp_pendiente_de_revisar.docx"))
    assert reread["Respuesta correcta"].tolist() == ["B", "D"]


def test_import_answers_applies_similarity_filter(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    pd.DataFrame([{"Tema": "T", "Pregunta": "¿Cuál es la capital de Francia?"}]).to_excel(bank_path, index=False)
    generator = QuestionGenerator()

    df = generator.import_questions_from_responses(
        {"T": json.dumps([_question("¿Cuál es la capital de Francia?"), _question("¿Otra pregunta distinta?")])},
        output_dir=str(tmp_path), output_filename="sim", existing_bank_path=str(bank_path),
    )

    assert df["Pregunta"].tolist() == ["¿Otra pregunta distinta?"]
    assert len(generator.rejected_questions_list) == 1
    assert (tmp_path / "sim_similares_descartadas.docx").exists()


def test_parser_accepts_structured_output_schema_keys():
    text = json.dumps({"preguntas": [{
        "pregunta": "¿P?", "opciones": ["a", "b", "c", "d"], "respuesta_correcta": "C", "texto_relevante": "t",
    }]})

    questions, errors = parse_questions_response(text)

    assert errors == []
    assert questions[0]["Respuesta correcta"] == "C"
    assert questions[0]["Texto relevante"] == "t"


# ---------------------------------------------------------------------------
# Regressions found in the review of the multi-provider work
# ---------------------------------------------------------------------------
def _q(statement, answer="A", options=None):
    return {"Pregunta": statement, "Opciones": options or [f"{statement} {c}" for c in "abcd"],
            "Respuesta correcta": answer, "Texto relevante": ""}


def test_parser_reads_a_cut_fenced_answer_followed_by_its_continuation():
    first = "```json\n" + json.dumps([_q("P1"), _q("P2"), _q("P3")], indent=2)
    first = first[: first.index('"P3 c"')]  # output limit reached: no closing fence
    continuation = "```json\n" + json.dumps([_q("P3"), _q("P4")], indent=2) + "\n```"

    questions, _ = parse_questions_response(first + "\n\n" + continuation)

    assert [q["Pregunta"] for q in questions] == ["P1", "P2", "P3", "P4"]


def test_parser_keeps_unfenced_and_fenced_answers_pasted_together():
    text = json.dumps([_q("P1"), _q("P2")]) + "\n\nMás:\n```json\n" + json.dumps([_q("P3")]) + "\n```"

    assert len(parse_questions_response(text)[0]) == 3


def test_parser_backticks_inside_a_json_string_do_not_end_the_block():
    items = [_q("P0"), {**_q("P1"), "Texto relevante": "usa ``` para el código"}, _q("P2"), _q("P3")]
    text = "```json\n" + json.dumps(items, indent=2) + "\n```"

    assert len(parse_questions_response(text)[0]) == 4


def test_parser_keeps_generic_statements_with_different_options():
    text = json.dumps([_q("Señala la afirmación correcta:", "A", ["a1", "b1", "c1", "d1"]),
                       _q("Señala la afirmación correcta:", "C", ["a2", "b2", "c2", "d2"]),
                       _q("Señala la afirmación correcta:", "C", ["b2", "a2", "d2", "c2"])])

    questions, _ = parse_questions_response(text)

    assert len(questions) == 2  # the third one repeats the second (same options, other order)


@pytest.mark.parametrize("answer, expected", [
    ("A los 18 años", None),           # option text that only starts with a preposition
    ("B y C", None),                   # two letters
    ("B) dos", "B"),                   # letter followed by its own option text
    ("La correcta es la D", "D"),
    ("Opción C", "C"),
])
def test_parser_answer_letter_resolution(answer, expected):
    options = ["uno", "dos", "A los 18 años de edad", "cuatro"]
    questions, errors = parse_questions_response(json.dumps([_q("¿P?", answer, options)]))

    if expected is None:
        assert questions == [] and len(errors) == 1
    else:
        assert questions[0]["Respuesta correcta"] == expected


def test_parser_accepts_options_given_as_objects():
    text = json.dumps([{"Pregunta": "¿P?", "Opciones": [
        {"letra": "A", "texto": "uno"}, {"letra": "B", "texto": "dos", "correcta": True},
        {"letra": "C", "texto": "tres"}, {"letra": "D", "texto": "cuatro"}]}])

    questions, errors = parse_questions_response(text)

    assert errors == []
    assert questions[0]["Opciones"] == ["uno", "dos", "tres", "cuatro"]
    assert questions[0]["Respuesta correcta"] == "B"


def test_parser_survives_pathological_input_quickly():
    import time

    start = time.perf_counter()
    assert parse_questions_response("[" * 5000) == ([], [])
    assert parse_questions_response("{" * 20000) == ([], [])
    assert time.perf_counter() - start < 5


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
def test_partial_results_of_the_current_chunk_are_saved_on_a_fatal_error(tmp_path):
    fake = FakeClient([json.dumps([_q("P1"), _q("P2"), _q("P3")]), QuotaExceededError("429")])
    generator = QuestionGenerator(ai_client=fake)

    with pytest.raises(QuotaExceededError):
        generator.generate_multiple_choice_questions(
            [str(SAMPLE_PDF)], "PRL", num_questions_per_chunk_target=5, output_dir=str(tmp_path),
            output_filename="p")

    saved = pd.read_excel(tmp_path / "p_pendiente_de_revisar.xlsx")
    assert saved["Pregunta"].tolist() == ["P1", "P2", "P3"]


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
def test_sources_are_validated_before_any_api_call(tmp_path):
    unsupported = tmp_path / "notas.docx"
    unsupported.write_bytes(b"PK")
    fake = FakeClient([json.dumps([_q("Q1")])])
    generator = QuestionGenerator(ai_client=fake)

    with pytest.raises(ValueError):
        generator.generate_multiple_choice_questions(
            [str(SAMPLE_PDF), str(unsupported)], "PRL", output_dir=str(tmp_path), input_mode="pdf")
    with pytest.raises(FileNotFoundError):
        generator.generate_multiple_choice_questions(
            [str(SAMPLE_PDF), str(tmp_path / "no_existe.pdf")], "PRL", output_dir=str(tmp_path))
    assert fake.calls == []


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
def test_unexpected_errors_keep_the_questions_obtained(tmp_path):
    fake = FakeClient([json.dumps([_q("P1")]), json.dumps([_q("P2")])])
    generator = QuestionGenerator(ai_client=fake)
    real_analyze = generator._analyze_response
    calls = {"n": 0}

    def analyze_then_fail(text, topic):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("archivo bloqueado")
        return real_analyze(text, topic)

    generator._analyze_response = analyze_then_fail
    with pytest.raises(OSError):
        generator.generate_multiple_choice_questions(
            [str(SAMPLE_PDF)], "PRL", num_questions_per_chunk_target=1, output_dir=str(tmp_path),
            output_filename="u", process_by_pages=True, pages_per_chunk=2)

    assert pd.read_excel(tmp_path / "u_pendiente_de_revisar.xlsx")["Pregunta"].tolist() == ["P1"]


@pytest.mark.parametrize("message, expected, requests", [
    ("Your credit balance is too low to access the Anthropic API.", QuotaExceededError, 1),
    ("prompt is too long: 250000 tokens > 200000 maximum", InvalidRequestError, 1),
    ("output_config.format: json_schema is not supported for this model", InvalidRequestError, 2),
])
def test_rejected_requests_are_not_repeated(message, expected, requests):
    calls = []

    class BadRequest(Exception):
        status_code = 400

    def stream(**kwargs):
        calls.append(kwargs)
        raise BadRequest(message)

    client = AnthropicClient("key", "claude-opus-5-5", sdk_client=SimpleNamespace(messages=SimpleNamespace(stream=stream)))

    with pytest.raises(expected):
        client.generate("prompt")
    assert len(calls) == requests


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
def test_a_rejected_request_stops_the_run_instead_of_repeating_it(tmp_path):
    fake = FakeClient([InvalidRequestError("400")] * 10)
    generator = QuestionGenerator(ai_client=fake)

    with pytest.raises(InvalidRequestError):
        generator.generate_multiple_choice_questions(
            [str(SAMPLE_PDF)], "PRL", output_dir=str(tmp_path), process_by_pages=True, pages_per_chunk=2)
    assert len(fake.calls) == 1


def test_overloaded_error_in_the_middle_of_a_stream_is_classified():
    class StreamError(Exception):
        status_code = 200
        body = {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}

    client = AnthropicClient("key", "claude-opus-5-5", sdk_client=SimpleNamespace())

    assert type(client.translate_error(StreamError("Overloaded"))) is ServiceOverloadedError


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not available")
def test_same_named_sources_get_distinct_fragment_files(tmp_path):
    import shutil

    for folder in ("T1", "T2"):
        (tmp_path / folder).mkdir()
        shutil.copy(SAMPLE_PDF, tmp_path / folder / "apuntes.pdf")
    prompts = QuestionGenerator().build_generation_prompts(
        [str(tmp_path / "T1" / "apuntes.pdf"), str(tmp_path / "T2" / "apuntes.pdf")], "PRL",
        input_mode="pdf", process_by_pages=True, pages_per_chunk=2, attachments_dir=str(tmp_path / "adj"))

    assert prompts["Adjuntar"].nunique() == len(prompts) == 4


def test_long_answers_round_trip_with_relative_folders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generator = QuestionGenerator()
    prompts = pd.DataFrame([{"PDF": "a.pdf", "Tema": "T", "Fragmento": 1, "Total fragmentos": 1, "Páginas": "",
                             "Adjuntar": "", "Caracteres": 1, "Prompt": "p"}])
    long_answer = json.dumps([{**_q(f"P{i}"), "Texto relevante": "x" * 700} for i in range(50)])

    paths = generator.export_prompts(prompts, output_dir="salida", output_filename="rt", responses=[long_answer])
    df = generator.import_questions_from_prompts_file(paths["xlsx"], output_dir="salida", output_filename="imp")
    assert len(df) == 50

    # The workbook and its folder can be moved together.
    import shutil
    shutil.move("salida", "movida")
    df = generator.import_questions_from_prompts_file("movida/rt_prompts.xlsx", output_dir="movida",
                                                      output_filename="imp2")
    assert len(df) == 50


def test_bmp_images_are_converted_to_png(tmp_path):
    import struct

    pytest.importorskip("fitz")
    # Minimal 2x2 24-bit BMP (rows padded to 4 bytes).
    pixels = (b"\x00\x00\xff" * 2 + b"\x00\x00") * 2
    header = b"BM" + struct.pack("<IHHI", 54 + len(pixels), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, 2, 2, 1, 24, 0, len(pixels), 2835, 2835, 0, 0)
    image = tmp_path / "esquema.bmp"
    image.write_bytes(header + dib + pixels)

    items = QuestionGenerator()._load_source_as_image_items(str(image))

    assert items[0]["mime_type"] == "image/png"
    assert items[0]["bytes"].startswith(b"\x89PNG")


def test_sdk_client_can_still_be_replaced():
    sdk = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(text="[]")))
    generator = QuestionGenerator(api_key="k", model_name="gemini-flash-latest")

    generator.client = sdk

    assert generator.client is sdk
    assert generator.ai_client.generate("prompt") == "[]"


@pytest.mark.parametrize("answer, expected", [
    ("b) Dos (paráfrasis)", "B"),       # label-style letter with paraphrased text
    ("(c)", "C"),
    ("D.", "D"),
    ("B) cuatro", None),                # the label contradicts the text of another option
])
def test_parser_label_style_answers(answer, expected):
    options = ["uno", "dos", "tres", "cuatro"]
    questions, errors = parse_questions_response(json.dumps([_q("¿P?", answer, options)]))

    if expected is None:
        assert questions == [] and len(errors) == 1
    else:
        assert questions[0]["Respuesta correcta"] == expected
