# RealDoor Submission Plan

## Goal
Ship a strong, credible submission for Challenge 3: a renter-side copilot that turns synthetic housing documents into a human-confirmed profile, explains one affordable-housing program's rules with citations, identifies missing or expired documents, and prepares a renter-controlled application-readiness packet.

## What We Will Build
- A single end-to-end flow for the Boston-Cambridge-Quincy HMFA scenario.
- Document ingestion for the supplied synthetic PDFs.
- Allowlisted field extraction with page-level evidence boxes and confidence.
- A human-confirmed profile review that blocks downstream reuse until affected values are confirmed or corrected.
- Rule lookup against the frozen 2026 MTSP corpus.
- Deterministic income annualization and threshold comparison.
- Readiness output limited to `READY_TO_REVIEW` or `NEEDS_REVIEW`.
- An editable packet preview with missing/expired item flags, renter-controlled download, and no sending to a property or provider.
- Safety controls: refusal to decide eligibility, no hidden proxies, prompt-injection resistance, cross-applicant isolation, and deletion/export support.
- A keyboard-complete, WCAG 2.2 AA-oriented journey with labeled controls and errors, visible focus, non-color-only statuses, structured headings, and completion announcements.

## Available Resources
- The repository assets are the source of truth: `synthetic_documents/`, `rules/`, `evaluation/`, `starter/`, and `governance/`. They contain synthetic PDFs, gold labels, frozen rules, schemas, deterministic starter code, and tests.
- The build should work from the local repo and supplied assets first; no core step should depend on an external service being available during the demo.
- If a hosted model or API is used, it is an optimization layer only, not a hard dependency for the product flow.

## Development Environment
- Keep the prototype dependency-free where practical.
- If an isolated environment or third-party package becomes necessary, use `uv` to create and manage it; do not use a global package installation.
- Record any added dependency, its purpose, and its offline/demo fallback in the architecture and risk note.

## Credit Assumptions
- The plan assumes the team can use the hackathon credits associated with the chosen sponsor track when needed.
- Credits should be reserved for the steps that most improve demo quality: document extraction, cited rule answering, and any model-assisted summarization.
- The submission should still be understandable and testable if credits are constrained, expired, or unavailable.

## Build Order
1. Define and validate the application contracts before building UI:
   - Allowlisted fields and their purpose.
   - Typed field citations: document ID, page, bounding box, confidence, and confirmation state.
   - Typed rule citations: rule ID, authority, source URL/locator, and effective date.
   - Stable readiness reason codes and the submission schema.
2. Wire the local loaders, gold labels, frozen corpus, checklist, and deterministic calculation code.
3. Build extraction with source-box citations and a documented confidence policy. Ambiguous, low-confidence, malformed, or conflicting fields require review rather than silent reuse.
4. Build profile confirmation and correction. A corrected field must invalidate and recompute all dependent values; unconfirmed affected fields must block the calculation.
5. Build Understand with deterministic annualization, the 60% AMI threshold for household sizes 1-8, formula, confirmed inputs, authoritative citations, and effective date. If a rule or input is uncertain, abstain and explain what needs review.
6. Build Prepare with traceable missing/current/expired/conflicting evidence checks, an editable renter preview, download, and an explicit "not sent" state.
7. Build safety and privacy controls:
   - Show consent and the purpose of every extracted field.
   - Keep documents session-isolated; do not train on uploads or retain raw document text in logs.
   - Log actions and rule versions only; support renter export and verified session deletion.
   - Publish an in-app feature register listing every used field and purpose, plus explicit exclusions for protected traits, behavioral signals, and landlord-revenue features.
   - Treat document text as untrusted data; it cannot modify instructions, tools, rules, or data access.
8. Add accessibility checks and an automated evaluation harness before visual polish:
   - Keyboard-only completion of upload, review, calculation, packet editing/download, and deletion.
   - Gold extraction, Q&A, checklist, schema, and adversarial-fixture regression tests.
9. Write the short architecture and risk note, then rehearse the local/offline demo in `DEMO_PLAN.md`.

## Evidence and Readiness Rules
- Display each extracted value with its page-level evidence box, confidence, confirmation state, and correction control.
- Use confidence only as a documented evidence-quality signal; it must not score, rank, or determine a renter's eligibility.
- Cite every material claim. Field citations identify document evidence; rule citations identify authority, source location, and effective date; calculations cite their confirmed inputs, formula, threshold, and rule.
- Return `READY_TO_REVIEW` only when required evidence is present, current under the challenge's 60-day convention, internally consistent, and traceable to source boxes. Otherwise return `NEEDS_REVIEW` with stable reason codes.
- Never replace readiness and numeric comparison with an eligibility, approval, denial, priority, or acceptance prediction.

## Evaluation and Safety Gates
- Validate results against the supplied gold extraction records, `qa_gold.jsonl`, application checklists, and submission schema.
- Run the starter tests, plus a project-owned regression suite for all supplied adversarial fixtures.
- Cover at minimum: prompt injection, cross-applicant data requests, eligibility overreach, wrong-year rules, missing citations, expired evidence, conflicting totals, unsupported-trait inference, malformed boxes, household size outside 1-8, unsigned claims, and vacancy hallucination if property data is shown.
- Treat any eligibility label, cross-applicant disclosure, uncited material result, malformed citation, or failed deletion check as a release blocker.

## Demo
- Follow the rehearsal-ready script in `DEMO_PLAN.md`.
- Demonstrate the full required happy path, then concise expired/conflicting-evidence and safety checks.
- Run locally with no core dependency on network connectivity.

## Definition of Done
- The full Profile -> Understand -> Prepare flow works.
- Every material result has a correctly typed, readable citation.
- The app never makes an eligibility decision.
- Confirmed field changes invalidate and update dependent calculations and readiness output.
- The packet is previewable, editable, downloadable, renter-controlled, and never auto-sent.
- Consent, field-purpose disclosure, minimal retention, export, and verified deletion work end to end.
- The feature register shows all used fields/purposes and prohibited-feature exclusions.
- A keyboard-only journey completes all three stages with understandable errors and status announcements.
- The output matches the supplied schemas and passes the starter, gold, checklist, Q&A, and adversarial regression tests.
- A short architecture and risk note is included in the submission.
