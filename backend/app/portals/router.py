"""Hiring portals: how each one connects to Saige, and the user's profile link on each.

- "api" portals are fetched automatically through their public job APIs (Jobs for you).
- "alerts" portals (LinkedIn, Naukri, Indeed, ...) don't allow automated access. Saige lists their jobs
  from the job-alert emails they send to the user's Gmail, and the Chrome extension scores any
  posting the user opens there. Saige never logs into them or stores their passwords.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, HttpUrl

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.utils import new_id, utcnow

router = APIRouter(prefix="/integrations/portals", tags=["portals"])

PORTALS: list[dict] = [
    # Automatic (public job APIs / career pages)
    {"key": "himalayas", "name": "Himalayas", "method": "api", "region": "Global · filters by your country", "url": "https://himalayas.app/jobs"},
    {"key": "remotive", "name": "Remotive", "method": "api", "region": "Remote", "url": "https://remotive.com"},
    {"key": "jobicy", "name": "Jobicy", "method": "api", "region": "Remote", "url": "https://jobicy.com"},
    {"key": "arbeitnow", "name": "Arbeitnow", "method": "api", "region": "Europe · remote", "url": "https://www.arbeitnow.com"},
    {"key": "greenhouse", "name": "Greenhouse career pages", "method": "api", "region": "Company sites", "url": "https://www.greenhouse.com"},
    {"key": "lever", "name": "Lever career pages", "method": "api", "region": "Company sites", "url": "https://www.lever.co"},
    {"key": "ashby", "name": "Ashby career pages", "method": "api", "region": "Company sites", "url": "https://www.ashbyhq.com"},
    # Via job-alert emails + extension
    {"key": "linkedin", "name": "LinkedIn", "method": "alerts", "region": "Global", "url": "https://www.linkedin.com/jobs/",
     "alert_help": "On LinkedIn Jobs, search your role and location, then turn on 'Set alert'."},
    {"key": "naukri", "name": "Naukri", "method": "alerts", "region": "India", "url": "https://www.naukri.com/",
     "alert_help": "Naukri → Jobs → Job alerts → Create a job alert for your role and city."},
    {"key": "indeed", "name": "Indeed", "method": "alerts", "region": "Global", "url": "https://in.indeed.com/",
     "alert_help": "Search on Indeed and click 'Get new jobs for this search by email'."},
    {"key": "foundit", "name": "Foundit (Monster)", "method": "alerts", "region": "India · Gulf · SEA", "url": "https://www.foundit.in/",
     "alert_help": "Foundit → Job alerts → Create alert."},
    {"key": "glassdoor", "name": "Glassdoor", "method": "alerts", "region": "Global", "url": "https://www.glassdoor.co.in/Job/",
     "alert_help": "Search jobs and switch on 'Job alert'."},
    {"key": "instahyre", "name": "Instahyre", "method": "alerts", "region": "India", "url": "https://www.instahyre.com/",
     "alert_help": "Complete your profile; Instahyre emails matching opportunities."},
    {"key": "hirist", "name": "Hirist", "method": "alerts", "region": "India · tech", "url": "https://www.hirist.tech/",
     "alert_help": "Hirist → Job alerts."},
    {"key": "cutshort", "name": "Cutshort", "method": "alerts", "region": "India · tech", "url": "https://cutshort.io/",
     "alert_help": "Cutshort emails matches once your profile is complete."},
    {"key": "wellfound", "name": "Wellfound (AngelList)", "method": "alerts", "region": "Startups", "url": "https://wellfound.com/jobs",
     "alert_help": "Wellfound → Job preferences → email notifications."},
    {"key": "shine", "name": "Shine", "method": "alerts", "region": "India", "url": "https://www.shine.com/",
     "alert_help": "Shine → Job alerts."},
    {"key": "iimjobs", "name": "iimjobs", "method": "alerts", "region": "India · management", "url": "https://www.iimjobs.com/",
     "alert_help": "iimjobs → Job alerts."},
    {"key": "timesjobs", "name": "TimesJobs", "method": "alerts", "region": "India", "url": "https://www.timesjobs.com/",
     "alert_help": "TimesJobs → Job alerts."},
    {"key": "internshala", "name": "Internshala", "method": "alerts", "region": "India · freshers", "url": "https://internshala.com/",
     "alert_help": "Internshala → Preferences → email alerts."},
    {"key": "apna", "name": "apna", "method": "alerts", "region": "India", "url": "https://apna.co/",
     "alert_help": "apna sends job matches by email and in its app."},
]
KEYS = {p["key"] for p in PORTALS}


class PortalLinkIn(BaseModel):
    profile_url: HttpUrl | None = None
    alerts_on: bool = False
    note: str | None = Field(default=None, max_length=200)


@router.get("")
async def list_portals(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    links = {d["portal"]: d async for d in db[c.PORTAL_LINKS].find({"user_id": uid})}
    alerts: dict[str, int] = {}
    async for d in db[c.JOB_ALERTS].find({"user_id": uid}, {"portal": 1, "items": 1}):
        alerts[d.get("portal") or ""] = alerts.get(d.get("portal") or "", 0) + len(d.get("items", []))
    feed = await db[c.JOB_FEED].find_one({"_id": uid}, {"items.source": 1}) or {}
    from_api: dict[str, int] = {}
    for i in feed.get("items", []):
        from_api[i.get("source", "")] = from_api.get(i.get("source", ""), 0) + 1
    gmail = bool(await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail"}))
    out = []
    for p in PORTALS:
        link = links.get(p["key"], {})
        if p["method"] == "api":
            state = "connected"
        elif alerts.get(p["key"]):
            state = "receiving"
        elif link.get("alerts_on"):
            state = "waiting" if gmail else "needs_gmail"
        else:
            state = "setup"
        out.append({**p, "state": state, "jobs": from_api.get(p["key"], 0) + alerts.get(p["key"], 0),
                    "profile_url": link.get("profile_url"), "alerts_on": bool(link.get("alerts_on")), "note": link.get("note")})
    return {"gmail_connected": gmail, "portals": out}


@router.put("/{portal}")
async def save_portal(portal: str, body: PortalLinkIn, user: dict = Depends(get_current_user),
                      db: AsyncIOMotorDatabase = Depends(db_dep)):
    if portal not in KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown portal")
    await db[c.PORTAL_LINKS].update_one(
        {"user_id": user["_id"], "portal": portal},
        {"$set": {"profile_url": str(body.profile_url) if body.profile_url else None, "alerts_on": body.alerts_on,
                  "note": body.note, "updated_at": utcnow()},
         "$setOnInsert": {"_id": new_id(), "created_at": utcnow()}},
        upsert=True)
    return {"ok": True}
