from datetime import date, datetime

from app.database import collections as c
from app.jobs.deadline import extract_deadline, remind


def test_extract_deadline_formats():
    today = date(2026, 11, 14)
    assert extract_deadline("Apply by 30 November 2026.", today) == date(2026, 11, 30)
    assert extract_deadline("Last date to apply: 05/12/2026", today) == date(2026, 12, 5)
    assert extract_deadline("Applications close on Dec 3", today) == date(2026, 12, 3)
    assert extract_deadline("Application deadline - 2026-12-10", today) == date(2026, 12, 10)
    assert extract_deadline("Closing date: 15th Jan", today) == date(2027, 1, 15)
    assert extract_deadline("We move fast and value ownership.", today) is None


async def test_remind_once_for_jobs_closing_soon(db, monkeypatch):
    sent = []

    async def fake_notify(db_, **kw):
        sent.append(kw["title"])

    monkeypatch.setattr("app.jobs.deadline.notify", fake_notify)
    await db[c.JOBS].insert_many([
        {"_id": "j1", "user_id": "u1", "title": "SDET", "company": "PayCo", "deadline": "2026-11-15", "status": "new"},
        {"_id": "j2", "user_id": "u1", "title": "QA", "company": "Acme", "deadline": "2026-12-30", "status": "new"},
        {"_id": "j3", "user_id": "u1", "title": "Lead", "company": "Done", "deadline": "2026-11-15", "status": "applied"},
    ])
    now = datetime(2026, 11, 14, 9, 0)
    assert await remind(db, "u1", now) == 1 and "tomorrow" in sent[0] and "PayCo" in sent[0]
    assert await remind(db, "u1", now) == 0  # already reminded today
