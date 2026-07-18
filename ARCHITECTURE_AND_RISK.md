# RealDoor Architecture and Risk Note

## Architecture

RealDoor is a dependency-free local prototype served from `app.py` on `127.0.0.1`. Its Python service reads only organizer-supplied synthetic fixture metadata, frozen rules, checklists, and the 2026 MTSP table. The browser interface owns the transient session state: confirmation state, renter corrections, optional packet note, action log, and packet export.

The extraction adapter is intentionally deterministic: for supplied synthetic files, it maps fixture names to organizer-provided gold fields and source boxes. It does not claim to be a general OCR system. Raw PDF contents are not parsed, uploaded, or logged. Every public field is allowlisted; embedded instruction text is excluded and reported only as ignored untrusted content.

Income annualization is deterministic and uses explicit documented frequencies. The 60% threshold is selected only from the frozen FY 2026 Boston-Cambridge-Quincy table for household sizes 1-8. The product outputs a numerical comparison and readiness status, never eligibility or an approval/denial recommendation.

## Data and retention boundary

- The demo accepts supplied synthetic documents only.
- Local filename matching happens in the browser; the files themselves are never sent to the server.
- No database, analytics, hosted model, or persistent session storage is used.
- The action log stores event type, timestamp, and frozen rule version—not raw document text or values.
- Session deletion clears browser-held profile, packet, selected files, and audit state. The app does not send packets to a provider.

## Primary risks and controls

| Risk | Control |
| --- | --- |
| Eligibility or ranking overreach | Explicit UI boundary, refusal responses, deterministic readiness-only statuses, and regression tests. |
| Prompt injection in a document | Untrusted instruction text is excluded from the allowlist, never executed, and flagged as ignored. |
| Cross-applicant disclosure | One active browser session, no cross-household search, and a cited refusal response. |
| Wrong or stale rules | Frozen local FY 2026 corpus, source locator, authority, and effective-date display. |
| Untraceable extraction | Every displayed field carries document ID, page, bounding box, confidence, purpose, and confirmation state. |
| Conflicting, expired, or unsupported evidence | Checklist-backed `NEEDS_REVIEW` reason codes; uncertain values are not silently resolved. |
| Sensitive retention | No raw document upload/storage, transient in-memory session, renter-initiated export, and deletion control. |
| Accessibility failure | Semantic landmarks, labeled controls/errors, visible focus, keyboard-accessible controls, non-color status text, and ARIA live announcements. |

## Known prototype limits

This is a hackathon prototype, not a production eligibility system. It handles only the supplied single-metro/single-program simulation and fixture files. Its deterministic fixture adapter must be replaced with validated extraction, secure storage, authentication, retention governance, and qualified compliance review before any real-renter use.
