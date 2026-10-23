"""Nombres de columna del banco de preguntas (ARC-3).

Son contrato con los bancos que ya tienen los usuarios: si este test falla, se ha renombrado una
columna y los bancos existentes dejarían de leerse bien.
"""

from pyexamgenerator import schema


def test_bank_columns_keep_the_names_of_existing_banks():
    assert schema.BANK_COLUMNS == (
        "Número de pregunta",
        "Tema",
        "Estado",
        "Pregunta",
        "Respuesta A",
        "Respuesta B",
        "Respuesta C",
        "Respuesta D",
        "Respuesta correcta",
        "Texto relevante",
    )
    assert schema.TIMES_USED == "Veces usada en examen"
    assert (schema.STATUS_PENDING, schema.STATUS_ACCEPTABLE) == ("Pendiente de revisar", "Aceptable")


def test_answer_and_usage_columns():
    assert schema.ANSWER_COLUMNS == ("Respuesta A", "Respuesta B", "Respuesta C", "Respuesta D")
    assert tuple(schema.answer_column(letter) for letter in "ABCD") == schema.ANSWER_COLUMNS
    assert schema.usage_column("Parcial_1_25_26") == "Parcial_1_25_26_uso"
    assert schema.usage_column("Parcial").endswith(schema.USAGE_SUFFIX)
