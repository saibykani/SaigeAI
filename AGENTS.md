# Saige AI: agent guide

These are the rules and project context for any AI coding agent (Antigravity, Claude Code, Cursor, and others)
working in this repo. Read this file before you change anything.

## What Saige AI is

Saige AI is a truthful AI career-automation platform for one candidate at a time. It covers job discovery,
JD analysis and matching, tailored resumes and cover letters, application tracking, Gmail monitoring,
LinkedIn/Naukri profile optimisation, recruiter and referral outreach, a daily scheduler, and analytics.

- Live: frontend https://saige-ai.vercel.app, backend https://saige-ai-api.vercel.app
- Repo: https://github.com/saibykani/SaigeAI (branch `main`)
- Database: MongoDB Atlas (`saige_ai` database)

## Non-negotiable product rules

1. **Never fabricate candidate information.** Every generated claim (skill, tool, metric, title,
   employer, degree) must pass `backend/app/services/truth_guard.py::validate_claims` against the
   verified master profile. Unknown values stay `UNKNOWN`. Never invent numbers.
2. **Never bypass platform security.** Do not scrape LinkedIn, Naukri or Indeed, do not automate
   their logins, and do not store their passwords. Use official APIs, OAuth, public ATS APIs
   (Greenhouse, Lever, Ashby) or the user's own clicks (the bookmarklet in `/jobs/capture`). LinkedIn
   and Naukri offer no public profile-edit API, so profile updates are **copy-ready changes the user
   applies**, and then marks as applied.
3. **A human approves outward actions.** Applying, sending email and messaging recruiters wait
   for user approval (`USER_APPROVAL_REQUIRED` / `HUMAN_APPROVAL_REQUIRED`). Respect
   `automation.service.is_allowed()` (global pause plus per-capability pauses) and the daily limits.
   Recruiter outreach is capped at **10 per day**.
4. **Record every agent action.** Record agent runs with `services/agent_runs.py` and audit
   entries with `services/audit.py`, and notify the user through `services/notify.py`.
5. **Build incrementally.** Write tests for each module. Push only when `pytest` passes.

## Stack

| Layer | Tech |
|---|---|
| Frontend `frontend/` | Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind v4, shadcn-style UI in `components/ui`, lucide-react, Recharts |
| Backend `backend/` | Python 3.12, FastAPI, Pydantic v2, pydantic-settings, Motor (async MongoDB) |
| Auth | Email/password (bcrypt) plus Google OAuth. A 15-minute JWT access token and an opaque rotating refresh token in an HttpOnly SameSite=Strict cookie on `/api/auth`. Sessions last 30 days and slide. Reuse detection has a 60 s grace window. CSRF protection uses the `X-Requested-With: saige` header. |
| AI (optional) | Anthropic `claude-opus-5` via `messages.parse`. Enabled only when `ANTHROPIC_API_KEY` starts with `sk-ant-`. Everything must also work deterministically without it. |
| Gmail | Read-only OAuth (`gmail.readonly`). Tokens are encrypted with AES-GCM (`services/crypto.py`). |
| Deploy | Vercel runs two projects: `saige-ai` (root `frontend`) and `saige-ai-api` (root `backend`, `@vercel/python`, `backend/index.py`). The frontend proxies `/api/*` to `BACKEND_URL`, so cookies stay first-party. |

## Layout

```
backend/app/
  main.py                 # router registration (order matters: sync_router before profile router)
  config.py               # Settings (env_ignore_empty=True; llm_enabled requires sk-ant-)
  database/collections.py # ALL collection names + USER_SCOPED (export/delete) + EXPORT_EXCLUDED
  database/mongo.py       # lazy client, 8 s server-selection timeout, index creation
  auth/                   # register/login/refresh/logout, Google OAuth (+ Gmail link branch in callback)
  profiles/               # master profile (service._deep_merge), optimizer, LinkedIn/Naukri sync
  resumes/                # parser, import-to-profile, tailor/ATS/cover letter, DOCX export
  jobs/                   # jd_parser, 9-dimension matching, dedupe, ATS board sources, discover.py (job APIs + role-family title filter),
                          # feed.py (Jobs for you: country/remote scope, walk-ins, HR emails; cached in job_feed), alerts.py (portal job-alert emails),
                          # auto_apply.py (daily prepare + approve_many: email applications via SMTP with resume attached)
  portals/router.py       # hiring-portal catalogue (/integrations/portals): "api" portals vs "alerts" portals + user profile links
  applications/           # applications, answers (confidence), interviews + .ics
  email/                  # Gmail OAuth or App Password (imap.py read, smtp.py send approved outreach), classifier, ingest -> status
  analytics/              # /analytics/dashboard aggregate + service.breakdowns (source/role/resume/match, weekly, time-to-response)
  automation/             # AutomationSettings (mode, pauses, schedules, limits), is_allowed
  services/whatsapp.py    # mirrors every notify() to the user's WhatsApp via CallMeBot (best effort)
  notifications/, privacy/ (export + account delete), services/ (truth_guard, crypto, audit, notify, rate_limit, agent_runs, skills_vocab)
  scheduler/              # daily jobs (service.run_due_jobs), /api/cron/daily (CRON_SECRET), /api/scheduler/*
  recruiters/             # contacts (manual/CSV/inbox), truth-checked outreach drafts, caps (10/day, 3/company/week), follow-ups, reply/bounce detection
  extension/router.py     # personal access tokens (/auth/tokens) + PAT-only /ext/* (analyze, save, answers)
backend/tests/            # pytest + mongomock-motor; conftest disables .env and pops GOOGLE_*/ANTHROPIC_*
frontend/app/(app)/       # authenticated pages (profiles = LinkedIn & Naukri hub); frontend/app/login, /register = galaxy sign-in
frontend/components/      # app-shell (nav), kpi, galaxy, loader3d, theme, motion, ui/*
frontend/services/api.ts  # request() wrapper (auto refresh, CSRF header); types in types/api.ts
extension/                # Chrome MV3 extension (popup + options); `node scripts/build-extension.mjs` rebuilds icons and frontend/public/saige-extension.zip
docs/                     # ARCHITECTURE.md, DEPLOYMENT.md, NEXT_PHASES_PROMPT.md
```

