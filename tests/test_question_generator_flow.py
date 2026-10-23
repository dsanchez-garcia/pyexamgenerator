"""Flujo completo de `QuestionGenerator.generate_multiple_choice_questions` con Gemini simulado."""

from types import SimpleNamespace

import pandas as pd
import pymupdf
import pytest

from pyexamgenerator.question_generator import QuestionGenerator

_RESPONSE = (
    "{'Pregunta': '¿Qué regula la Ley 31/1995?', 'Opciones': ['La prevención de riesgos', 'El tráfico', "
    "'La fiscalidad', 'El urbanismo'], 'Respuesta correcta': 'A', 'Texto relevante': 'Ley de prevención'}"
    "\n\n"
    "{'Pregunta': '¿Quién debe garantizar la seguridad?', 'Opciones': ['El empresario', 'El cliente', "
    "'El proveedor', 'Nadie'], 'Respuesta correcta': 'a', 'Texto relevante': 'deber de protección'}"
)


def _pdf(path, text):
    document = pymupdf.open()
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


def test_generated_questions_similar_to_the_bank_are_filtered(tmp_path):
    """TST-3: `filter_generated_questions_duplicates` no tenía test."""
    bank_path = tmp_path / "banco.xlsx"
    pd.DataFrame({"Pregunta": ["¿Qué regula la Ley 31/1995 de prevención de riesgos laborales?"]}).to_excel(
        bank_path, index=False
    )
    generated = pd.DataFrame(
        {
            "Pregunta": [
                "¿Qué regula la Ley 31/1995 de prevención de riesgos laborales?",  # same statement
                "¿Quién debe garantizar la seguridad de los trabajadores?",
            ]
        }
    )
    generator = QuestionGenerator(api_key="dummy", model_name="models/test")

    accepted, rejected = generator.filter_generated_questions_duplicates(generated, str(bank_path), 0.8)

    assert accepted["Pregunta"].tolist() == ["¿Quién debe garantizar la seguridad de los trabajadores?"]
    assert rejected["Similitud"].tolist() == [pytest.approx(1.0)]
    assert rejected["Pregunta Coincidente"].iloc[0].startswith("¿Qué regula la Ley 31/1995")

    empty_accepted, empty_rejected = generator.filter_generated_questions_duplicates(pd.DataFrame(), str(bank_path))
    assert empty_accepted.empty and empty_rejected.empty
    with pytest.raises(FileNotFoundError):
        generator.filter_generated_questions_duplicates(generated, str(tmp_path / "no_existe.xlsx"))


def test_unreadable_duplicates_bank_stops_before_calling_gemini(tmp_path):
    """ARC-9: si el banco elegido para evitar duplicados no se podía leer, se generaba igualmente sin
    el filtro y solo quedaba un aviso en la consola."""
    pdf_path = _pdf(tmp_path / "Tema 1.pdf", "La ley de prevencion de riesgos laborales.")
    calls = []
    generator = QuestionGenerator(api_key="dummy", model_name="models/test")
    generator.client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: calls.append(kwargs)))

    with pytest.raises(ValueError, match="No se pudo leer el banco de preguntas existente"):
        generator.generate_multiple_choice_questions(
            pdf_paths=[pdf_path],
            prompt_type="PRL",
            num_questions_per_chunk_target=1,
            output_dir=str(tmp_path),
            existing_bank_path=str(tmp_path / "no_existe.xlsx"),
            similarity_threshold=0.8,
        )

    assert calls == []


def _pages_pdf(path, pages):
    document = pymupdf.open()
    for text in pages:
        document.new_page().insert_text((72, 72), text)
    document.save(str(path))
    document.close()
    return str(path)


