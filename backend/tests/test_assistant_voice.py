"""Voice assistant: multilingual intents, translated deterministic replies, speakable output."""

import pytest

from app.agents import llm
from app.assistant import voice as v
from app.database import collections as c
from tests.job_fixtures import PROFILE


@pytest.mark.parametrize("text,intent", [
    ("Hey Saige, any new jobs?", "jobs"), ("कोई नई नौकरी है", "jobs"), ("కొత్త ఉద్యోగాలు ఉన్నాయా", "jobs"),
    ("புதிய வேலை இருக்கிறதா", "jobs"), ("ಹೊಸ ಉದ್ಯೋಗ ಇದೆಯೇ", "jobs"), ("പുതിയ ജോലി ഉണ്ടോ", "jobs"),
    ("मेरा अगला इंटरव्यू कब है", "interviews"), ("next interview?", "interviews"), ("ഇന്റർവ്യൂ എപ്പോൾ", "interviews"),
    ("मेरे आवेदन की स्थिति", "applications"), ("any replies today", "emails"), ("follow-ups due?", "followups"),
    ("resume tips", "profile"), ("help", "help"),
])
def test_detect_intent(text, intent):
    assert v.detect_intent(text) == intent


def test_speakable_strips_markdown():
    out = v.speakable("**Top** jobs:\n• A at B\n- C at D [x](http://e.com)")
    assert "*" not in out and "•" not in out and "http" not in out and "\n" not in out


async def test_voice_replies_in_language(client, auth, db):
    llm.set_provider(None)
    await client.put("/api/profile", headers=auth, json=PROFILE)
    uid = (await db[c.USERS].find_one({}))["_id"]
    await db[c.JOB_FEED].insert_one({"_id": uid, "items": [
        {"title": f"SDET {i}", "company": f"Co{i}", "score": 80} for i in range(5)]})
    for lang, word in [("en", "5 matching"), ("hi", "नौकरियाँ"), ("te", "ఉద్యోగాలు"), ("ta", "வேலைகள்"), ("kn", "ಉದ್ಯೋಗ"), ("ml", "ജോലി")]:
        r = await client.post("/api/assistant/chat", headers=auth, json={
            "messages": [{"role": "user", "content": "new jobs"}], "language": lang, "voice": True})
        reply = r.json()["reply"]
        assert word in reply and "SDET 0" in reply and "SDET 3" not in reply, (lang, reply)
    r = await client.post("/api/assistant/chat", headers=auth, json={
        "messages": [{"role": "user", "content": "इंटरव्यू"}], "language": "hi", "voice": True})
    assert "इंटरव्यू" in r.json()["reply"]


async def test_bad_language_rejected(client, auth):
    r = await client.post("/api/assistant/chat", headers=auth, json={"messages": [{"role": "user", "content": "hi"}], "language": "xx"})
    assert r.status_code == 422


class Fake:
    seen = ""

    async def chat(self, *, system, messages):
        Fake.seen = system
        return "**Ok** done"


async def test_claude_gets_language_and_voice_instruction(client, auth):
    llm.set_provider(Fake())
    try:
        r = await client.post("/api/assistant/chat", headers=auth, json={
            "messages": [{"role": "user", "content": "hi"}], "language": "ta", "voice": True})
        assert "Tamil" in Fake.seen and "spoken" in Fake.seen and r.json()["reply"] == "Ok done"
    finally:
        llm.set_provider(None)
