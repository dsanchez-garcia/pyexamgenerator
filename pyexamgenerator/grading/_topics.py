"""Topic named in an attendance session, a schedule or a class quiz.

Shared by the absence justifications (:mod:`pyexamgenerator.grading.attendance`) and the PIR bonus
(:mod:`pyexamgenerator.grading.pir_bonus`), so both recognise the same spellings.
"""

from __future__ import annotations

import re
from typing import Optional

from pyexamgenerator.grading._text import normalize_text
from pyexamgenerator.grading.settings import current_settings


def topic_key(text: object) -> Optional[str]:
    """Topic named in a session, schedule or quiz text: 'TEMA NN' or a named topic (else None).

    Shared by the attendance and the PIR flows, which used to accept different spellings ('Ley 31/95'
    only in one of them). Separators are interchangeable ('Ley 31/95', 'Ley 31_95', 'Ley 31/1995')
    and words must be whole ('Sistema 3' is not 'Tema 3'). The named topics and their expressions
    come from :mod:`pyexamgenerator.grading.settings` ('LPRL' for 'Ley 31/95', 'RSP' for 'RD 39/97').
    """
    words = re.sub(r"[^a-z0-9]+", " ", normalize_text(text))
    for name, pattern in current_settings().named_topics:
        if re.search(pattern, words):
            return name
    match = re.search(r"\btema\s*0?(\d{1,2})\b", words)
    if match:
        return f"TEMA {int(match.group(1)):02d}"
    return None
