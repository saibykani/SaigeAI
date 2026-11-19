# ruff: noqa: E501
"""Super admin analytics (/api/superadmin/*): executive overview, funnel, retention cohorts, feature adoption, breakdowns, live feed,
global search. Every endpoint takes a date range (`days`, or `date_from`/`date_to`) and returns only aggregates or event names."""

import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from app.auth.deps import db_dep
from app.auth.roles import effective_role
from app.database import collections as c
from app.superadmin import metrics as m
from app.utils import as_utc, utcnow

router = APIRouter()


def _rng(days: int = Query(30, ge=1, le=366), date_from: str = "", date_to: str = ""):
    return m.parse_range(days, date_from, date_to)


def _kpi(value, previous, series, unit: str = "") -> dict:
    return {"value": value, "previous": previous, "change_pct": m.change_pct(value, previous), "series": series, "unit": unit}


@router.get("/overview")
async def overview(rng=Depends(_rng), db=Depends(db_dep)):
    return await _overview(db, *rng)


async def _overview(db, start, end):
    ps, pe = m.previous_range(start, end)
    days, last, plast = m.day_list(start, end), (end - timedelta(microseconds=1)).date(), (start - timedelta(microseconds=1)).date()
    ud = await m.user_days(db, ps - timedelta(days=30), end)

    def window(day: date, n: int) -> int:
        return len(m.active_users(ud, day - timedelta(days=n - 1), day))

    sign = await m.daily_counts(db, c.USERS, "created_at", {}, start, end)
    base_total = await db[c.USERS].count_documents({"created_at": {"$lt": start}})
    running, total_series = base_total, []
    for d in days:
        running += sign.get(d, 0)
        total_series.append(running)
    signups, psignups = sum(sign.values()), await db[c.USERS].count_documents({"created_at": {"$gte": ps, "$lt": pe}})

    cohort, pcohort = await m.signup_cohort(db, start, end), await m.signup_cohort(db, ps, pe)
    act, pact = await m.activated_ids(db, cohort), await m.activated_ids(db, pcohort)
    by_day: dict[date, list[int]] = {}
    for uid, created in cohort.items():
        by_day.setdefault(created.date(), [0, 0])
        by_day[created.date()][0] += 1
        by_day[created.date()][1] += uid in act
    act_series = [m.pct(by_day[d][1], by_day[d][0]) or 0 if d in by_day else 0 for d in days]

    async def count_series(coll, field, match):
        d = await m.daily_counts(db, coll, field, match, start, end)
        return [d.get(x, 0) for x in days], sum(d.values()), await db[coll].count_documents({**match, field: {"$gte": ps, "$lt": pe}})

    apps_s, apps_n, apps_p = await count_series(c.APPLICATIONS, "applied_at", {})
    sent_s, sent_n, sent_p = await count_series(c.OUTREACH, "sent_at", {})
    runs_s, runs_n, runs_p = await count_series(c.AGENT_RUNS, "start_time", {})
    rep_s, rep_n, rep_p = await count_series(c.OUTREACH, "sent_at", {"status": "replied"})
    err_s, err_n, err_p = await count_series(c.AGENT_RUNS, "start_time", {"status": "failed"})
    reply_series = [m.pct(r, s) or 0 for r, s in zip(rep_s, sent_s, strict=True)]
    err_series = [m.pct(e, r) or 0 for e, r in zip(err_s, runs_s, strict=True)]

    dau = [window(d, 1) for d in days]
    kpis = {
        "total_users": _kpi(base_total + signups, base_total, total_series),
        "dau": _kpi(window(last, 1), window(plast, 1), dau),
        "wau": _kpi(window(last, 7), window(plast, 7), [window(d, 7) for d in days]),
        "mau": _kpi(window(last, 30), window(plast, 30), [window(d, 30) for d in days]),
        "signups": _kpi(signups, psignups, [sign.get(d, 0) for d in days]),
        "activation_rate": _kpi(m.pct(len(act), len(cohort)), m.pct(len(pact), len(pcohort)), act_series, "%"),
        "applications_sent": _kpi(apps_n, apps_p, apps_s),
        "emails_sent": _kpi(sent_n, sent_p, sent_s),
        "reply_rate": _kpi(m.pct(rep_n, sent_n), m.pct(rep_p, sent_p), reply_series, "%"),
        "agent_runs": _kpi(runs_n, runs_p, runs_s),
        "error_rate": _kpi(m.pct(err_n, runs_n), m.pct(err_p, runs_p), err_series, "%"),
    }
    series = [{"date": d.isoformat(), "signups": sign.get(d, 0), "active": dau[i]} for i, d in enumerate(days)]
    total = await db[c.USERS].count_documents({})
    return {"range": {"start": start.isoformat(), "end": end.isoformat()}, "kpis": kpis, "series": series,
            "totals": {"users": total, "disabled": await db[c.USERS].count_documents({"is_active": False}),
                       "resumes": await db[c.RESUMES].count_documents({}), "applications": await db[c.APPLICATIONS].count_documents({})}}


