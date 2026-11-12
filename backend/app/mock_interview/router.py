"""AI mock interview (/api/mock-interview): questions from the JD + verified profile, deterministic scoring, report.

Claude (optional) only rewrites/extends the question list; scoring and model-answer outlines are deterministic and
built from the candidate's own verified facts (truth guard), so nothing is invented about the candidate."""

from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.agents.llm import get_provider
from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.mock_interview import questions as qs
from app.mock_interview.scoring import model_outline, score_answer
from app.profiles.service import get_profile
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import new_id, utcnow

router = APIRouter(prefix="/mock-interview", tags=["mock-interview"])
KINDS = {"hr", "behavioural", "project", "experience", "skill", "gap", "technical"}


class StartIn(BaseModel):
    role: str = Field(default="", max_length=200)
    jd_text: str = Field(default="", max_length=30000)
    job_id: str | None = None
    application_id: str | None = None
    interview_type: Literal["hr", "technical", "behavioural", "mixed"] = "mixed"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    num_questions: int = Field(default=8, ge=5, le=15)
    language: Literal["en", "hi", "te", "ta", "kn", "ml"] = "en"
    persona: str = Field(default="priya", max_length=40)


class AnswerIn(BaseModel):
    index: int = Field(ge=0, le=20)
    text: str = Field(default="", max_length=8000)
    duration_s: int | None = Field(default=None, ge=0, le=3600)
    skipped: bool = False


class _LLMQuestion(BaseModel):
    text: str
    kind: str
    skill: str | None = None
    keywords: list[str] = []
    star: bool = False


class _LLMQuestions(BaseModel):
    questions: list[_LLMQuestion]


LANG_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "kn": "Kannada", "ml": "Malayalam"}


async def _llm_questions(ctx: dict, body: StartIn, base: list[dict]) -> list[dict] | None:
    provider = get_provider()
    if not provider:
        return None
    system = ("You are an interview coach. Write realistic interview questions. Only refer to projects, employers and skills "
              "listed as the candidate's own; for 'missing' skills ask how they would learn/approach them, never assume experience. "
              "Never state numbers about the candidate.")
    prompt = (f"Role: {ctx['role']}\nType: {body.interview_type}\nDifficulty: {body.difficulty}\nCount: {body.num_questions}\n"
              f"Language for question text: {LANG_NAMES[body.language]}\n"
              f"JD skills the candidate has: {', '.join(ctx['have']) or '-'}\nJD skills missing: {', '.join(ctx['miss']) or '-'}\n"
              f"Projects: {', '.join(ctx['projects']) or '-'}\nEmployers: {', '.join(f'{t} at {co}' for co, t in ctx['experience']) or '-'}\n"
              f"Draft questions (improve, keep the mix): {[q['text'] for q in base]}\n"
              "kind is one of hr, behavioural, project, experience, skill, gap, technical. keywords: 3-6 English keywords a good answer "
              "would mention. star=true for behavioural/project/experience.")
    out = await provider.extract(system=system, prompt=prompt, schema=_LLMQuestions)
    if not out or not out.questions:
        return None
    allowed_skills = {s.lower() for s in ctx["have"] + ctx["miss"]}
    res = []
    for q in out.questions[: body.num_questions]:
        kind = q.kind if q.kind in KINDS else "technical"
        skill = q.skill if q.skill and q.skill.lower() in allowed_skills else None
        if kind in {"skill", "gap"} and not skill:
            kind = "technical"
        res.append({"text": q.text.strip()[:600], "kind": kind, "skill": skill,
                    "keywords": [k.lower() for k in q.keywords[:6]], "star": bool(q.star)})
    return res if len(res) >= 5 else None


