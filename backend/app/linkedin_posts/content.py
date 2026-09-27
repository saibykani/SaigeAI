"""Daily LinkedIn post content: a rotating series built from the user's role and verified skills.

Posts share practical knowledge about the skills the user really has (from the verified profile) and
never claim results, employers or numbers that aren't in the profile. With an Anthropic key, Claude
writes the post from the same facts and the text is truth-checked; otherwise templates are used.
"""

import re

from app.schemas.profile import Profile

SERIES: dict[str, str] = {
    "tip": "Tip of the day", "mistake": "Common mistake", "checklist": "Checklist", "interview": "Interview question of the day",
    "tool": "Tool spotlight", "learned": "What I'm learning", "career": "Career note",
}

# Short, factual knowledge per skill (general best practice, not claims about the user).
KNOW: dict[str, dict[str, list[str]]] = {
    "selenium": {"tips": ["Prefer explicit waits over Thread.sleep: wait for the condition, not the clock.",
                          "Keep locators in page objects so one UI change is one code change.",
                          "Use data-testid attributes agreed with developers: stable, readable locators."],
                 "mistakes": ["Mixing implicit and explicit waits: timeouts stack and tests slow down unpredictably."]},
    "playwright": {"tips": ["Use auto-waiting locators (getByRole, getByTestId) instead of manual waits.",
                            "Turn on tracing for failed CI runs: the trace viewer shows every step, network call and DOM snapshot."],
                   "mistakes": ["Sharing one browser context across tests: state leaks and tests stop being independent."]},
    "api testing": {"tips": ["Test the contract, not just the status code: schema, headers and error bodies matter.",
                             "Cover idempotency: calling the same POST twice should not create two orders."],
                    "mistakes": ["Only testing happy paths: most production API bugs live in 4xx and edge cases."]},
    "rest assured": {"tips": ["Build a reusable RequestSpecification for base URI, auth and logging.",
                              "Validate JSON schema in one line with matchesJsonSchemaInClasspath."],
                     "mistakes": ["Hard-coding tokens in tests instead of fetching them in a setup step."]},
    "postman": {"tips": ["Run collections in CI with Newman and keep environments out of source control."],
                "mistakes": ["Chaining requests through global variables that other collections overwrite."]},
    "java": {"tips": ["Use AssertJ for readable assertions: assertThat(list).extracting(\"name\").contains(\"Asha\")."],
             "mistakes": ["Catching Exception in test code and hiding the real failure."]},
    "python": {"tips": ["pytest fixtures with the right scope make setup fast and tests independent."],
               "mistakes": ["Mutable default arguments in helpers: they're shared between calls."]},
    "jenkins": {"tips": ["Split long suites into parallel stages and publish JUnit reports so failures are one click away."],
                "mistakes": ["Re-running failed builds until green instead of fixing flaky tests."]},
    "ci/cd": {"tips": ["Fast smoke tests on every commit, full regression nightly: feedback in minutes, coverage every day."],
              "mistakes": ["Letting the pipeline stay red: people stop trusting it within a week."]},
    "jmeter": {"tips": ["Ramp users up gradually and watch latency percentiles (p95, p99), not just averages."],
               "mistakes": ["Load testing from a laptop on Wi-Fi: you measure your network, not the system."]},
    "sql": {"tips": ["Validate migrations with counts and checksums per table before and after."],
            "mistakes": ["Testing only with tiny datasets: query plans change at production scale."]},
    "testng": {"tips": ["Use groups (smoke, regression) and data providers to keep one suite flexible."]},
    "appium": {"tips": ["Run on a real device farm for release candidates; emulators miss real-world issues."]},
    "docker": {"tips": ["Spin up dependencies with docker compose so every tester gets the same environment."]},
    "kubernetes": {"tips": ["Test readiness and liveness probes: a pod that restarts silently is a bug."]},
}
GENERIC_TIPS = ["Write the test name as the behaviour: 'rejects expired card' beats 'test_card_3'.",
                "A flaky test is a bug: quarantine it, find the cause, fix it.",
                "Automate what's stable and repeated; explore what's new and risky."]
CHECKLISTS = {
    "default": ["Clear acceptance criteria before testing starts", "Happy path, edge cases and error states covered",
                "Test data ready and reset after each run", "Results reported where the team looks every day",
                "Flaky tests tracked, not ignored"],
}
INTERVIEW = ["How would you decide what to automate first in a new project?",
             "A test passes locally but fails in CI. How do you debug it?",
             "How do you measure the quality of a test suite?",
             "What makes an API test different from a UI test?"]


def _skills(profile: Profile) -> list[str]:
    return [s for s in profile.skills.all()][:20]


def _hashtags(profile: Profile, skill: str | None, n: int) -> list[str]:
    tags = []
    for s in [skill, profile.personal.current_designation, *_skills(profile)[:6], "Testing", "QualityEngineering", "Careers"]:
        if not s:
            continue
        t = "#" + re.sub(r"[^A-Za-z0-9]", "", s.title())
        if len(t) > 2 and t.lower() not in {x.lower() for x in tags}:
            tags.append(t)
    return tags[:n]


