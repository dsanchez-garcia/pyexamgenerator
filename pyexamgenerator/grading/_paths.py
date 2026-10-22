"""Output path resolution shared by the grading workflows."""

from pathlib import Path
from typing import Optional


def prepare_output_path(path: str, output_dir: Optional[str] = None) -> str:
    """Returns where to write ``path`` and makes sure its folder exists.

    With ``output_dir``, a relative path is written inside that folder (only its file name is
    kept); an absolute path is an explicit choice and is kept as is (before, it was moved into
    ``output_dir`` too). Without ``output_dir`` the path is used unchanged.
    """
    target = Path(path)
    if output_dir and not target.is_absolute():
        target = Path(output_dir) / target.name
    if str(target.parent) not in ("", "."):
        target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)
