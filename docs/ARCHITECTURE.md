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
