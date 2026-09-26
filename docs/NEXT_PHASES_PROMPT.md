# Saige AI: prompt for the remaining phases

Paste the block below into Antigravity (or any coding agent), **one phase at a time**. Phase 6 is
done, so start with "Phase 7". After each phase, check the app locally, then send "Continue with the next phase".

---

## Master prompt (paste this first)

```
You are continuing development of Saige AI, a truthful AI career-automation platform.
The repo is at the workspace root. Before writing any code:

1. Read AGENTS.md (rules, stack, layout, commands, design system), docs/ARCHITECTURE.md
   and docs/DEPLOYMENT.md.
2. Skim backend/app/main.py, backend/app/database/collections.py,
   backend/app/automation/service.py, backend/app/profiles/sync_service.py,
   backend/app/services/{truth_guard,notify,agent_runs,audit}.py,
   frontend/components/app-shell.tsx, frontend/components/kpi.tsx,
   frontend/services/api.ts and frontend/types/api.ts, so you copy the existing patterns
   (routers per module, service layer, Pydantic models, user_id scoping on every query,
   useApi/request hooks on the frontend, PageHeader/Notice/Card components).
3. Run the backend tests (cd backend; .venv/Scripts/python -m pytest -q) to confirm a green baseline.

Hard rules (never break them):
- Never fabricate candidate data. Every generated claim goes through truth_guard.validate_claims.
- Never scrape or automate logins on LinkedIn/Naukri/Indeed and never store their passwords.
  Profile changes are copy-ready suggestions that the user applies and then marks as applied.
- Outward actions (apply, send email, message a recruiter) need user approval, respect
  automation.is_allowed() and the daily limits. Recruiter outreach is capped at 10 per day.
- Every query is scoped by user_id. New per-user collections go in collections.py AND USER_SCOPED.
- Keep the design: Graphite black default, Google Sans, glass cards, one solid accent per KPI
  card (tone prop), no pink/blue pastel or mixed gradients, and subtle motion.
- Write pytest tests for every backend module (mongomock-motor, see tests/conftest.py) and keep
  ruff clean (line length 150). Run npm run lint and npx tsc --noEmit on the frontend.
- Commit as saibykani07@gmail.com and push to main only when all tests pass.
- Update the NAV/UPCOMING arrays in app-shell.tsx, the Help & Docs page (frontend/app/(app)/help)
  and docs/*.md when a phase lands.

Work in small steps: first a plan for the phase, then backend (models, service, router, tests),
then frontend (types, page, nav), then docs. At the end, tell me what changed, how to test it,
and any Google, Vercel or Atlas setting I must change by hand.

Now do: <PHASE NAME FROM BELOW>
```

---

## Phase 6: Connected Profiles hub and daily profile-refresh scheduler (DONE; kept for reference)

**Goal:** give LinkedIn and Naukri a dedicated **"LinkedIn & Naukri"** section, separate from the
generic Integrations page. Add a scheduler that refreshes both profiles every day, truthfully.

Backend:
- `backend/app/scheduler/` (the package exists and is empty):
  - `service.py` with `run_due_jobs(db, now)`. For each user, read `AutomationSettings.schedules`
    (timezone defaults to Asia/Kolkata). Decide which daily jobs are due, then run them and record
    each run in `scheduler_jobs` (`user_id`, `job`, `run_date`, `status`, `result`, `started_at`,
    `finished_at`). There is a unique index on `(user_id, job, run_date)`, so a job never runs twice
    on the same day.
  - Daily jobs:
    - `profile_refresh`: runs inside `profile_optimization_window`. It calls the existing
      profile-sync agent (`profiles/sync_service`: the same logic as `POST /profile-sync/run`) for
      LinkedIn and Naukri, and creates pending `profile_changes`.
    - `naukri_freshness`: Naukri ranks recently updated profiles higher. If the Naukri snapshot's
      `last_updated_at` is more than 1 day old, create ONE rotating, truthful micro-edit suggestion.
      Rotate between resume headline wording, the order of key skills, and the summary's first line,
      each built only from verified profile data. Notify: "Your 2-minute Naukri refresh is ready".
    - `job_discovery`: sync followed ATS boards (`jobs/service`).
    - `gmail_sync`: only if Gmail is connected (`email/service`).
    - `followups`: flag applications whose follow-up is due on day 3, 7 or 14.
    - `morning_report`: creates a notification summarising what ran.
  - Respect `is_allowed()` for each capability, `paused_all`, and the new per-platform toggles below.
  - `router.py`:
    - `GET /api/cron/daily`, protected by the header `Authorization: Bearer ${CRON_SECRET}` (Vercel
      Cron sends it automatically when the `CRON_SECRET` env var is set). It runs `run_due_jobs` for
      all users in batches, and must finish in under 60 s on Vercel. Process at most N users per
      call and use a cursor if needed.
    - `POST /api/scheduler/run-now/{job}` lets the user trigger a job for themselves (rate limited).
    - `GET /api/scheduler/history?limit=30` returns the user's run history.
  - Add a `profile_schedule` block to `AutomationSettings`: `linkedin_enabled`, `naukri_enabled`,
    `refresh_time` ("08:00"), `days` (default: all), and `naukri_daily_freshness` (bool).