## Commands

```bash
# backend (from backend/)
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/python -m pytest -q          # must pass before any push
.venv/Scripts/ruff check app tests         # line length 150
env -u ANTHROPIC_API_KEY .venv/Scripts/uvicorn app.main:app --reload --reload-dir app --port 8000

# frontend (from frontend/)
npm install
npm run dev -- -p 3100                     # http://localhost:3100 (use localhost, not 127.0.0.1)
npm run lint && npx tsc --noEmit && npm test
NEXT_DIST_DIR=.next-build npm run build    # separate dist dir so it doesn't clash with dev
```

Local env: `backend/.env` (or the root `.env`) holds `MONGODB_URI`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI=http://localhost:3100/api/auth/google/callback`,
`FRONTEND_URL=http://localhost:3100`. `frontend/.env.local` sets `BACKEND_URL=http://localhost:8000`.
Never commit env files.

## Git and deploy rules

- Commit author **must** be `saibykani07@gmail.com`, because Vercel Hobby blocks other authors.
- Run `pytest` and the frontend lint and type-check, then push to `main`. Vercel deploys both projects
  automatically.
- When you add a backend env var, add it to `.env.example` and `docs/DEPLOYMENT.md`, and tell the user
  to set it in Vercel.
- When you add a new per-user collection, add it to `collections.py` and to `USER_SCOPED`, so export and
  account deletion cover it.

## Design system (the user is picky, so follow it)

- Google Sans typography and an Apple-like feel: glass cards, large radii, subtle motion (`animate-rise`,
  `lift`, `CountUp`, `ProgressRing` in `components/motion.tsx`).
- The default theme is **Graphite (pure black)**. Themes are set via `<html data-theme>`, with tokens in
  `app/globals.css` and the list in `components/theme-config.ts`.
- **The user dislikes pink/blue pastel gradients and mixed-colour gradients.** Each KPI card uses one
  solid accent (`tone` prop in `components/kpi.tsx`, from `--tone-*` tokens: green, orange, yellow,
  purple, red, mint, teal, lime). Surfaces stay black or neutral.
- The login page is a full-screen interactive canvas Milky Way (`components/galaxy.tsx`). It rotates
  slowly, reacts to hover and click, and shows the "Saige AI" wordmark only, with no logo mark.
- Charts use the validated series tokens `--chart-1..4` (orange, violet, green, amber; no blue or pink).
  Keep one axis, neutral label text, a legend, and a table-view toggle.
- The Help & Docs manual lives in `frontend/app/(app)/help/manual.ts`, with screenshots in `frontend/public/help/*.jpg`.
  Update both when a screen changes.
- App shell strings are translatable via `components/i18n.tsx` (en, hi, te); wrap new nav and menu labels in `t()`.
- The 3D loader is `components/loader3d.tsx`. Use it for full-page and route loading.
- Every page uses `PageHeader` and `Notice` from `components/app-shell.tsx`. Update the `NAV` and
  `UPCOMING` arrays there when a phase lands.
- The sidebar is kept short (9 entries). Pages with related data share one entry and switch with `tabs`
  in `NAV` (Dashboard·Analytics, Applications·Interviews, LinkedIn & Naukri·Resume sync,
  Settings = Integrations·Automation & privacy). Profile lives in the avatar menu, not the sidebar.
- Company contact email: `info.saigeai@gmail.com` (`CONTACT_EMAIL` in `components/legal.tsx`).
