# RealDoor Architecture and Risk Note

## Architecture

RealDoor is a local prototype served from `app.py` on `127.0.0.1`. Its Python service reads only organizer-supplied synthetic fixtures, frozen rules, checklists, and the 2026 MTSP table. PyMuPDF runs locally to extract selectable text and page geometry from the supplied PDFs. The browser interface owns the transient session state: confirmation state, renter corrections, optional packet note, action log, and packet export.

The extraction adapter is deliberately narrow. It parses only typed allowlisted fields after known labels in the supplied synthetic document formats; the organizer gold labels are retained as a regression oracle, not as the runtime extraction source. Raster-only PDFs or unrecognized label/value pairs return an explicit abstention. The app does not claim general OCR accuracy, and it blocks confirmation if a material calculation input was not recovered from readable local evidence. Every public field is allowlisted; embedded instruction text is excluded and reported only as ignored untrusted content.

Income annualization is deterministic and uses explicit documented frequencies. The 60% threshold is selected only from the frozen FY 2026 Boston-Cambridge-Quincy table for household sizes 1-8. The product outputs a numerical comparison and readiness status, never eligibility or an approval/denial recommendation.

ProofChain is a deterministic traceability layer over that same contract. It shows the cited path from allowlisted evidence to renter confirmation, frozen-rule calculation, review checks, bounded next-evidence actions, and the renter-controlled packet. A correction marks affected results stale until reconfirmation; ProofChain never resolves a conflict, fills a gap, or makes a program decision.

## Data and retention boundary

- The demo accepts supplied synthetic documents only. A browser upload must be a byte-for-byte SHA-256 match to a locally installed organizer fixture; arbitrary and real-renter documents are rejected.
- Fixture-selector documents are read from the local repository. Accepted browser-upload bytes travel only to the loopback server, are parsed in process memory, and are discarded after the JSON evidence response. They are not written, logged, or sent to a provider.
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
| Untraceable extraction | Every displayed candidate field carries document ID, page, bounding box, confidence, purpose, and confirmation state. A visible fixture-only benchmark reports coverage, exactness when extracted, and raster abstentions; ProofChain exposes the cited path into each material output. |
| Parser overclaim or silent fallback | The parser uses no gold value at runtime, abstains on raster/missing evidence, and blocks confirmation when a material calculation input was not recovered. The frozen deterministic corpus remains separately identified as the challenge rule/checklist oracle. |
| Parser licensing before commercialization | This prototype uses PyMuPDF for local geometry extraction. Its AGPL/commercial-license model requires counsel and a production licensing decision before a closed-source commercial deployment. |
| Conflicting, expired, or unsupported evidence | Checklist-backed `NEEDS_REVIEW` reason codes; uncertain values are not silently resolved. |
| Sensitive retention | No raw document upload/storage, transient in-memory session, renter-initiated export, and deletion control. |
| Property-data overclaim | Availability, rents, waitlists, ownership procedures, and application status are always marked unknown; project views never rank or silently suppress records. |
| Accessibility failure | Semantic landmarks, labeled controls/errors, visible focus, keyboard-accessible controls, non-color status text, and ARIA live announcements. |

## Known prototype limits

This is a hackathon prototype, not a production eligibility system. It handles only the supplied single-metro/single-program simulation and exact fixture files. Before real-renter use it needs evaluated OCR/document understanding across representative populations and languages, secure storage, authentication, retention governance, consent/terms approval, monitoring, and qualified compliance review.
