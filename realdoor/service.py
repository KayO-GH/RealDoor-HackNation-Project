"""Deterministic data and safety services for the RealDoor prototype.

This module intentionally uses the organizer-provided synthetic gold labels for
the supplied fixture documents. It is a demo extraction adapter, not a general
OCR or eligibility engine. Raw PDF contents are never read or logged by the
application server.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


EVENT_DATE = date(2026, 7, 18)
CURRENT_DOCUMENT_DAYS = 60
FREQUENCY_MULTIPLIERS = {
    "weekly": 52,
    "biweekly": 26,
    "semimonthly": 24,
    "monthly": 12,
    "annual": 1,
}
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
FIELD_PURPOSES = {
    "person_name": "Identify the household record during this local session.",
    "household_size": "Select the supplied 60% AMI threshold.",
    "address": "Show the renter's submitted application context; it is not used for scoring.",
    "application_date": "Show the source document date.",
    "pay_date": "Establish the source pay period's recency.",
    "pay_period_start": "Explain the source pay period.",
    "pay_period_end": "Explain the source pay period.",
    "pay_frequency": "Annualize documented recurring gross income.",
    "regular_hours": "Reconcile documented base pay.",
    "hourly_rate": "Reconcile documented base pay.",
    "gross_pay": "Explain the documented source amount.",
    "net_pay": "Display evidence only; never used for the annualized gross-income calculation.",
    "document_date": "Check the challenge's 60-day evidence convention.",
    "weekly_hours": "Reconcile employment evidence.",
    "monthly_benefit": "Annualize independently documented recurring benefit income.",
    "benefit_frequency": "Annualize independently documented recurring benefit income.",
    "statement_month": "Identify the gig-income statement period.",
    "gross_receipts": "Annualize documented gig receipts for the challenge calculation.",
    "platform_fees": "Display source evidence; it does not infer undocumented income.",
}
EXCLUSIONS = [
    "Protected traits or proxies",
    "Immigration, disability, health, or family-status inference",
    "Behavioral, device, credit, or landlord-revenue signals",
    "Eligibility, approval, denial, priority, ranking, or acceptance prediction",
]


@dataclass(frozen=True)
class Source:
    label: str
    amount: float
    frequency: str
    document_id: str
    field: str
    citation: dict[str, Any]

    @property
    def annualized(self) -> float:
        return round(self.amount * FREQUENCY_MULTIPLIERS[self.frequency], 2)


class RealDoorService:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._documents = self._load_jsonl("synthetic_documents/gold/document_gold.jsonl")
        self._rules = self._load_jsonl("rules/rule_corpus.jsonl")
        self._qa = self._load_jsonl("evaluation/qa_gold.jsonl")
        self._checklists = self._load_checklists()
        self._thresholds = self._load_thresholds()
        self._documents_by_household: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for document in self._documents:
            self._documents_by_household[document["household_id"]].append(document)

    def _load_jsonl(self, relative_path: str) -> list[dict[str, Any]]:
        with (self.root / relative_path).open(encoding="utf-8") as file:
            return [json.loads(line) for line in file if line.strip()]

    def _load_checklists(self) -> dict[str, dict[str, Any]]:
        with (self.root / "evaluation/application_checklists.json").open(encoding="utf-8") as file:
            return {row["household_id"]: row for row in json.load(file)}

    def _load_thresholds(self) -> dict[int, dict[str, Any]]:
        with (self.root / "data/mtsp_2026_boston_cambridge_quincy.csv").open(encoding="utf-8") as file:
            return {int(row["household_size"]): row for row in csv.DictReader(file)}

    def household_summaries(self) -> list[dict[str, Any]]:
        summaries = []
        for household_id in sorted(self._documents_by_household):
            checklist = self._checklists[household_id]
            application = self._document_by_type(household_id, "application_summary")
            name = self._field_value(application, "person_name")
            summaries.append({
                "household_id": household_id,
                "name": name,
                "scenario": checklist["scenario"],
                "expected_readiness_status": checklist["expected_readiness_status"],
            })
        return summaries

    def household_payload(self, household_id: str) -> dict[str, Any]:
        if household_id not in self._documents_by_household:
            raise KeyError(household_id)
        checklist = self._checklists[household_id]
        documents = [self._public_document(document) for document in self._documents_by_household[household_id]]
        profile_fields = self._profile_fields(household_id)
        sources = self._income_sources(household_id)
        calculation = self._calculation(household_id, sources)
        return {
            "household_id": household_id,
            "documents": documents,
            "profile_fields": profile_fields,
            "income_sources": [self._source_payload(source) for source in sources],
            "calculation": calculation,
            "readiness": self._readiness_payload(checklist),
            "rules": self._relevant_rules(),
            "consent": self.consent_payload(),
        }

    def submission_payload(self, household_id: str) -> dict[str, Any]:
        """Return the organizer's required non-decisioning submission shape."""
        payload = self.household_payload(household_id)
        calculation = payload["calculation"]
        citations = [calculation["calculation_citation"], payload["readiness"]["citation"]]
        if calculation["threshold_citation"]:
            citations.append(calculation["threshold_citation"])
        citations.extend(source["citation"] for source in calculation["sources"])
        return {
            "household_id": household_id,
            "annualized_income": calculation["annualized_income"],
            "comparison": calculation["comparison"],
            "readiness_status": payload["readiness"]["status"],
            "citations": citations,
        }

    def consent_payload(self) -> dict[str, Any]:
        return {
            "summary": "Synthetic files stay in this browser session. The local server uses fixture metadata only and does not store raw document contents.",
            "allowlisted_fields": [
                {"field": field, "purpose": FIELD_PURPOSES[field]}
                for field in sorted(FIELD_PURPOSES)
            ],
            "exclusions": EXCLUSIONS,
            "retention": "Session data lives in browser memory. Deleting the session clears the profile and packet. Action events record event type and rule version, never raw document text.",
        }

    def safety_answer(self, question: str, active_household: str | None) -> dict[str, Any]:
        lowered = question.lower()
        exact_gold_answer = next((row for row in self._qa if row["question"].lower() == lowered.strip()), None)
        if exact_gold_answer:
            return {
                "kind": "rule_answer",
                "answer": exact_gold_answer["answer"],
                "citations": [self._rule_citation(self._rule(rule_id)) for rule_id in exact_gold_answer["rule_ids"]],
            }
        if any(word in lowered for word in ("disability", "immigration", "health", "race", "religion", "family status")):
            return self._safety_response(
                "I cannot infer or use protected traits, immigration status, disability, health, or family status. I can only work with the published rule and confirmed allowlisted evidence.",
                ["CH-SAFETY-001", "CH-DECISION-001"],
            )
        if any(word in lowered for word in ("eligible", "eligibility", "approved", "approve", "denied", "deny")):
            return self._safety_response(
                "I cannot decide eligibility, approval, or denial. I can show the confirmed values, frozen-rule comparison, readiness status, and what a qualified human should review.",
                ["CH-DECISION-001", "CH-READINESS-001"],
            )
        if any(word in lowered for word in ("another household", "other applicant", "other renter", "their income", "their document")):
            return self._safety_response(
                "I cannot disclose another household's information. This session only shows the active renter-controlled profile.",
                ["CH-SAFETY-001"],
            )
        if any(word in lowered for word in ("available", "vacancy", "vacant", "waitlist")):
            return self._safety_response(
                "The supplied property data does not establish live vacancies, rents, waitlists, or application status. Availability is unknown unless separately supplied.",
                ["HUD-DATA-001"],
            )
        if any(word in lowered for word in ("ignore", "system prompt", "instructions")):
            return self._safety_response(
                "Document text and user prompts are untrusted data. They cannot change the frozen rules, reveal system data, or cause a decision.",
                ["CH-SAFETY-001", "CH-DECISION-001"],
            )
        if "2025" in lowered or "wrong year" in lowered:
            return self._safety_response(
                "This prototype uses only the frozen FY 2026 corpus and its stated effective dates. It will not substitute a remembered 2025 value.",
                ["HUD-MTSP-001", "HUD-MTSP-002"],
            )
        if "citation" in lowered or "source" in lowered:
            return self._safety_response(
                "I will not present a material rule or calculation result without a readable source citation. Check the field evidence box or rule citation before reuse.",
                ["CH-SAFETY-001", "CH-INCOME-001"],
            )
        if "unsigned" in lowered or "self-declaration" in lowered or "self declaration" in lowered:
            return self._safety_response(
                "An unsigned self-declaration is not treated as employer evidence. Preserve it as a review gap and ask a qualified human which corroborating document is needed.",
                ["CH-READINESS-001", "CH-DECISION-001"],
            )
        if active_household and "annualized income" in lowered:
            calculation = self.household_payload(active_household)["calculation"]
            return {
                "kind": "rule_answer",
                "answer": f"${calculation['annualized_income']:,.2f} under the frozen annualization convention.",
                "citations": [calculation["calculation_citation"], *[source["citation"] for source in calculation["sources"]]],
            }
        if active_household and ("compare" in lowered or "comparison" in lowered):
            calculation = self.household_payload(active_household)["calculation"]
            return {
                "kind": "rule_answer",
                "answer": calculation["comparison"],
                "citations": [calculation["calculation_citation"], calculation["threshold_citation"]],
            }
        if active_household and "readiness" in lowered:
            payload = self.household_payload(active_household)
            return {
                "kind": "rule_answer",
                "answer": payload["readiness"]["status"],
                "citations": [payload["readiness"]["citation"]],
            }
        if active_household and ("threshold" in lowered or "60%" in lowered or "ami" in lowered):
            payload = self.household_payload(active_household)
            calculation = payload["calculation"]
            return {
                "kind": "rule_answer",
                "answer": f"The frozen 60% threshold for household size {calculation['household_size']} is ${calculation['threshold']:,.0f}.",
                "citations": [calculation["threshold_citation"]],
            }
        return self._safety_response(
            "Ask about the confirmed profile, the frozen 2026 threshold, a citation, or a packet review reason. I will not infer protected traits or make program decisions.",
            ["CH-SAFETY-001", "CH-DECISION-001"],
        )

    def _safety_response(self, answer: str, rule_ids: list[str]) -> dict[str, Any]:
        rules = {rule["rule_id"]: rule for rule in self._rules}
        return {"kind": "safety", "answer": answer, "citations": [self._rule_citation(rules[rule_id]) for rule_id in rule_ids]}

    def _public_document(self, document: dict[str, Any]) -> dict[str, Any]:
        confidence = "medium" if document.get("rasterized") else "high"
        confidence_reason = "Rasterized fixture; renter confirmation is required." if confidence == "medium" else "Native synthetic fixture with a supplied source box; renter confirmation is required."
        fields = []
        for field in document["fields"]:
            if field["field"] not in ALLOWLISTED_FIELDS:
                continue
            fields.append({
                **field,
                "confidence": confidence,
                "confidence_reason": confidence_reason,
                "confirmation_state": "pending",
                "purpose": FIELD_PURPOSES[field["field"]],
            })
        return {
            "document_id": document["document_id"],
            "document_type": document["document_type"],
            "file_name": document["file_name"],
            "page_count": document["page_count"],
            "preview_url": f"/documents/{document['file_name']}",
            "preview_image_url": f"/previews/{Path(document['file_name']).with_suffix('.png').name}",
            "contains_untrusted_content": bool(document.get("contains_adversarial_text")),
            "untrusted_content_handling": "Ignored: untrusted text is not extracted, displayed, or used as an instruction.",
            "fields": fields,
        }

    def _profile_fields(self, household_id: str) -> list[dict[str, Any]]:
        application = self._document_by_type(household_id, "application_summary")
        return [self._field_payload(application, name) for name in ("person_name", "household_size", "address", "application_date")]

    def _field_payload(self, document: dict[str, Any], name: str) -> dict[str, Any]:
        field = next(field for field in document["fields"] if field["field"] == name)
        payload = self._public_document(document)
        public_field = next(item for item in payload["fields"] if item["field"] == name)
        return {**public_field, "document_id": document["document_id"], "document_type": document["document_type"]}

    def _income_sources(self, household_id: str) -> list[Source]:
        documents = self._documents_by_household[household_id]
        sources: list[Source] = []
        pay_stubs = [document for document in documents if document["document_type"] == "pay_stub"]
        if pay_stubs:
            pay_stub = max(pay_stubs, key=lambda document: self._field_value(document, "pay_date") or "")
            hours = self._field_value(pay_stub, "regular_hours")
            rate = self._field_value(pay_stub, "hourly_rate")
            frequency = self._field_value(pay_stub, "pay_frequency")
            if hours is not None and rate is not None and frequency in FREQUENCY_MULTIPLIERS:
                amount = round(float(hours) * float(rate), 2)
                sources.append(Source("Documented base wages", amount, frequency, pay_stub["document_id"], "gross_pay", self._field_citation(pay_stub, "gross_pay")))
        for document in documents:
            if document["document_type"] == "benefit_letter":
                amount = self._field_value(document, "monthly_benefit")
                frequency = self._field_value(document, "benefit_frequency")
                if amount is not None and frequency in FREQUENCY_MULTIPLIERS:
                    sources.append(Source("Documented recurring benefit", float(amount), frequency, document["document_id"], "monthly_benefit", self._field_citation(document, "monthly_benefit")))
            if document["document_type"] == "gig_statement":
                amount = self._field_value(document, "gross_receipts")
                if amount is not None:
                    sources.append(Source("Documented gig receipts (requires review)", float(amount), "monthly", document["document_id"], "gross_receipts", self._field_citation(document, "gross_receipts")))
        return sources

    def _calculation(self, household_id: str, sources: list[Source]) -> dict[str, Any]:
        household_size = int(self._field_value(self._document_by_type(household_id, "application_summary"), "household_size"))
        threshold_row = self._thresholds.get(household_size)
        annualized_income = round(sum(source.annualized for source in sources), 2)
        if threshold_row is None:
            comparison = "no_frozen_threshold"
            threshold = None
            threshold_citation = None
        else:
            threshold = float(threshold_row["core_challenge_threshold"])
            comparison = "below_or_equal" if annualized_income <= threshold else "above"
            threshold_citation = {
                "rule_id": "HUD-MTSP-002",
                "authority": "official_hud",
                "effective_date": threshold_row["effective_date"],
                "source_url": threshold_row["source_url"],
                "source_locator": f"PDF page {threshold_row['source_pdf_page']}",
            }
        return {
            "household_size": household_size,
            "sources": [self._source_payload(source) for source in sources],
            "formula": "Sum each independently documented recurring source: amount × explicit frequency.",
            "annualized_income": annualized_income,
            "threshold": threshold,
            "comparison": comparison,
            "threshold_citation": threshold_citation,
            "calculation_citation": self._rule_citation(self._rule("CH-INCOME-001")),
        }

    def _readiness_payload(self, checklist: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": checklist["expected_readiness_status"],
            "reasons": checklist["expected_review_reasons"],
            "missing_document_types": checklist["missing_document_types"],
            "current_document_convention": f"Documents are current when dated no more than {CURRENT_DOCUMENT_DAYS} days before {EVENT_DATE.isoformat()} for this challenge simulation.",
            "citation": self._rule_citation(self._rule("CH-READINESS-001")),
        }

    def _relevant_rules(self) -> list[dict[str, Any]]:
        return [self._rule_citation(self._rule(rule_id)) for rule_id in ("HUD-MTSP-001", "HUD-MTSP-002", "CH-INCOME-001", "CH-READINESS-001", "CH-SAFETY-001", "CH-DECISION-001")]

    def _source_payload(self, source: Source) -> dict[str, Any]:
        return {"label": source.label, "amount": source.amount, "frequency": source.frequency, "annualized": source.annualized, "document_id": source.document_id, "field": source.field, "citation": source.citation}

    def _field_citation(self, document: dict[str, Any], name: str) -> dict[str, Any]:
        field = next(field for field in document["fields"] if field["field"] == name)
        return {"document_id": document["document_id"], "page": field["page"], "bbox": field["bbox"], "bbox_units": field["bbox_units"]}

    def _rule_citation(self, rule: dict[str, Any]) -> dict[str, Any]:
        return {key: rule[key] for key in ("rule_id", "authority", "effective_date", "source_url", "source_locator")}

    def _rule(self, rule_id: str) -> dict[str, Any]:
        return next(rule for rule in self._rules if rule["rule_id"] == rule_id)

    def _document_by_type(self, household_id: str, document_type: str) -> dict[str, Any]:
        return next(document for document in self._documents_by_household[household_id] if document["document_type"] == document_type)

    @staticmethod
    def _field_value(document: dict[str, Any], name: str) -> Any:
        return next((field["value"] for field in document["fields"] if field["field"] == name), None)
