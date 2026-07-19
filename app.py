#!/usr/bin/env python3
"""Run the local RealDoor prototype: python3 app.py"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from realdoor.service import RealDoorService


ROOT = Path(__file__).parent.resolve()
SERVICE = RealDoorService(ROOT)
STATIC_ROOT = ROOT / "web"
DOCUMENT_ROOT = ROOT / "synthetic_documents" / "documents"


class AppHandler(BaseHTTPRequestHandler):
    server_version = "RealDoor/0.1"

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/households":
            return self._json(SERVICE.household_summaries())
        if parsed.path == "/api/properties":
            return self._json(SERVICE.property_context())
        if parsed.path.startswith("/api/households/"):
            if parsed.path.endswith("/local-evidence"):
                household_id = parsed.path.removesuffix("/local-evidence").rsplit("/", 1)[-1].upper()
                try:
                    return self._json(SERVICE.local_evidence_payload(household_id))
                except KeyError:
                    return self._json({"error": "Unknown synthetic household."}, HTTPStatus.NOT_FOUND)
            household_id = parsed.path.rsplit("/", 1)[-1].upper()
            try:
                return self._json(SERVICE.household_payload(household_id))
            except KeyError:
                return self._json({"error": "Unknown synthetic household."}, HTTPStatus.NOT_FOUND)
        if parsed.path == "/api/consent":
            return self._json(SERVICE.consent_payload())
        if parsed.path.startswith("/documents/"):
            return self._file(DOCUMENT_ROOT, parsed.path.removeprefix("/documents/"))
        if parsed.path.startswith("/rules/"):
            return self._file(ROOT / "rules", parsed.path.removeprefix("/rules/"))
        if parsed.path.startswith("/governance/"):
            return self._file(ROOT / "governance", parsed.path.removeprefix("/governance/"))
        if parsed.path == "/":
            return self._file(STATIC_ROOT, "index.html")
        return self._file(STATIC_ROOT, parsed.path.removeprefix("/"))

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/local-evidence":
            return self._local_evidence()
        if path != "/api/ask":
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4096:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError
            question = str(payload.get("question", ""))
            household = payload.get("household")
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return self._json({"error": "Send a short local question."}, HTTPStatus.BAD_REQUEST)
        if household is not None:
            if not isinstance(household, str):
                return self._json({"error": "Household must be a synthetic household ID."}, HTTPStatus.BAD_REQUEST)
            household = household.strip().upper() or None
        if household:
            try:
                SERVICE.household_payload(household)
            except KeyError:
                return self._json({"error": "Unknown synthetic household."}, HTTPStatus.NOT_FOUND)
        return self._json(SERVICE.safety_answer(question, household))

    def _local_evidence(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 2_000_000:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
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
            return self._json(SERVICE.uploaded_local_evidence_payload(decoded))
        except (ValueError, TypeError, UnicodeDecodeError):
            return self._json({"error": "Choose one to four exact supplied synthetic PDFs for one household."}, HTTPStatus.BAD_REQUEST)

    def _json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, base: Path, requested: str):
        candidate = (base / requested).resolve()
        if base not in candidate.parents and candidate != base:
            return self.send_error(HTTPStatus.NOT_FOUND)
        if not candidate.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):  # noqa: A003
        # Do not log URLs because prompts can contain sensitive text. Local startup only is logged.
        return


if __name__ == "__main__":
    address = ("127.0.0.1", int(os.environ.get("REALDOOR_PORT", "8000")))
    print(f"RealDoor local prototype: http://{address[0]}:{address[1]}")
    ThreadingHTTPServer(address, AppHandler).serve_forever()
