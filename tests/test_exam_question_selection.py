"""Selección de preguntas al generar exámenes: estado sin distinguir mayúsculas, reparto de un
número total de preguntas entre temas y alerta de uso que cancela la generación."""

import random

import pandas as pd
import pytest

from pyexamgenerator.exam_generator import ExamGenerator


def _build_minimal_bank_df():
    return pd.DataFrame(
        [
            {
                "Número de pregunta": 1,
                "Tema": "Tema 01",
                "Estado": "aceptable",
                "Pregunta": "¿Capital de Francia?",
                "Respuesta A": "Madrid",
                "Respuesta B": "Paris",
                "Respuesta C": "Lisboa",
                "Respuesta D": "Roma",
                "Respuesta correcta": "b",
                "Texto relevante": "Paris es la capital de Francia.",
            }
        ]
    )


def _build_bank_df(num_per_topic=None):
    """Builds a small acceptable question bank spread over three topics."""
    if num_per_topic is None:
        num_per_topic = {"Tema 01": 4, "Tema 02": 4, "Tema 03": 4}
    rows = []
    number = 1
    for topic, count in num_per_topic.items():
        for i in range(count):
            rows.append(
                {
                    "Número de pregunta": number,
                    "Tema": topic,
                    "Estado": "aceptable",
                    "Pregunta": f"{topic} - Pregunta {i + 1}",
                    "Respuesta A": f"{topic}-{i}-A",
                    "Respuesta B": f"{topic}-{i}-B",
                    "Respuesta C": f"{topic}-{i}-C",
                    "Respuesta D": f"{topic}-{i}-D",
                    "Respuesta correcta": "a",
                    "Texto relevante": f"Relevante {topic} {i}",
                }
            )
            number += 1
    return pd.DataFrame(rows)


def test_exam_generator_accepts_estado_case_insensitive(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    _build_minimal_bank_df().to_excel(bank_path, index=False)

    generator = ExamGenerator()
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(tmp_path),
        subject="Geo",
        exam="Parcial",
        course="25-26",
        exam_names=["A"],
        export_moodle_xml=False,
        update_excel=False,
    )

    assert (tmp_path / "examen_Geo_Parcial_25-26_A.docx").exists()


def test_distribute_questions_equitably_even_split():
    bank = _build_bank_df({"Tema 01": 5, "Tema 02": 5, "Tema 03": 5})
    allocation = ExamGenerator._distribute_questions_equitably(bank, 6)
    assert allocation == {"Tema 01": 2, "Tema 02": 2, "Tema 03": 2}
    assert sum(allocation.values()) == 6


def test_distribute_questions_equitably_odd_total_gives_extra_to_first_topics():
    bank = _build_bank_df({"Tema 01": 5, "Tema 02": 5, "Tema 03": 5})
    allocation = ExamGenerator._distribute_questions_equitably(bank, 7)
    assert sum(allocation.values()) == 7
    # The first topic (alphabetical) receives the extra question.
    assert allocation["Tema 01"] == 3
    assert allocation["Tema 02"] == 2
    assert allocation["Tema 03"] == 2


def test_distribute_questions_equitably_redistributes_when_topic_is_short():
    # Tema 01 only has 1 question; its shortfall must spill over to the others.
    bank = _build_bank_df({"Tema 01": 1, "Tema 02": 5, "Tema 03": 5})
    allocation = ExamGenerator._distribute_questions_equitably(bank, 7)
    assert sum(allocation.values()) == 7
    assert allocation["Tema 01"] == 1
    assert allocation["Tema 02"] + allocation["Tema 03"] == 6


