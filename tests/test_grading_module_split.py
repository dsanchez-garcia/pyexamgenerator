"""ARC-5: `attendance.py` y `extraction.py` se dividieron; las rutas de import anteriores siguen valiendo."""

import pytest

from pyexamgenerator import grading
from pyexamgenerator.grading import _topics, attendance, pir_bonus, theory_bonus


def test_attendance_still_exports_the_bonus_classes():
    assert attendance.PIRBonusCalculator is pir_bonus.PIRBonusCalculator
    assert attendance.PIRSession is pir_bonus.PIRSession
    assert attendance.TheoryBonusApplier is theory_bonus.TheoryBonusApplier
    assert attendance.TheoryTopicReporter is theory_bonus.TheoryTopicReporter
    assert attendance.apply_theory_bonus_from_attendance_quiz is theory_bonus.apply_theory_bonus_from_attendance_quiz
    assert attendance.export_theory_topic_reports is theory_bonus.export_theory_topic_reports
    assert grading.PIRBonusCalculator is pir_bonus.PIRBonusCalculator


def test_justifications_and_pir_share_the_topic_rules():
    assert attendance.topic_key is _topics.topic_key
    assert pir_bonus.topic_key is _topics.topic_key


def test_extraction_still_exports_the_image_grader():
    extraction = pytest.importorskip("pyexamgenerator.grading.extraction")
    from pyexamgenerator.grading import image_grading
    from pyexamgenerator.grading.extraction import ImageExamGrader, QuestionInfo

    assert ImageExamGrader is image_grading.ImageExamGrader is grading.ImageExamGrader
    assert QuestionInfo is image_grading.QuestionInfo
    assert extraction.CorrectorExamenesDesdeImagenes is image_grading.ImageExamGrader
    assert extraction.PreguntaInfo is image_grading.QuestionInfo
    with pytest.raises(AttributeError):
        extraction.no_existe  # noqa: B018 - the lookup is what is tested