@router.get("/funnel")
async def funnel(rng=Depends(_rng), db=Depends(db_dep)):
    return {"stages": await m.funnel(db, *rng)}


@router.get("/cohorts")
async def cohorts(weeks: int = Query(8, ge=2, le=26), db=Depends(db_dep)):
    return {"weeks": await m.cohorts(db, weeks)}


@router.get("/features")
async def features(rng=Depends(_rng), db=Depends(db_dep)):
    start, end = rng
    days = m.day_list(start, end)
    ps, pe = m.previous_range(start, end)
    ud = await m.user_days(db, start, end)
    active_total = len({u for u, _ in ud})
    match = {"timestamp": {"$gte": start, "$lt": end}, "action": {"$not": m.NOT_ADMIN_ACTION}}
    rows = await db[c.AUDIT_LOGS].aggregate([
        {"$match": match},
        {"$group": {"_id": {"a": "$action", "d": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}}}, "n": {"$sum": 1},
                    "users": {"$addToSet": "$user_id"}}},
    ]).to_list(length=None)
    feats: dict[str, dict] = {}
    actions: dict[str, int] = {}
    for r in rows:
        name = m.feature_of(r["_id"]["a"])
        if name == "auth":
            continue
        f = feats.setdefault(name, {"name": name, "events": 0, "users": set(), "daily": {}})
        f["events"] += r["n"]
        f["users"] |= {u for u in r["users"] if u}
        f["daily"][r["_id"]["d"]] = f["daily"].get(r["_id"]["d"], 0) + r["n"]
        actions[r["_id"]["a"]] = actions.get(r["_id"]["a"], 0) + r["n"]
    prev = await db[c.AUDIT_LOGS].aggregate([
        {"$match": {"timestamp": {"$gte": ps, "$lt": pe}, "action": {"$not": m.NOT_ADMIN_ACTION}}},
        {"$group": {"_id": {"$arrayElemAt": [{"$split": ["$action", "."]}, 0]}, "n": {"$sum": 1}}},
    ]).to_list(length=None)
    prev_by = {r["_id"]: r["n"] for r in prev}
    out = [{"name": f["name"], "events": f["events"], "users": len(f["users"]), "adoption_pct": m.pct(len(f["users"]), active_total),
            "previous_events": prev_by.get(f["name"], 0), "series": [f["daily"].get(d.isoformat(), 0) for d in days]}
           for f in sorted(feats.values(), key=lambda x: -x["events"])[:14]]
    agents = await db[c.AGENT_RUNS].aggregate([
        {"$match": {"start_time": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$agent_name", "runs": {"$sum": 1}, "failed": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                    "users": {"$addToSet": "$user_id"}}}, {"$sort": {"runs": -1}}, {"$limit": 20},
    ]).to_list(length=None)
    return {"dates": [d.isoformat() for d in days], "active_users": active_total, "features": out,
            "top_actions": [{"name": k, "count": v} for k, v in sorted(actions.items(), key=lambda kv: -kv[1])[:40]],
            "agents": [{"name": a["_id"] or "unknown", "runs": a["runs"], "failed": a["failed"], "users": len([u for u in a["users"] if u])}
                       for a in agents]}


def _city(loc) -> str:
    return (str(loc).split(",")[0].strip().title() if loc else "") or ""


@router.get("/breakdowns")
async def breakdowns(rng=Depends(_rng), db=Depends(db_dep)):
    start, end = rng
    rng_match = {"created_at": {"$gte": start, "$lt": end}}

    async def top(coll, field, match, limit=10):
        rows = await db[coll].aggregate([
            {"$match": {**match, field: {"$nin": [None, ""]}}},
            {"$group": {"_id": {"$toLower": f"${field}"}, "label": {"$first": f"${field}"}, "n": {"$sum": 1}, "users": {"$addToSet": "$user_id"}}},
            {"$sort": {"n": -1}}, {"$limit": limit},
        ]).to_list(length=None)
        return [{"name": r["label"], "count": r["n"], "users": len(r["users"])} for r in rows]

    cities: dict[str, int] = {}
    unknown = 0
    async for p in db[c.CANDIDATE_PROFILES].find({}, {"personal.current_location": 1}):
        city = _city((p.get("personal") or {}).get("current_location"))
        if city:
            cities[city] = cities.get(city, 0) + 1
        else:
            unknown += 1
    logins = await db[c.AUDIT_LOGS].aggregate([
        {"$match": {"action": "auth.login", "timestamp": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": {"p": {"$ifNull": ["$details.platform", "unknown"]}, "os": {"$ifNull": ["$details.os", "unknown"]}},
                    "n": {"$sum": 1}, "users": {"$addToSet": "$user_id"}}},
    ]).to_list(length=None)
    plat: dict[str, dict] = {}
    osd: dict[str, int] = {}
    for r in logins:
        p = plat.setdefault(r["_id"]["p"], {"name": r["_id"]["p"], "logins": 0, "users": set()})
        p["logins"] += r["n"]
        p["users"] |= set(r["users"])
        osd[r["_id"]["os"]] = osd.get(r["_id"]["os"], 0) + r["n"]
    return {"companies": await top(c.APPLICATIONS, "company", rng_match), "roles": await top(c.APPLICATIONS, "role", rng_match),
            "geography": {"cities": [{"name": k, "count": v} for k, v in sorted(cities.items(), key=lambda kv: -kv[1])[:12]], "unknown": unknown},
            "platforms": [{"name": p["name"], "logins": p["logins"], "users": len(p["users"])} for p in plat.values()],
            "os": [{"name": k, "count": v} for k, v in sorted(osd.items(), key=lambda kv: -kv[1])]}


@router.get("/live")
async def live(limit: int = Query(30, ge=1, le=100), db=Depends(db_dep)):
    since = utcnow() - timedelta(days=7)
    ev = await db[c.AUDIT_LOGS].find({"timestamp": {"$gte": since}, "user_id": {"$ne": None}, "action": {"$not": m.NOT_ADMIN_ACTION}},
                                     {"user_id": 1, "action": 1, "timestamp": 1, "details.platform": 1}).sort("timestamp", -1).limit(limit).to_list(length=None)
    runs = await db[c.AGENT_RUNS].find({"start_time": {"$gte": since}}, {"user_id": 1, "agent_name": 1, "status": 1, "start_time": 1}) \
        .sort("start_time", -1).limit(limit).to_list(length=None)
    uids = list({e["user_id"] for e in ev} | {r["user_id"] for r in runs if r.get("user_id")})
    who = {u["_id"]: u for u in await db[c.USERS].find({"_id": {"$in": uids}}, {"email": 1, "name": 1}).to_list(length=None)}
    items = [{"at": as_utc(e["timestamp"]).isoformat(), "user_id": e["user_id"], "email": who.get(e["user_id"], {}).get("email", "deleted user"),
              "kind": "login" if e["action"].startswith("auth.login") else "event", "label": e["action"],
              "platform": (e.get("details") or {}).get("platform")} for e in ev]
    items += [{"at": as_utc(r["start_time"]).isoformat(), "user_id": r.get("user_id"), "email": who.get(r.get("user_id"), {}).get("email", "system"),
               "kind": "run", "label": f"{r.get('agent_name')} ({r.get('status')})", "platform": None} for r in runs]
    items.sort(key=lambda x: x["at"], reverse=True)
    return {"items": items[:limit]}


@router.get("/search")
async def search(q: str = Query("", max_length=120), db=Depends(db_dep)):
    if len(q.strip()) < 2:
        return {"users": []}
    rx = {"$regex": re.escape(q.strip()), "$options": "i"}
    rows = await db[c.USERS].find({"$or": [{"email": rx}, {"name": rx}]}, {"email": 1, "name": 1, "role": 1, "is_active": 1}).limit(8).to_list(length=None)
    return {"users": [{"id": u["_id"], "email": u["email"], "name": u.get("name", ""), "role": effective_role(u), "is_active": u.get("is_active", True)}
                      for u in rows]}