def test_pdf_text_is_read_with_pypdf_not_the_abandoned_pypdf2(tmp_path):
    """PKG-4: PyPDF2 está abandonado (avisaba en cada ejecución); el texto se lee con su sucesor, pypdf.

    En un proceso aparte, para que otros tests no hayan importado ya PyPDF2.
    """
    import subprocess
    import sys
    from pathlib import Path

    pdf = _pages_pdf(tmp_path / "Tema 1.pdf", ["Uno", "Dos"])
    code = (
        "import sys\n"
        "from pyexamgenerator.question_generator import QuestionGenerator\n"
        f"pages, text = QuestionGenerator._read_pdf({pdf!r})\n"
        "print([page.strip() for page in pages], 'PyPDF2' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=Path(__file__).resolve().parents[1],
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "['Uno', 'Dos'] False"


def test_pdf_split_into_page_chunks_for_the_prompts(tmp_path):
    """Troceo de un PDF por páginas (sin llamar a Gemini): fragmentos de N páginas, un número total de
    fragmentos equilibrados, y el mismo resultado al reutilizar el generador con otro PDF (ARC-13)."""
    five_pages = _pages_pdf(tmp_path / "Tema 1.pdf", [f"Contenido de la pagina {n}" for n in range(1, 6)])
    two_pages = _pages_pdf(tmp_path / "Tema 2.pdf", ["Primera", "Segunda"])
    generator = QuestionGenerator(api_key="dummy", model_name="models/test")

    def chunk_count(pdf, **kwargs):
        prompts = generator.build_generation_prompts(
            pdf_paths=[pdf],
            prompt_type="PRL",
            process_by_pages=True,
            include_similar_questions_in_prompt=False,
            **kwargs,
        )
        return len(prompts)

    assert chunk_count(five_pages, pages_per_chunk=2) == 3
    assert chunk_count(five_pages, total_chunks=2) == 2
    assert chunk_count(two_pages, pages_per_chunk=2) == 1
    assert chunk_count(five_pages, pages_per_chunk=1) == 5


def test_generators_keep_no_scratch_state_between_runs(tmp_path):
    """ARC-13: el XML de Moodle y el texto de los PDF se construían en atributos de la instancia
    (`self.quiz`, `self.answer_a`, `self.page_texts`…): dos trabajos con la misma instancia (p. ej.
    desde la GUI, en hilos) se pisaban."""
    import random

    from pyexamgenerator.exam_generator import ExamGenerator

    pdf = _pages_pdf(tmp_path / "Tema 1.pdf", ["Uno", "Dos", "Tres"])
    question_generator = QuestionGenerator(api_key="dummy", model_name="models/test")
    question_generator.build_generation_prompts(
        pdf_paths=[pdf], prompt_type="PRL", process_by_pages=True, include_similar_questions_in_prompt=False
    )
    assert not any(hasattr(question_generator, name) for name in ("page_texts", "text", "num_pages"))

    bank = tmp_path / "banco.xlsx"
    pd.DataFrame(
        [
            {
                "Número de pregunta": n,
                "Tema": "Tema 01",
                "Estado": "Aceptable",
                "Pregunta": f"¿{n}?",
                "Respuesta A": "a",
                "Respuesta B": "b",
                "Respuesta C": "c",
                "Respuesta D": "d",
                "Respuesta correcta": "a",
                "Texto relevante": "",
            }
            for n in (1, 2)
        ]
    ).to_excel(bank, index=False)
    exam_generator = ExamGenerator()
    random.seed(7)
    exam_generator.generate_exam_from_excel(
        bank_excel_path=str(bank),
        output_dir=str(tmp_path / "salida"),
        subject="Asig",
        exam="Parcial",
        course="25-26",
        exam_names=["A"],
        export_moodle_xml=True,
    )
    scratch = (
        "quiz",
        "category",
        "category_name",
        "text",
        "question",
        "name",
        "answer_a",
        "answer_b",
        "answer_c",
        "answer_d",
        "exam_text",
        "full_exam_text",
    )
    assert [name for name in scratch if hasattr(exam_generator, name)] == []
    assert list((tmp_path / "salida").glob("*_A.xml"))
