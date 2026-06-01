"""Subpaquete de corrección de exámenes (integrado desde `examgrader`).

Cubre: corrección desde Excel/Moodle, OCR de hojas manuscritas (opcional), integración de notas,
cruce de asistencias + justificaciones + cuestionarios, y el punto extra PIR.

El OCR (cv2/rapidocr) es una dependencia pesada y **opcional**: instálala con
``pip install pyexamgenerator[grading]``. Sin ella, todo lo que no sea OCR sigue funcionando y
``HAS_OCR`` vale ``False``.
"""

from pyexamgenerator.grading.api import (
    ExamCorrectionAPI,
    ExcelGradingConfig,
    ImageGradingConfig,
    MoodleIntegrationConfig,
    OCRIntegrationConfig,
    PIRBonusConfig,
    TheoryBonusConfig,
    TheoryTopicReportConfig,
    EnrollmentMergeConfig,
    AbsenceJustificationConfig,
    FinalGradeConfig,
)
from pyexamgenerator.grading.data import SharedExamDataStore, EnrollmentMerger
from pyexamgenerator.grading.graders import ExamGrader
from pyexamgenerator.grading.integrations import MoodleGradeIntegrator, OcrGradeIntegrator
from pyexamgenerator.grading.session import GradingSession
from pyexamgenerator.grading.final_grade import FinalGradeCalculator
from pyexamgenerator.grading.attendance import (
    AbsenceJustificationManager,
    PIRBonusCalculator,
    TheoryBonusApplier,
    TheoryTopicReporter,
)

# OCR pesado (cv2/rapidocr): opcional -> pip install pyexamgenerator[grading]
try:
    from pyexamgenerator.grading.extraction import AnswerSheetExtractor, ImageExamGrader

    HAS_OCR = True
except ImportError:
    AnswerSheetExtractor = None
    ImageExamGrader = None
    HAS_OCR = False

__all__ = [
    "ExamCorrectionAPI",
    # Clases trabajadoras con estado (guardan inputs/outputs como atributos)
    "SharedExamDataStore",
    "EnrollmentMerger",
    "ExamGrader",
    "MoodleGradeIntegrator",
    "OcrGradeIntegrator",
    "AbsenceJustificationManager",
    "PIRBonusCalculator",
    "TheoryBonusApplier",
    "TheoryTopicReporter",
    "AnswerSheetExtractor",
    "ImageExamGrader",
    "GradingSession",
    "FinalGradeCalculator",
    "HAS_OCR",
    # Configs
    "ExcelGradingConfig",
    "ImageGradingConfig",
    "MoodleIntegrationConfig",
    "OCRIntegrationConfig",
    "PIRBonusConfig",
    "TheoryBonusConfig",
    "TheoryTopicReportConfig",
    "EnrollmentMergeConfig",
    "AbsenceJustificationConfig",
    "FinalGradeConfig",
]
