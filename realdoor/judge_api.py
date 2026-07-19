"""Public, synthetic-only API for the RealDoor judge demo.

This module deliberately does not import the v1 persistence, upload, or AI
services.  It is the only application entrypoint deployed to Vercel.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .service import RealDoorService


ROOT = Path(__file__).parents[1]
SERVICE = RealDoorService(ROOT)
app = FastAPI(
    title="RealDoor judge demo",
    version="1.0.0",
    description="Synthetic-document LIHTC readiness demo; never eligibility decisioning.",
)


class DemoQuestion(BaseModel):
    question: str = Field(max_length=4096)
    household: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "synthetic_judge_demo",
        "deployment_mode": os.environ.get("REALDOOR_DEPLOYMENT_MODE", "judge_demo"),
    }


@app.get("/api/households")
def households() -> list[dict]:
    return SERVICE.household_summaries()


@app.get("/api/households/{household_id}")
def household(household_id: str) -> dict:
    try:
        return SERVICE.household_payload(household_id.upper())
    except KeyError as error:
        raise HTTPException(404, "Unknown synthetic household.") from error


@app.get("/api/consent")
def consent() -> dict:
    return SERVICE.consent_payload()


@app.post("/api/ask")
def ask(body: DemoQuestion) -> JSONResponse:
    household_id = body.household.strip().upper() if body.household else None
    if household_id and household_id not in {item["household_id"] for item in SERVICE.household_summaries()}:
        raise HTTPException(404, "Unknown synthetic household.")
    return JSONResponse(SERVICE.safety_answer(body.question, household_id), headers={"Cache-Control": "no-store"})


# Vercel emits public/ as static output rather than placing it in /var/task.
# Mount it only for local runs, where the directory is available beside the app.
PUBLIC_ROOT = ROOT / "public"
if PUBLIC_ROOT.is_dir() and not os.environ.get("VERCEL"):
    app.mount("/", StaticFiles(directory=PUBLIC_ROOT, html=True), name="judge-client")
