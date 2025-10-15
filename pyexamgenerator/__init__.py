# pyexamgenerator/__init__.py

# Define la versión del paquete (Fuente Única de Verdad)
__version__ = "0.1.0"  # O la versión actual que tengas

# --- API Pública ---
# "Promueve" las clases y excepciones principales al espacio de nombres del paquete.
# Esto permite a los usuarios importarlas directamente desde 'pyexamgenerator'.

from .exam_generator import ExamGenerator, NoAcceptableQuestionsError
from .question_generator import QuestionGenerator, QuotaExceededError
from .question_bank_manager import QuestionBankManager

# (Opcional pero muy recomendado) Define explícitamente la API pública.
# Esto controla lo que se importa cuando un usuario hace `from pyexamgenerator import *`.
__all__ = [
    'ExamGenerator',
    'NoAcceptableQuestionsError',
    'QuestionGenerator',
    'QuotaExceededError',
    'QuestionBankManager',
    '__version__',
]