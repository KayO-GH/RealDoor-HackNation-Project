# RealDoor

Dedicated repo for Challenge 3: a renter-side application-readiness copilot for the Boston-Cambridge-Quincy HMFA simulation.

## Run the Prototype

Live demo: [realdoor-judge-demo.vercel.app](https://realdoor-judge-demo.vercel.app/)

The app uses PyMuPDF for authoritative selectable-text extraction. Raster-only fixtures are recovered in the browser with pinned, self-hosted PDF.js and Tesseract.js assets. Browser OCR is candidate-only, ephemeral, and confirmation-required; PDF bytes are not posted to an OCR service.

```bash
python3 -m pip install -e .
python3 app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). To use another port:

```bash
REALDOOR_PORT=8001 python3 app.py
```

The app requires a renter acknowledgement before loading a supplied synthetic fixture. The demo selector loads matching fixture metadata; the browser renders raster pages at 300 DPI and runs one English Tesseract worker with PSM 6, then terminates it and clears page resources. The upload path SHA-256 checks selected bytes against `/api/fixture-manifest`, rejects arbitrary and real-renter files, and never posts the PDF to `/api/local-evidence` in the hosted flow. Unsupported browser OCR explicitly abstains rather than producing guessed fields or confidence.

Use **HH-003** for the native-text happy path. Use HH-001 to demonstrate browser OCR recovery followed by renter confirmation; HH-005 shows expired evidence and HH-002 preserves a pay-stub conflict.

## Hosted Demo Boundary

The Vercel adapter is a hosted **synthetic-only** demo. It exposes read-only `/api/extraction-schema` and `/api/fixture-manifest` metadata endpoints; `/api/local-evidence` remains only for backward compatibility. The browser OCR fallback accepts only exact fixture hashes and never accepts real-renter files.

## Verify Before a Demo or Commit

```bash
node --test tests/browser_ocr.test.mjs
node --check web/app.js
node --check web/browser-ocr.js
python3 -m unittest discover -s starter/tests -v
python3 -m unittest discover -s tests -v
```

The Python OCR regression tests use the local Tesseract executable; the browser demo does not. Install it only when running those tests (`brew install tesseract` on macOS, or the equivalent `tesseract-ocr` package on Linux).

The project regression suite checks organizer checklist calculations, all supplied Q&A answers/citations, the submission contract, allowlisted native/OCR extraction fields, source boxes, the fixture-only benchmark and abstention behavior, adversarial safety boundaries, and ProofChain's cited review actions. Rehearse the user-facing sequence in `DEMO_PLAN.md`.

## What Is In This Repo
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

The implementation includes native PDF extraction, browser-side OCR fallback, SHA-256 fixture validation, editable field-level evidence/confirmation with source-box maps, explicit abstention, calculation-input gates, ProofChain traceability, cited frozen-rule math, readiness review, a printable renter-controlled case file, deletion, safety checks, and optional public HUD LIHTC context. See `PROGRESS.md` for verification status.