def pick(profile: Profile, day: int, series: list[str], topics: list[str]) -> tuple[str, str | None]:
    """The day's theme and the skill it's about (rotates through both)."""
    themes = [s for s in series if s in SERIES] or list(SERIES)
    theme = themes[day % len(themes)]
    pool = [t for t in topics if t.strip()] or _skills(profile) or ["Software testing"]
    return theme, pool[(day // len(themes) + day) % len(pool)]


def template_post(profile: Profile, day: int, theme: str, skill: str | None, *, disclaimer: str = "", hashtags: int = 5,
                  emojis: bool = True) -> dict:
    p = profile.personal
    key = (skill or "").lower()
    kb = KNOW.get(key, {})
    tips = kb.get("tips") or GENERIC_TIPS
    mistakes = kb.get("mistakes") or ["Automating unstable features first: the suite breaks before it pays off."]
    e = (lambda x: x) if emojis else (lambda x: "")
    who = f"{p.current_designation}" if p.current_designation else "QA professional"
    if theme == "tip":
        title = f"{skill}: one tip that saves hours"
        points = tips[:3]
        body = f"{e('💡 ')}{SERIES[theme]} · {skill}\n\n" + "\n".join(f"{e('→ ')}{t}" for t in points)
    elif theme == "mistake":
        title = f"A common {skill} mistake"
        points = [mistakes[day % len(mistakes)], "What to do instead: " + tips[day % len(tips)]]
        body = f"{e('⚠️ ')}{SERIES[theme]} · {skill}\n\n{points[0]}\n\n{e('✅ ')}{points[1]}"
    elif theme == "checklist":
        title = "My pre-release test checklist"
        points = CHECKLISTS["default"]
        body = f"{e('📋 ')}{SERIES[theme]}\n\n" + "\n".join(f"{e('☑️ ')}{x}" for x in points)
    elif theme == "interview":
        q = INTERVIEW[day % len(INTERVIEW)]
        title = "Interview question of the day"
        points = [q, "How I'd approach it: start from risk, keep it measurable, explain trade-offs."]
        body = f"{e('🎯 ')}{SERIES[theme]}\n\n“{q}”\n\n{points[1]}\n\nHow would you answer? {e('👇')}"
    elif theme == "tool":
        title = f"Tool spotlight: {skill}"
        points = tips[:2]
        body = f"{e('🛠️ ')}{SERIES[theme]} · {skill}\n\nWhy I keep using it as a {who}:\n" + "\n".join(f"{e('• ')}{t}" for t in points)
    elif theme == "learned":
        title = f"Learning in public: {skill}"
        points = [tips[-1], "Small, consistent practice beats weekend marathons."]
        body = f"{e('📚 ')}{SERIES[theme]}\n\nThis week I'm going deeper into {skill}.\n\n{e('→ ')}{points[0]}\n{e('→ ')}{points[1]}"
    else:
        yrs = f"{p.total_experience_years:g} years" if p.total_experience_years else "my years"
        title = "A career note"
        points = ["Quality is a team habit, not a phase at the end.", "Write bug reports developers want to read: steps, expected, actual, evidence."]
        body = f"{e('🌱 ')}{SERIES[theme]}\n\nWhat {yrs} as a {who} taught me:\n\n" + "\n".join(f"{e('→ ')}{x}" for x in points)
    tags = _hashtags(profile, skill, hashtags)
    text = body.strip() + "\n\n" + " ".join(tags)
    if disclaimer.strip():
        text += "\n\n" + disclaimer.strip()
    slides = [(title, [])] + [(f"{i + 1}", [pt]) for i, pt in enumerate(points)] + [("Follow for more", [f"{p.name or ''} · {who}"])]
    return {"theme": theme, "series": SERIES[theme], "skill": skill, "title": title, "text": text[:2900], "hashtags": tags,
            "points": points, "slides": slides}


async def write_post(profile: Profile, day: int, s) -> dict:
    """The day's post: Claude (truth-checked) when available, otherwise the template."""
    from app.agents.llm import get_provider
    from app.services.truth_guard import GeneratedClaims, validate_claims

    theme, skill = pick(profile, day, s.series, s.topics)
    base = template_post(profile, day, theme, skill, disclaimer=s.disclaimer, hashtags=s.hashtags, emojis=s.emojis)
    provider = get_provider()
    if provider is None or not hasattr(provider, "chat"):
        return {**base, "engine": "template"}
    facts = {"name": profile.personal.name, "role": profile.personal.current_designation,
             "years": profile.personal.total_experience_years, "skills": _skills(profile)}
    text = await provider.chat(
        system=("You write one LinkedIn post for a job seeker. Use only these verified facts about them: "
                f"{facts}. Never invent employers, numbers, results or projects. Share practical, accurate knowledge. "
                f"Tone: {s.tone}. 90-160 words, short lines, no markdown headings. Do not add hashtags."),
        messages=[{"role": "user", "content": f"Series: {SERIES[theme]}. Topic: {skill}. Key points you may use: {base['points']}"}])
    if not text:
        return {**base, "engine": "template"}
    check = validate_claims(GeneratedClaims(text=text), profile)
    if not check.passed:
        return {**base, "engine": "template"}
    full = text.strip() + "\n\n" + " ".join(base["hashtags"]) + (("\n\n" + s.disclaimer.strip()) if s.disclaimer.strip() else "")
    return {**base, "text": full[:2900], "engine": "claude"}
