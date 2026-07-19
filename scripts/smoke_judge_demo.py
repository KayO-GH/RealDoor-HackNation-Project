#!/usr/bin/env python3
"""Exercise a deployed RealDoor synthetic judge demo.

Usage: python scripts/smoke_judge_demo.py https://your-project.vercel.app
"""

from __future__ import annotations

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(base_url: str, path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, bytes]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request_object = Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request_object, timeout=20) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def require(status: int, expected: int, label: str) -> None:
    if status != expected:
        raise SystemExit(f"FAIL {label}: expected {expected}, got {status}")
    print(f"PASS {label}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/smoke_judge_demo.py https://your-project.vercel.app")
    base_url = sys.argv[1]
    status, _ = request(base_url, "/")
    require(status, 200, "root page")
    status, body = request(base_url, "/health")
    require(status, 200, "health endpoint")
    if json.loads(body)["mode"] != "synthetic_judge_demo":
        raise SystemExit("FAIL health endpoint: unexpected deployment mode")
    status, body = request(base_url, "/api/households")
    require(status, 200, "household list")
    households = json.loads(body)
    for summary in households:
        household_id = summary["household_id"]
        status, body = request(base_url, f"/api/households/{household_id}")
        require(status, 200, f"{household_id} payload")
        for document in json.loads(body)["documents"]:
            status, _ = request(base_url, document["preview_url"])
            require(status, 200, f"{document['file_name']} fixture")
            status, _ = request(base_url, document["preview_image_url"])
            require(status, 200, f"{document['file_name']} rendered page")
    status, _ = request(base_url, "/api/consent")
    require(status, 200, "consent endpoint")
    status, _ = request(base_url, "/api/ask", "POST", {"question": "What is the frozen 60% threshold?", "household": "HH-001"})
    require(status, 200, "rules question")
    status, _ = request(base_url, "/v1/households")
    require(status, 404, "v1 routes disabled")


if __name__ == "__main__":
    main()
