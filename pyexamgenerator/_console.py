"""Console questions used when the caller passes no callback (scripts run from a terminal).

The library asks through optional callbacks (e.g. ``review_callback``); these helpers are only the
default for an interactive terminal. Without one (GUI, notebook, CI) ``input()`` would block or fail,
so callers check :func:`stdin_is_interactive` first.
"""

import sys

_YES_ANSWERS = {"sí", "si", "s", "yes", "y"}


def stdin_is_interactive() -> bool:
    """True when input() can ask the user (a terminal), False under a GUI, notebook or CI."""
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def ask_yes_no(question: str) -> bool:
    """Asks ``question`` in the console; accepts sí/si/s/yes/y (any case) as yes."""
    return input(question).strip().lower() in _YES_ANSWERS
