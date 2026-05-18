import random

import pandas as pd

from pyexamgenerator.exam_generator import ExamGenerator


def test_build_exam_variant_df_keeps_correct_answer_text_and_canonical_numbering():
    generator = ExamGenerator()
    source_df = pd.DataFrame(
        [
            {
                "Pregunta": "Q1",
                "Respuesta A": "Q1-A",
                "Respuesta B": "Q1-B",
                "Respuesta C": "Q1-C",
                "Respuesta D": "Q1-D",
                "Respuesta correcta": "c",
            },
            {
                "Pregunta": "Q2",
                "Respuesta A": "Q2-A",
                "Respuesta B": "Q2-B",
                "Respuesta C": "Q2-C",
                "Respuesta D": "Q2-D",
                "Respuesta correcta": "a",
            },
            {
                "Pregunta": "Q3",
                "Respuesta A": "Q3-A",
                "Respuesta B": "Q3-B",
                "Respuesta C": "Q3-C",
                "Respuesta D": "Q3-D",
                "Respuesta correcta": "d",
            },
        ]
    )

    expected_correct_text_by_question = {
        row["Pregunta"]: row[f"Respuesta {row['Respuesta correcta'].upper()}"]
        for _, row in source_df.iterrows()
    }

    random.seed(20260518)
    variant_df = generator._build_exam_variant_df(source_df)

    assert list(variant_df["Número de pregunta"]) == [1, 2, 3]
    assert "Texto respuesta correcta" not in variant_df.columns

    for _, row in variant_df.iterrows():
        correct_letter = row["Respuesta correcta"].upper()
        current_correct_text = row[f"Respuesta {correct_letter}"]
        assert current_correct_text == expected_correct_text_by_question[row["Pregunta"]]


def test_format_question_number_is_always_two_digits():
    assert ExamGenerator._format_question_number(1) == "01"
    assert ExamGenerator._format_question_number(9) == "09"
    assert ExamGenerator._format_question_number(10) == "10"

