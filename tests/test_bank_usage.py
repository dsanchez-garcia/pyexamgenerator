"""Registro del uso de preguntas en el banco: columna del examen generado, actualización desde
exámenes existentes, etiquetas derivadas del nombre del fichero y nombres de columna sin tildes."""

import random

import pandas as pd

from pyexamgenerator.exam_generator import ExamGenerator
from pyexamgenerator.question_bank_manager import QuestionBankManager


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


def test_generated_complete_xlsx_marks_current_exam_usage_column_as_one(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    bank = _build_bank_df({"Tema 01": 5})
    bank["Historico_uso"] = [0, 1, 0, 1, 0]
    bank["Veces usada en examen"] = [0, 1, 2, 3, 4]
    bank.to_excel(bank_path, index=False)

    generator = ExamGenerator()
    random.seed(20260601)
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(tmp_path),
        subject="Geo",
        exam="UsoXlsx",
        course="25-26",
        exam_names=["A"],
        total_questions=3,
        export_moodle_xml=False,
        update_excel=False,
    )

    exam_xlsx = tmp_path / "examen_Geo_UsoXlsx_25-26_A_completo.xlsx"
    df = pd.read_excel(exam_xlsx)
    assert df.columns[-1] == "UsoXlsx_25_26_uso"
    assert df["UsoXlsx_25_26_uso"].tolist() == [1, 1, 1]


