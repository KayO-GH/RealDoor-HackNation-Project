# RealDoor Implementation Progress

## Status

**In progress — first verified implementation checkpoint complete.** This file is the implementation checklist for `PLAN.md`.

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

## In progress

- [ ] Final requirement-by-requirement audit against `PLAN.md` and the official brief.
- [ ] Commit and push the verified checkpoint to the `dev` branch.

## Remaining verification gates

- [x] Starter tests pass.
- [x] Gold/checklist/adversarial regression checks pass.
- [x] Browser smoke test proves consent, the happy path, correction, safety, and deletion.
- [x] Architecture and risk note is complete.
- [ ] Completion audit maps every `PLAN.md` requirement to evidence.