def test_generate_exam_with_total_questions_equitativo(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    _build_bank_df({"Tema 01": 4, "Tema 02": 4, "Tema 03": 4}).to_excel(bank_path, index=False)

    generator = ExamGenerator()
    random.seed(20260601)
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(tmp_path),
        subject="Geo",
        exam="Total",
        course="25-26",
        exam_names=["A"],
        total_questions=9,
        total_distribution="equitativo",
        export_moodle_xml=False,
        update_excel=False,
    )

    exam_xlsx = tmp_path / "examen_Geo_Total_25-26_A_completo.xlsx"
    assert exam_xlsx.exists()
    df = pd.read_excel(exam_xlsx)
    assert len(df) == 9
    # 9 across 3 topics => 3 each.
    assert df["Tema"].value_counts().to_dict() == {"Tema 01": 3, "Tema 02": 3, "Tema 03": 3}


def test_generate_exam_with_total_questions_azar(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    _build_bank_df({"Tema 01": 4, "Tema 02": 4, "Tema 03": 4}).to_excel(bank_path, index=False)

    generator = ExamGenerator()
    random.seed(20260601)
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(tmp_path),
        subject="Geo",
        exam="TotalAzar",
        course="25-26",
        exam_names=["A"],
        total_questions=5,
        total_distribution="azar",
        export_moodle_xml=False,
        update_excel=False,
    )

    exam_xlsx = tmp_path / "examen_Geo_TotalAzar_25-26_A_completo.xlsx"
    assert exam_xlsx.exists()
    df = pd.read_excel(exam_xlsx)
    assert len(df) == 5


def test_usage_warning_callback_can_cancel_generation(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    bank = _build_bank_df({"Tema 01": 3})
    bank["Veces usada en examen"] = [4, 3, 5]
    bank.to_excel(bank_path, index=False)

    calls = []

    def cancel_callback(warning_df, threshold, message):
        calls.append((warning_df.copy(), threshold, message))
        return False

    generator = ExamGenerator()
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(tmp_path),
        subject="Geo",
        exam="Warn",
        course="25-26",
        exam_names=["A"],
        export_moodle_xml=False,
        update_excel=False,
        usage_warning_threshold=3,
        usage_warning_callback=cancel_callback,
    )

    assert generator.generation_cancelled is True
    assert len(calls) == 1
    warning_df, threshold, message = calls[0]
    assert threshold == 3
    assert len(warning_df) == 2
    assert "mas de 3 veces" in message
    assert not (tmp_path / "examen_Geo_Warn_25-26_A.docx").exists()


def test_first_questions_of_each_topic_are_selected_in_bank_order(tmp_path):
    """TST-3: el método 'primeras' no tenía test."""
    bank_path = tmp_path / "bank.xlsx"
    _build_bank_df().to_excel(bank_path, index=False)
    generator = ExamGenerator()

    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(tmp_path),
        subject="Geo",
        exam="Primeras",
        course="25-26",
        exam_names=["A"],
        questions_per_topic={"Tema 01": 2, "Tema 03": 1},
        selection_method="primeras",
    )

    assert sorted(generator.exam_df["Pregunta"]) == [
        "Tema 01 - Pregunta 1",
        "Tema 01 - Pregunta 2",
        "Tema 03 - Pregunta 1",
    ]


def test_bank_without_acceptable_questions_raises_a_clear_error(tmp_path):
    """TST-3: `NoAcceptableQuestionsError` no tenía test."""
    from pyexamgenerator.exam_generator import NoAcceptableQuestionsError

    bank_path = tmp_path / "bank.xlsx"
    bank = _build_bank_df({"Tema 01": 2})
    bank["Estado"] = "Pendiente de revisar"
    bank.to_excel(bank_path, index=False)

    with pytest.raises(NoAcceptableQuestionsError, match="Aceptable"):
        ExamGenerator().generate_exam_from_excel(
            bank_excel_path=str(bank_path),
            output_dir=str(tmp_path),
            subject="Geo",
            exam="Ninguna",
            course="25-26",
            exam_names=["A"],
            questions_per_topic={"Tema 01": 1},
        )

    assert not list(tmp_path.glob("*.docx"))
