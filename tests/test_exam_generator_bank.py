"""Regresiones de lectura del banco y registro de uso en `ExamGenerator`."""

import random

import pandas as pd

from pyexamgenerator.exam_generator import ExamGenerator


def _bank(prefix, numbers):
    return pd.DataFrame(
        [
            {
                "Número de pregunta": number,
                "Tema": "Tema 01",
                "Estado": "Aceptable",
                "Pregunta": f"{prefix} pregunta {i}",
                "Respuesta A": "a",
                "Respuesta B": "b",
                "Respuesta C": "c",
                "Respuesta D": "d",
                "Respuesta correcta": "a",
                "Texto relevante": "",
            }
            for i, number in enumerate(numbers)
        ]
    )


def _generate(generator, bank_path, out_dir, **kwargs):
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(out_dir),
        subject="Asig",
        exam="Parcial",
        course="25-26",
        exam_names=["A"],
        **kwargs,
    )


def test_generator_rereads_bank_on_every_call(tmp_path):
    """BUG-1: una segunda generación con otro banco no debe reutilizar el primero."""
    bank_one = tmp_path / "uno.xlsx"
    bank_two = tmp_path / "dos.xlsx"
    _bank("Uno", [1, 2, 3]).to_excel(bank_one, index=False)
    _bank("Dos", [1, 2, 3]).to_excel(bank_two, index=False)

    generator = ExamGenerator()
    random.seed(1)
    _generate(generator, bank_one, tmp_path / "out1")
    _generate(generator, bank_two, tmp_path / "out2", update_excel=True)

    exam_two = pd.read_excel(tmp_path / "out2" / "examen_Asig_Parcial_25-26_A_completo.xlsx")
    assert all(text.startswith("Dos") for text in exam_two["Pregunta"])

    # El banco 2 actualizado conserva sus propias preguntas (antes se sobrescribía con el banco 1).
    updated_two = pd.read_excel(bank_two)
    assert all(text.startswith("Dos") for text in updated_two["Pregunta"])


def test_update_excel_marks_only_selected_rows_with_duplicate_numbers(tmp_path):
    """BUG-2: 'Número de pregunta' repetido (bancos fusionados) no debe marcar filas ajenas."""
    bank = _bank("Q", [1, 2, 1, 2])  # números repetidos, como tras concatenar dos bancos
    bank["Tema"] = ["Tema 01", "Tema 01", "Tema 02", "Tema 02"]
    bank_path = tmp_path / "banco.xlsx"
    bank.to_excel(bank_path, index=False)

    generator = ExamGenerator()
    random.seed(3)
    _generate(
        generator,
        bank_path,
        tmp_path / "out",
        questions_per_topic={"Tema 01": 2},
        update_excel=True,
    )

    updated = pd.read_excel(bank_path)
    usage_cols = [col for col in updated.columns if col.endswith("_uso")]
    assert len(usage_cols) == 1
    marked = updated.loc[updated[usage_cols[0]] == 1, "Tema"].tolist()
    assert marked == ["Tema 01", "Tema 01"]
    assert updated["Veces usada en examen"].tolist() == [1, 1, 0, 0]


def test_usage_column_name_strips_accents_like_the_bank_manager(tmp_path):
    """BUG-6: la generación convertía las tildes en '_' ('Evaluaci_n'), a diferencia del banco."""
    bank_path = tmp_path / "banco.xlsx"
    _bank("Q", [1, 2]).to_excel(bank_path, index=False)

    generator = ExamGenerator()
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(tmp_path / "out"),
        subject="Asig",
        exam="Evaluación Final",
        course="25-26",
        exam_names=["A"],
        update_excel=True,
    )

    usage_cols = [col for col in pd.read_excel(bank_path).columns if col.endswith("_uso")]
    assert usage_cols == ["Evaluacion_Final_25_26_uso"]


def test_usage_column_reuses_legacy_name_when_present(tmp_path):
    """BUG-6: si el banco ya tiene la columna con el nombre antiguo, se reutiliza (sin duplicar)."""
    bank = _bank("Q", [1, 2])
    bank["Evaluaci_n_Final_25_26_uso"] = [1, 0]
    bank_path = tmp_path / "banco.xlsx"
    bank.to_excel(bank_path, index=False)

    generator = ExamGenerator()
    random.seed(0)
    generator.generate_exam_from_excel(
        bank_excel_path=str(bank_path),
        output_dir=str(tmp_path / "out"),
        subject="Asig",
        exam="Evaluación Final",
        course="25-26",
        exam_names=["A"],
        update_excel=True,
    )

    updated = pd.read_excel(bank_path)
    usage_cols = [col for col in updated.columns if col.endswith("_uso")]
    assert usage_cols == ["Evaluaci_n_Final_25_26_uso"]
    assert updated["Veces usada en examen"].tolist() == [1, 1]
