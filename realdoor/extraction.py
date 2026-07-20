"""Local, synthetic-PDF evidence extraction for the RealDoor prototype.

The parser reads selectable text and word geometry directly from supplied
synthetic PDFs. When a PDF has no text layer, it can use a locally installed
Tesseract binary to recover strict, review-required OCR candidates. It never
uses organizer gold values at runtime.
"""

from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import fitz


ALLOWLISTED_FIELDS = {
    "person_name",
    "household_size",
    "address",
    "application_date",
    "pay_date",
    "pay_period_start",
    "pay_period_end",
    "pay_frequency",
    "regular_hours",
    "hourly_rate",
    "gross_pay",
    "net_pay",
    "document_date",
    "weekly_hours",
    "monthly_benefit",
    "benefit_frequency",
    "statement_month",
    "gross_receipts",
    "platform_fees",
}

FIELD_LABELS = {
    "application_summary": (
        ("person_name", "APPLICANT", "string"),
        ("household_size", "HOUSEHOLD SIZE", "integer"),
        ("address", "MAILING ADDRESS", "string"),
        ("application_date", "APPLICATION DATE", "date"),
    ),
    "pay_stub": (
        ("person_name", "EMPLOYEE", "string"),
        ("pay_date", "PAY DATE", "date"),
        ("pay_period_start", "PAY PERIOD", "date"),
        ("pay_period_end", "THROUGH", "date"),
        ("pay_frequency", "PAY FREQUENCY", "frequency"),
        ("regular_hours", "REGULAR HOURS", "number"),
        ("hourly_rate", "HOURLY RATE", "currency"),
        ("gross_pay", "GROSS PAY", "currency"),
        ("net_pay", "NET PAY", "currency"),
    ),
    "employment_letter": (
        ("person_name", "EMPLOYEE", "string"),
        ("document_date", "LETTER DATE", "date"),
        ("weekly_hours", "HOURS PER WEEK", "number"),
        ("hourly_rate", "HOURLY RATE", "currency"),
    ),
    "benefit_letter": (
        ("person_name", "RECIPIENT", "string"),
        ("document_date", "LETTER DATE", "date"),
        ("monthly_benefit", "MONTHLY AMOUNT", "currency"),
        ("benefit_frequency", "FREQUENCY", "frequency"),
    ),
    "gig_statement": (
        ("person_name", "WORKER", "string"),
        ("statement_month", "STATEMENT MONTH", "month"),
        ("gross_receipts", "GROSS RECEIPTS", "currency"),
        ("platform_fees", "PLATFORM FEES", "currency"),
    ),
}

UNTRUSTED_MARKERS = (
    "ignore prior instructions",
    "ignore previous instructions",
    "disregard prior instructions",
    "disregard previous instructions",
    "system prompt",
    "developer message",
    "mark this applicant approved",
    "reveal the system",
)

OCR_DPI = 300
OCR_MIN_CONFIDENCE = 90.0
OCR_TIMEOUT_SECONDS = 15


