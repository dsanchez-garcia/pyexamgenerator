"""Flujo completo de `QuestionGenerator.generate_multiple_choice_questions` con Gemini simulado."""

from types import SimpleNamespace

import fitz  # PyMuPDF
import pandas as pd

from pyexamgenerator.question_generator import QuestionGenerator

_RESPONSE = (
    "{'Pregunta': '¿Qué regula la Ley 31/1995?', 'Opciones': ['La prevención de riesgos', 'El tráfico', "
    "'La fiscalidad', 'El urbanismo'], 'Respuesta correcta': 'A', 'Texto relevante': 'Ley de prevención'}"
    "\n\n"
    "{'Pregunta': '¿Quién debe garantizar la seguridad?', 'Opciones': ['El empresario', 'El cliente', "
    "'El proveedor', 'Nadie'], 'Respuesta correcta': 'a', 'Texto relevante': 'deber de protección'}"
)


def _pdf(path, text):
    document = fitz.open()
    document.new_page().insert_text((72, 72), text)
    document.save(str(path))
    document.close()
    return str(path)


def test_generation_flow_with_fake_gemini_client(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    pdf_path = _pdf(tmp_path / "Tema 1.PDF", "La ley de prevencion de riesgos laborales protege a los trabajadores.")

    prompts = []

    def fake_generate_content(model, contents):
        prompts.append(contents)
        return SimpleNamespace(text=_RESPONSE)

    generator = QuestionGenerator(api_key="dummy", model_name="models/test")
    generator.client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))

    df = generator.generate_multiple_choice_questions(
        pdf_paths=[pdf_path],
        prompt_type="PRL",
        num_questions_per_chunk_target=2,
        output_dir=str(tmp_path / "salida"),
    )

    assert len(prompts) == 1
    assert "prevencion de riesgos" in prompts[0]
    assert len(df) == 2
    # BUG-14: el tema sale del nombre sin la extensión, también en mayúsculas ('.PDF').
    assert set(df["Tema"]) == {"Tema 1"}
    assert set(df["Estado"]) == {"Pendiente de revisar"}
    # BUG-14: el nombre por defecto ya no repite el sufijo ('..._pendiente_de_revisar_pendiente_de_revisar').
    saved = pd.read_excel(tmp_path / "salida" / "preguntas_pendiente_de_revisar.xlsx")
    assert len(saved) == 2
    assert (tmp_path / "salida" / "preguntas_pendiente_de_revisar.docx").exists()
