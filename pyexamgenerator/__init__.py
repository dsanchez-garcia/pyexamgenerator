# pyexamgenerator/__init__.py

# Define la versión del paquete (Fuente Única de Verdad)
__version__ = "0.3.0"  # 0.3.0: integración del subpaquete de corrección `grading`

# --- API Pública ---
# "Promueve" las clases y excepciones principales al espacio de nombres del paquete.
# Esto permite a los usuarios importarlas directamente desde 'pyexamgenerator'.

from .exam_generator import ExamConfig, ExamGenerator, NoAcceptableQuestionsError
from .question_generator import (
    QuestionGenerator,
    QuotaExceededError,
    ServiceOverloadedError,
    GeminiRequestError,
)
from .question_bank_manager import QuestionBankManager

# Subpaquete de corrección de exámenes (complementa la generación). El OCR es opcional:
# `pip install pyexamgenerator[grading]`. Se accede como `pyexamgenerator.grading.<...>`.
from . import grading

# (Opcional pero muy recomendado) Define explícitamente la API pública.
# Esto controla lo que se importa cuando un usuario hace `from pyexamgenerator import *`.
__all__ = [
    'ExamConfig',
    'ExamGenerator',
    'NoAcceptableQuestionsError',
    'QuestionGenerator',
    'QuotaExceededError',
    'ServiceOverloadedError',
    'GeminiRequestError',
    'QuestionBankManager',
    'grading',
    '__version__',
]