class LocalPdfEvidenceExtractor:
    """Extract typed, allowlisted evidence from a supplied synthetic PDF."""

    def extract_path(self, path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
        return self.extract_bytes(path.read_bytes(), metadata)

    def extract_bytes(self, pdf_bytes: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            pages = list(document)
            page_text = [page.get_text("text") for page in pages]
            joined_text = "\n".join(page_text)
            untrusted = any(marker in joined_text.lower() for marker in UNTRUSTED_MARKERS)
            public = {
                "document_id": metadata["document_id"],
                "household_id": metadata["household_id"],
                "document_type": metadata["document_type"],
                "file_name": metadata["file_name"],
                "page_count": len(pages),
                "preview_url": f"/documents/{metadata['file_name']}",
                "contains_untrusted_content": untrusted,
                "untrusted_content_handling": (
                    "Detected untrusted instruction-like text. It is excluded from extraction and cannot alter rules, tools, or the packet."
                    if untrusted
                    else "Only allowlisted evidence is considered; document text cannot alter rules, tools, or the packet."
                ),
                "extraction_engine": "local_pdf_text_v1",
            }
            expected = FIELD_LABELS[metadata["document_type"]]
            if not any(text.strip() for text in page_text):
                ocr = self._extract_ocr_fields(pages, expected)
                ocr_text = ocr["text"]
                ocr_fields = ocr["fields"]
                ocr_untrusted = any(marker in ocr_text.lower() for marker in UNTRUSTED_MARKERS)
                status = self._status_for(ocr_fields, expected)
                reason = ocr["reason"] if status == "abstained" else None
                return {
                    **public,
                    "contains_untrusted_content": ocr_untrusted,
                    "untrusted_content_handling": (
                        "Detected untrusted instruction-like text. It is excluded from extraction and cannot alter rules, tools, or the packet."
                        if ocr_untrusted
                        else "Only allowlisted evidence is considered; document text cannot alter rules, tools, or the packet."
                    ),
                    "extraction_engine": "local_tesseract_ocr_v1",
                    "extraction_status": status,
                    "extraction_summary": self._summary(ocr_fields, expected, "OCR", ocr["reason"]),
                    "abstention_reason": reason,
                    "fields": ocr_fields,
                }
            fields = []
            for field, label, kind in expected:
                candidate = self._value_after_label(page_text, label)
                if candidate is None:
                    continue
                value = self._typed_value(candidate, kind)
                if value is None or field not in ALLOWLISTED_FIELDS:
                    continue
                source = self._source_box(pages, label, candidate)
                confidence = "high" if source else "medium"
                fields.append({
                    "field": field,
                    "value": value,
                    "raw_value": candidate,
                    "page": source["page"] if source else None,
                    "bbox": source["bbox"] if source else None,
                    "bbox_units": "pdf_points_bottom_left_origin" if source else None,
                    "confidence": confidence,
                    "confidence_reason": (
                        "Explicit label, typed value, and PDF source box detected. Confidence measures evidence extraction only; renter confirmation is still required."
                        if source
                        else "Explicit label and typed value detected, but no precise text box was recovered. Renter review is required."
                    ),
                    "extraction_method": "native_text",
                    "confirmation_state": "pending",
                })
            return {
                **public,
                "extraction_status": self._status_for(fields, expected),
                "extraction_summary": self._summary(fields, expected, "selectable PDF text"),
                "abstention_reason": None if fields else "No allowlisted label/value pairs were recovered. RealDoor will not infer missing evidence.",
                "fields": fields,
            }
        finally:
            document.close()

    @staticmethod
    def _status_for(fields: list[dict[str, Any]], expected: tuple[tuple[str, str, str], ...]) -> str:
        if not fields:
            return "abstained"
        return "extracted" if len(fields) == len(expected) else "partial"

    @staticmethod
    def _summary(
        fields: list[dict[str, Any]],
        expected: tuple[tuple[str, str, str], ...],
        method: str,
        failure: str | None = None,
    ) -> str:
        recovered = {field["field"] for field in fields}
        missing = [field.replace("_", " ") for field, _, _ in expected if field not in recovered]
        prefix = f"Recovered {len(fields)} of {len(expected)} allowlisted fields from {method}"
        if method == "OCR":
            prefix += f" with every used token at or above {OCR_MIN_CONFIDENCE:.0f}% confidence"
        if not missing:
            return f"{prefix}."
        detail = f"Unrecovered fields: {', '.join(missing)}." if fields else failure or f"Unrecovered fields: {', '.join(missing)}."
        return f"{prefix}. {detail}"

    def _extract_ocr_fields(
        self,
        pages: list[fitz.Page],
        expected: tuple[tuple[str, str, str], ...],
    ) -> dict[str, Any]:
        tesseract = shutil.which("tesseract")
        if not tesseract:
            return {
                "fields": [],
                "text": "",
                "reason": "No selectable text layer was found and local Tesseract OCR is unavailable in this runtime.",
            }

        fields: list[dict[str, Any]] = []
        text: list[str] = []
        for page_number, page in enumerate(pages, start=1):
            try:
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72),
                    colorspace=fitz.csGRAY,
                    alpha=False,
                )
                result = subprocess.run(
                    [tesseract, "stdin", "stdout", "-l", "eng", "--psm", "6", "tsv"],
                    input=pixmap.tobytes("png"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=OCR_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return {
                    "fields": [],
                    "text": "\n".join(text),
                    "reason": f"Local Tesseract OCR timed out after {OCR_TIMEOUT_SECONDS} seconds per page.",
                }
            except OSError:
                return {
                    "fields": [],
                    "text": "\n".join(text),
                    "reason": "No selectable text layer was found and local Tesseract OCR is unavailable in this runtime.",
                }
            if result.returncode != 0:
                return {
                    "fields": [],
                    "text": "\n".join(text),
                    "reason": "Local Tesseract OCR or its English language data is unavailable in this runtime.",
                }
            lines, page_text = self._ocr_lines(result.stdout)
            if lines is None:
                return {
                    "fields": [],
                    "text": "\n".join(text),
                    "reason": "Local Tesseract OCR returned malformed TSV output.",
                }
            text.append(page_text)
            fields.extend(self._ocr_page_fields(page, page_number, pixmap.width, pixmap.height, lines, expected))

        by_field = {field["field"]: field for field in fields}
        accepted = [by_field[field] for field, _, _ in expected if field in by_field]
        return {
            "fields": accepted,
            "text": "\n".join(text),
            "reason": "No allowlisted label/value pairs qualified for local OCR at the required 90% token-confidence threshold.",
        }

    @staticmethod
    def _ocr_lines(tsv: bytes) -> tuple[list[dict[str, Any]] | None, str]:
        try:
            reader = csv.DictReader(io.StringIO(tsv.decode("utf-8")), delimiter="\t")
            required = {"level", "block_num", "par_num", "line_num", "left", "top", "width", "height", "conf", "text"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                return None, ""
            grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
            all_text: list[str] = []
            for row in reader:
                if row["level"] != "5" or not row["text"].strip():
                    continue
                word = {
                    "text": row["text"].strip(),
                    "confidence": float(row["conf"]),
                    "left": float(row["left"]),
                    "top": float(row["top"]),
                    "width": float(row["width"]),
                    "height": float(row["height"]),
                }
                all_text.append(word["text"])
                grouped.setdefault((row["block_num"], row["par_num"], row["line_num"]), []).append(word)
        except (KeyError, TypeError, UnicodeDecodeError, ValueError, csv.Error):
            return None, ""

        lines = []
        for words in grouped.values():
            ordered = sorted(words, key=lambda word: word["left"])
            lines.append({
                "words": ordered,
                "left": min(word["left"] for word in ordered),
                "right": max(word["left"] + word["width"] for word in ordered),
                "top": min(word["top"] for word in ordered),
                "bottom": max(word["top"] + word["height"] for word in ordered),
            })
        return sorted(lines, key=lambda line: (line["top"], line["left"])), " ".join(all_text)

    def _ocr_page_fields(
        self,
        page: fitz.Page,
        page_number: int,
        pixel_width: int,
        pixel_height: int,
        lines: list[dict[str, Any]],
        expected: tuple[tuple[str, str, str], ...],
    ) -> list[dict[str, Any]]:
        labels: dict[str, tuple[dict[str, Any], int, int]] = {}
        for field, label, _ in expected:
            label_tokens = [self._ocr_token(token) for token in label.split()]
            for line in lines:
                words = line["words"]
                for start in range(len(words) - len(label_tokens) + 1):
                    candidate = words[start:start + len(label_tokens)]
                    if (
                        all(word["confidence"] >= OCR_MIN_CONFIDENCE for word in candidate)
                        and [self._ocr_token(word["text"]) for word in candidate] == label_tokens
                    ):
                        labels[field] = (line, start, start + len(label_tokens))
                        break
                if field in labels:
                    break

        results = []
        for field, _, kind in expected:
            located = labels.get(field)
            if not located:
                continue
            label_line, start, end = located
            label_words = label_line["words"][start:end]
            label_left = min(word["left"] for word in label_words)
            label_right = max(word["left"] + word["width"] for word in label_words)
            row_labels = sorted(
                [
                    (
                        other_field,
                        min(word["left"] for word in other_line["words"][other_start:other_end]),
                        max(word["left"] + word["width"] for word in other_line["words"][other_start:other_end]),
                    )
                    for other_field, (other_line, other_start, other_end) in labels.items()
                    if other_line is label_line
                ],
                key=lambda item: item[1],
            )
            position = next(index for index, item in enumerate(row_labels) if item[0] == field)
            left_limit = (row_labels[position - 1][2] + label_left) / 2 if position else float("-inf")
            right_limit = (label_right + row_labels[position + 1][1]) / 2 if position + 1 < len(row_labels) else float("inf")
            value_words = self._ocr_value_words(lines, label_line, label_right, left_limit, right_limit, kind)
            if not value_words:
                continue
            raw_value = " ".join(word["text"] for word in value_words)
            value = self._typed_value(raw_value, kind)
            if value is None or field not in ALLOWLISTED_FIELDS:
                continue
            bbox = self._ocr_bbox(page, pixel_width, pixel_height, value_words)
            results.append({
                "field": field,
                "value": value,
                "raw_value": raw_value,
                "page": page_number,
                "bbox": bbox,
                "bbox_units": "pdf_points_bottom_left_origin",
                "confidence": "medium",
                "confidence_reason": "Known label, strict typed value, and geometric OCR source box matched. OCR evidence remains review-required.",
                "extraction_method": "ocr",
                "ocr_confidence": round(min(word["confidence"] for word in [*label_words, *value_words]), 2),
                "confirmation_state": "pending",
            })
        return results

    @staticmethod
    def _ocr_token(value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    def _ocr_value_words(
        self,
        lines: list[dict[str, Any]],
        label_line: dict[str, Any],
        label_right: float,
        left_limit: float,
        right_limit: float,
        kind: str,
    ) -> list[dict[str, Any]] | None:
        ordered = sorted(lines, key=lambda line: (line["top"], line["left"]))
        for line in ordered:
            same_line = line is label_line
            if same_line:
                candidates = [word for word in line["words"] if word["left"] >= label_right]
            elif line["top"] >= label_line["bottom"] - 2:
                if line["top"] - label_line["bottom"] > OCR_DPI * 1.5:
                    break
                candidates = line["words"]
            else:
                continue
            candidates = [
                word for word in candidates
                if word["confidence"] >= OCR_MIN_CONFIDENCE
                and left_limit <= word["left"] + word["width"] / 2 < right_limit
            ]
            if not candidates:
                continue
            raw_value = " ".join(word["text"] for word in candidates)
            if self._typed_value(raw_value, kind) is not None:
                return candidates
        return None

    @staticmethod
    def _ocr_bbox(page: fitz.Page, pixel_width: int, pixel_height: int, words: list[dict[str, Any]]) -> list[float]:
        x0 = min(word["left"] for word in words)
        y0 = min(word["top"] for word in words)
        x1 = max(word["left"] + word["width"] for word in words)
        y1 = max(word["top"] + word["height"] for word in words)
        x_scale = page.rect.width / pixel_width
        y_scale = page.rect.height / pixel_height
        return [
            round(x0 * x_scale, 2),
            round(page.rect.height - y1 * y_scale, 2),
            round(x1 * x_scale, 2),
            round(page.rect.height - y0 * y_scale, 2),
        ]

    @staticmethod
    def _value_after_label(page_text: list[str], label: str) -> str | None:
        lines = [line.strip() for text in page_text for line in text.splitlines() if line.strip()]
        normalized_label = re.sub(r"\s+", " ", label.upper())
        for index, line in enumerate(lines):
            normalized_line = re.sub(r"\s+", " ", line.upper())
            if normalized_line == normalized_label and index + 1 < len(lines):
                return lines[index + 1]
        return None

    @staticmethod
    def _typed_value(raw: str, kind: str) -> Any | None:
        if kind == "string":
            return raw.strip()
        if kind == "date":
            value = raw.strip()
            return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
        if kind == "month":
            value = raw.strip()
            return value if re.fullmatch(r"\d{4}-\d{2}", value) else None
        if kind == "frequency":
            value = raw.strip().lower()
            return value if value in {"weekly", "biweekly", "semimonthly", "monthly", "annual"} else None
        if kind in {"integer", "number", "currency"}:
            number = re.sub(r"[^0-9.-]", "", raw)
            if not number:
                return None
            try:
                numeric = float(number)
            except ValueError:
                return None
            if kind == "integer":
                return int(numeric) if numeric.is_integer() else None
            return int(numeric) if numeric.is_integer() and kind == "number" else numeric
        return None

    @staticmethod
    def _source_box(pages: list[fitz.Page], label: str, raw_value: str) -> dict[str, Any] | None:
        candidates: list[tuple[float, int, fitz.Rect]] = []
        for page_number, page in enumerate(pages, start=1):
            label_hits = page.search_for(label)
            value_hits = page.search_for(raw_value)
            for label_box in label_hits:
                for value_box in value_hits:
                    if value_box.y0 < label_box.y1 - 4:
                        continue
                    distance = (value_box.y0 - label_box.y1) * 2 + abs(value_box.x0 - label_box.x0)
                    candidates.append((distance, page_number, value_box))
        if not candidates:
            return None
        _, page_number, box = min(candidates, key=lambda candidate: candidate[0])
        height = pages[page_number - 1].rect.height
        return {
            "page": page_number,
            "bbox": [round(box.x0, 2), round(height - box.y1, 2), round(box.x1, 2), round(height - box.y0, 2)],
        }
        return None
