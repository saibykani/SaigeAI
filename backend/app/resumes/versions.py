"""Resume versions per company: which resume went to which company, and which versions got replies.

Built only from the user's own records: resumes (uploaded, tailored and ATS Studio versions), applications that
reference a resume, and recruiter emails linked to those applications."""

from collections import defaultdict

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.analytics.insights import REPLY_EMAILS
from app.analytics.service import INTERVIEW, RESPONSE, rate
from app.database import collections as c


async def by_company(db: AsyncIOMotorDatabase, uid: str) -> dict:
    resumes = {r["_id"]: r async for r in db[c.RESUMES].find({"user_id": uid, "status": {"$ne": "archived"}},
                                                             {"name": 1, "kind": 1, "company": 1, "created_at": 1, "job_id": 1})}
    apps = await db[c.APPLICATIONS].find({"user_id": uid, "resume_id": {"$ne": None}}).to_list(5000)
    job_ids = list({a.get("job_id") for a in apps if a.get("job_id")} | {r.get("job_id") for r in resumes.values() if r.get("job_id")})
    jobs = {j["_id"]: j async for j in db[c.JOBS].find({"_id": {"$in": job_ids}, "user_id": uid}, {"company": 1, "title": 1})}
    replied_by_mail = {e["application_id"] async for e in db[c.EMAILS].find(
        {"user_id": uid, "application_id": {"$in": [a["_id"] for a in apps]}, "category": {"$in": list(REPLY_EMAILS)}}, {"application_id": 1})}

    per_resume: dict[str, dict] = defaultdict(lambda: {"sent": 0, "replied": 0, "interviews": 0})
    companies: dict[str, dict] = {}
    for a in apps:
        rid = a["resume_id"]
        job = jobs.get(a.get("job_id")) or {}
        company = (job.get("company") or a.get("company") or "Unknown company").strip()
        sent = bool(a.get("applied_at"))
        replied = a.get("status") in RESPONSE or a["_id"] in replied_by_mail
        interviewed = a.get("status") in INTERVIEW
        st = per_resume[rid]
        st["sent"] += int(sent)
        st["replied"] += int(sent and replied)
        st["interviews"] += int(interviewed)
        co = companies.setdefault(company.lower(), {"company": company, "versions": {}})
        r = resumes.get(rid) or {}
        v = co["versions"].setdefault(rid, {"resume_id": rid, "name": r.get("name") or "Deleted resume", "kind": r.get("kind"),
                                            "applications": []})
        v["applications"].append({"application_id": a["_id"], "role": job.get("title") or a.get("role") or "",
                                  "status": a.get("status"), "sent": sent, "replied": replied,
                                  "applied_at": a["applied_at"].isoformat() if a.get("applied_at") else None})

    # Tailored versions made for a company but not sent yet still show up under that company.
    for rid, r in resumes.items():
        company = (r.get("company") or (jobs.get(r.get("job_id")) or {}).get("company") or "").strip()
        if not company:
            continue
        co = companies.setdefault(company.lower(), {"company": company, "versions": {}})
        co["versions"].setdefault(rid, {"resume_id": rid, "name": r.get("name") or "Resume", "kind": r.get("kind"), "applications": []})

    out_companies = []
    for co in companies.values():
        versions = list(co["versions"].values())
        for v in versions:
            s = per_resume.get(v["resume_id"], {"sent": 0, "replied": 0, "interviews": 0})
            v.update(sent=s["sent"], replied=s["replied"], reply_rate=rate(s["replied"], s["sent"]))
        sent = sum(1 for v in versions for x in v["applications"] if x["sent"])
        replied = sum(1 for v in versions for x in v["applications"] if x["sent"] and x["replied"])
        out_companies.append({"company": co["company"], "versions": sorted(versions, key=lambda v: -len(v["applications"])),
                              "sent": sent, "replied": replied})
    out_companies.sort(key=lambda c_: (-c_["sent"], c_["company"].lower()))

    leaderboard = []
    for rid, s in per_resume.items():
        if s["sent"]:
            r = resumes.get(rid) or {}
            leaderboard.append({"resume_id": rid, "name": r.get("name") or "Deleted resume", "kind": r.get("kind"), **s,
                                "reply_rate": rate(s["replied"], s["sent"])})
    leaderboard.sort(key=lambda x: (-(x["reply_rate"] or 0), -x["sent"]))
    best = next((x for x in leaderboard if x["sent"] >= 3), None)  # no "best" claim from fewer than 3 sends
    return {"companies": out_companies, "resumes": leaderboard, "best": best}
