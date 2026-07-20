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

The prototype uses PyMuPDF locally to read selectable text and source geometry from organizer-supplied synthetic PDFs. The hosted Vercel demo keeps that native parser authoritative and recovers raster-only fixtures in the renter's browser with pinned, self-hosted PDF.js and Tesseract.js assets. Browser OCR is candidate-only, ephemeral, confirmation-required, and never posts PDF bytes to an OCR service.

```bash
python3 -m pip install -e .
# macOS: brew install tesseract
# Linux: install your distribution's tesseract-ocr package with English data
python3 app.py
```

Open `http://127.0.0.1:8000`. To use a different local port:

```bash
REALDOOR_PORT=8001 python3 app.py
```

The app requires a renter acknowledgement before loading a supplied synthetic fixture. The demo selector loads matching fixture metadata; the browser renders raster pages at 300 DPI and runs one English Tesseract worker with PSM 6, then terminates it and clears page resources. The upload path SHA-256 checks selected bytes against `/api/fixture-manifest`, rejects arbitrary and real-renter files, and never posts the PDF to `/api/local-evidence` in the hosted flow. Unsupported browser OCR explicitly abstains rather than producing guessed fields or confidence.

Use **HH-003** for the happy path: its profile and calculation inputs have readable local evidence. Use HH-005 for expired evidence, HH-002 for a preserved pay-stub conflict, and HH-001 to demonstrate strict local OCR recovery followed by renter confirmation.

## Hosted Demo Boundary

The Vercel adapter is a hosted **synthetic-only** demo. It exposes read-only `/api/extraction-schema` and `/api/fixture-manifest` metadata endpoints; `/api/local-evidence` remains only for backward compatibility. The browser OCR fallback accepts only exact fixture hashes and never accepts real-renter files.

## Verify Before a Demo or Commit

```bash
python3 -m unittest discover -s starter/tests -v
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py
```

The project regression suite checks organizer checklist calculations, all supplied Q&A answers/citations, the submission contract, allowlisted native/OCR extraction fields, source boxes, the fixture-only benchmark and abstention behavior, adversarial safety boundaries, and ProofChain's cited review actions. Rehearse the user-facing sequence in `DEMO_PLAN.md`.

## What Is In This Repo
- Challenge plan and working norms.
- Starter pack docs, rules, governance, and evaluation assets.
- Synthetic documents and gold labels.
- Starter code, schemas, and tests.
- `app.py`, `realdoor/`, and `web/`: the local renter-facing prototype, deterministic rule service, visible local-PDF evidence extractor, and ProofChain evidence-traceability layer.
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

The local end-to-end implementation includes editable field-level evidence/confirmation with actual PDF source-box maps, a disclosed fixture benchmark, strict local OCR fallback with explicit abstention, a calculation-input recovery gate, ProofChain's cited evidence-to-packet path, cited frozen-rule math, readiness reasons that update after corrections, a printable renter-controlled case file, deletion, live safety checks, keyboard-accessible controls, and an optional public HUD LIHTC context view with explicit renter-selected filters and unknown availability. See `PROGRESS.md` for the current verification status before changing or demoing the app.
