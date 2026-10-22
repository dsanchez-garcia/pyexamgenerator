"""La versión publicada coincide en todos los ficheros que la declaran (PKG-7)."""

import json
import re
from pathlib import Path

import pyexamgenerator

ROOT = Path(__file__).resolve().parents[1]


def _citation_field(name):
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    match = re.search(rf'^{re.escape(name)}:\s*"?([^"\r\n]+?)"?\s*$', text, re.M)
    assert match, f"CITATION.cff no tiene '{name}'"
    return match.group(1)


def test_version_and_release_date_match_everywhere():
    """Al publicar, la versión cambia en `__init__.py`, CITATION.cff y .zenodo.json, y la fecha en
    esos dos y en CHANGELOG.md: este test avisa si alguno se queda atrás."""
    version = pyexamgenerator.__version__
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    release_date = _citation_field("date-released")

    assert _citation_field("version") == version
    assert zenodo["version"] == version
    assert zenodo["publication_date"] == release_date
    assert f"## [{version}] - {release_date}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    tag_urls = [item["identifier"] for item in zenodo.get("related_identifiers", []) if "/tree/" in item["identifier"]]
    assert tag_urls and all(url.endswith(f"/tree/v{version}") for url in tag_urls)
