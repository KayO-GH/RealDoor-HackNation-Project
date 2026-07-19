"""Local, synthetic-PDF evidence extraction for the RealDoor prototype.

The parser reads selectable text and word geometry directly from supplied
synthetic PDFs. It never uses organizer gold values at runtime. Raster-only
fixtures abstain so a renter can request OCR or human review instead of seeing
a fabricated value or confidence score.
"""

from __future__ import annotations

import re
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
            if not any(text.strip() for text in page_text):
                return {
                    **public,
                    "extraction_status": "abstained",
                    "abstention_reason": "No selectable text layer was found. RealDoor will not fabricate fields or confidence for this rasterized synthetic PDF.",
                    "fields": [],
                }
            fields = []
            for field, label, kind in FIELD_LABELS[metadata["document_type"]]:
                candidate = self._value_after_label(page_text, label)
                if candidate is None:
                    continue
                value = self._typed_value(candidate, kind)
                if value is None or field not in ALLOWLISTED_FIELDS:
                    continue
                source = self._source_box(pages, candidate)
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
                    "confirmation_state": "pending",
                })
            return {
                **public,
                "extraction_status": "extracted" if fields else "abstained",
                "abstention_reason": None if fields else "No allowlisted label/value pairs were recovered. RealDoor will not infer missing evidence.",
                "fields": fields,
            }
        finally:
            document.close()

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
        if kind in {"string", "date", "month"}:
            return raw.strip()
        if kind == "frequency":
            value = raw.strip().lower()
            return value if value in {"weekly", "biweekly", "semimonthly", "monthly", "annual"} else None
        if kind in {"integer", "number", "currency"}:
            number = re.sub(r"[^0-9.-]", "", raw)
            if not number:
                return None
            numeric = float(number)
            return int(numeric) if kind == "integer" or numeric.is_integer() and kind == "number" else numeric
        return None

    @staticmethod
    def _source_box(pages: list[fitz.Page], raw_value: str) -> dict[str, Any] | None:
        for page_number, page in enumerate(pages, start=1):
            hits = page.search_for(raw_value)
            if not hits:
                continue
            box = hits[0]
            height = page.rect.height
            return {
                "page": page_number,
                "bbox": [round(box.x0, 2), round(height - box.y1, 2), round(box.x1, 2), round(height - box.y0, 2)],
            }
        return None
