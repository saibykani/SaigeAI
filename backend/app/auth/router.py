import logging
import secrets

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth import google
from app.auth.deps import db_dep, get_current_user, require_csrf_header
from app.auth.service import (
    REFRESH_COOKIE,
    authenticate,
    clear_refresh_cookie,
    create_user,
    issue_session,
    revoke_session,
    rotate_session,
    user_out,
)
from app.config import get_settings
from app.database import collections as c
from app.schemas.auth import (
    ConnectedAccount,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.audit import log_action
from app.services.rate_limit import auth_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE = "saige_oauth_state"


@router.post("/register", response_model=TokenResponse, status_code=201,
             dependencies=[Depends(auth_limiter.dependency("register"))])
async def register(body: RegisterRequest, response: Response,
                   db: AsyncIOMotorDatabase = Depends(db_dep)):
    user = await create_user(db, email=body.email, name=body.name, password=body.password)
    await seed_profile(db, user["_id"], body)
    return await issue_session(db, user, response)


async def seed_profile(db: AsyncIOMotorDatabase, uid: str, body: RegisterRequest) -> None:
    """Start the master profile with what the user typed at sign-up (their own statements)."""
    from app.profiles.service import update_profile
    from app.schemas.profile import ProfileUpdate

    extras = (body.phone, body.current_designation, body.total_experience_years, body.target_role, body.current_location,
              body.country, body.notice_period_days, body.linkedin_url)
    if all(v in (None, "") for v in extras):
        return
    personal = {k: v for k, v in {"name": body.name, "email": body.email, "phone": body.phone,
                                  "current_designation": body.current_designation,
                                  "total_experience_years": body.total_experience_years,
                                  "current_location": body.current_location, "country": body.country,
                                  "notice_period_days": body.notice_period_days}.items() if v not in (None, "")}
    patch: dict = {"personal": personal}
    if body.target_role:
        patch["preferences"] = {"target_roles": [r.strip() for r in body.target_role.split(",") if r.strip()][:5]}
    if body.current_location:
        patch.setdefault("preferences", {})["preferred_locations"] = [body.current_location]
    if body.linkedin_url:
        personal["linkedin_url"] = body.linkedin_url
    try:
        await update_profile(db, uid, ProfileUpdate.model_validate(patch), source="signup")
    except Exception:  # noqa: BLE001, S110 - sign-up must succeed even if a detail is rejected
        pass


@router.post("/login", response_model=TokenResponse,
             dependencies=[Depends(auth_limiter.dependency("login"))])
async def login(body: LoginRequest, response: Response, db: AsyncIOMotorDatabase = Depends(db_dep)):
    user = await authenticate(db, body.email, body.password)
    await log_action(db, user_id=user["_id"], action="auth.login", entity="user",
                     entity_id=user["_id"], details={"provider": "password"})
    return await issue_session(db, user, response)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(require_csrf_header)])
async def refresh(response: Response, db: AsyncIOMotorDatabase = Depends(db_dep),
                  saige_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE)):
    try:
        return await rotate_session(db, saige_refresh, response)
    except HTTPException:
        clear_refresh_cookie(response)
        raise


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_header)])
async def logout(response: Response, db: AsyncIOMotorDatabase = Depends(db_dep),
                 saige_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE)):
    await revoke_session(db, saige_refresh)
    clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return user_out(user)


@router.get("/connections", response_model=list[ConnectedAccount])
async def connections(user: dict = Depends(get_current_user)):
    """Connected external accounts. Gmail / LinkedIn / Naukri connectors land in later phases;
    credentials for those platforms are never stored - only OAuth grants where officially offered."""
    return [
        ConnectedAccount(provider="google", connected=bool(user.get("google_sub")),
                         scopes=google.SIGNIN_SCOPES if user.get("google_sub") else [],
                         status="connected" if user.get("google_sub") else "not_connected"),
        ConnectedAccount(provider="gmail", connected=False, status="planned_phase_5"),
        ConnectedAccount(provider="linkedin", connected=False, status="planned_phase_7"),
        ConnectedAccount(provider="naukri", connected=False, status="planned_phase_7"),
    ]


# ---------------------------------------------------------------- Google OAuth

@router.get("/google/authorize")
async def google_authorize():
    s = get_settings()
    if not s.google_oauth_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured")
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(google.authorization_url(state), status_code=302)
    resp.set_cookie(OAUTH_STATE_COOKIE, state, max_age=600, httponly=True,
                    secure=s.cookie_secure, samesite="lax", path="/api/auth/google")
    return resp


@router.get("/google/callback")
async def google_callback(
    code: str | None = None, state: str | None = None, error: str | None = None,
    saige_oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
    saige_gmail_link: str | None = Cookie(default=None, alias="saige_gmail_link"),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    s = get_settings()
    if error or not code or not state:
        # Google sends ?error=access_denied when the user cancels or the account isn't an approved tester.
        target = "/integrations?gmail=error" if saige_gmail_link and not saige_oauth_state else "/login?error=google_denied"
        return RedirectResponse(f"{s.frontend_url}{target}", status_code=302)
    if saige_gmail_link and not saige_oauth_state:
        from app.email.router import complete_gmail_link
        return await complete_gmail_link(db, code, state, saige_gmail_link)
    fail = RedirectResponse(f"{s.frontend_url}/login?error=google", status_code=302)
    if not s.google_oauth_enabled or not saige_oauth_state or \
            not secrets.compare_digest(state, saige_oauth_state):
        return fail
    try:
        info = await google.exchange_code(code)
    except (httpx.HTTPError, KeyError):
        logger.warning("Google code exchange failed")
        return fail
    if not info.get("email") or not info.get("email_verified"):
        return fail

    user = await db[c.USERS].find_one({"google_sub": info["sub"]})
    if not user:
        existing = await db[c.USERS].find_one({"email": info["email"].lower()})
        if existing:
            # Link only because Google asserts the email is verified.
            await db[c.USERS].update_one({"_id": existing["_id"]},
                                         {"$set": {"google_sub": info["sub"]}})
            user = {**existing, "google_sub": info["sub"]}
        else:
            user = await create_user(db, email=info["email"], name=info.get("name") or "",
                                     google_sub=info["sub"])
    await log_action(db, user_id=user["_id"], action="auth.login", entity="user",
                     entity_id=user["_id"], details={"provider": "google"})
    resp = RedirectResponse(f"{s.frontend_url}/auth/callback", status_code=302)
    await issue_session(db, user, resp)  # sets refresh cookie; frontend then calls /refresh
    resp.delete_cookie(OAUTH_STATE_COOKIE, path="/api/auth/google")
    return resp
