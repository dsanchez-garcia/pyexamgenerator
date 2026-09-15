"""Persistable grading session: bridges exam generation and correction.

A :class:`GradingSession` stores the paths of generated exams, the inputs and column mapping of each
grading workflow, the configuration used and a summary of the results. It is written **both** as a
binary pickle (``.pkl``, exact round-trip) and as a human-readable JSON (``.json``, equivalent
content) so a correction session can be resumed later — for example, knowing the paths of the exams
that were generated and grading them directly without re-specifying every route.
"""

from __future__ import annotations

import json
import pickle
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _to_plain(value: Any) -> Any:
    """Converts dataclasses / nested containers into JSON-serializable primitives."""
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _to_plain(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _strip_known_ext(path: str) -> str:
    """Returns ``path`` without a trailing ``.pkl`` / ``.json`` extension."""
    p = Path(path)
    if p.suffix.lower() in {".pkl", ".json"}:
        return str(p.with_suffix(""))
    return str(path)


@dataclass
class GradingSession:
    """A resumable session linking generated exams with grading workflows.

    Attributes:
        name: Friendly name for the session.
        created_at / updated_at: ISO timestamps.
        generated_exams: One dict per generated exam type (subject/exam/course/exam_type + paths
            ``docx``/``full_docx``/``xlsx``/``xml``).
        grading_inputs: Input paths and column mapping used for correction.
        workflow_configs: Configuration of each workflow that has been run (serialized dataclasses).
        results_summary: Per-workflow summary (row counts, output files, ...).
    """

    name: str = "sesion_pyexamgenerator"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    generated_exams: List[Dict[str, Any]] = field(default_factory=list)
    grading_inputs: Dict[str, Any] = field(default_factory=dict)
    workflow_configs: Dict[str, Any] = field(default_factory=dict)
    results_summary: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def add_generated_exam(
        self,
        *,
        subject: Optional[str] = None,
        exam: Optional[str] = None,
        course: Optional[str] = None,
        exam_type: Optional[str] = None,
        docx: Optional[str] = None,
        full_docx: Optional[str] = None,
        xlsx: Optional[str] = None,
        xml: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """Records the paths of one generated exam type and returns the stored record."""
        record: Dict[str, Any] = {
            "subject": subject,
            "exam": exam,
            "course": course,
            "exam_type": exam_type,
            "docx": docx,
            "full_docx": full_docx,
            "xlsx": xlsx,
            "xml": xml,
        }
        record.update(extra)
        self.generated_exams.append(record)
        self.touch()
        return record

    def record_workflow(
        self,
        name: str,
        config: Any = None,
        outputs: Any = None,
        summary: Any = None,
    ) -> None:
        """Stores the configuration and a results summary of a grading workflow run."""
        if config is not None:
            self.workflow_configs[name] = _to_plain(config)
        entry = self.results_summary.setdefault(name, {})
        if outputs is not None:
            entry["outputs"] = _to_plain(outputs)
        if summary is not None:
            plain_summary = _to_plain(summary)
            if isinstance(plain_summary, dict):
                entry.update(plain_summary)
            else:
                entry["summary"] = plain_summary
        self.touch()

    def set_grading_inputs(self, **inputs: Any) -> None:
        """Merges grading input paths / column mapping into the session."""
        self.grading_inputs.update(_to_plain(inputs))
        self.touch()

    # Convenience accessors for resuming correction directly from generated exams.
    def generated_xml_paths(self) -> List[str]:
        return [str(r["xml"]) for r in self.generated_exams if r.get("xml")]

    def generated_completo_xlsx_paths(self) -> List[str]:
        return [str(r["xlsx"]) for r in self.generated_exams if r.get("xlsx")]

    def generated_docx_paths(self) -> List[str]:
        return [str(r["docx"]) for r in self.generated_exams if r.get("docx")]

    def to_dict(self) -> Dict[str, Any]:
        return _to_plain(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GradingSession":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: str) -> Tuple[str, str]:
        """Writes the session to ``<base>.pkl`` and ``<base>.json`` and returns both paths."""
        base = _strip_known_ext(path)
        pkl_path = base + ".pkl"
        json_path = base + ".json"
        Path(pkl_path).parent.mkdir(parents=True, exist_ok=True)
        self.touch()
        with open(pkl_path, "wb") as handle:
            pickle.dump(self, handle)
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)
        return pkl_path, json_path

    @classmethod
    def load(cls, path: str) -> "GradingSession":
        """Loads a session from ``path`` (``.pkl`` or ``.json``) or from its base name.

        If an exact file is given it is used; otherwise the pickle is preferred over the JSON.
        """
        p = Path(path)
        if p.suffix.lower() == ".pkl" and p.exists():
            with open(p, "rb") as handle:
                return pickle.load(handle)
        if p.suffix.lower() == ".json" and p.exists():
            with open(p, "r", encoding="utf-8") as handle:
                return cls.from_dict(json.load(handle))

        base = _strip_known_ext(str(path))
        pkl_candidate = Path(base + ".pkl")
        if pkl_candidate.exists():
            with open(pkl_candidate, "rb") as handle:
                return pickle.load(handle)
        json_candidate = Path(base + ".json")
        if json_candidate.exists():
            with open(json_candidate, "r", encoding="utf-8") as handle:
                return cls.from_dict(json.load(handle))
        raise FileNotFoundError(f"No session file found for '{path}' (.pkl or .json).")
