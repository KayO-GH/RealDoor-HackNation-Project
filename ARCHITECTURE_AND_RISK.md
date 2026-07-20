# RealDoor Architecture and Risk Note

## Architecture

RealDoor is a synthetic-only prototype. Its Python service remains authoritative for selectable PDF text and page geometry. In the hosted Vercel flow, only raster-abstained documents enter the browser fallback: PDF.js renders 300 DPI grayscale pages and one self-hosted Tesseract.js WebAssembly worker runs English PSM 6 OCR. The worker is terminated after the batch; canvases, object URLs, OCR text, and fields are not persisted. The browser interface owns transient session state: confirmation state, renter corrections, optional packet note, action log, and packet export.

The extraction adapter is deliberately narrow. It parses only typed allowlisted fields after known labels in the supplied synthetic document formats; the organizer gold labels are retained as a regression oracle, not as the runtime extraction source. OCR candidates require a recognized known label, strict label/value geometry, valid typed value, and at least 90% confidence on every used OCR token. Raster-only PDFs without a qualifying candidate, local Tesseract, or English data return an explicit abstention. The app does not claim general OCR accuracy, and it blocks confirmation if a material calculation input was not recovered from native text or strict local OCR evidence. Every public field is allowlisted; embedded instruction text is excluded and reported only as ignored untrusted content.

Income annualization is deterministic and uses explicit documented frequencies. The 60% threshold is selected only from the frozen FY 2026 Boston-Cambridge-Quincy table for household sizes 1-8. The product outputs a numerical comparison and readiness status, never eligibility or an approval/denial recommendation.

ProofChain is a deterministic traceability layer over that same contract. It shows the cited path from allowlisted evidence to renter confirmation, frozen-rule calculation, review checks, bounded next-evidence actions, and the renter-controlled packet. A correction marks affected results stale until reconfirmation; ProofChain never resolves a conflict, fills a gap, or makes a program decision.

## Data and retention boundary

- The demo accepts supplied synthetic documents only. A browser upload must be a byte-for-byte SHA-256 match to a locally installed organizer fixture; arbitrary and real-renter documents are rejected.
- Fixture-selector documents are read from the local repository. Browser uploads are SHA-256 checked locally against the fixture manifest; hosted PDF bytes are rendered and OCR'd in the active browser only. The legacy local-evidence endpoint remains available for compatibility but is not called by the hosted UI.
- No database, analytics, hosted model, or persistent session storage is used.
- The action log stores event type, timestamp, and frozen rule version—not raw document text or values.
- Session deletion clears browser-held profile, packet, selected files, and audit state. The app does not send packets to a provider.
- The optional Discover view uses only the organizer-provided HUD LIHTC subset. It labels availability as unknown, presents the complete unranked set by default, and applies only explicit renter-selected city or reported-bedroom views.

## Primary risks and controls

| Risk | Control |
| --- | --- |
| Eligibility or ranking overreach | Explicit UI boundary, refusal responses, deterministic readiness-only statuses, and regression tests. |
| Prompt injection in a document | Untrusted instruction text is excluded from the allowlist, never executed, and flagged as ignored. |
| Cross-applicant disclosure | One active browser session, no cross-household search, and a cited refusal response. |
| Wrong or stale rules | Frozen local FY 2026 corpus, source locator, authority, and effective-date display. |
| Untraceable extraction | Every displayed candidate field carries document ID, page, bounding box, confidence, purpose, confirmation state, and OCR token confidence where applicable. A visible fixture-only benchmark separates native text from OCR candidate coverage/exactness; ProofChain exposes the cited path into each material output. |
| Parser overclaim or silent fallback | The parser uses no gold value at runtime, uses OCR only with strict geometry and a 90% token gate, abstains on missing or unqualified evidence, and blocks confirmation when a material calculation input was not recovered. The frozen deterministic corpus remains separately identified as the challenge rule/checklist oracle. |
| Parser licensing before commercialization | This prototype uses PyMuPDF for local geometry extraction. Its AGPL/commercial-license model requires counsel and a production licensing decision before a closed-source commercial deployment. |
| Conflicting, expired, or unsupported evidence | Checklist-backed `NEEDS_REVIEW` reason codes; uncertain values are not silently resolved. |
| Sensitive retention | No raw document upload/storage, transient in-memory session, renter-initiated export, and deletion control. |
| Property-data overclaim | Availability, rents, waitlists, ownership procedures, and application status are always marked unknown; project views never rank or silently suppress records. |
| Accessibility failure | Semantic landmarks, labeled controls/errors, visible focus, keyboard-accessible controls, non-color status text, and ARIA live announcements. |

## Known prototype limits

This is a hackathon prototype, not a production eligibility system. It handles only the supplied single-metro/single-program simulation and exact fixture files. Before real-renter use it needs evaluated OCR/document understanding across representative populations and languages, secure storage, authentication, retention governance, consent/terms approval, monitoring, and qualified compliance review.
