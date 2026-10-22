"""Assigning a written name to an enrolled student only when the match is safe (GRD-6).

A similarity threshold cannot tell a typo ("Maria Garcia Lopes") from another student ("Mario" for
"María"): both score 0.94 against "María García López". So a name is assigned automatically only when

- it has the same words as exactly one enrolled name, in any order and ignoring accents, case and
  punctuation ("GARCÍA LÓPEZ, MARÍA"), or
- its words (two or more) are all in the name of exactly one student ("María García" for
  "María García López").

Otherwise nothing is assigned and the most similar student is returned as a candidate, so the caller
can report it for review.
"""

import re
from difflib import SequenceMatcher
from typing import List, NamedTuple, Optional, Sequence, Tuple

from pyexamgenerator.grading._text import normalize_text

EXACT = "name_exact"
CONTAINED = "name_contained"
AMBIGUOUS = "name_ambiguous"  # several students fit: two with the same name, or two containing it
NONE = "none"


class NameMatch(NamedTuple):
    position: Optional[int]  # position in ``names`` of the assigned student; None if not assigned
    kind: str  # EXACT, CONTAINED, AMBIGUOUS or NONE
    candidate: Optional[int]  # position of the most similar student (also when not assigned)
    score: float  # similarity (0-1) between the written name and the candidate


def name_words(name: object) -> Tuple[str, ...]:
    """The words of a name without accents, case or punctuation, sorted: their order does not matter."""
    return tuple(sorted(re.sub(r"[^a-z0-9]+", " ", normalize_text(name)).split()))


def _similarity(a: Tuple[str, ...], b: Tuple[str, ...]) -> float:
    return SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()


def _contains(words: Tuple[str, ...], part: Tuple[str, ...]) -> bool:
    return all(words.count(word) >= part.count(word) for word in set(part))


def match_name(written: object, names: Sequence[object]) -> NameMatch:
    """Matches ``written`` against ``names`` (enrolled students' full names) with the rules above."""
    target = name_words(written)
    if not target:
        return NameMatch(None, NONE, None, 0.0)
    words: List[Tuple[str, ...]] = [name_words(name) for name in names]
    scores = [_similarity(target, w) for w in words]
    candidate = max(range(len(words)), key=scores.__getitem__) if words else None
    best = scores[candidate] if candidate is not None else 0.0

    exact = [i for i, w in enumerate(words) if w == target]
    if len(exact) == 1:
        return NameMatch(exact[0], EXACT, exact[0], 1.0)
    if len(exact) > 1:
        return NameMatch(None, AMBIGUOUS, exact[0], 1.0)
    if len(target) >= 2:
        containing = [i for i, w in enumerate(words) if _contains(w, target)]
        if len(containing) == 1:
            return NameMatch(containing[0], CONTAINED, containing[0], scores[containing[0]])
        if containing:
            return NameMatch(None, AMBIGUOUS, candidate, best)
    return NameMatch(None, NONE, candidate, best)