async def _job_source(db: AsyncIOMotorDatabase, uid: str, body: StartIn) -> tuple[str, str, list[str], str | None]:
    job_id = body.job_id
    if body.application_id:
        app_doc = await db[c.APPLICATIONS].find_one({"_id": body.application_id, "user_id": uid})
        if not app_doc:
            raise HTTPException(404, "Application not found")
        job_id = app_doc.get("job_id")
        if not job_id:
            return app_doc.get("role", ""), "", [], app_doc.get("company")
    if job_id:
        job = await db[c.JOBS].find_one({"_id": job_id, "user_id": uid})
        if not job:
            raise HTTPException(404, "Job not found")
        return job.get("title", ""), job.get("description") or "", job.get("skills") or [], job.get("company")
    return body.role, body.jd_text, [], None


def _public(doc: dict) -> dict:
    d = {k: v for k, v in doc.items() if k not in {"_id", "user_id"}}
    d["id"] = doc["_id"]
    return d


@router.post("/sessions", status_code=201)
async def start(body: StartIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    role, jd_text, jd_skills, company = await _job_source(db, uid, body)
    if not role.strip() and not jd_text.strip():
        raise HTTPException(422, "Give a role, a job description, or pick a saved job")
    profile = await get_profile(db, uid)
    async with agent_run(db, "mock_interview", uid, {"type": body.interview_type, "n": body.num_questions,
                                                     "language": body.language, "job_id": body.job_id}) as run:
        ctx = qs.context(profile, role.strip(), jd_text, jd_skills)
        base = qs.generate(ctx, body.interview_type, body.difficulty, body.num_questions)
        generated_by = "templates"
        llm = await _llm_questions(ctx, body, base)
        if llm:
            base, generated_by = llm, "claude"
        run.action(f"Generated {len(base)} questions ({generated_by})")
        now = utcnow()
        doc = {"_id": new_id(), "user_id": uid, "role": ctx["role"], "company": company, "job_id": body.job_id,
               "application_id": body.application_id, "interview_type": body.interview_type, "difficulty": body.difficulty,
               "language": body.language, "persona": body.persona, "generated_by": generated_by,
               "jd_skills": ctx["jd_skills"], "have": ctx["have"], "missing": ctx["miss"],
               "questions": [{**q, "index": i} for i, q in enumerate(base)], "answers": {}, "status": "in_progress",
               "report": None, "created_at": now, "updated_at": now}
        await db[c.MOCK_INTERVIEWS].insert_one(doc)
        run.output = {"session_id": doc["_id"], "questions": len(base)}
    await log_action(db, user_id=uid, action="mock_interview.start", entity="mock_interview", entity_id=doc["_id"],
                     details={"type": body.interview_type, "questions": len(base)})
    return _public(doc)


@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    out = []
    async for d in db[c.MOCK_INTERVIEWS].find({"user_id": user["_id"]}).sort("created_at", -1).limit(50):
        out.append({"id": d["_id"], "role": d["role"], "company": d.get("company"), "interview_type": d["interview_type"],
                    "status": d["status"], "questions": len(d["questions"]),
                    "score": (d.get("report") or {}).get("overall"), "created_at": d["created_at"]})
    return out


async def _get(db: AsyncIOMotorDatabase, uid: str, sid: str) -> dict:
    d = await db[c.MOCK_INTERVIEWS].find_one({"_id": sid, "user_id": uid})
    if not d:
        raise HTTPException(404, "Session not found")
    return d


@router.get("/sessions/{sid}")
async def get_session(sid: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return _public(await _get(db, user["_id"], sid))


@router.post("/sessions/{sid}/answer")
async def answer(sid: str, body: AnswerIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    d = await _get(db, user["_id"], sid)
    if body.index >= len(d["questions"]):
        raise HTTPException(422, "No such question")
    q = d["questions"][body.index]
    profile = await get_profile(db, user["_id"])
    result = score_answer(q, "" if body.skipped else body.text, qs.profile_skills(profile))
    entry = {"text": "" if body.skipped else body.text, "skipped": body.skipped, "duration_s": body.duration_s,
             **result, "outline": model_outline(q, profile), "answered_at": utcnow()}
    await db[c.MOCK_INTERVIEWS].update_one({"_id": sid}, {"$set": {f"answers.{body.index}": entry, "updated_at": utcnow()}})
    return entry


def build_report(d: dict) -> dict:
    answers = d.get("answers") or {}
    per_q, per_skill, dims = [], defaultdict(list), defaultdict(list)
    for q in d["questions"]:
        a = answers.get(str(q["index"]))
        s = a["score"] if a else 0
        per_q.append({"index": q["index"], "question": q["text"], "kind": q["kind"], "skill": q.get("skill"), "score": s,
                      "answered": bool(a and not a.get("skipped")), "feedback": (a or {}).get("feedback") or ["Not answered."],
                      "outline": (a or {}).get("outline") or [], "answer": (a or {}).get("text", "")})
        per_skill[q.get("skill") or {"hr": "Communication", "behavioural": "Behavioural (STAR)", "project": "Projects",
                                      "experience": "Experience", "technical": "Problem solving"}.get(q["kind"], "General")].append(s)
        for k, v in ((a or {}).get("breakdown") or {}).items():
            dims[k].append(v)
    overall = round(sum(x["score"] for x in per_q) / max(1, len(per_q)))
    dim_avg = {k: round(sum(v) / len(v)) for k, v in dims.items()}
    labels = {"relevance": "Answers stay on the question", "structure": "Clear STAR structure", "specifics": "Concrete specifics and tools",
              "length": "Good answer length", "fluency": "Few filler words"}
    tips = {"relevance": "Restate the question's key point in your first sentence.",
            "structure": "Use STAR: Situation, Task, Action, Result.",
            "specifics": "Name the tools you used and a verifiable result.",
            "length": "Aim for 1 to 2 minutes (60 to 250 words) per answer.",
            "fluency": "Replace filler words with a short pause."}
    ranked = sorted(dim_avg.items(), key=lambda kv: kv[1], reverse=True)
    strengths = [labels[k] for k, v in ranked if v >= 70][:3]
    improvements = [tips[k] for k, v in reversed(ranked) if v < 70][:3]
    skipped = sum(1 for x in per_q if not x["answered"])
    if skipped:
        improvements.append(f"{skipped} question{'s' if skipped > 1 else ''} skipped: practise those first.")
    if d.get("missing"):
        improvements.append(f"Prepare an honest learning plan for: {', '.join(d['missing'][:4])}.")
    return {"overall": overall, "dimensions": dim_avg,
            "skills": [{"skill": k, "score": round(sum(v) / len(v))} for k, v in per_skill.items()],
            "strengths": strengths or ["You completed the interview: keep practising to build fluency."],
            "improvements": improvements, "questions": per_q, "answered": len(per_q) - skipped}


@router.post("/sessions/{sid}/finish")
async def finish(sid: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    d = await _get(db, uid, sid)
    async with agent_run(db, "mock_interview_report", uid, {"session_id": sid}) as run:
        report = build_report(d)
        run.output = {"overall": report["overall"], "answered": report["answered"]}
        run.action(f"Scored {len(report['questions'])} answers")
    await db[c.MOCK_INTERVIEWS].update_one({"_id": sid}, {"$set": {"report": report, "status": "completed", "updated_at": utcnow()}})
    await log_action(db, user_id=uid, action="mock_interview.finish", entity="mock_interview", entity_id=sid,
                     details={"overall": report["overall"]})
    await notify(db, user_id=uid, kind="mock_interview", title=f"Mock interview scored {report['overall']}/100",
                 body=f"{d['role']}: {report['answered']} of {len(report['questions'])} answered.", link="/mock-interview")
    return report


@router.delete("/sessions/{sid}")
async def delete(sid: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await _get(db, user["_id"], sid)
    await db[c.MOCK_INTERVIEWS].delete_one({"_id": sid})
    await log_action(db, user_id=user["_id"], action="mock_interview.delete", entity="mock_interview", entity_id=sid)
    return {"ok": True}
