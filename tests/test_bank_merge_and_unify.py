"""Fusión de bancos: añadir solo las preguntas aceptables y unificar varios bancos con criterio de
duplicado por enunciado o por enunciado y respuestas."""

import pandas as pd
import pytest

from pyexamgenerator.question_bank_manager import QuestionBankManager


def _q(statement, a, b, c, d, topic="Tema 01", estado="aceptable"):
    return {
        "Tema": topic,
        "Estado": estado,
        "Pregunta": statement,
        "Respuesta A": a,
        "Respuesta B": b,
        "Respuesta C": c,
        "Respuesta D": d,
        "Respuesta correcta": "a",
        "Texto relevante": "",
    }


def test_question_bank_manager_add_only_acceptable_is_case_insensitive(tmp_path):
    existing_path = tmp_path / "existing.xlsx"
    reviewed_path = tmp_path / "reviewed.xlsx"

    pd.DataFrame(
        [], columns=["Pregunta", "Respuesta A", "Respuesta B", "Respuesta C", "Respuesta D", "Estado"]
    ).to_excel(existing_path, index=False)
    pd.DataFrame(
        [
            {
                "Pregunta": "P1",
                "Respuesta A": "A",
                "Respuesta B": "B",
                "Respuesta C": "C",
                "Respuesta D": "D",
                "Estado": "aceptable",
            }
        ]
    ).to_excel(reviewed_path, index=False)

    manager = QuestionBankManager()
    added_count, updated_df = manager.add_questions_without_duplicates(
        existing_bank_path=str(existing_path),
        reviewed_questions_path=str(reviewed_path),
        add_only_acceptable=True,
    )

    assert added_count == 1
    assert updated_df is not None
    assert len(updated_df) == 1


def test_duplicate_check_columns_none_uses_the_default_columns(tmp_path):
    """DEV-1 (bugbear B006): el valor por defecto era una lista mutable, y pasar None explícitamente
    fallaba con TypeError; ahora None significa las columnas por defecto (enunciado y respuestas)."""
    existing_path = tmp_path / "existing.xlsx"
    reviewed_path = tmp_path / "reviewed.xlsx"
    pd.DataFrame([_q("P1", "A", "B", "C", "D")]).to_excel(existing_path, index=False)
    pd.DataFrame([_q("P1", "A", "B", "C", "D"), _q("P2", "A", "B", "C", "D")]).to_excel(reviewed_path, index=False)

    added_count, updated_df = QuestionBankManager().add_questions_without_duplicates(
        existing_bank_path=str(existing_path),
        reviewed_questions_path=str(reviewed_path),
        duplicate_check_columns=None,
    )

    assert added_count == 1
    assert updated_df["Pregunta"].tolist() == ["P1", "P2"]


def test_unify_banks_statement_only_dedups_by_statement(tmp_path):
    bank1 = pd.DataFrame([_q("¿Capital de Francia?", "París", "Londres", "Roma", "Berlín")])
    bank2 = pd.DataFrame(
        [
            _q("¿Capital de Francia?", "Paris", "London", "Rome", "Madrid"),  # same statement, other answers
            _q("¿Capital de Italia?", "Roma", "París", "Madrid", "Berlín"),
        ]
    )
    p1, p2, out = tmp_path / "b1.xlsx", tmp_path / "b2.xlsx", tmp_path / "unif.xlsx"
    bank1.to_excel(p1, index=False)
    bank2.to_excel(p2, index=False)

    manager = QuestionBankManager()
    df, stats = manager.unify_question_banks([str(p1), str(p2)], str(out), duplicate_criterion="enunciado")

    assert len(df) == 2
    assert stats["duplicates_removed"] == 1
    assert stats["total_read"] == 3
    assert set(df["Pregunta"]) == {"¿Capital de Francia?", "¿Capital de Italia?"}
    # The first bank wins: the kept "Francia" row keeps the first bank's answers.
    francia = df[df["Pregunta"] == "¿Capital de Francia?"].iloc[0]
    assert francia["Respuesta B"] == "Londres"
    assert out.exists()


def test_unify_banks_statement_and_answers_keeps_distinct_answers(tmp_path):
    bank1 = pd.DataFrame([_q("¿Capital de Francia?", "París", "Londres", "Roma", "Berlín")])
    bank2 = pd.DataFrame([_q("¿Capital de Francia?", "Paris", "London", "Rome", "Madrid")])
    p1, p2 = tmp_path / "b1.xlsx", tmp_path / "b2.xlsx"
    bank1.to_excel(p1, index=False)
    bank2.to_excel(p2, index=False)

    manager = QuestionBankManager()
    df, stats = manager.unify_question_banks(
        [str(p1), str(p2)], duplicate_criterion="enunciado_y_respuestas", save=False
    )
    # Same statement but different answers -> both kept.
    assert len(df) == 2
    assert stats["duplicates_removed"] == 0


def test_unify_banks_answer_set_is_order_independent(tmp_path):
    bank1 = pd.DataFrame([_q("Pregunta X", "A", "B", "C", "D")])
    bank2 = pd.DataFrame([_q("Pregunta X", "B", "A", "D", "C")])  # same options, reordered
    p1, p2 = tmp_path / "b1.xlsx", tmp_path / "b2.xlsx"
    bank1.to_excel(p1, index=False)
    bank2.to_excel(p2, index=False)

    manager = QuestionBankManager()
    df, stats = manager.unify_question_banks([str(p1), str(p2)], duplicate_criterion="pregunta_respuestas", save=False)
    # Reordered identical options are treated as the same question.
    assert len(df) == 1
    assert stats["duplicates_removed"] == 1


def test_unify_three_banks_with_gui_alias_and_normalization(tmp_path):
    bank1 = pd.DataFrame([_q("Misma pregunta", "a", "b", "c", "d")])
    bank2 = pd.DataFrame([_q("  MISMA PREGUNTA ", "a", "b", "c", "d")])  # case/space variant
    bank3 = pd.DataFrame([_q("Otra pregunta", "a", "b", "c", "d")])
    paths = []
    for i, b in enumerate((bank1, bank2, bank3)):
        p = tmp_path / f"b{i}.xlsx"
        b.to_excel(p, index=False)
        paths.append(str(p))

    manager = QuestionBankManager()
    df, stats = manager.unify_question_banks(paths, duplicate_criterion="pregunta_unica", save=False)
    # The case/whitespace variant of "Misma pregunta" is a duplicate -> 2 unique remain.
    assert len(df) == 2
    assert stats["duplicates_removed"] == 1
    assert len(stats["banks"]) == 3


def test_unify_banks_requires_paths():
    manager = QuestionBankManager()
    with pytest.raises(ValueError):
        manager.unify_question_banks([])
