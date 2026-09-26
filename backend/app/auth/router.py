import logging
import secrets

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
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
    return await issue_session(db, user, response)


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
    code: str = Query(...), state: str = Query(...),
    saige_oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    s = get_settings()
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
