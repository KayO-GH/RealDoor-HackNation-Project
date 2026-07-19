"""Vercel adapter for the synthetic-only RealDoor demo.

The local ``app.py`` server remains the offline implementation. This adapter
lets judges open the same prototype from a Vercel Function while preserving
the exact-fixture upload guard and avoiding persistent storage.
"""

from __future__ import annotations

import base64
from http import HTTPStatus
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file

from realdoor.service import RealDoorService


ROOT = Path(__file__).parents[1].resolve()
STATIC_ROOT = ROOT / "web"
DOCUMENT_ROOT = ROOT / "synthetic_documents" / "documents"
SERVICE = RealDoorService(ROOT)

app = Flask(__name__)


@app.after_request
def add_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


def _json(payload: dict | list, status: HTTPStatus = HTTPStatus.OK):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _file(base: Path, requested: str) -> Response:
    candidate = (base / requested).resolve()
    if base not in candidate.parents or not candidate.is_file():
        abort(HTTPStatus.NOT_FOUND)
    response = send_file(candidate, conditional=False)
    response.headers["Cache-Control"] = "no-store"
    return response


def _local_evidence():
    try:
        if request.content_length is None or not 1 <= request.content_length <= 2_000_000:
            raise ValueError
        payload = request.get_json(silent=False)
        uploads = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(uploads, list) or not 1 <= len(uploads) <= 4:
            raise ValueError
        decoded = []
        for upload in uploads:
            if not isinstance(upload, dict) or not isinstance(upload.get("file_name"), str) or not isinstance(upload.get("content_base64"), str):
                raise ValueError
            pdf_bytes = base64.b64decode(upload["content_base64"], validate=True)
            if not 1 <= len(pdf_bytes) <= 400_000:
                raise ValueError
            decoded.append({"file_name": upload["file_name"], "bytes": pdf_bytes})
        return _json(SERVICE.uploaded_local_evidence_payload(decoded))
    except (TypeError, ValueError):
        return _json({"error": "Choose one to four exact supplied synthetic PDFs for one household."}, HTTPStatus.BAD_REQUEST)


@app.route("/api", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/api/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/api/<path:path>", methods=["GET", "POST"])
def handler(path: str):
    """Dispatch the original path preserved by the Vercel catch-all route."""
    path = path.strip("/")
    if request.method == "POST":
        if path == "api/local-evidence":
            return _local_evidence()
        if path != "api/ask":
            abort(HTTPStatus.NOT_FOUND)
        try:
            if request.content_length is None or not 1 <= request.content_length <= 4096:
                raise ValueError
            payload = request.get_json(silent=False)
            if not isinstance(payload, dict):
                raise ValueError
            question = str(payload.get("question", ""))
            household = payload.get("household")
        except (TypeError, ValueError):
            return _json({"error": "Send a short synthetic-demo question."}, HTTPStatus.BAD_REQUEST)
        if household is not None:
            if not isinstance(household, str):
                return _json({"error": "Household must be a synthetic household ID."}, HTTPStatus.BAD_REQUEST)
            household = household.strip().upper() or None
        if household:
            try:
                SERVICE.household_payload(household)
            except KeyError:
                return _json({"error": "Unknown synthetic household."}, HTTPStatus.NOT_FOUND)
        return _json(SERVICE.safety_answer(question, household))

    if path == "api/households":
        return _json(SERVICE.household_summaries())
    if path == "api/properties":
        return _json(SERVICE.property_context())
    if path == "api/consent":
        return _json(SERVICE.consent_payload())
    if path.startswith("api/households/"):
        if path.endswith("/local-evidence"):
            household_id = path.removesuffix("/local-evidence").rsplit("/", 1)[-1].upper()
            try:
                return _json(SERVICE.local_evidence_payload(household_id))
            except KeyError:
                return _json({"error": "Unknown synthetic household."}, HTTPStatus.NOT_FOUND)
        household_id = path.rsplit("/", 1)[-1].upper()
        try:
            return _json(SERVICE.household_payload(household_id))
        except KeyError:
            return _json({"error": "Unknown synthetic household."}, HTTPStatus.NOT_FOUND)
    if path.startswith("documents/"):
        return _file(DOCUMENT_ROOT, path.removeprefix("documents/"))
    if path.startswith("rules/"):
        return _file(ROOT / "rules", path.removeprefix("rules/"))
    if path.startswith("governance/"):
        return _file(ROOT / "governance", path.removeprefix("governance/"))
    return _file(STATIC_ROOT, "index.html" if not path else path)
