# Architecture notes

## Backend module pattern

Each domain module under `backend/app/<module>/` has:

- `router.py`: HTTP layer only. It validates input, handles auth dependencies and shapes the
  response.
- `service.py`: business logic and database access.

`schemas/` holds the Pydantic request/response models. `services/` holds shared cross-cutting
logic: audit, notifications, rate limiting, the skills vocabulary and the truth guard.

## Source of truth

The **master candidate profile** (`candidate_profiles`) is the source of truth.

- **Resume import** (`POST /resumes/{id}/import-to-profile`) only *fills empty fields* and
  *adds new list entries*. It never overwrites a value the user has already verified. Conflicts
  are reported back as `skipped`.
- **External platforms** (LinkedIn, Naukri, from Phase 7) must go through the same rule. Every
  change is proposed with its before and after values and requires approval.

In Phase 1, the knowledge base sections (experience, projects, education, certifications) are
embedded in the profile document. They are always read and written together, and a single
document gives atomic updates. They can be split into the separate `candidate_*` collections
listed in the spec later if they need to be queried independently.

## Truthfulness guard

`services/truth_guard.validate_claims()` is the gate every generator must pass through.
Generators have to declare structured claims alongside their text:

- skills
- companies
- titles
- certifications
- projects
- education
- years of experience
- salary

The free text is scanned as well. It is checked for vocabulary skills the candidate hasn't
verified, for quantified metrics that don't appear verbatim in a verified achievement, and for
year counts that exceed verified experience. Any violation produces `VALIDATION FAILED`.

## Resume parsing

The parser (`resumes/parser.py`) is deterministic and heuristic: it detects sections, date
ranges, bullets and degree patterns. Every value it outputs is copied from the source text.
When it's unsure, it leaves the field empty and adds a warning, so the UI shows `UNKNOWN`.
An LLM-assisted parser may be added later, but its output must pass the truth guard against
the raw text.

## Job intelligence (Phase 2)

The pipeline is: import → JD analysis → duplicate check → match score → store.

**Where jobs come from.** Only these sources are used:

- JDs the user pastes. This works for any site, including LinkedIn and Naukri.
- Official, public ATS job-board APIs: Greenhouse, Lever and Ashby.

Request URLs are built from fixed hosts plus a validated board id, so there is no SSRF risk.
URLs from LinkedIn, Naukri, Indeed and similar sites are refused with instructions to paste the
JD instead. None of those sites is ever fetched.

**JD analysis** (`jobs/jd_parser.py`) is deterministic. It extracts:

- sections, and required vs. preferred skills
- experience range
- salary (LPA/INR and USD/EUR/GBP)
- work mode and employment type
- seniority, domains and degree
- notice period and visa sponsorship

**Optional Claude enrichment** (`agents/jd_agent.py`) runs only when `ANTHROPIC_API_KEY` is set.
Its output is untrusted, so only grounded values are kept: skills that appear in the JD text,
bullets that nearly quote the JD, and numbers present in the JD. Any failure falls back to the
deterministic result.

**Matching** (`jobs/matching.py`) scores these dimensions: skills, experience, role, domain,
location, salary, notice period, education and work authorization.

- Dimensions with missing data are UNKNOWN and are excluded from the weighted average.
- Weights are configurable per user.
- A concrete tool implies its umbrella skill for matching only (Rest Assured → API Testing).
  The truth guard stays strict.
- A JD with no recognizable skills is capped at 60, so it can't rank as a strong match.

**Duplicate detection** (`jobs/dedupe.py`) treats two jobs as the same when any of these hold:

- same source and external id
- same canonical URL
- same company, with a similar title, compatible location and description similarity
  (5-word shingle Jaccard)

Duplicates merge into one canonical job that keeps every source reference.

**Board sync** runs as a recorded agent run (`agent_runs`) and respects the
`job_discovery` pause. Postings are filtered by target role *before* the 200-per-sync cap.

## Automation safety

Every future agent or worker must call `automation.service.is_allowed(db, user_id, capability)`
before acting. `pause-all` blocks every capability at once.

The default mode is **conservative**: the AI discovers, analyzes and generates, and the user
approves everything.

## Scaling notes

- **Rate limiter:** in-process, so swap it for Redis when running more than one backend replica.
- **Resume file storage:** files are stored as BSON binary in `resume_files`, with a 5 MB cap
  (under the 16 MB document limit). Move them to GridFS or object storage if the limit needs
  to grow.
