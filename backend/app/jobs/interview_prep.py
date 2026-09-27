"""Interview prep for a job: likely technical questions from the JD's skills, behavioural questions
paired with the user's own achievements (for STAR answers), questions to ask, and research links.
Built only from the job description and the verified profile; nothing about the user is invented."""

import re
from urllib.parse import quote

from app.jobs.matching import candidate_skills
from app.schemas.job import JDAnalysis
from app.schemas.profile import Profile
from app.services.skills_vocab import canonical, normalize_key

TECH = {
    "selenium": ["How do you design a maintainable Selenium framework (Page Object Model, waits, reporting)?",
                 "How do you handle flaky tests caused by dynamic elements or timing?"],
    "playwright": ["Why choose Playwright over Selenium for a new project? What about auto-waits and tracing?"],
    "cypress": ["What can't Cypress do well, and how do you work around it?"],
    "rest assured": ["Walk through validating a REST API response (status, schema, headers) with Rest Assured."],
    "postman": ["How do you turn a Postman collection into an automated suite in CI?"],
    "api testing": ["How do you test an API for idempotency, pagination and error handling?"],
    "java": ["Explain the difference between an interface and an abstract class, with a test-code example."],
    "python": ["How do pytest fixtures work, and when would you use scope='session'?"],
    "jenkins": ["How do you run tests in parallel in a Jenkins pipeline and publish reports?"],
    "ci/cd": ["Where do automated tests sit in your CI/CD pipeline, and how do you keep it fast?"],
    "jmeter": ["How do you design a load test in JMeter and read throughput vs latency?"],
    "sql": ["Write a query to find duplicate records, and explain how you'd validate data after a migration."],
    "kubernetes": ["How would you run a test suite against services deployed on Kubernetes?"],
    "docker": ["How do you use Docker to make test environments reproducible?"],
    "testng": ["How do TestNG groups, priorities and data providers help organise a suite?"],
    "appium": ["How do you handle device fragmentation in mobile automation with Appium?"],
    "git": ["How do you review test code in pull requests?"],
    "agile": ["How do you plan testing inside a two-week sprint?"],
}
BEHAVIOURAL = [
    ("Tell me about a bug you found that others missed.", ("bug", "defect", "issue", "prod")),
    ("Describe a time you improved a process or reduced effort.", ("reduc", "improv", "automat", "faster", "%")),
    ("Tell me about a disagreement with a developer or manager and how you resolved it.", ("team", "collab", "stakeholder")),
    ("Describe a project you led end to end.", ("led", "built", "design", "own")),
    ("Tell me about a tight deadline and how you handled it.", ("release", "deadline", "deliver", "sprint")),
]
ASK = [
    "What does a typical release cycle look like, and where does testing fit in?",
    "How do you measure test quality today (coverage, escaped defects, flakiness)?",
    "What would success look like for this role in the first 90 days?",
    "What's the biggest quality challenge the team is facing right now?",
]


def build(profile: Profile, job: dict) -> dict:
    jd = JDAnalysis.model_validate(job.get("analysis") or {})
    have = candidate_skills(profile)
    skills = list(dict.fromkeys(jd.required_skills + jd.preferred_skills))[:10]
    technical = []
    for s in skills:
        key = canonical(s).lower()
        qs = TECH.get(key) or [f"How have you used {canonical(s)} in a real project? What went wrong and what did you learn?"]
        technical.append({"skill": canonical(s), "you_have_it": normalize_key(canonical(s)) in have, "questions": qs[:2]})
    wins = [a for e in profile.knowledge.experience for a in (e.achievements or [])] + \
           [r for e in profile.knowledge.experience for r in (e.responsibilities or [])][:10]
    behavioural = []
    for q, hints in BEHAVIOURAL:
        story = next((w for w in wins if any(h in w.lower() for h in hints)), None)
        behavioural.append({"question": q, "your_story": story,
                            "tip": "Answer with STAR: Situation, Task, Action, Result (use your real numbers)." if story
                            else "Pick a real example from your work; add it to your Profile achievements so Saige can suggest it."})
    company = job.get("company") or ""
    research = [
        {"label": "Company news", "url": f"https://www.google.com/search?q={quote(company + ' news')}&tbm=nws"},
        {"label": "Interview experiences (Glassdoor)",
         "url": "https://www.google.com/search?q=" + quote(f"{company} {job.get('title', '')} interview questions glassdoor")},
        {"label": "People at the company (LinkedIn)", "url": f"https://www.linkedin.com/search/results/people/?keywords={quote(company + ' QA')}"},
    ]
    gaps = [t["skill"] for t in technical if not t["you_have_it"]]
    return {"job": {"title": job.get("title"), "company": company}, "technical": technical, "behavioural": behavioural,
            "ask_them": ASK, "research": research,
            "prepare_first": gaps[:5],
            "pitch": _pitch(profile, job, [t["skill"] for t in technical if t["you_have_it"]][:3])}


def _pitch(profile: Profile, job: dict, strengths: list[str]) -> str:
    p = profile.personal
    yrs = f" with {p.total_experience_years:g} years of experience" if p.total_experience_years else ""
    base = f"I'm {p.name or 'a candidate'}, {('a ' + p.current_designation) if p.current_designation else 'working in QA'}{yrs}"
    if strengths:
        base += f", mostly in {', '.join(strengths)}"
    return re.sub(r"\s+", " ", base + f". I'm excited about the {job.get('title', 'role')} role at {job.get('company', 'your company')} "
                  "because it matches what I do best, and I'd love to bring that to your team.")
