import difflib
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import pandas as pd

# Backend OCR: el paquete nuevo `rapidocr` (>=2, soporta Python 3.13/3.14) si esta disponible;
# si no, el antiguo `rapidocr_onnxruntime` (solo Python <3.13). La API difiere y se normaliza
# en AnswerSheetExtractor._ocr_call.
try:
    from rapidocr import RapidOCR

    _RAPIDOCR_BACKEND = "new"
except ImportError:  # pragma: no cover - depende del entorno
    from rapidocr_onnxruntime import RapidOCR

    _RAPIDOCR_BACKEND = "legacy"

from pyexamgenerator.grading._ids import normalize_id
from pyexamgenerator.grading._text import normalize_key

logger = logging.getLogger(__name__)


Point = Tuple[float, float]


@dataclass
class OcrToken:
    text: str
    conf: float
    points: List[Point]
    cx: float
    cy: float


@dataclass
class SheetResult:
    image: str
    exam_type: Optional[str]
    first_name_raw: Optional[str]
    last_name_raw: Optional[str]
    student_name_ocr: Optional[str]
    student_name_official: Optional[str]
    student_id_official: Optional[str]
    answers: Dict[str, str]
    audit_rows: List[Dict[str, object]]
    rotation_degrees: int = 0


@dataclass
class DebugCell:
    question_num: int
    letter: str
    score: float
    rect: Tuple[int, int, int, int]
    selected: bool


