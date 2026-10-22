"""Small text helpers shared by the generation modules."""

import unicodedata


def strip_accents(text) -> str:
    """Removes diacritics from ``text`` (á→a, é→e, ñ→n, ü→u, ...).

    Used before building safe column names so accented letters are kept as their base letter
    instead of being turned into underscores by a ``[^a-zA-Z0-9_]`` sanitizer.
    """
    normalized = unicodedata.normalize('NFKD', str(text))
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))
