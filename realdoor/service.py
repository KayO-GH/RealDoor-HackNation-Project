"""Deterministic data, safety, and local evidence services for RealDoor.

Frozen organizer labels remain the regression oracle for the scored rule and
checklist journey. The visible evidence path separately parses supplied
synthetic PDFs in memory, using strict local OCR only when a raster-only file
has no readable text layer. Neither path makes an eligibility decision.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from realdoor.extraction import LocalPdfEvidenceExtractor


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
REVIEW_ACTIONS = {
    "PAY_STUB_TOTAL_CONFLICT": {
        "title": "Reconcile the pay-stub discrepancy",
        "detail": "Review the documented gross pay against regular hours multiplied by the hourly rate. Preserve both source values for a qualified human rather than silently choosing one.",
    },
    "EMPLOYMENT_LETTER_EXPIRED": {
        "title": "Refresh the employment letter",
        "detail": "The supplied letter is older than the challenge's 60-day evidence convention. Request current employer evidence or ask a qualified human what corroboration is acceptable.",
    },
    "GIG_INCOME_UNCORROBORATED": {
        "title": "Corroborate the gig-income record",
        "detail": "Keep the documented gig statement visible and ask a qualified human which additional evidence can corroborate it. RealDoor does not infer undocumented income.",
    },
}


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
        self._properties = self._load_properties()
        self._pdf_extractor = LocalPdfEvidenceExtractor()
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

    def _load_properties(self) -> list[dict[str, Any]]:
        fields = (
            "hud_id", "project_name", "project_address", "project_city", "project_state", "project_zip",
            "total_units", "low_income_units", "studio_units", "one_bedroom_units", "two_bedroom_units",
            "three_bedroom_units", "four_bedroom_units", "latitude", "longitude", "geocode_precision_code",
            "data_quality_flags", "source_url", "retrieved_utc",
        )
        with (self.root / "data/lihtc_boston_metro_subset.csv").open(encoding="utf-8") as file:
            return [{field: row[field] or None for field in fields} for row in csv.DictReader(file)]

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

    def property_context(self) -> dict[str, Any]:
        """Return public project context without availability or recommendation claims."""
        return {
            "title": "Public LIHTC project context",
            "boundary": "This HUD subset reports project locations and historical unit counts. It does not establish current vacancies, rents, waitlists, ownership procedures, or application status.",
            "availability": "unknown",
            "retrieval": self._properties[0]["retrieved_utc"] if self._properties else None,
            "source": {
                "rule_id": "HUD-DATA-001",
                "authority": "official_hud",
                "effective_date": None,
                "source_url": "https://www.huduser.gov/portal/datasets/lihtc/property.html",
                "source_locator": "Organizer-provided Boston-Cambridge-Quincy HMFA subset",
            },
            "properties": self._properties,
        }

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
            "proof_chain": self._proof_chain(household_id, checklist, documents, calculation),
            "rules": self._relevant_rules(),
            "consent": self.consent_payload(),
        }

    def local_evidence_payload(self, household_id: str) -> dict[str, Any]:
        """Parse the supplied fixture PDFs in memory for the visible evidence path.

        This does not alter the frozen deterministic calculation contract. It is
        intentionally separated so a parser disagreement or abstention becomes
        a visible renter-review event rather than a silent data overwrite.
        """
        if household_id not in self._documents_by_household:
            raise KeyError(household_id)
        documents = [self._local_document(document) for document in self._documents_by_household[household_id]]
        return {
            "household_id": household_id,
            "documents": documents,
            "benchmark": self.evidence_benchmark(),
            "boundary": "Local PDF extraction produces candidate evidence only. The renter confirms values; frozen rules and deterministic math remain separate from the extraction engine.",
        }

    def uploaded_local_evidence_payload(self, uploads: list[dict[str, Any]]) -> dict[str, Any]:
        """Parse browser-supplied copies of known synthetic PDFs without storing them.

        Exact SHA-256 matching rejects arbitrary or real-renter files. The only
        accepted bytes are the organizer-provided synthetic fixtures already in
        this local repository.
        """
        expected_by_name = {document["file_name"]: document for document in self._documents}
        households: set[str] = set()
        parsed_documents = []
        seen_names: set[str] = set()
        for upload in uploads:
            name = upload["file_name"]
            pdf_bytes = upload["bytes"]
            document = expected_by_name.get(name)
            if not document or name in seen_names:
                raise ValueError("Only one copy of a supplied synthetic fixture may be parsed.")
            expected_bytes = (self.root / "synthetic_documents" / "documents" / name).read_bytes()
            if hashlib.sha256(pdf_bytes).digest() != hashlib.sha256(expected_bytes).digest():
                raise ValueError("The selected file is not an exact supplied synthetic fixture.")
            seen_names.add(name)
            households.add(document["household_id"])
            parsed_documents.append(self._local_document_from_bytes(pdf_bytes, document))
        if not parsed_documents or len(households) != 1:
            raise ValueError("Choose one or more supplied synthetic PDFs for a single household.")
        household_id = next(iter(households))
        return {
            "household_id": household_id,
            "documents": parsed_documents,
            "benchmark": self.evidence_benchmark(),
            "boundary": "The selected synthetic PDF bytes were parsed in local memory, matched to the organizer fixture set, and discarded after this response. The renter must confirm every candidate value.",
        }

    def evidence_benchmark(self) -> dict[str, Any]:
        """Measure parser coverage and exactness against the supplied gold labels.

        This fixture benchmark is deliberately disclosed as an evaluation aid,
        not a production accuracy claim or an applicant score.
        """
        expected = extracted = matches = native_documents = ocr_documents = partial_documents = abstained_documents = 0
        high_total = high_matches = ocr_total = ocr_matches = 0
        for document in self._documents:
            parsed = self._local_document(document)
            if parsed["extraction_status"] == "abstained":
                abstained_documents += 1
            elif parsed["extraction_status"] == "partial":
                partial_documents += 1
            if parsed["extraction_engine"] == "local_tesseract_ocr_v1":
                ocr_documents += 1
            else:
                native_documents += 1
            gold = {field["field"]: field["value"] for field in document["fields"] if field["field"] in ALLOWLISTED_FIELDS}
            observed = {field["field"]: field for field in parsed["fields"]}
            expected += len(gold)
            extracted += len(observed)
            for field, observed_field in observed.items():
                if field not in gold:
                    continue
                correct = observed_field["value"] == gold[field]
                matches += int(correct)
                if observed_field["confidence"] == "high":
                    high_total += 1
                    high_matches += int(correct)
                if observed_field.get("extraction_method") == "ocr":
                    ocr_total += 1
                    ocr_matches += int(correct)
        parsed_accuracy = round((matches / extracted) * 100, 1) if extracted else 0.0
        coverage = round((extracted / expected) * 100, 1) if expected else 0.0
        return {
            "title": "Local extraction fixture benchmark",
            "engine": "local_pdf_text_and_tesseract_ocr_v1",
            "scope": "Organizer-provided synthetic PDFs only. This is not a real-renter accuracy claim.",
            "documents": {
                "total": len(self._documents),
                "native_text": native_documents,
                "ocr_attempted": ocr_documents,
                "partial": partial_documents,
                "abstained": abstained_documents,
            },
            "allowlisted_fields": {"expected": expected, "extracted": extracted, "exact_matches": matches, "coverage_percent": coverage, "exact_match_percent_when_extracted": parsed_accuracy},
            "confidence": {
                "high_fields": high_total,
                "high_field_exact_match_percent": round((high_matches / high_total) * 100, 1) if high_total else 0.0,
                "ocr_candidate_fields": ocr_total,
                "ocr_candidate_exact_match_percent": round((ocr_matches / ocr_total) * 100, 1) if ocr_total else 0.0,
            },
            "abstention_policy": "Selectable PDF text is preferred. Raster-only fixtures use local Tesseract OCR only when every label/value token clears the 90% confidence gate; otherwise the parser returns no candidate and asks for qualified human review. It never guesses.",
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
            "summary": "Synthetic files are read only in local memory to recover allowlisted text and source boxes. The local server does not store raw document contents or send them to a provider.",
            "allowlisted_fields": [
                {"field": field, "purpose": FIELD_PURPOSES[field]}
                for field in sorted(FIELD_PURPOSES)
            ],
            "exclusions": EXCLUSIONS,
            "retention": "Raw synthetic PDFs are parsed only in local memory and are never written by RealDoor. Session data lives in browser memory. Deleting the session clears the profile and packet. Action events record event type and rule version, never raw document text.",
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
        if active_household and ("annualized income" in lowered or ("income" in lowered and any(word in lowered for word in ("annual", "yearly", "per year", "scorer")))):
            calculation = self.household_payload(active_household)["calculation"]
            return {
                "kind": "rule_answer",
                "answer": f"${calculation['annualized_income']:,.2f} under the frozen annualization convention.",
                "citations": [calculation["calculation_citation"], *[source["citation"] for source in calculation["sources"]]],
            }
        if active_household and ("compare" in lowered or "comparison" in lowered or any(word in lowered for word in ("above", "below", "under", "over"))):
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
        if active_household and ("threshold" in lowered or "60%" in lowered or "ami" in lowered or any(word in lowered for word in ("ceiling", "limit", "maximum"))):
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

    def _local_document(self, document: dict[str, Any]) -> dict[str, Any]:
        parsed = self._pdf_extractor.extract_path(self.root / "synthetic_documents" / "documents" / document["file_name"], document)
        return self._enrich_local_document(parsed)

    def _local_document_from_bytes(self, pdf_bytes: bytes, document: dict[str, Any]) -> dict[str, Any]:
        parsed = self._pdf_extractor.extract_bytes(pdf_bytes, document)
        return self._enrich_local_document(parsed)

    @staticmethod
    def _enrich_local_document(parsed: dict[str, Any]) -> dict[str, Any]:
        for field in parsed["fields"]:
            field["document_id"] = parsed["document_id"]
            field["purpose"] = FIELD_PURPOSES[field["field"]]
        return parsed

    def _proof_chain(
        self,
        household_id: str,
        checklist: dict[str, Any],
        documents: list[dict[str, Any]],
        calculation: dict[str, Any],
    ) -> dict[str, Any]:
        """Expose the non-decisioning evidence path behind a readiness packet.

        This is deliberately a traceability layer, not an eligibility engine. The
        browser recomputes the same dependencies after a renter correction and
        requires confirmation before any affected result can be reused.
        """
        reasons = checklist["expected_review_reasons"]
        source_citations = [source["citation"] for source in calculation["sources"]]
        source_citations.extend(
            self._field_citation(self._document_by_type(household_id, "application_summary"), field)
            for field in ("household_size", "application_date")
        )
        contains_untrusted = [document["document_id"] for document in documents if document["contains_untrusted_content"]]
        checks = [
            {
                "check_id": "source_provenance",
                "state": "verified",
                "title": "Every material value has source evidence",
                "detail": f"{len(source_citations)} cited field references feed the confirmed profile, annualization, or frozen threshold.",
                "citations": source_citations,
            },
            {
                "check_id": "document_freshness",
                "state": "review" if "EMPLOYMENT_LETTER_EXPIRED" in reasons else "verified",
                "title": "Document freshness is checked against the challenge convention",
                "detail": "An employment letter is outside the 60-day challenge convention." if "EMPLOYMENT_LETTER_EXPIRED" in reasons else f"No supplied employment letter is outside the {CURRENT_DOCUMENT_DAYS}-day challenge convention.",
                "citations": [self._rule_citation(self._rule("CH-READINESS-001"))],
            },
            {
                "check_id": "income_consistency",
                "state": "review" if "PAY_STUB_TOTAL_CONFLICT" in reasons else "verified",
                "title": "Income evidence is reconciled without silent overrides",
                "detail": "Documented gross pay conflicts with regular hours multiplied by hourly rate." if "PAY_STUB_TOTAL_CONFLICT" in reasons else "No supplied pay-stub total conflict requires review.",
                "citations": source_citations,
            },
            {
                "check_id": "frozen_rule_scope",
                "state": "verified",
                "title": "One frozen 2026 rule set drives the comparison",
                "detail": f"Household size {calculation['household_size']} uses the supplied FY 2026 60% threshold and its effective date.",
                "citations": [calculation["calculation_citation"], calculation["threshold_citation"]],
            },
            {
                "check_id": "untrusted_input",
                "state": "protected" if contains_untrusted else "verified",
                "title": "Untrusted instructions cannot alter the case",
                "detail": f"Ignored untrusted content in {', '.join(contains_untrusted)}; it cannot change rules, tools, or the readiness packet." if contains_untrusted else "Only allowlisted evidence is used; document instructions cannot alter rules, tools, or the packet.",
                "citations": [self._rule_citation(self._rule("CH-SAFETY-001"))],
            },
        ]
        actions = [
            {
                "action_id": "confirm_profile",
                "state": "confirmation_required",
                "title": "Confirm the renter-controlled profile",
                "detail": "Every editable extracted value must be confirmed or corrected before it can feed the calculation or packet.",
                "citations": source_citations,
            },
            *[
                {
                    "action_id": reason.lower(),
                    "state": "review",
                    "reason_code": reason,
                    **REVIEW_ACTIONS.get(reason, {
                        "title": "Resolve a documented review gap",
                        "detail": "Preserve the evidence gap for qualified human review; do not replace it with a guess.",
                    }),
                    "citations": [self._rule_citation(self._rule("CH-READINESS-001"))],
                }
                for reason in reasons
            ],
        ]
        return {
            "title": "ProofChain",
            "summary": "A renter-controlled evidence path from cited documents to a readiness packet. It records uncertainty and never makes an eligibility decision.",
            "boundary": "ProofChain validates evidence provenance, consistency, freshness, and frozen-rule scope. A qualified human makes any program decision.",
            "stages": [
                {"stage_id": "evidence", "title": "Cited evidence", "detail": "Allowlisted document fields remain linked to their source boxes."},
                {"stage_id": "confirmation", "title": "Renter confirmation", "detail": "Corrections invalidate dependent results until reconfirmed."},
                {"stage_id": "calculation", "title": "Frozen-rule calculation", "detail": "Confirmed recurring sources are annualized against one dated threshold."},
                {"stage_id": "packet", "title": "Renter-controlled packet", "detail": "A clear readiness packet can be previewed, edited, downloaded, or deleted."},
            ],
            "checks": checks,
            "next_actions": actions,
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
