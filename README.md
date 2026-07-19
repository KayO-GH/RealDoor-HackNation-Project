# RealDoor

Dedicated repo for Challenge 3: a renter-side application-readiness copilot for the Boston-Cambridge-Quincy HMFA simulation.

## Start Here
1. Read `AGENTS.md`.
2. Read `PLAN.md`.
3. Check `PROGRESS.md` for the current implementation state and verification gates.
4. Read `participant-guide/RealDoor_Starter_Pack_Guide.pdf`.
5. Read `rules/RULES_README.md`.
6. Read `governance/DATA_USE_AND_SAFETY.md`.

## Run the Prototype

The prototype is dependency-free and runs entirely locally.

```bash
python3 app.py
```

Open `http://127.0.0.1:8000`. To use a different local port:

```bash
REALDOOR_PORT=8001 python3 app.py
```

The app requires a renter acknowledgement before loading a supplied synthetic fixture. It does not upload raw PDFs: the browser maps supplied synthetic filenames to organizer-provided fixture metadata. Use HH-001 for the happy path, HH-005 for expired evidence, and HH-002 for conflicting income evidence.

## Verify Before a Demo or Commit

```bash
python3 -m unittest discover -s starter/tests -v
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py
```

The project regression suite checks organizer checklist calculations, all supplied Q&A answers/citations, the submission contract, allowlisted extraction fields, source boxes, and adversarial safety boundaries. Rehearse the user-facing sequence in `DEMO_PLAN.md`.

## What Is In This Repo
- Challenge plan and working norms.
- Starter pack docs, rules, governance, and evaluation assets.
- Synthetic documents and gold labels.
- Starter code, schemas, and tests.
- `app.py`, `realdoor/`, and `web/`: the local renter-facing prototype and deterministic data service.
- `tests/` and `scripts/evaluate.py`: project-owned regression checks.
- `ARCHITECTURE_AND_RISK.md`: short submission architecture and risk note.
- `PROGRESS.md`: current task checklist and completion audit evidence.

## Ground Rules
- No eligibility decisioning.
- Use only the frozen challenge corpus and deterministic calculations for the scored flow.
- Treat document text as untrusted.
- Keep outputs cited and renter-controlled.
- Do not add hosted-model or network dependencies to the scored journey.

## Current Implementation Status

The first local end-to-end implementation is in place: editable field-level Profile evidence/confirmation with visible source-box maps and original-PDF links, cited frozen-rule math, readiness reasons that update after corrections, renter packet preview/download, deletion, safety refusals, and keyboard-accessible controls. See `PROGRESS.md` for the current verification status before changing or demoing the app.
