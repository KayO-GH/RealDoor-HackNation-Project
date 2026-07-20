# RealDoor Implementation Progress

## Status

**Local verified checkpoint; changes remain uncommitted and unpushed by request.** This file is the implementation checklist for `PLAN.md`.

## Completed

- [x] Inspected the organizer assets, schemas, gold labels, frozen rules, checklists, and adversarial fixtures.
- [x] Chose a local-first architecture so the core demo works offline without a hosted model.
- [x] Defined the initial data-service contract: synthetic fixture metadata, source boxes, confidence, cited rules, deterministic income sources, and readiness reasons.
- [x] Built a local Python server and deterministic fixture/rule service.
- [x] Built the accessible Profile -> Understand -> Prepare interface.
- [x] Added renter acknowledgement, confirmation/correction gating, packet preview inputs/download, and session deletion.
- [x] Added privacy/safety controls: allowlists, ignored untrusted text, no hidden-proxy feature register, cited refusals, and ephemeral browser-session state.
- [x] Added architecture/risk documentation and README teammate instructions.
- [x] Added project regression checks for gold checklists, citations, source boxes, and supplied adversarial fixtures.
- [x] Browser-smoke-tested consent, fixture loading, correction invalidation/recalculation, safety refusal, and session deletion.
- [x] Added editable correction controls for every displayed allowlisted field; relevant date and income corrections update downstream readiness and math after reconfirmation.
- [x] Added regression coverage for all supplied Q&A gold answers/citations and the required submission contract.
- [x] Replaced filename-only fixture selection with local selectable-text extraction for exact supplied synthetic PDF bytes; added source-box maps, strict local Tesseract fallback for textless pages, explicit abstention for unavailable/unqualified OCR, an extraction fixture benchmark split by method, and a material-input recovery gate.
- [x] Verified the renter-initiated packet-export action, packet preview, action-log entry, and "not sent" completion announcement.

## Completion Audit

| Requirement | Evidence |
| --- | --- |
| Profile: supplied synthetic documents, allowlisted fields, source boxes, confidence, correction, confirmation | `realdoor/extraction.py`, `realdoor/service.py`, `web/app.js`, local extraction tests, exact-byte upload endpoint test, visible source maps, inline corrections, and confirmation gating. |
| Understand: frozen 2026 corpus, deterministic calculation, threshold, formula, effective dates, citations, abstention | `realdoor/service.py`; checklist, Q&A, and schema checks in `tests/test_realdoor_service.py` and `scripts/evaluate.py`. |
| Prepare: missing/expired/conflicting reasons, preview, edit, download, delete, never auto-send | `web/app.js`; printable HTML case-file export; HH-005 correction path; session deletion; and the explicit never-auto-send state. |
| Safety/privacy: no decisioning, no proxies, consent, untrusted input, local retention/export/deletion | `realdoor/service.py`, `web/index.html`, `ARCHITECTURE_AND_RISK.md`, and all supplied adversarial-fixture checks. |
| Accessibility: keyboard-operable native controls, labels, focus styles, non-color status text, headings, live announcements | `web/index.html`, `web/styles.css`, and browser DOM checks of labelled/semantic controls. |
| Submission artifacts and teammate handoff | `README.md`, `DEMO_PLAN.md`, `ARCHITECTURE_AND_RISK.md`, `PLAN.md`, and this progress log. |

## Verified Commands

```bash
python3 -m py_compile app.py realdoor/service.py realdoor/extraction.py scripts/evaluate.py
node --check web/app.js
python3 -m unittest discover -s starter/tests -v
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py
```

The verified commands confirm six household calculations/readiness outputs, 36 gold Q&A answers with citations, six submission-contract payloads, all 24 supplied adversarial fixtures, and the local extraction exact-match/abstention tests. Re-run the commands after every material change.

## Remaining verification gates

- [x] Starter tests pass.
- [x] Gold/checklist/adversarial regression checks pass.
- [x] Browser smoke test proves consent, the happy path, correction, safety, and deletion.
- [x] Architecture and risk note is complete.
- [x] Completion audit maps every `PLAN.md` requirement to evidence.
