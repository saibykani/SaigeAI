"""Account roles: jobseeker (default), recruiter, admin. The super admin is the user whose email
equals SUPER_ADMIN_EMAIL; that account always has admin rights and alone can grant or revoke admin."""

from fastapi import Depends, HTTPException, status

from app.auth.deps import get_current_user
from app.config import get_settings

ROLES = ("jobseeker", "recruiter", "admin")
SIGNUP_ROLES = ("jobseeker", "recruiter")


def is_super_admin(user: dict) -> bool:
    email = (get_settings().super_admin_email or "").strip().lower()
    return bool(email) and (user.get("email") or "").lower() == email


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


async def require_recruiter(user: dict = Depends(get_current_user)) -> dict:
    if effective_role(user) not in ("recruiter", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Recruiter accounts only")
    return user