class AnswerSheetExtractor:
    """Extracts exam type, student identity and answers from scanned answer sheets."""

    def __init__(
        self,
        enrollment_xlsx_path: Optional[str] = None,
        enrollment_df: Optional[pd.DataFrame] = None,
        debug_dir: Optional[str] = None,
        min_mark_ratio: float = 0.17,
        min_gap: float = 0.05,
        aggressive_recovery: bool = False,
        aggressive_min_ratio: float = 0.11,
        aggressive_min_gap_ratio: float = 0.25,
        aggressive_min_top_vs_second: float = 1.10,
        id_col: str = "Número de ID",
        forced_student_by_image: Optional[Dict[str, str]] = None,
        temp_image_dir: Optional[str] = None,
    ) -> None:
        self.ocr = RapidOCR()
        self._ocr_backend = _RAPIDOCR_BACKEND
        self.enrollment_df: Optional[pd.DataFrame] = None
        self.lookup_names: List[str] = []
        self.debug_dir = debug_dir
        self.min_mark_ratio = float(min_mark_ratio)
        self.min_gap = float(min_gap)
        self.aggressive_recovery = bool(aggressive_recovery)
        self.aggressive_min_ratio = float(aggressive_min_ratio)
        self.aggressive_min_gap_ratio = float(aggressive_min_gap_ratio)
        self.aggressive_min_top_vs_second = float(aggressive_min_top_vs_second)
        self.id_col = id_col
        self.temp_image_dir = self._resolve_temp_image_dir(temp_image_dir)
        # Identificación manual del alumno por imagen: {nombre_de_imagen: "Número de ID" o nombre oficial}.
        # Se usa para hojas cuyo nombre manuscrito el OCR no puede leer (incidencia MISSING_ID).
        self.forced_student_by_image: Dict[str, str] = {
            str(k): str(v) for k, v in (forced_student_by_image or {}).items()
        }
        if enrollment_df is not None:
            self._set_enrollment_df(enrollment_df)
        if enrollment_xlsx_path:
            self._load_enrollment(enrollment_xlsx_path)

    def _set_enrollment_df(self, enrollment_df: pd.DataFrame) -> None:
        # A filtered or sorted roster keeps its old labels; reset them so labels and positions agree.
        enrollment = enrollment_df.reset_index(drop=True)
        enrollment["Lookup_Name"] = (
            enrollment["Nombre"].astype(str).str.strip() + " " + enrollment["Apellido(s)"].astype(str).str.strip()
        ).str.lower()
        self.enrollment_df = enrollment
        self.lookup_names = enrollment["Lookup_Name"].tolist()

    def _load_enrollment(self, enrollment_xlsx_path: str) -> None:
        self._set_enrollment_df(pd.read_excel(enrollment_xlsx_path))

    _normalize = staticmethod(normalize_key)

    @classmethod
    def _normalize_option_label(cls, text: str) -> Optional[str]:
        norm = cls._normalize(text)
        if norm in {"a", "4"}:
            return "a"
        if norm in {"b", "8"}:
            return "b"
        if norm in {"c"}:
            return "c"
        if norm in {"d", "0", "o"}:
            return "d"
        if norm in {"nc", "mc"}:
            return "nc"
        return None

    @staticmethod
    def _parse_question_number(text: str) -> Optional[int]:
        clean = str(text).strip()
        match = re.search(r"\b(\d{1,2})\b", clean)
        if not match:
            return None
        number = int(match.group(1))
        if 1 <= number <= 99:
            return number
        return None

    def _ocr_call(self, image_gray: np.ndarray) -> List[Sequence]:
        """Run OCR and normalize the result to a list of ``[points, text, conf]`` items.

        Handles both backends: the new ``rapidocr`` returns a ``RapidOCROutput`` object with
        ``.boxes``/``.txts``/``.scores``; the legacy ``rapidocr_onnxruntime`` returns a
        ``(result, elapse)`` tuple where each item is already ``[points, text, conf]``.
        """
        if self._ocr_backend == "new":
            image_bgr = (
                image_gray if getattr(image_gray, "ndim", 2) == 3 else cv2.cvtColor(image_gray, cv2.COLOR_GRAY2BGR)
            )
            out = self.ocr(image_bgr)
            if out is None or out.boxes is None:
                return []
            return [[box, txt, score] for box, txt, score in zip(out.boxes, out.txts, out.scores, strict=True)]

        result, _ = self.ocr(image_gray)
        return list(result) if result else []

    @staticmethod
    def _token_from_result(item: Sequence) -> OcrToken:
        points = [(float(x), float(y)) for x, y in item[0]]
        cx = sum(x for x, _ in points) / len(points)
        cy = sum(y for _, y in points) / len(points)
        return OcrToken(text=str(item[1]).strip(), conf=float(item[2]), points=points, cx=cx, cy=cy)

    @staticmethod
    def _rotate_image(image_gray: np.ndarray, angle: int) -> np.ndarray:
        if angle == 0:
            return image_gray
        if angle == 90:
            return cv2.rotate(image_gray, cv2.ROTATE_90_CLOCKWISE)
        if angle == 180:
            return cv2.rotate(image_gray, cv2.ROTATE_180)
        if angle == 270:
            return cv2.rotate(image_gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
        raise ValueError(f"Unsupported rotation angle: {angle}")

    @classmethod
    def _orientation_score(cls, tokens: Sequence[OcrToken]) -> float:
        if not tokens:
            return 0.0

        score = 0.0
        for token in tokens:
            norm = cls._normalize(token.text)
            if norm in {"a", "b", "c", "d", "nc", "tipo", "nombre", "apellido", "apellidos"}:
                score += 3.0
            if re.fullmatch(r"\d{2}", token.text.strip()):
                score += 2.0

        header_hits = sum(1 for t in tokens if cls._normalize(t.text) in {"a", "b", "c", "d", "nc"})
        score += min(header_hits, 5) * 1.5
        return score

    def _extract_tokens_with_auto_rotation(
        self,
        image_gray: np.ndarray,
    ) -> Tuple[np.ndarray, List[OcrToken], int]:
        best_score = float("-inf")
        best_tokens: List[OcrToken] = []
        best_image = image_gray
        best_angle = 0

        for angle in (0, 90, 180, 270):
            rotated = self._rotate_image(image_gray, angle)
            items = self._ocr_call(rotated)
            if not items:
                continue

            tokens = [self._token_from_result(item) for item in items]
            score = self._orientation_score(tokens)
            if score > best_score:
                best_score = score
                best_tokens = tokens
                best_image = rotated
                best_angle = angle

        return best_image, best_tokens, best_angle

    def _extract_exam_type(self, tokens: Sequence[OcrToken]) -> Optional[str]:
        joined = " ".join(t.text for t in tokens)
        match = re.search(r"tipo\s*[:\-]?\s*([a-z0-9]+)", joined, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    def _extract_label_value(self, tokens: Sequence[OcrToken], label_key: str, y_tol: float = 40.0) -> Optional[str]:
        if label_key == "first_name":
            valid_labels = {"nombre"}
        elif label_key == "last_name":
            valid_labels = {"apellido", "apellidos"}
        else:
            valid_labels = {label_key}

        label_candidates = [t for t in tokens if self._normalize(t.text) in valid_labels]
        if not label_candidates:
            return None

        label = max(label_candidates, key=lambda t: t.conf)
        value_candidates = [
            t
            for t in tokens
            if t.cx > label.cx + 20
            and abs(t.cy - label.cy) <= y_tol
            and len(self._normalize(t.text)) >= 2
            and self._normalize(t.text) not in {"apellidos", "apellido", "nombre", "dninie", "firma", "datosdelalumno"}
        ]
        if not value_candidates:
            return None

        value = min(value_candidates, key=lambda t: (abs(t.cy - label.cy), t.cx))
        return value.text.strip() or None

    def _match_official_student(
        self,
        student_name_ocr: Optional[str],
        first_name_raw: Optional[str],
        last_name_raw: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        if self.enrollment_df is None:
            return None, None

        if first_name_raw and last_name_raw:
            first_name_norm = self._normalize(first_name_raw)
            last_name_norm = self._normalize(last_name_raw)
            best_idx: Any = None  # a row label of enrollment_df
            best_score = 0.0

            for idx, row in self.enrollment_df.iterrows():
                row_first = self._normalize(str(row.get("Nombre", "")))
                row_last = self._normalize(str(row.get("Apellido(s)", "")))
                score_first = SequenceMatcher(None, first_name_norm, row_first).ratio()
                score_last = SequenceMatcher(None, last_name_norm, row_last).ratio()
                score = (0.35 * score_first) + (0.65 * score_last)
                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx is not None and best_score >= 0.50:
                # best_idx is an index label (from iterrows), so look it up with .loc.
                row = self.enrollment_df.loc[best_idx]
                official_name = f"{row['Nombre']} {row['Apellido(s)']}".strip()
                official_id = normalize_id(row.get(self.id_col, "")) or None
                return official_name, official_id

        if not student_name_ocr:
            return None, None

        cleaned_name = student_name_ocr.strip().lower()
        matches = difflib.get_close_matches(cleaned_name, self.lookup_names, n=1, cutoff=0.6)
        if not matches:
            return None, None

        row = self.enrollment_df[self.enrollment_df["Lookup_Name"] == matches[0]].iloc[0]
        official_name = f"{row['Nombre']} {row['Apellido(s)']}".strip()
        official_id = normalize_id(row.get(self.id_col, "")) or None
        return official_name, official_id

    def _resolve_forced_student(self, identifier: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolve a manually supplied student identifier against the enrollment.

        ``identifier`` may be the official ``id_col`` value ("Número de ID") or the student's
        full name as it appears in the enrollment. Returns ``(official_name, official_id)``.
        Raises ``ValueError`` if no enrollment is loaded or the identifier matches no student.
        """
        if self.enrollment_df is None:
            raise ValueError("forced_student_by_image requiere una matrícula cargada (enrollment_df).")

        ident = str(identifier).strip()
        if not ident:
            raise ValueError("forced_student_by_image: identificador de alumno vacío.")

        def _row_to_pair(row: pd.Series) -> Tuple[Optional[str], Optional[str]]:
            official_name = f"{row.get('Nombre', '')} {row.get('Apellido(s)', '')}".strip()
            official_id = normalize_id(row.get(self.id_col, "")) or None
            return official_name or None, official_id

        # 1) Coincidencia exacta por "Número de ID" (lo más inequívoco).
        if self.id_col in self.enrollment_df.columns:
            id_series = self.enrollment_df[self.id_col].map(normalize_id)
            matches = self.enrollment_df[id_series == normalize_id(ident)]
            if not matches.empty:
                return _row_to_pair(matches.iloc[0])

        # 2) Coincidencia exacta por nombre completo normalizado ("Nombre Apellido(s)").
        ident_norm = self._normalize(ident)
        for _, row in self.enrollment_df.iterrows():
            full = f"{row.get('Nombre', '')} {row.get('Apellido(s)', '')}"
            full_rev = f"{row.get('Apellido(s)', '')} {row.get('Nombre', '')}"
            if self._normalize(full) == ident_norm or self._normalize(full_rev) == ident_norm:
                return _row_to_pair(row)

        # 3) Coincidencia aproximada por nombre.
        fuzzy = difflib.get_close_matches(ident.lower(), self.lookup_names, n=1, cutoff=0.6)
        if fuzzy:
            row = self.enrollment_df[self.enrollment_df["Lookup_Name"] == fuzzy[0]].iloc[0]
            return _row_to_pair(row)

        raise ValueError(
            f"forced_student_by_image: no se encontró ningún alumno para '{identifier}' "
            f"en la matrícula (ni por '{self.id_col}' ni por nombre)."
        )

    @staticmethod
    def _infer_question_spacing(question_tokens: Sequence[OcrToken]) -> float:
        ys = sorted(t.cy for t in question_tokens)
        if len(ys) < 2:
            return 35.0
        deltas = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        deltas = [d for d in deltas if 10 <= d <= 80]
        if not deltas:
            return 35.0
        deltas.sort()
        return deltas[len(deltas) // 2]

    def _extract_answers(
        self,
        tokens: Sequence[OcrToken],
        image_gray: np.ndarray,
    ) -> Tuple[Dict[str, str], List[DebugCell], Dict[str, str]]:
        option_tokens = [t for t in tokens if self._normalize_option_label(t.text) is not None]
        if len(option_tokens) < 4:
            return {}, [], {}

        option_by_letter: Dict[str, OcrToken] = {}
        for letter in ("a", "b", "c", "d", "nc"):
            candidates = [t for t in option_tokens if self._normalize_option_label(t.text) == letter]
            if candidates:
                option_by_letter[letter] = max(candidates, key=lambda t: t.conf)

        base_labels = ["a", "b", "c", "d"]
        order_idx = {label: i for i, label in enumerate(base_labels)}
        detected_base = [label for label in base_labels if label in option_by_letter]
        if len(detected_base) < 3:
            return {}, [], {}

        detected_sorted = sorted(detected_base, key=lambda label: order_idx[label])
        steps: List[float] = []
        for i in range(len(detected_sorted) - 1):
            left = detected_sorted[i]
            right = detected_sorted[i + 1]
            idx_gap = order_idx[right] - order_idx[left]
            if idx_gap <= 0:
                continue
            x_gap = option_by_letter[right].cx - option_by_letter[left].cx
            steps.append(x_gap / float(idx_gap))
        if not steps:
            return {}, [], {}

        steps.sort()
        base_step = steps[len(steps) // 2]
        anchor_label = detected_sorted[0]
        anchor_x = option_by_letter[anchor_label].cx
        option_x: Dict[str, float] = {}
        for label in base_labels:
            if label in option_by_letter:
                option_x[label] = option_by_letter[label].cx
            else:
                option_x[label] = anchor_x + ((order_idx[label] - order_idx[anchor_label]) * base_step)
        if "nc" in option_by_letter:
            option_x["nc"] = option_by_letter["nc"].cx

        header_y = sum(option_by_letter[label].cy for label in detected_base) / float(len(detected_base))

        q_tokens_all = []
        for t in tokens:
            qnum = self._parse_question_number(t.text)
            if qnum is None:
                continue
            if t.cy <= header_y:
                continue
            q_tokens_all.append(t)
        if not q_tokens_all:
            return {}, [], {}

        x_bin_size = 60.0
        bins: Dict[int, List[OcrToken]] = {}
        for t in q_tokens_all:
            bin_key = int(t.cx // x_bin_size)
            bins.setdefault(bin_key, []).append(t)

        best_bin_key = max(bins.keys(), key=lambda k: len(bins[k]))
        best_bin_tokens = bins[best_bin_key]
        center_x = sum(t.cx for t in best_bin_tokens) / float(len(best_bin_tokens))
        q_tokens = [t for t in q_tokens_all if abs(t.cx - center_x) <= 85]
        if len(q_tokens) < 8:
            q_tokens = q_tokens_all
        if not q_tokens:
            return {}, [], {}

        q_by_num: Dict[int, OcrToken] = {}
        for tok in q_tokens:
            parsed = self._parse_question_number(tok.text)
            if parsed is None:
                continue
            num = parsed
            if num not in q_by_num or tok.conf > q_by_num[num].conf:
                q_by_num[num] = tok

        q_sorted = sorted(q_by_num.items(), key=lambda kv: kv[0])
        if not q_sorted:
            return {}, [], {}
        spacing = self._infer_question_spacing([kv[1] for kv in q_sorted])

        y_by_num: Dict[int, float] = {num: tok.cy for num, tok in q_sorted}
        min_num = min(y_by_num.keys())
        max_num = max(y_by_num.keys())

        for num in range(min_num - 1, 0, -1):
            next_num = num + 1
            if next_num in y_by_num:
                est = y_by_num[next_num] - spacing
                if est > 0:
                    y_by_num[num] = est

        for num in range(1, max_num + 1):
            if num in y_by_num:
                continue
            lower = [k for k in y_by_num.keys() if k < num]
            upper = [k for k in y_by_num.keys() if k > num]
            if lower and upper:
                lo = max(lower)
                hi = min(upper)
                frac = (num - lo) / float(hi - lo)
                y_by_num[num] = y_by_num[lo] + ((y_by_num[hi] - y_by_num[lo]) * frac)
            elif lower:
                lo = max(lower)
                y_by_num[num] = y_by_num[lo] + spacing
            elif upper:
                hi = min(upper)
                y_by_num[num] = y_by_num[hi] - spacing

        q_sorted_final = sorted(y_by_num.items(), key=lambda kv: kv[0])

        # Build a binary mask to measure ink density per answer cell.
        blur = cv2.GaussianBlur(image_gray, (5, 5), 0)
        ink = cv2.adaptiveThreshold(
            blur,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            35,
            15,
        )

        cell_h = max(10, int(spacing * 0.36))
        cell_w = max(10, int(spacing * 0.34))

        out: Dict[str, str] = {}
        debug_cells: List[DebugCell] = []
        decision_by_question: Dict[str, str] = {}

        def score_letters_for_y(
            y_center: int, letters: Sequence[str]
        ) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
            scored: List[Tuple[str, float, Tuple[int, int, int, int]]] = []
            for letter in letters:
                x = int(option_x[letter])
                y0 = max(0, y_center - cell_h)
                y1 = min(ink.shape[0], y_center + cell_h)
                x0 = max(0, x - cell_w)
                x1 = min(ink.shape[1], x + cell_w)
                roi = ink[y0:y1, x0:x1]
                ratio = float(np.count_nonzero(roi)) / float(roi.size) if roi.size else 0.0
                scored.append((letter, ratio, (x0, y0, x1, y1)))
            return scored

        for qnum, qy in q_sorted_final:
            key = f"Pregunta {qnum:02d}"
            y = int(qy)
            letters_to_score = ["a", "b", "c", "d"] + (["nc"] if "nc" in option_by_letter else [])

            y_offsets = [0, int(cell_h * 0.45), -int(cell_h * 0.45)]
            best_candidate = None
            for y_offset in y_offsets:
                y_try = max(0, min(ink.shape[0] - 1, y + y_offset))
                scored = score_letters_for_y(y_try, letters_to_score)
                scored_sorted = sorted(scored, key=lambda item: item[1], reverse=True)
                best_l = scored_sorted[0][0]
                best_s = scored_sorted[0][1]
                second_s = scored_sorted[1][1] if len(scored_sorted) > 1 else 0.0
                margin = best_s - second_s
                candidate_tuple = (best_s, margin, y_try, scored_sorted, best_l, second_s)
                if best_candidate is None or candidate_tuple[:2] > best_candidate[:2]:
                    best_candidate = candidate_tuple

            assert best_candidate is not None
            best_score, margin_score, y_selected, scored_sorted, best_letter, second_score = best_candidate

            adaptive_accept = (
                best_score >= (self.min_mark_ratio * 0.78)
                and margin_score >= (self.min_gap * 0.45)
                and (best_score / max(second_score, 1e-6)) >= 1.22
            )

            aggressive_accept = (
                self.aggressive_recovery
                and best_score >= self.aggressive_min_ratio
                and margin_score >= (self.min_gap * self.aggressive_min_gap_ratio)
                and (best_score / max(second_score, 1e-6)) >= self.aggressive_min_top_vs_second
            )

            strict_reject = best_score < self.min_mark_ratio or margin_score < self.min_gap
            if strict_reject and not adaptive_accept and not aggressive_accept:
                out[key] = "-"
                selected_letter = None
                decision_by_question[key] = "blank"
            elif best_letter == "nc":
                out[key] = "nc"
                selected_letter = "nc"
                decision_by_question[key] = "nc"
            else:
                out[key] = best_letter
                selected_letter = best_letter
                if strict_reject and aggressive_accept and not adaptive_accept:
                    decision_by_question[key] = "aggressive"
                elif strict_reject and adaptive_accept:
                    decision_by_question[key] = "adaptive"
                else:
                    decision_by_question[key] = "strict"

            scored_for_debug = score_letters_for_y(y_selected, letters_to_score)
            for letter, ratio, rect in scored_for_debug:
                x0, y0, x1, y1 = rect
                debug_cells.append(
                    DebugCell(
                        question_num=qnum,
                        letter=letter,
                        score=ratio,
                        rect=(x0, y0, x1, y1),
                        selected=(letter == selected_letter),
                    )
                )

        return out, debug_cells, decision_by_question

    def _save_debug_image(self, image_path: str, image_gray: np.ndarray, debug_cells: Sequence[DebugCell]) -> None:
        if not self.debug_dir:
            return

        os.makedirs(self.debug_dir, exist_ok=True)
        image_color = cv2.cvtColor(image_gray, cv2.COLOR_GRAY2BGR)

        for cell in debug_cells:
            x0, y0, x1, y1 = cell.rect
            color = (0, 190, 0) if cell.selected else (0, 70, 210)
            thickness = 2 if cell.selected else 1
            cv2.rectangle(image_color, (x0, y0), (x1, y1), color, thickness)
            label = f"{cell.question_num:02d}-{cell.letter}:{cell.score:.2f}"
            cv2.putText(
                image_color, label, (x0, max(12, y0 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA
            )

        stem = Path(image_path).stem
        out_path = Path(self.debug_dir) / f"{stem}_debug.png"
        cv2.imwrite(str(out_path), image_color)

    @staticmethod
    def _build_audit_rows(
        image_path: str,
        answers: Dict[str, str],
        debug_cells: Sequence[DebugCell],
        decision_by_question: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, object]]:
        by_question: Dict[int, Dict[str, float]] = {}
        for cell in debug_cells:
            by_question.setdefault(cell.question_num, {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0, "nc": 0.0})
            by_question[cell.question_num][cell.letter] = cell.score

        rows: List[Dict[str, object]] = []
        for question_num in sorted(by_question.keys()):
            key = f"Pregunta {question_num:02d}"
            scores = by_question[question_num]
            rows.append(
                {
                    "Imagen": image_path,
                    "Pregunta": key,
                    "Score_a": scores.get("a", 0.0),
                    "Score_b": scores.get("b", 0.0),
                    "Score_c": scores.get("c", 0.0),
                    "Score_d": scores.get("d", 0.0),
                    "Score_nc": scores.get("nc", 0.0),
                    "Seleccionada": answers.get(key, "-"),
                    "Decision": (decision_by_question or {}).get(key, ""),
                    "AutoRecovered": "si" if (decision_by_question or {}).get(key, "") == "aggressive" else "no",
                }
            )

        return rows

    @staticmethod
    def _load_grayscale_image(image_path: str) -> Optional[np.ndarray]:
        """Read grayscale image with a Unicode-path fallback for Windows/OpenCV."""
        image_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image_gray is not None:
            return image_gray

        try:
            raw = np.fromfile(image_path, dtype=np.uint8)
        except OSError:
            return None

        if raw.size == 0:
            return None
        return cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)

    @staticmethod
    def _default_temp_image_dir() -> str:
        # System temp folder: the Desktop is often synced to the cloud (e.g. OneDrive), and these
        # are scans of students' answer sheets.
        return str(Path(tempfile.gettempdir()) / "pyexamgenerator_temp")

    @classmethod
    def _resolve_temp_image_dir(cls, temp_image_dir: Optional[str]) -> str:
        candidate = str(temp_image_dir).strip() if temp_image_dir else ""
        base = candidate or cls._default_temp_image_dir()
        return str(Path(base).expanduser())

    @staticmethod
    def _safe_temp_copy_name(image_path: str) -> str:
        src = Path(image_path)
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", src.stem).strip("._") or "image"
        suffix = src.suffix or ".img"
        return f"{stem}{suffix}"

    def _load_grayscale_image_from_temp_copy(self, image_path: str) -> Optional[np.ndarray]:
        source = Path(image_path)
        if not source.exists():
            return None

        temp_root = Path(getattr(self, "temp_image_dir", self._default_temp_image_dir())).expanduser()
        try:
            temp_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

        temp_name = self._safe_temp_copy_name(image_path)
        try:
            # Ultimo recurso: copiar a una ruta temporal "limpia" y reintentar la lectura.
            with tempfile.TemporaryDirectory(prefix="sheet_", dir=str(temp_root)) as tmp_dir:
                temp_path = Path(tmp_dir) / temp_name
                shutil.copy2(str(source), str(temp_path))
                return self._load_grayscale_image(str(temp_path))
        except Exception:
            return None

    def _load_grayscale_image_with_fallback(self, image_path: str) -> Optional[np.ndarray]:
        image_gray = self._load_grayscale_image(image_path)
        if image_gray is not None:
            return image_gray
        return self._load_grayscale_image_from_temp_copy(image_path)

    def process_image(self, image_path: str) -> SheetResult:
        image_gray = self._load_grayscale_image_with_fallback(image_path)
        if image_gray is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        image_oriented, tokens, rotation_degrees = self._extract_tokens_with_auto_rotation(image_gray)
        if not tokens:
            return SheetResult(
                image=image_path,
                exam_type=None,
                first_name_raw=None,
                last_name_raw=None,
                student_name_ocr=None,
                student_name_official=None,
                student_id_official=None,
                answers={},
                audit_rows=[],
                rotation_degrees=0,
            )
        exam_type = self._extract_exam_type(tokens)

        first_name_raw = self._extract_label_value(tokens, "first_name")
        last_name_raw = self._extract_label_value(tokens, "last_name")

        student_name_ocr = None
        if first_name_raw and last_name_raw:
            student_name_ocr = f"{first_name_raw} {last_name_raw}".strip()
        elif first_name_raw:
            student_name_ocr = first_name_raw

        student_name_official, student_id_official = self._match_official_student(
            student_name_ocr, first_name_raw, last_name_raw
        )

        # Identificación manual del alumno: prevalece sobre el resultado del OCR.
        forced_key = Path(image_path).name
        if forced_key in self.forced_student_by_image:
            student_name_official, student_id_official = self._resolve_forced_student(
                self.forced_student_by_image[forced_key]
            )

        answers, debug_cells, decision_by_question = self._extract_answers(tokens, image_oriented)
        self._save_debug_image(image_path, image_oriented, debug_cells)
        audit_rows = self._build_audit_rows(image_path, answers, debug_cells, decision_by_question)

        return SheetResult(
            image=image_path,
            exam_type=exam_type,
            first_name_raw=first_name_raw,
            last_name_raw=last_name_raw,
            student_name_ocr=student_name_ocr,
            student_name_official=student_name_official,
            student_id_official=student_id_official,
            answers=answers,
            audit_rows=audit_rows,
            rotation_degrees=rotation_degrees,
        )

    def process_batch(self, image_paths: Sequence[str], skip_errors: bool = False) -> List[SheetResult]:
        """Processes every image. With ``skip_errors`` an image that cannot be processed is
        recorded in ``self.failed_images`` as ``(path, error)`` instead of aborting the batch."""
        self.failed_images: List[Tuple[str, str]] = []
        results: List[SheetResult] = []
        for path in image_paths:
            try:
                results.append(self.process_image(path))
            except Exception as exc:  # noqa: BLE001 - reported per image when skip_errors
                if not skip_errors:
                    raise
                self.failed_images.append((str(path), f"{type(exc).__name__}: {exc}"))
        return results


def results_to_dataframe(results: Sequence[SheetResult]) -> pd.DataFrame:
    all_questions = sorted({k for r in results for k in r.answers.keys()})
    rows = []
    for r in results:
        row = {
            "Imagen": r.image,
            "Tipo_Examen": r.exam_type or "",
            "Rotacion_Grados": r.rotation_degrees,
            "Nombre_Raw": r.first_name_raw or "",
            "Apellidos_Raw": r.last_name_raw or "",
            "Nombre_OCR": r.student_name_ocr or "",
            "Nombre_Oficial": r.student_name_official or "",
            "ID_Oficial": r.student_id_official or "",
        }
        for q in all_questions:
            row[q] = r.answers.get(q, "")
        rows.append(row)
    return pd.DataFrame(rows)


def audit_to_dataframe(results: Sequence[SheetResult]) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for r in results:
        rows.extend(r.audit_rows)
    if not rows:
        return pd.DataFrame(
            columns=[
                "Imagen",
                "Pregunta",
                "Score_a",
                "Score_b",
                "Score_c",
                "Score_d",
                "Score_nc",
                "Seleccionada",
                "Decision",
                "AutoRecovered",
            ]
        )
    return pd.DataFrame(rows)


# Backward-compatible aliases
HojaResultado = SheetResult
DebugCelda = DebugCell
ExtractorHojaRespuestas = AnswerSheetExtractor
resultados_a_dataframe = results_to_dataframe
auditoria_a_dataframe = audit_to_dataframe
procesar_imagen = AnswerSheetExtractor.process_image
procesar_lote = AnswerSheetExtractor.process_batch


# ImageExamGrader moved to image_grading.py (ARC-5). Imported lazily: image_grading imports this module.
_MOVED_TO_IMAGE_GRADING = {
    "ImageExamGrader",
    "QuestionInfo",
    "CorrectorExamenesDesdeImagenes",
    "PreguntaInfo",
}


def __getattr__(name: str):
    """Names moved to :mod:`pyexamgenerator.grading.image_grading`, still importable from here."""
    if name in _MOVED_TO_IMAGE_GRADING:
        from pyexamgenerator.grading import image_grading

        return getattr(image_grading, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    # Same command as before: python -m pyexamgenerator.grading.extraction
    from pyexamgenerator.grading.image_grading import main

    main()
