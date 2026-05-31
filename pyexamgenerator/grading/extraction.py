import argparse
import difflib
import os
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

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
    ) -> None:
        self.ocr = RapidOCR()
        self._ocr_backend = _RAPIDOCR_BACKEND
        self.enrollment_df = None
        self.lookup_names: List[str] = []
        self.debug_dir = debug_dir
        self.min_mark_ratio = float(min_mark_ratio)
        self.min_gap = float(min_gap)
        self.aggressive_recovery = bool(aggressive_recovery)
        self.aggressive_min_ratio = float(aggressive_min_ratio)
        self.aggressive_min_gap_ratio = float(aggressive_min_gap_ratio)
        self.aggressive_min_top_vs_second = float(aggressive_min_top_vs_second)
        self.id_col = id_col
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
        self.enrollment_df = enrollment_df.copy()
        self.enrollment_df["Lookup_Name"] = (
            self.enrollment_df["Nombre"].astype(str).str.strip()
            + " "
            + self.enrollment_df["Apellido(s)"].astype(str).str.strip()
        ).str.lower()
        self.lookup_names = self.enrollment_df["Lookup_Name"].tolist()

    def _load_enrollment(self, enrollment_xlsx_path: str) -> None:
        self._set_enrollment_df(pd.read_excel(enrollment_xlsx_path))

    @staticmethod
    def _strip_accents(text: str) -> str:
        normalized = unicodedata.normalize("NFD", text)
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

    @classmethod
    def _normalize(cls, text: str) -> str:
        clean = cls._strip_accents(text).lower()
        return re.sub(r"[^a-z0-9]", "", clean)

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
            image_bgr = image_gray if getattr(image_gray, "ndim", 2) == 3 else cv2.cvtColor(image_gray, cv2.COLOR_GRAY2BGR)
            out = self.ocr(image_bgr)
            if out is None or out.boxes is None:
                return []
            return [[box, txt, score] for box, txt, score in zip(out.boxes, out.txts, out.scores)]

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
            and self._normalize(t.text)
            not in {"apellidos", "apellido", "nombre", "dninie", "firma", "datosdelalumno"}
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
            best_idx = None
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
                row = self.enrollment_df.iloc[best_idx]
                official_name = f"{row['Nombre']} {row['Apellido(s)']}".strip()
                official_id = str(row.get("Número de ID", "")).strip() or None
                return official_name, official_id

        if not student_name_ocr:
            return None, None

        cleaned_name = student_name_ocr.strip().lower()
        matches = difflib.get_close_matches(cleaned_name, self.lookup_names, n=1, cutoff=0.6)
        if not matches:
            return None, None

        row = self.enrollment_df[self.enrollment_df["Lookup_Name"] == matches[0]].iloc[0]
        official_name = f"{row['Nombre']} {row['Apellido(s)']}".strip()
        official_id = str(row.get("Número de ID", "")).strip() or None
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
            official_id = str(row.get(self.id_col, "")).strip() or None
            return official_name or None, official_id

        # 1) Coincidencia exacta por "Número de ID" (lo más inequívoco).
        if self.id_col in self.enrollment_df.columns:
            id_series = self.enrollment_df[self.id_col].astype(str).str.strip()
            matches = self.enrollment_df[id_series == ident]
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
            key = int(t.cx // x_bin_size)
            bins.setdefault(key, []).append(t)

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

        def score_letters_for_y(y_center: int, letters: Sequence[str]) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
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
            scores = [(letter, ratio) for letter, ratio, _rect in scored_sorted]

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
            cv2.putText(image_color, label, (x0, max(12, y0 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

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

    def process_image(self, image_path: str) -> SheetResult:
        image_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
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

    def process_batch(self, image_paths: Sequence[str]) -> List[SheetResult]:
        return [self.process_image(path) for path in image_paths]


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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract data from JPG/PNG answer sheets")
    parser.add_argument("images", nargs="+", help="Image paths to process")
    parser.add_argument("--enrollment", default=None, help="Official enrollment Excel (optional)")
    parser.add_argument("--output", default="respuestas_alumnos_paso1_desde_imagenes.xlsx", help="Output Excel")
    parser.add_argument("--audit-output", default=None, help="Optional audit Excel with per-question scores")
    parser.add_argument("--debug-dir", default=None, help="Directory to save debug images")
    parser.add_argument("--min-mark-ratio", type=float, default=0.17, help="Minimum ink ratio to accept a mark")
    parser.add_argument("--min-gap", type=float, default=0.05, help="Minimum difference between top and second option")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    extractor = AnswerSheetExtractor(
        enrollment_xlsx_path=args.enrollment,
        debug_dir=args.debug_dir,
        min_mark_ratio=args.min_mark_ratio,
        min_gap=args.min_gap,
    )
    results = extractor.process_batch(args.images)
    df = results_to_dataframe(results)
    df.to_excel(args.output, index=False)
    print(f"OK: file generated at {args.output}")

    if args.audit_output:
        df_audit = audit_to_dataframe(results)
        df_audit.to_excel(args.audit_output, index=False)
        print(f"OK: audit generated at {args.audit_output}")

    for r in results:
        print(
            f"- {Path(r.image).name}: type={r.exam_type or '?'} | "
            f"name={r.student_name_ocr or '?'} | official={r.student_name_official or '?'}"
        )


if __name__ == "__main__":
    main()


# Backward-compatible aliases
HojaResultado = SheetResult
DebugCelda = DebugCell
ExtractorHojaRespuestas = AnswerSheetExtractor
resultados_a_dataframe = results_to_dataframe
auditoria_a_dataframe = audit_to_dataframe
procesar_imagen = AnswerSheetExtractor.process_image
procesar_lote = AnswerSheetExtractor.process_batch




# Image-based grading

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from pyexamgenerator.grading.data import build_merged_enrollment_from_sources
from pyexamgenerator.grading.data import SharedExamDataStore


@dataclass
class QuestionInfo:
    name: str
    answers: Dict[str, float]


class ImageExamGrader:
    """Integrated flow: OCR answer sheets -> resolve exam type -> grade over 10."""

    def __init__(
        self,
        xml_paths: Sequence[str],
        enrollment_path: Optional[str] = None,
        enrollment_paths: Optional[Sequence[str]] = None,
        min_mark_ratio: float = 0.17,
        min_gap: float = 0.05,
        debug_dir: Optional[str] = None,
        aggressive_recovery: bool = False,
        aggressive_min_ratio: float = 0.11,
        aggressive_min_gap_ratio: float = 0.25,
        aggressive_min_top_vs_second: float = 1.10,
        enrollment_sheet: int = 0,
        last_name_col: str = "Apellido(s)",
        first_name_col: str = "Nombre",
        id_col: str = "Número de ID",
        email_col: str = "Dirección de correo",
        forced_student_by_image: Optional[Dict[str, str]] = None,
        shared_store: Optional[SharedExamDataStore] = None,
        **legacy_kwargs,
    ) -> None:
        enrollment_path = enrollment_path or legacy_kwargs.pop("matriculados_path", None)
        enrollment_paths = enrollment_paths or legacy_kwargs.pop("matriculados_paths", None)
        last_name_col = legacy_kwargs.pop("col_apellidos", last_name_col)
        first_name_col = legacy_kwargs.pop("col_nombre", first_name_col)
        id_col = legacy_kwargs.pop("col_id", id_col)
        email_col = legacy_kwargs.pop("col_email", email_col)
        if legacy_kwargs:
            raise TypeError(f"Unexpected arguments: {sorted(legacy_kwargs.keys())}")

        if not xml_paths:
            raise ValueError("At least one exam XML file is required.")

        self.xml_paths = [str(p) for p in xml_paths]
        self.enrollment_path = enrollment_path
        self.enrollment_paths = [str(p) for p in (enrollment_paths or []) if str(p).strip()]
        self.enrollment_sheet = enrollment_sheet
        self.last_name_col = last_name_col
        self.first_name_col = first_name_col
        self.id_col = id_col
        self.email_col = email_col
        self.shared_store = shared_store or SharedExamDataStore()

        self.enrollment_df = self._load_enrollment(enrollment_path)

        self.extractor = AnswerSheetExtractor(
            enrollment_df=self.enrollment_df,
            debug_dir=debug_dir,
            min_mark_ratio=min_mark_ratio,
            min_gap=min_gap,
            aggressive_recovery=aggressive_recovery,
            aggressive_min_ratio=aggressive_min_ratio,
            aggressive_min_gap_ratio=aggressive_min_gap_ratio,
            aggressive_min_top_vs_second=aggressive_min_top_vs_second,
            id_col=id_col,
            forced_student_by_image=forced_student_by_image,
        )

        self.questions_by_exam_type = self._load_xmls_by_exam_type(self.xml_paths)
        self.available_exam_types = sorted(self.questions_by_exam_type.keys())

    def _load_enrollment(self, enrollment_path: Optional[str]) -> Optional[pd.DataFrame]:
        if self.enrollment_paths:
            return build_merged_enrollment_from_sources(self.enrollment_paths, sheet_name=self.enrollment_sheet)

        if not enrollment_path:
            return None
        return self.shared_store.load_enrollment(
            xlsx_path=enrollment_path,
            sheet_name=self.enrollment_sheet,
            first_name_col=self.first_name_col,
            last_name_col=self.last_name_col,
            with_lookup_name=True,
        )

    @staticmethod
    def _infer_exam_type_from_xml_filename(xml_path: str) -> str:
        name = Path(xml_path).name.upper()
        match = re.search(r"_([0-9]+[A-Z])\.XML$", name)
        if match:
            return match.group(1)

        match = re.search(r"\b([0-9]+[A-Z])\b", name)
        if match:
            return match.group(1)

        raise ValueError(f"Could not infer exam type from XML filename: {xml_path}")

    def _load_xmls_by_exam_type(self, xml_paths: Sequence[str]) -> Dict[str, Dict[str, QuestionInfo]]:
        raw = self.shared_store.load_questions_by_exam_type(
            xml_paths=xml_paths,
            infer_exam_type=self._infer_exam_type_from_xml_filename,
        )
        out: Dict[str, Dict[str, QuestionInfo]] = {}
        for exam_type, questions in raw.items():
            out[exam_type] = {
                q_name: QuestionInfo(name=q_name, answers=answer_map)
                for q_name, answer_map in questions.items()
            }
        return out

    def _resolve_exam_type(
        self,
        sheet: SheetResult,
        forced_type_by_image: Dict[str, str],
        prompt_if_missing: bool,
    ) -> str:
        image_name = Path(sheet.image).name
        if image_name in forced_type_by_image:
            exam_type = forced_type_by_image[image_name].upper()
            if exam_type not in self.questions_by_exam_type:
                raise ValueError(f"Forced exam type unavailable for {image_name}: {exam_type}")
            return exam_type

        if sheet.exam_type:
            exam_type = str(sheet.exam_type).strip().upper()
            if exam_type in self.questions_by_exam_type:
                return exam_type

        if not prompt_if_missing:
            raise ValueError(
                f"Could not determine exam type for {image_name}. "
                f"Available types: {', '.join(self.available_exam_types)}"
            )

        suggestion = self._suggest_exam_type_from_answers(sheet.answers)
        options = ", ".join(self.available_exam_types)
        prompt = (
            f"Exam type not detected for '{image_name}'. "
            f"Options [{options}]"
            + (f" (suggested: {suggestion})" if suggestion else "")
            + ": "
        )

        while True:
            selected = input(prompt).strip().upper()
            if not selected and suggestion:
                return suggestion
            if selected in self.questions_by_exam_type:
                return selected
            print(f"Invalid value. Must be one of: {options}")

    def _suggest_exam_type_from_answers(self, answers: Dict[str, str]) -> Optional[str]:
        if not answers:
            return None

        best_exam_type = None
        best_score = float("-inf")
        for exam_type in self.available_exam_types:
            score, _ = self._calculate_score_for_type(answers, exam_type)
            if score > best_score:
                best_score = score
                best_exam_type = exam_type
        return best_exam_type

    def _calculate_score_for_type(self, answers: Dict[str, str], exam_type: str) -> Tuple[float, Dict[str, str]]:
        questions = self.questions_by_exam_type[exam_type]
        question_count = len(questions)
        points_per_question = 10.0 / float(question_count)
        points_per_question_output: Dict[str, str] = {}

        for question_name in sorted(questions.keys()):
            answer = str(answers.get(question_name, "")).strip().lower()
            if not answer or answer in {"-", "nc"}:
                points_per_question_output[question_name] = "-"
                continue

            fraction = questions[question_name].answers.get(answer, 0.0)
            points = points_per_question * fraction
            points_per_question_output[question_name] = f"{points:.2f}".replace(".", ",")

        total = 0.0
        for question_name in sorted(questions.keys()):
            answer = str(answers.get(question_name, "")).strip().lower()
            if not answer or answer in {"-", "nc"}:
                continue
            fraction = questions[question_name].answers.get(answer, 0.0)
            total += points_per_question * fraction

        return max(0.0, total), points_per_question_output

    def _enrollment_row_from_id(self, official_id: Optional[str]) -> Optional[pd.Series]:
        if self.enrollment_df is None or not official_id:
            return None

        normalized_id = str(official_id).strip()
        if normalized_id == "":
            return None

        series = self.enrollment_df[self.id_col].astype(str).str.strip()
        matches = self.enrollment_df[series == normalized_id]
        if matches.empty:
            return None
        return matches.iloc[0]

    @staticmethod
    def _parse_decimal_grade(value: object) -> Optional[float]:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        if text in {"", "-"}:
            return None
        text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    def _build_ocr_incidents(
        self,
        sheet_results: Sequence[SheetResult],
        grades_df: pd.DataFrame,
        audit_df: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        incidents: List[Dict[str, object]] = []
        grade_by_image: Dict[str, float] = {}
        for _, row in grades_df.iterrows():
            image = str(row.get("Imagen", "")).strip()
            grade = self._parse_decimal_grade(row.get("Calificacion/10,00", ""))
            if image and grade is not None:
                grade_by_image[image] = grade

        low_margin_by_image: Dict[str, int] = {}
        if audit_df is not None and not audit_df.empty:
            for _, row in audit_df.iterrows():
                image = str(row.get("Imagen", "")).strip()
                selected = str(row.get("Seleccionada", "")).strip().lower()
                scores = [
                    float(row.get("Score_a", 0.0) or 0.0),
                    float(row.get("Score_b", 0.0) or 0.0),
                    float(row.get("Score_c", 0.0) or 0.0),
                    float(row.get("Score_d", 0.0) or 0.0),
                    float(row.get("Score_nc", 0.0) or 0.0),
                ]
                scores = sorted(scores, reverse=True)
                margin = scores[0] - scores[1] if len(scores) > 1 else 0.0
                if selected not in {"", "-"} and margin < (self.extractor.min_gap * 1.2):
                    low_margin_by_image[image] = low_margin_by_image.get(image, 0) + 1

        unresolved_by_image: Dict[str, int] = {}
        if audit_df is not None and not audit_df.empty:
            unresolved_mask = audit_df["Seleccionada"].astype(str).str.strip().eq("-")
            unresolved = audit_df.loc[unresolved_mask]
            for image, group in unresolved.groupby("Imagen"):
                unresolved_by_image[str(image)] = int(len(group))

        for sheet in sheet_results:
            image = sheet.image
            if not str(sheet.student_id_official or "").strip():
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "MISSING_ID",
                        "Severidad": "alta",
                        "Detalle": "No se pudo asociar ID oficial al OCR del alumno.",
                    }
                )

            if not str(sheet.exam_type or "").strip():
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "MISSING_EXAM_TYPE",
                        "Severidad": "alta",
                        "Detalle": "No se pudo detectar el tipo de examen en la hoja.",
                    }
                )

            grade = grade_by_image.get(image)
            if grade is not None and grade <= 0.0:
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "ZERO_SCORE",
                        "Severidad": "media",
                        "Detalle": "La nota total OCR es 0,00. Revisión manual recomendada.",
                    }
                )

            low_count = low_margin_by_image.get(image, 0)
            if low_count > 0:
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "LOW_CONFIDENCE_MARKS",
                        "Severidad": "media",
                        "Detalle": f"Se detectaron {low_count} pregunta(s) con margen de marcado bajo.",
                    }
                )

            unresolved_count = unresolved_by_image.get(image, 0)
            if unresolved_count > 0:
                incidents.append(
                    {
                        "Imagen": image,
                        "Tipo": "UNRESOLVED_ANSWERS",
                        "Severidad": "media",
                        "Detalle": f"Quedan {unresolved_count} respuesta(s) sin identificar ('-').",
                    }
                )

        if not incidents:
            return pd.DataFrame(columns=["Imagen", "Tipo", "Severidad", "Detalle"])
        return pd.DataFrame(incidents)

    @staticmethod
    def _best_option_from_audit_row(row: Dict[str, object]) -> Tuple[str, float, float]:
        score_map = {
            "a": float(row.get("Score_a", 0.0) or 0.0),
            "b": float(row.get("Score_b", 0.0) or 0.0),
            "c": float(row.get("Score_c", 0.0) or 0.0),
            "d": float(row.get("Score_d", 0.0) or 0.0),
            "nc": float(row.get("Score_nc", 0.0) or 0.0),
        }
        ordered = sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)
        best_label, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        return best_label, best_score, second_score

    def _is_doubtful_audit_row(self, row: Dict[str, object]) -> bool:
        selected = str(row.get("Seleccionada", "")).strip().lower()
        decision = str(row.get("Decision", "")).strip().lower()
        _, best_score, second_score = self._best_option_from_audit_row(row)
        margin = best_score - second_score
        if selected == "-":
            return True
        if decision in {"adaptive", "aggressive"}:
            return True
        return margin < (self.extractor.min_gap * 1.2)

    @staticmethod
    def _question_sort_key(question_label: str) -> int:
        match = re.search(r"(\d+)", str(question_label))
        return int(match.group(1)) if match else 9999

    def _run_interactive_review(
        self,
        sheet_results: Sequence[SheetResult],
        open_image_on_review: bool = True,
    ) -> Tuple[int, List[Dict[str, object]]]:
        print("Interactive OCR review enabled. Confirming doubtful answers...")
        updated = 0
        changes: List[Dict[str, object]] = []

        for sheet in sheet_results:
            candidates = [row for row in sheet.audit_rows if self._is_doubtful_audit_row(row)]
            if not candidates:
                continue

            candidates = sorted(candidates, key=lambda row: self._question_sort_key(str(row.get("Pregunta", ""))))

            image_path = str(sheet.image)
            if open_image_on_review:
                try:
                    os.startfile(image_path)  # type: ignore[attr-defined]
                except Exception:
                    print(f"Could not open image automatically: {image_path}")

            print("\n---")
            print(f"Image: {image_path}")
            print(f"Detected exam type: {sheet.exam_type or '?'}")
            print("Options: a/b/c/d/nc/- ; Enter keeps current value.")

            for row in candidates:
                question = str(row.get("Pregunta", "")).strip()
                current = str(sheet.answers.get(question, "-")).strip().lower() or "-"
                suggested, top_score, second_score = self._best_option_from_audit_row(row)
                margin = top_score - second_score

                while True:
                    answer = input(
                        f"{question} | current={current} | suggested={suggested} "
                        f"(margin={margin:.3f}) -> "
                    ).strip().lower()
                    if answer == "":
                        answer = current
                    if answer in {"a", "b", "c", "d", "nc", "-"}:
                        break
                    print("Invalid value. Use: a/b/c/d/nc/- or Enter.")

                if answer != current:
                    sheet.answers[question] = answer
                    row["Seleccionada"] = answer
                    row["Decision"] = "manual"
                    row["AutoRecovered"] = "no"
                    updated += 1
                    changes.append(
                        {
                            "Imagen": image_path,
                            "Pregunta": question,
                            "Valor_Anterior": current,
                            "Valor_Final": answer,
                            "Sugerida_OCR": suggested,
                            "Margen_OCR": round(float(margin), 4),
                        }
                    )

        print(f"Interactive review completed. Updated answers: {updated}")
        return updated, changes

    @staticmethod
    def _manual_changes_to_dataframe(changes: Sequence[Dict[str, object]]) -> pd.DataFrame:
        cols = ["Imagen", "Pregunta", "Valor_Anterior", "Valor_Final", "Sugerida_OCR", "Margen_OCR"]
        if not changes:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame(changes, columns=cols)

    @staticmethod
    def _build_manual_review_dataframe(audit_df: Optional[pd.DataFrame]) -> pd.DataFrame:
        columns = [
            "Imagen",
            "Pregunta",
            "Seleccionada",
            "Decision",
            "Sugerida",
            "Score_top",
            "Score_segunda",
            "Margen",
            "Accion_Manual",
            "Observaciones",
        ]
        if audit_df is None or audit_df.empty:
            return pd.DataFrame(columns=columns)

        work = audit_df.copy()
        work["Seleccionada"] = work["Seleccionada"].astype(str).str.strip().str.lower()
        unresolved = work[work["Seleccionada"] == "-"]
        if unresolved.empty:
            return pd.DataFrame(columns=columns)

        rows: List[Dict[str, object]] = []
        for _, row in unresolved.iterrows():
            scores = {
                "a": float(row.get("Score_a", 0.0) or 0.0),
                "b": float(row.get("Score_b", 0.0) or 0.0),
                "c": float(row.get("Score_c", 0.0) or 0.0),
                "d": float(row.get("Score_d", 0.0) or 0.0),
                "nc": float(row.get("Score_nc", 0.0) or 0.0),
            }
            sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            top_label, top_score = sorted_scores[0]
            second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
            rows.append(
                {
                    "Imagen": row.get("Imagen", ""),
                    "Pregunta": row.get("Pregunta", ""),
                    "Seleccionada": "-",
                    "Decision": row.get("Decision", ""),
                    "Sugerida": top_label,
                    "Score_top": round(top_score, 4),
                    "Score_segunda": round(second_score, 4),
                    "Margen": round(top_score - second_score, 4),
                    "Accion_Manual": "",
                    "Observaciones": "",
                }
            )
        return pd.DataFrame(rows, columns=columns)

    def grade_from_images(
        self,
        image_paths: Sequence[str],
        output_answers: str,
        output_grades: str,
        output_dir: Optional[str] = None,
        output_audit: Optional[str] = None,
        output_incidents: Optional[str] = None,
        output_review: Optional[str] = None,
        output_manual_changes: Optional[str] = None,
        interactive_review: bool = False,
        open_image_on_review: bool = True,
        forced_type_by_image: Optional[Dict[str, str]] = None,
        prompt_missing_type: bool = True,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        forced = {k: v for k, v in (forced_type_by_image or {}).items()}

        output_base = Path(output_dir) if output_dir else None
        if output_base is not None:
            output_base.mkdir(parents=True, exist_ok=True)
            output_answers = str(output_base / Path(output_answers).name)
            output_grades = str(output_base / Path(output_grades).name)
            if output_audit:
                output_audit = str(output_base / Path(output_audit).name)
            if output_incidents:
                output_incidents = str(output_base / Path(output_incidents).name)
            if output_review:
                output_review = str(output_base / Path(output_review).name)
            if output_manual_changes:
                output_manual_changes = str(output_base / Path(output_manual_changes).name)

        sheet_results = self.extractor.process_batch(image_paths)
        manual_changes: List[Dict[str, object]] = []
        if interactive_review:
            _updated, manual_changes = self._run_interactive_review(sheet_results, open_image_on_review=open_image_on_review)

        answers_df = results_to_dataframe(sheet_results)

        resolved_types: List[str] = []
        moodle_rows: List[Dict[str, str]] = []

        all_questions = sorted({q for exam in self.questions_by_exam_type.values() for q in exam.keys()})
        max_question_num = max(int(re.search(r"\d+", q).group()) for q in all_questions)
        reference_weight = 10.0 / max_question_num
        reference_weight_str = f"{reference_weight:.2f}".replace(".", ",")

        for sheet in sheet_results:
            exam_type = self._resolve_exam_type(sheet, forced, prompt_missing_type)
            resolved_types.append(exam_type)
            total_score, points_by_question = self._calculate_score_for_type(sheet.answers, exam_type)

            row: Dict[str, str] = {
                "Imagen": sheet.image,
                "Tipo_Examen": exam_type,
                "Nombre_OCR": sheet.student_name_ocr or "",
                "Nombre_Oficial": sheet.student_name_official or "",
                "ID_Oficial": sheet.student_id_official or "",
                "Calificacion/10,00": f"{total_score:.2f}".replace(".", ","),
            }

            enrollment_row = self._enrollment_row_from_id(sheet.student_id_official)
            if enrollment_row is not None:
                row[self.last_name_col] = str(enrollment_row.get(self.last_name_col, ""))
                row[self.first_name_col] = str(enrollment_row.get(self.first_name_col, ""))
                row[self.id_col] = str(enrollment_row.get(self.id_col, ""))
                row[self.email_col] = str(enrollment_row.get(self.email_col, ""))
                if "Grupo_Principal" in enrollment_row.index:
                    row["Grupo_Principal"] = str(enrollment_row.get("Grupo_Principal", ""))
                if "Subgrupo_Practicas" in enrollment_row.index:
                    row["Subgrupo_Practicas"] = str(enrollment_row.get("Subgrupo_Practicas", ""))

            for question in all_questions:
                question_num = int(re.search(r"\d+", question).group())
                col_name = f"P. {question_num} /{reference_weight_str}"
                row[col_name] = points_by_question.get(question, "-")

            moodle_rows.append(row)

        answers_df["Tipo_Examen_Usado"] = resolved_types
        answers_df.to_excel(output_answers, index=False)

        grades_df = pd.DataFrame(moodle_rows)
        grades_df.to_excel(output_grades, index=False)

        audit_df = None
        if output_audit:
            audit_df = audit_to_dataframe(sheet_results)
            audit_df.to_excel(output_audit, index=False)

        incidents_df = self._build_ocr_incidents(sheet_results, grades_df, audit_df)
        if output_incidents:
            incidents_df.to_excel(output_incidents, index=False)

        review_df = self._build_manual_review_dataframe(audit_df)
        if output_review:
            review_df.to_excel(output_review, index=False)

        if output_manual_changes:
            manual_df = self._manual_changes_to_dataframe(manual_changes)
            manual_df.to_excel(output_manual_changes, index=False)

        return answers_df, grades_df, audit_df

    def corregir_desde_imagenes(
        self,
        image_paths: Sequence[str],
        salida_respuestas: str,
        salida_calificaciones: str,
        salida_auditoria: Optional[str] = None,
        salida_incidencias: Optional[str] = None,
        salida_revision: Optional[str] = None,
        salida_cambios_manuales: Optional[str] = None,
        tipo_forzado_por_imagen: Optional[Dict[str, str]] = None,
        preguntar_tipo_faltante: bool = True,
        output_dir: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        return self.grade_from_images(
            image_paths=image_paths,
            output_answers=salida_respuestas,
            output_grades=salida_calificaciones,
            output_dir=output_dir,
            output_audit=salida_auditoria,
            output_incidents=salida_incidencias,
            output_review=salida_revision,
            output_manual_changes=salida_cambios_manuales,
            forced_type_by_image=tipo_forzado_por_imagen,
            prompt_missing_type=preguntar_tipo_faltante,
        )


def _parse_forced_type(items: Sequence[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --force-type item: {item}. Use IMAGE=TYPE")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip().upper()
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrated grading from scanned answer sheet images")
    parser.add_argument("images", nargs="+", help="JPG/PNG answer sheet images")
    parser.add_argument("--xmls", nargs="+", required=True, help="Available XML templates (e.g. 2A, 2B)")
    parser.add_argument("--enrollment", default=None, help="Enrollment Excel")
    parser.add_argument("--enrollment-list", nargs="+", default=None, help="Optional list of enrollment Excels to merge")
    parser.add_argument("--output-answers", default="respuestas_alumnos_paso1_desde_imagenes.xlsx")
    parser.add_argument("--output-grades", default="calificaciones_desde_imagenes.xlsx")
    parser.add_argument("--output-audit", default=None)
    parser.add_argument("--output-incidents", default=None)
    parser.add_argument("--output-review", default=None)
    parser.add_argument("--output-manual-changes", default=None)
    parser.add_argument("--interactive-review", action="store_true", help="Ask the user to confirm doubtful answers")
    parser.add_argument("--no-open-image", action="store_true", help="Do not auto-open the image during interactive review")
    parser.add_argument("--output-dir", default=None, help="Directory where all outputs are generated")
    parser.add_argument("--debug-dir", default=None)
    parser.add_argument("--min-mark-ratio", type=float, default=0.17)
    parser.add_argument("--min-gap", type=float, default=0.05)
    parser.add_argument(
        "--force-type",
        action="append",
        default=[],
        help="Assign exam type by image: 'ImageName.jpg=2B'. Repeatable.",
    )
    parser.add_argument(
        "--no-prompt-type",
        action="store_true",
        help="Fail instead of prompting when exam type is missing and not forced.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    forced = _parse_forced_type(args.force_type)

    grader = ImageExamGrader(
        xml_paths=args.xmls,
        enrollment_path=args.enrollment,
        enrollment_paths=args.enrollment_list,
        min_mark_ratio=args.min_mark_ratio,
        min_gap=args.min_gap,
        debug_dir=args.debug_dir,
    )

    answers_df, grades_df, audit_df = grader.grade_from_images(
        image_paths=args.images,
        output_answers=args.output_answers,
        output_grades=args.output_grades,
        output_dir=args.output_dir,
        output_audit=args.output_audit,
        output_incidents=args.output_incidents,
        output_review=args.output_review,
        output_manual_changes=args.output_manual_changes,
        interactive_review=args.interactive_review,
        open_image_on_review=not args.no_open_image,
        forced_type_by_image=forced,
        prompt_missing_type=not args.no_prompt_type,
    )

    print(f"OK: answers -> {args.output_answers} ({len(answers_df)} rows)")
    print(f"OK: grades -> {args.output_grades} ({len(grades_df)} rows)")
    if audit_df is not None:
        print(f"OK: audit -> {args.output_audit} ({len(audit_df)} rows)")
    if args.output_incidents:
        try:
            incidents_count = len(pd.read_excel(args.output_incidents))
            print(f"OK: incidents -> {args.output_incidents} ({incidents_count} rows)")
        except Exception:
            print(f"OK: incidents -> {args.output_incidents}")
    if args.output_review:
        try:
            review_count = len(pd.read_excel(args.output_review))
            print(f"OK: review -> {args.output_review} ({review_count} rows)")
        except Exception:
            print(f"OK: review -> {args.output_review}")
    if args.output_manual_changes:
        try:
            manual_count = len(pd.read_excel(args.output_manual_changes))
            print(f"OK: manual changes -> {args.output_manual_changes} ({manual_count} rows)")
        except Exception:
            print(f"OK: manual changes -> {args.output_manual_changes}")


if __name__ == "__main__":
    main()


# Backward-compatible aliases
PreguntaInfo = QuestionInfo
CorrectorExamenesDesdeImagenes = ImageExamGrader

