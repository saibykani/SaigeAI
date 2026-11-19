"""Account roles: jobseeker (default), recruiter, admin. The super admin is the user whose email
equals SUPER_ADMIN_EMAIL; that account always has admin rights and alone can grant or revoke admin."""

from fastapi import Depends, HTTPException, status

from app.auth.deps import get_current_user
from app.config import get_settings

ROLES = ("jobseeker", "recruiter", "admin")
SIGNUP_ROLES = ("jobseeker", "recruiter")


OWNER_EMAIL = "saibykani07@gmail.com"


def super_admin_emails() -> set[str]:
    """SUPER_ADMIN_EMAIL is a comma-separated list; the owner is always a super admin when the setting is unset."""
    raw = get_settings().super_admin_email
    emails = {e.strip().lower() for e in (raw or "").split(",") if e.strip()}
    return emails or {OWNER_EMAIL}


def is_super_admin(user: dict) -> bool:
    return (user.get("email") or "").strip().lower() in super_admin_emails()


def effective_role(user: dict) -> str:
    if is_super_admin(user):
        return "admin"
    role = user.get("role")
    return role if role in ROLES else "jobseeker"


def is_admin(user: dict) -> bool:
    return effective_role(user) == "admin"


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


async def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    if not is_super_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin only")
    return user


async def require_recruiter(user: dict = Depends(get_current_user)) -> dict:
    if effective_role(user) not in ("recruiter", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Recruiter accounts only")
    return user
