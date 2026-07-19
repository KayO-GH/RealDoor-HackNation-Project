"""FastAPI application for the authenticated RealDoor v1 API."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

from .production import RealDoorV1, Settings


@lru_cache
def service() -> RealDoorV1:
    return RealDoorV1(Settings())


app = FastAPI(title="RealDoor v1 API", version="1.0.0", description="Renter-controlled LIHTC readiness; never eligibility decisioning.")
app.mount("/app", StaticFiles(directory="web/v1", html=True), name="v1-client")


def account(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication is required.")
    try:
        return service().account(authorization.removeprefix("Bearer "))
    except PermissionError as error:
        raise HTTPException(401, str(error)) from error


def fail(error: Exception) -> HTTPException:
    return HTTPException(400 if isinstance(error, ValueError) else 403, str(error))


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerify(BaseModel):
    token: str


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    authority_attested: bool


class FieldConfirmation(BaseModel):
    value: str = Field(min_length=1, max_length=500)


class ShareRequest(BaseModel):
    packet_id: str


class ShareAccess(BaseModel):
    access_code: str = Field(pattern=r"^\d{8}$")


@app.get("/health")
def health() -> dict[str, str]:
    settings = Settings()
    return {"status": "ok", "ai_mode": "enabled" if settings.openai_enabled and settings.openai_data_controls_approved else "review_only"}


@app.post("/v1/auth/magic-links", status_code=202)
def request_magic_link(body: MagicLinkRequest) -> dict[str, str]:
    token = service().issue_magic_link(str(body.email))
    # A mail provider sends this URL in production. It is returned only for local development.
    return {"message": "If the account exists, a sign-in link has been sent.", "development_token": token}


@app.post("/v1/auth/magic-links/verify")
def verify_magic_link(body: MagicLinkVerify) -> dict[str, str]:
    try:
        return service().verify_magic_link(body.token)
    except ValueError as error:
        raise HTTPException(401, str(error)) from error


@app.post("/v1/households")
def create_household(body: HouseholdCreate, account_id: str = Depends(account)) -> dict[str, str]:
    try:
        return service().household(account_id, body.name, body.authority_attested)
    except Exception as error:
        raise fail(error) from error


@app.post("/v1/households/{household_id}/documents")
async def upload_document(
    household_id: str,
    document_type: str = Form(),
    file: UploadFile = File(),
    account_id: str = Depends(account),
) -> dict:
    try:
        return service().upload(account_id, household_id, file.filename or "upload", file.content_type or "", document_type, await file.read())
    except Exception as error:
        raise fail(error) from error


@app.get("/v1/households/{household_id}/documents/{document_id}")
def get_document(household_id: str, document_id: str, account_id: str = Depends(account)) -> dict:
    try:
        return service().document(account_id, household_id, document_id)
    except Exception as error:
        raise fail(error) from error


@app.put("/v1/households/{household_id}/documents/{document_id}/fields/{field_id}")
def confirm_field(household_id: str, document_id: str, field_id: str, body: FieldConfirmation, account_id: str = Depends(account)) -> dict:
    try:
        return service().confirm_field(account_id, household_id, document_id, field_id, body.value)
    except Exception as error:
        raise fail(error) from error


@app.post("/v1/households/{household_id}/packets")
def create_packet(household_id: str, account_id: str = Depends(account)) -> dict:
    try:
        return service().packet(account_id, household_id)
    except Exception as error:
        raise fail(error) from error


@app.post("/v1/households/{household_id}/shares")
def create_share(household_id: str, body: ShareRequest, account_id: str = Depends(account)) -> dict:
    try:
        return service().share(account_id, household_id, body.packet_id)
    except Exception as error:
        raise fail(error) from error


@app.post("/v1/shares/{token}")
def view_share(token: str, body: ShareAccess) -> JSONResponse:
    try:
        return JSONResponse(service().public_packet(token, body.access_code), headers={"Cache-Control": "no-store"})
    except Exception as error:
        raise fail(error) from error


@app.delete("/v1/households/{household_id}/shares/{share_id}", status_code=204)
def revoke_share(household_id: str, share_id: str, account_id: str = Depends(account)) -> None:
    try:
        service().revoke_share(account_id, household_id, share_id)
    except Exception as error:
        raise fail(error) from error


@app.delete("/v1/account", status_code=204)
def delete_account(account_id: str = Depends(account)) -> None:
    service().delete_account(account_id)
