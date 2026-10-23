"""`ExamConfig`: las opciones de `generate_exam_from_excel` en un objeto (ARC-6)."""

import random

import numpy as np
import pandas as pd
import pytest
from docx import Document

from pyexamgenerator import ExamConfig, ExamGenerator


def _bank(path):
    rows = [
        {
            "Número de pregunta": i + 1,
            "Tema": f"Tema 0{i % 2 + 1}",
            "Estado": "Aceptable",
            "Pregunta": f"Pregunta {i + 1}",
            "Respuesta A": f"A{i}",
            "Respuesta B": f"B{i}",
            "Respuesta C": f"C{i}",
            "Respuesta D": f"D{i}",
            "Respuesta correcta": "ABCD"[i % 4],
            "Texto relevante": "",
        }
        for i in range(6)
    ]
    pd.DataFrame(rows).to_excel(path, index=False)
    return str(path)


def _generate(bank, out_dir, *args, **kwargs):
    random.seed(7)
    np.random.seed(7)
    generator = ExamGenerator()
    generator.generate_exam_from_excel(bank, *args, output_dir=str(out_dir), **kwargs)
    return generator


def _texts(paths):
    return [[p.text for p in Document(path).paragraphs] for path in paths]


def test_config_gives_the_same_exams_as_the_options_by_name(tmp_path):
    bank = _bank(tmp_path / "banco.xlsx")
    options = dict(
        subject="PRL", exam="Parcial", course="25-26", exam_names=["A", "B"], questions_per_topic={"Tema 01": 2}
    )

    by_name = _generate(bank, tmp_path / "por_nombre", **options)
    with_config = _generate(bank, tmp_path / "con_config", ExamConfig(**options))

    assert [r["exam_type"] for r in with_config.generated_exams] == ["A", "B"]
    assert _texts(r["docx"] for r in with_config.generated_exams) == _texts(r["docx"] for r in by_name.generated_exams)


def test_an_option_by_name_overrides_the_config_without_changing_it(tmp_path):
    bank = _bank(tmp_path / "banco.xlsx")
    config = ExamConfig(subject="PRL", exam="Parcial", course="25-26", exam_names=["A"])

    generator = _generate(bank, tmp_path / "salida", config, exam="Final")

    assert generator.generated_exams[0]["exam"] == "Final"
    assert (tmp_path / "salida" / "examen_PRL_Final_25-26_A.docx").exists()
    assert config.exam == "Parcial"


def test_the_other_options_go_by_name(tmp_path):
    """El segundo argumento era `output_dir`; ahora es el `ExamConfig` y lo demás va por nombre."""
    with pytest.raises(TypeError, match="ExamConfig"):
        ExamGenerator().generate_exam_from_excel(_bank(tmp_path / "banco.xlsx"), str(tmp_path / "salida"))


def test_an_unknown_option_is_an_error(tmp_path):
    with pytest.raises(TypeError, match="no_existe"):
        ExamGenerator().generate_exam_from_excel(_bank(tmp_path / "banco.xlsx"), no_existe=1)
