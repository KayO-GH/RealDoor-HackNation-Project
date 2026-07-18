#!/usr/bin/env python3
"""Run deterministic local verification against the organizer fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from realdoor.service import RealDoorService  # noqa: E402


def check(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"PASS  {message}")
    else:
        print(f"FAIL  {message}")
        failures.append(message)


def main() -> int:
    service = RealDoorService(ROOT)
    failures: list[str] = []
    check(len(service.household_summaries()) == 6, "six supplied household fixtures are available", failures)

    checklists = json.loads((ROOT / "evaluation/application_checklists.json").read_text(encoding="utf-8"))
    for checklist in checklists:
        payload = service.household_payload(checklist["household_id"])
        calc = payload["calculation"]
        check(calc["annualized_income"] == checklist["expected_annualized_income"], f"{checklist['household_id']} annualized income matches gold checklist", failures)
        check(calc["comparison"] == checklist["comparison"], f"{checklist['household_id']} threshold comparison matches gold checklist", failures)
        check(payload["readiness"]["status"] == checklist["expected_readiness_status"], f"{checklist['household_id']} readiness status matches gold checklist", failures)

    qa_gold = [json.loads(line) for line in (ROOT / "evaluation/qa_gold.jsonl").read_text(encoding="utf-8").splitlines() if line]
    for qa in qa_gold:
        answer = service.safety_answer(qa["question"], qa["household_id"])
        answer_rule_ids = {citation["rule_id"] for citation in answer["citations"]}
        check(answer["answer"] == qa["answer"] and set(qa["rule_ids"]).issubset(answer_rule_ids), f"{qa['qa_id']} matches gold answer and citations", failures)

    submission_schema = json.loads((ROOT / "starter/schemas/submission.schema.json").read_text(encoding="utf-8"))
    required_submission_fields = set(submission_schema["required"])
    allowed_comparisons = set(submission_schema["properties"]["comparison"]["enum"])
    allowed_readiness = set(submission_schema["properties"]["readiness_status"]["enum"])
    for household in service.household_summaries():
        submission = service.submission_payload(household["household_id"])
        shape_is_valid = required_submission_fields.issubset(submission) and submission["comparison"] in allowed_comparisons and submission["readiness_status"] in allowed_readiness and bool(submission["citations"])
        check(shape_is_valid, f"{household['household_id']} submission matches required contract", failures)

    adversarial = [json.loads(line) for line in (ROOT / "evaluation/adversarial_tests.jsonl").read_text(encoding="utf-8").splitlines() if line]
    direct_categories = {"prompt_injection", "cross_applicant_leak", "eligibility_overreach", "vacancy_hallucination", "wrong_year_limit", "missing_citation", "unsupported_trait", "unsigned_claim"}
    for fixture in adversarial:
        if fixture["category"] in direct_categories:
            answer = service.safety_answer(fixture["input"], "HH-001")
            check(bool(answer["citations"]), f"{fixture['test_id']} returns a bounded answer with citations", failures)
        elif fixture["category"] == "expired_document":
            check("EMPLOYMENT_LETTER_EXPIRED" in service.household_payload("HH-005")["readiness"]["reasons"], f"{fixture['test_id']} produces expired-evidence review", failures)
        elif fixture["category"] == "conflicting_totals":
            check("PAY_STUB_TOTAL_CONFLICT" in service.household_payload("HH-002")["readiness"]["reasons"], f"{fixture['test_id']} produces conflict review", failures)
        elif fixture["category"] == "malformed_bbox":
            valid = all(0 <= field["bbox"][0] < field["bbox"][2] <= 612 and 0 <= field["bbox"][1] < field["bbox"][3] <= 792 for doc in service.household_payload("HH-001")["documents"] for field in doc["fields"])
            check(valid, f"{fixture['test_id']} source boxes validate", failures)
        elif fixture["category"] == "household_size_9":
            check(9 not in service._thresholds, f"{fixture['test_id']} has no supplied frozen threshold", failures)

    print(f"\n{'FAILED' if failures else 'PASSED'}: {len(failures)} issue(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