- `backend/vercel.json`: add `"crons": [{"path": "/api/cron/daily", "schedule": "30 2 * * *"}]`
  (08:00 IST). Vercel Hobby allows one run per day. Also document an external free cron (cron-job.org)
  for more frequent runs. Add `CRON_SECRET` to `config.py`, `.env.example` and `DEPLOYMENT.md`.
- Tests: due-time calculation across timezones, idempotency (running twice creates one change),
  pause respected, cron auth rejects a bad secret, and the Naukri freshness rotation never produces
  an unverified claim.

Frontend:
- New nav item "LinkedIn & Naukri" (`/profiles`, icon `Linkedin`/`UserRound`). Two big tabs or cards:
  - **LinkedIn**: snapshot form (headline, about, skills, experience, profile URL), a completeness
    score, pending suggestions with Copy / Mark applied / Edit / Reject, the history of applied changes,
    and a "Open LinkedIn edit page" deep link (https://www.linkedin.com/in/me/edit/intro/).
  - **Naukri**: same layout, plus a "Daily freshness" streak card (days in a row the profile was
    refreshed) and a deep link to https://www.naukri.com/mnjuser/profile.
  - A **Schedule** card: toggles per platform, time picker, days-of-week chips, timezone, and
    "Run now". Show a history timeline from `/scheduler/history`.
- Keep `/profile-sync` as the consistency and master-resume view, or merge it into `/profiles`
  and redirect.
- Show the scheduler's status on the Dashboard ("Next profile refresh 08:00 IST · last ran ✓").
- The Integrations page keeps only technical connectors (Gmail, Google, ATS boards, Calendar,
  Claude, the bookmarklet). Its LinkedIn/Naukri tiles link to `/profiles`.

---

## Phase 7: Recruiters and referral outreach (Uplers-style)

- Collections exist: `recruiters`, `recruiter_contacts`, `outreach`, `followups`.
- `backend/app/recruiters/`:
  - Contact discovery comes **only** from what the user adds (manual entry, CSV import, contacts
    found in imported Gmail messages from recruiters, and a job's posted contact email). No
    scraping, and no guessing emails from name patterns.
  - Company grouping, duplicate detection (email or LinkedIn URL), and tags (recruiter, hiring
    manager, referral, alumni).
  - Draft generator (templates, with optional Claude polish) for: referral request, cold email to
    recruiter, follow-up, and thank-you. Every draft goes through `truth_guard`. Personalise with the
    job, a verified skill match, and a mutual context the user provides.
  - An outreach state machine: `draft` → `approved` → `sent` (by the user via mailto/Gmail
    compose link or copy for LinkedIn, then "mark sent") → `replied` / `bounced` / `no_response` /
    `unsubscribed`. A daily cap of 10 is enforced server-side (`limits.daily_recruiter_contact_limit`),
    plus a per-company-domain cap of 3 per week. The first message to any contact needs explicit approval.
  - Follow-up engine: day 3, 7 and 14 (configurable), and it stops automatically on a reply
    (detected from Gmail ingest by thread or sender) or on an unsubscribe.
  - Endpoints: CRUD `/recruiters`, `/recruiters/import-csv`, `/outreach` (list, filter),
    `/outreach/draft`, `/outreach/{id}/approve|mark-sent|mark-replied|cancel`, and `/outreach/stats`.
- Frontend: `/recruiters` page with a contacts table, a company view, a "Find referral for this job"
  button on the job detail page (lists the contacts you have at that company and drafts the
  request), an outreach queue with daily-cap meter (x/10), and a follow-ups due list.
- Tests: cap enforcement, duplicate detection, the reply stopping follow-ups, and the truth guard on drafts.

---

## Phase 8: Analytics and notification centre

- `/analytics` page (Recharts, following the design rules: single axis, one accent per series,
  table view toggle), showing:
  - funnel over time;
  - response, interview and offer rate by **source** (ATS board, capture, manual, referral), by
    **role family**, and by **resume version** (which tailored resume performs best);
  - time-to-response distribution;
  - match score against outcome;
  - outreach reply rate;
  - profile-refresh streak and its correlation with recruiter views (user-entered numbers only);
  - weekly email digest content (in-app).
- Backend: `analytics/service.py` aggregation pipelines plus `/analytics/{breakdown}` endpoints,
  cached per user per day in `system_settings` or a new `analytics_cache` collection (add it to
  USER_SCOPED).
- Notification centre: a bell dropdown in `app-shell` header with an unread count, mark all read,
  and deep links. Use the existing `/notifications` API, and add `POST /notifications/read-all`.
  Add optional web push later.
- Remove "Analytics" from `UPCOMING`, and add it to NAV.

---

## Phase 9: Browser extension (Chrome MV3)

- `extension/` folder. The popup shows the match score for the current tab's job posting (sends
  the page text to `/api/jobs/import`, with the user's session through the site cookie, or a
  personal access token created at `/settings`). There is a "Save to Saige" button, a "Tailor
  resume" shortcut, and an autofill helper that **suggests** answers from `/applications/{id}`
  answers for the user to insert with one click. It never submits forms by itself.
- Backend: personal access tokens (hashed, scoped, revocable) in `integrations`, plus CORS for the
  `chrome-extension://` origin.
- Replaces the bookmarklet as the recommended capture method (keep the bookmarklet as a fallback).

---

## Phase 10: Hardening and launch

- Google OAuth verification: privacy policy page (`/privacy`), terms page (`/terms`), the app
  homepage, a domain you own, then submit for verification. The `gmail.readonly` scope is restricted
  and needs a security assessment (CASA) for public users. Until then, keep the app in **Testing**
  with up to 100 test users.
- Rate limiting on every write endpoint, and structured logging with request IDs.
- Sentry (frontend and backend), uptime check on `/api/health`, and daily Atlas backup.
- Accessibility pass (keyboard, focus rings, contrast in all themes), mobile layout pass, and
  Lighthouse ≥ 90.
- Playwright e2e: register → import resume → add job → tailor → application → mark applied.

---

## Current state (September 2026)

Phases 1–6 are shipped:
- auth and 30-day sessions;
- master profile filled from the resume;
- resumes, parsing, tailoring, ATS checks, cover letters and DOCX export;
- jobs: ATS boards, capture bookmarklet and 9-dimension matching;
- applications and interviews (.ics);
- Gmail read-only sync with automatic status updates;
- LinkedIn/Naukri copy-ready suggestions (`/profile-sync`);
- Dashboard with coloured KPIs;
- themes: Graphite, Obsidian, Aurora, Ember, Forest, Daylight;
- galaxy sign-in and a 3D loader;
- Help & Docs page;
- LinkedIn & Naukri hub (`/profiles`) with a daily scheduler (`/api/cron/daily`), a Naukri freshness
  streak, and run history.

There are 175 backend tests. Set `CRON_SECRET` in the backend Vercel project to enable the daily cron.

**Known manual setup:**
- Google Cloud → Google Auth Platform → **Audience → Test users**: add every Google account that
  should be able to sign in (for example saibykani07@gmail.com). Otherwise Google shows "Access
  blocked: has not completed the Google verification process".
- Enable the Gmail API, and add the `gmail.readonly` scope under **Data access**.
