"""Google Drive backup: every generated ATS resume is saved as a PDF in a "Saige AI Resumes" folder in the user's own Drive.
Uses the narrow drive.file scope (Saige can only see files it created). Best effort: never blocks resume generation."""

import json
import logging

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.email import gmail
from app.services import crypto
from app.utils import utcnow

logger = logging.getLogger("saige.drive")
FOLDER = "Saige AI Resumes"


def http_client() -> httpx.AsyncClient:
    """Factory (patched in tests)."""
    return httpx.AsyncClient(timeout=20)


async def drive_integration(db: AsyncIOMotorDatabase, uid: str) -> dict | None:
    integ = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail", "refresh_token_enc": {"$exists": True}})
    return integ if integ and gmail.DRIVE_SCOPE in (integ.get("scopes") or []) else None


async def _folder(client: httpx.AsyncClient, token: str, integ: dict, db: AsyncIOMotorDatabase) -> str:
    if integ.get("drive_folder_id"):
        return integ["drive_folder_id"]
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("https://www.googleapis.com/drive/v3/files", headers=h,
                          json={"name": FOLDER, "mimeType": "application/vnd.google-apps.folder"})
    r.raise_for_status()
    fid = r.json()["id"]
    await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"drive_folder_id": fid}})
    return fid


async def upload(db: AsyncIOMotorDatabase, uid: str, filename: str, data: bytes, mime: str = "application/pdf") -> str | None:
    """Returns the Drive file link, or None when Drive isn't connected / the upload failed."""
    integ = await drive_integration(db, uid)
    if not integ:
        return None
    try:
        token = await gmail.access_token(crypto.decrypt(integ["refresh_token_enc"]))
        async with http_client() as client:
            folder = await _folder(client, token, integ, db)
            boundary = "saigeboundary7f3a"
            meta = json.dumps({"name": filename, "parents": [folder]})
            body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{boundary}\r\n"
                    f"Content-Type: {mime}\r\n\r\n").encode() + data + f"\r\n--{boundary}--".encode()
            r = await client.post("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink",
                                  headers={"Authorization": f"Bearer {token}", "Content-Type": f"multipart/related; boundary={boundary}"},
                                  content=body)
            r.raise_for_status()
        await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"drive_last_upload_at": utcnow(), "drive_error": None}})
        return r.json().get("webViewLink")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Drive backup failed", extra={"user_id": uid, "error": str(exc)[:200]})
        await db[c.INTEGRATIONS].update_one({"_id": integ["_id"]}, {"$set": {"drive_error": str(exc)[:200]}})
        return None
