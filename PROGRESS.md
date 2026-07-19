# RealDoor Implementation Progress

## Status

**Complete — final verified checkpoint pushed to `dev`.** This file is the implementation checklist for `PLAN.md`.

## Completed

- [x] Inspected the organizer assets, schemas, gold labels, frozen rules, checklists, and adversarial fixtures.
- [x] Chose a dependency-free local architecture so the core demo works offline.
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
- [x] Verified the supplied-PDF filename selection path and added visible page-coordinate source-box maps linked to the original synthetic PDFs.
- [x] Verified the renter-initiated packet-export action, packet preview, action-log entry, and "not sent" completion announcement.

## Completion Audit

| Requirement | Evidence |
| --- | --- |
| Profile: supplied synthetic documents, allowlisted fields, source boxes, confidence, correction, confirmation | `realdoor/service.py`, `web/app.js`, and browser checks of filename selection, visible source maps, inline corrections, and confirmation gating. |
| Understand: frozen 2026 corpus, deterministic calculation, threshold, formula, effective dates, citations, abstention | `realdoor/service.py`; checklist, Q&A, and schema checks in `tests/test_realdoor_service.py` and `scripts/evaluate.py`. |
| Prepare: missing/expired/conflicting reasons, preview, edit, download, delete, never auto-send | `web/app.js`; HH-005 browser correction test; packet-preview/export browser check; session-deletion browser check. |
| Safety/privacy: no decisioning, no proxies, consent, untrusted input, local retention/export/deletion | `realdoor/service.py`, `web/index.html`, `ARCHITECTURE_AND_RISK.md`, and all supplied adversarial-fixture checks. |
| Accessibility: keyboard-operable native controls, labels, focus styles, non-color status text, headings, live announcements | `web/index.html`, `web/styles.css`, and browser DOM checks of labelled/semantic controls. |
| Submission artifacts and teammate handoff | `README.md`, `DEMO_PLAN.md`, `ARCHITECTURE_AND_RISK.md`, `PLAN.md`, and this progress log. |

## Verified Commands

```bash
python3 -m py_compile app.py realdoor/service.py scripts/evaluate.py
node --check web/app.js
python3 -m unittest discover -s starter/tests -v
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py
```

All commands pass. The evaluator confirms six household calculations/readiness outputs, 36 gold Q&A answers with citations, six submission-contract payloads, and all 24 supplied adversarial fixtures.

## Remaining verification gates

- [x] Starter tests pass.
- [x] Gold/checklist/adversarial regression checks pass.
- [x] Browser smoke test proves consent, the happy path, correction, safety, and deletion.
- [x] Architecture and risk note is complete.
- [x] Completion audit maps every `PLAN.md` requirement to evidence.
