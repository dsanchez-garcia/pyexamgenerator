"""Small text helpers shared by the generation modules."""

import re
import unicodedata

# Characters not allowed in file names on Windows (and '/' on every system), plus control characters.
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def strip_accents(text) -> str:
    """Removes diacritics from ``text`` (á→a, é→e, ñ→n, ü→u, ...).

    Used before building safe column names so accented letters are kept as their base letter
    instead of being turned into underscores by a ``[^a-zA-Z0-9_]`` sanitizer.
    """
    normalized = unicodedata.normalize('NFKD', str(text))
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def safe_filename_part(value) -> str:
    """Makes ``value`` usable inside a file name on any system ('' for None).

    Invalid characters (``/ \\ : * ? " < > |``) become '-', and surrounding spaces and trailing dots
    (rejected by Windows) are removed. Accents, spaces and commas are kept.
    """
    if value is None:
        return ''
    text = _INVALID_FILENAME_CHARS.sub('-', str(value))
    return text.strip().rstrip('.').strip()