def test_update_bank_with_exam_marks_used_questions(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    bank_df = _build_bank_df({"Tema 01": 4, "Tema 02": 4})
    bank_df.to_excel(bank_path, index=False)

    # Build an "exam" file that uses a subset of the bank questions (answers shuffled / reordered).
    used = bank_df.iloc[[0, 2, 5]].copy()
    # Simulate the shuffle that exams apply to answers: swap A and B text. Matching is by statement.
    used = used.rename(columns={"Respuesta A": "Respuesta B", "Respuesta B": "Respuesta A"})
    exam_path = tmp_path / "examen_completo.xlsx"
    used.to_excel(exam_path, index=False)

    manager = QuestionBankManager()
    matched, df_updated = manager.update_bank_with_exam(
        str(bank_path), str(exam_path), exam_label="Parcial1 25-26"
    )

    assert matched == 3
    assert df_updated is not None
    usage_columns = [c for c in df_updated.columns if c.endswith("_uso")]
    assert usage_columns == ["Parcial1_25_26_uso"]
    assert df_updated["Parcial1_25_26_uso"].sum() == 3
    assert "Veces usada en examen" in df_updated.columns
    assert df_updated["Veces usada en examen"].sum() == 3
    # The matched statements are flagged.
    used_statements = set(used["Pregunta"])
    flagged = df_updated.loc[df_updated["Parcial1_25_26_uso"] == 1, "Pregunta"]
    assert set(flagged) == used_statements


def test_update_bank_with_exam_missing_file_returns_error(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    _build_bank_df({"Tema 01": 2}).to_excel(bank_path, index=False)

    manager = QuestionBankManager()
    matched, df_updated = manager.update_bank_with_exam(
        str(bank_path), str(tmp_path / "no_existe.xlsx")
    )
    assert matched == -1
    assert df_updated is None


def test_update_bank_with_exams_multiple_labels(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    bank_df = _build_bank_df({"Tema 01": 4, "Tema 02": 4})
    bank_df.to_excel(bank_path, index=False)

    # Two exams using overlapping subsets of the bank, each with its own label.
    exam1 = bank_df.iloc[[0, 1]].copy()
    exam1_path = tmp_path / "examen_parcial1_completo.xlsx"
    exam1.to_excel(exam1_path, index=False)

    exam2 = bank_df.iloc[[1, 5, 6]].copy()  # row 1 is shared with exam1
    exam2_path = tmp_path / "examen_parcial2_completo.xlsx"
    exam2.to_excel(exam2_path, index=False)

    manager = QuestionBankManager()
    total, df_updated, stats = manager.update_bank_with_exams(
        str(bank_path),
        [
            {"path": str(exam1_path), "label": "Parcial1 25-26"},
            (str(exam2_path), "Parcial2 25-26"),
        ],
    )

    assert total == 5  # 2 from exam1 + 3 from exam2
    assert df_updated is not None
    usage_columns = sorted(c for c in df_updated.columns if c.endswith("_uso"))
    assert usage_columns == ["Parcial1_25_26_uso", "Parcial2_25_26_uso"]
    assert df_updated["Parcial1_25_26_uso"].sum() == 2
    assert df_updated["Parcial2_25_26_uso"].sum() == 3
    # The shared question (row 1) is flagged in both columns; the aggregate counts both.
    assert df_updated["Veces usada en examen"].sum() == 5
    assert df_updated.loc[1, "Veces usada en examen"] == 2

    assert stats["total_matched"] == 5
    assert [e["matched"] for e in stats["exams"]] == [2, 3]
    assert stats["errors"] == []


def test_update_bank_with_exams_default_label_from_filename(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    bank_df = _build_bank_df({"Tema 01": 3})
    bank_df.to_excel(bank_path, index=False)

    exam_path = tmp_path / "examen_X_completo.xlsx"
    bank_df.iloc[[0]].to_excel(exam_path, index=False)

    manager = QuestionBankManager()
    # A bare path string (no label) falls back to the file name.
    total, df_updated, stats = manager.update_bank_with_exams(str(bank_path), [str(exam_path)])

    assert total == 1
    assert "examen_X_completo_uso" in df_updated.columns


def test_update_bank_with_exams_skips_unreadable_exam(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    bank_df = _build_bank_df({"Tema 01": 3})
    bank_df.to_excel(bank_path, index=False)

    good_exam = tmp_path / "bueno_completo.xlsx"
    bank_df.iloc[[0, 2]].to_excel(good_exam, index=False)

    manager = QuestionBankManager()
    total, df_updated, stats = manager.update_bank_with_exams(
        str(bank_path),
        [
            {"path": str(good_exam), "label": "Bueno"},
            {"path": str(tmp_path / "no_existe.xlsx"), "label": "Fantasma"},
        ],
    )

    # The missing exam is skipped (reported in errors), the good one is still processed.
    assert total == 2
    assert df_updated["Bueno_uso"].sum() == 2
    assert "Fantasma_uso" not in df_updated.columns
    assert len(stats["errors"]) == 1
    assert stats["errors"][0]["path"].endswith("no_existe.xlsx")


def test_update_bank_with_exams_bank_missing_returns_error(tmp_path):
    exam_path = tmp_path / "examen_completo.xlsx"
    _build_bank_df({"Tema 01": 1}).iloc[[0]].to_excel(exam_path, index=False)

    manager = QuestionBankManager()
    total, df_updated, stats = manager.update_bank_with_exams(
        str(tmp_path / "no_existe_bank.xlsx"), [str(exam_path)]
    )
    assert total == -1
    assert df_updated is None


def test_update_bank_with_exams_no_exams_returns_error(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    _build_bank_df({"Tema 01": 1}).to_excel(bank_path, index=False)

    manager = QuestionBankManager()
    total, df_updated, stats = manager.update_bank_with_exams(str(bank_path), [])
    assert total == -1
    assert df_updated is None


def test_usage_column_name_strips_accents():
    manager = QuestionBankManager()
    col = manager._usage_column_name(
        "examen_Prevención_Industrial_Evaluación_continua_GITI_GIE_GIEI_25_26_1A_completo", "x.xlsx"
    )
    # No accented letter is turned into an underscore: 'ó' -> 'o'.
    assert col == "examen_Prevencion_Industrial_Evaluacion_continua_GITI_GIE_GIEI_25_26_1A_completo_uso"
    assert "Prevenci_n" not in col
    # Other diacritics (ñ, ü) are also reduced to the base letter.
    assert manager._usage_column_name("Año_Múñoz_Düsseldorf", "x.xlsx") == "Ano_Munoz_Dusseldorf_uso"


def test_label_from_filename_keeps_selected_parts():
    manager = QuestionBankManager()
    name = "examen_Prevencion_Industrial_de_Riesgos_Evaluacion_continua_GITI_GIE_GIEI_25_26_1A_completo.xlsx"
    # 1-based ranges with negative indices counted from the end.
    assert manager.label_from_filename(name, "_", "2:3, -4:-2") == "Prevencion_Industrial_25_26_1A"
    # A list of 1-based indices works too.
    assert manager.label_from_filename(name, "_", [2, 3]) == "Prevencion_Industrial"
    # No parts (or empty/None) keeps the whole base name (without extension).
    whole = "examen_Prevencion_Industrial_de_Riesgos_Evaluacion_continua_GITI_GIE_GIEI_25_26_1A_completo"
    assert manager.label_from_filename(name) == whole
    assert manager.label_from_filename(name, "_", "") == whole
    # Out-of-range indices are ignored; if nothing valid is left, falls back to the whole name.
    assert manager.label_from_filename("a_b_c.xlsx", "_", "99") == "a_b_c"


def test_update_bank_with_exams_derives_label_from_filename(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    bank_df = _build_bank_df({"Tema 01": 3})
    bank_df.to_excel(bank_path, index=False)

    exam_path = tmp_path / "examen_Prevención_Industrial_25_26_1A_completo.xlsx"
    bank_df.iloc[[0, 1]].to_excel(exam_path, index=False)

    manager = QuestionBankManager()
    # No explicit label -> derive from file name keeping parts 2:4, and strip accents in the column.
    total, df_updated, stats = manager.update_bank_with_exams(
        str(bank_path), [str(exam_path)], label_delimiter="_", label_parts="2:4"
    )

    assert total == 2
    assert stats["exams"][0]["label"] == "Prevención_Industrial_25"
    assert stats["exams"][0]["column"] == "Prevencion_Industrial_25_uso"
    assert "Prevencion_Industrial_25_uso" in df_updated.columns


def test_update_bank_with_exams_explicit_label_overrides_derivation(tmp_path):
    bank_path = tmp_path / "bank.xlsx"
    bank_df = _build_bank_df({"Tema 01": 2})
    bank_df.to_excel(bank_path, index=False)

    exam_path = tmp_path / "examen_largo_completo.xlsx"
    bank_df.iloc[[0]].to_excel(exam_path, index=False)

    manager = QuestionBankManager()
    total, df_updated, stats = manager.update_bank_with_exams(
        str(bank_path),
        [{"path": str(exam_path), "label": "MiEtiqueta"}],
        label_delimiter="_",
        label_parts="1",  # ignored because an explicit label is provided
    )
    assert stats["exams"][0]["label"] == "MiEtiqueta"
    assert stats["exams"][0]["column"] == "MiEtiqueta_uso"
