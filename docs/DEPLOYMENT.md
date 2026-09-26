# Deploying Saige AI

Saige AI has three parts, and each runs on its own service:

| Part | Where | Why |
|---|---|---|
| Frontend (Next.js, `frontend/`) | **Vercel** | Serves the UI and proxies `/api/*` to the backend, so the login cookie stays first-party |
| Backend (FastAPI, `backend/`) | **Render**, Railway, Fly.io or any container host | Long-running Python API; Vercel is not a good fit for it |
| Database | **MongoDB Atlas** | Already set up |

The frontend cannot work on Vercel until the backend is deployed somewhere and `BACKEND_URL` points at it.

## 1a. Backend on Vercel (simplest if you already use Vercel)

1. Vercel → **Add New… → Project** → import the same GitHub repo again.
2. Name it `saige-ai-api` and set **Root Directory** to `backend`. Vercel reads
   `backend/vercel.json` and `backend/index.py`.
3. Under **Environment Variables**, add:

   | Key | Value |
   |---|---|
   | `MONGODB_URI` | your Atlas connection string (from `.env`) |
   | `JWT_SECRET` | a new random secret, generated with `python -c "import secrets;print(secrets.token_urlsafe(64))"` |
   | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | from `.env` |
   | `FRONTEND_URL`, `CORS_ORIGINS` | `https://saige-ai.vercel.app` |
   | `GOOGLE_REDIRECT_URI` | `https://saige-ai.vercel.app/api/auth/google/callback` |
   | `ENVIRONMENT` | `production` |
   | `COOKIE_SECURE` | `true` |
   | `MAX_UPLOAD_MB` | `4`, because Vercel limits request bodies to 4.5 MB |

4. Click **Deploy**. When it's live, open `https://saige-ai-api.vercel.app/api/health`. It
   should return `{"status":"ok","database":true}`.
5. In the **frontend** project, add `BACKEND_URL=https://saige-ai-api.vercel.app` and
   **Redeploy**. The `/api` proxy address is fixed when the frontend is built, so the redeploy
   is required.
6. Atlas → **Network Access**: allow `0.0.0.0/0`, because Vercel has no fixed IP addresses.

## 1b. Backend on Render (alternative)

1. Go to https://render.com, sign in with GitHub, then click **New → Blueprint** and pick this repo.
   `render.yaml` at the repo root creates the `saige-ai-api` web service.
2. When Render asks for the secret values, copy them from your local `.env`:
   `MONGODB_URI`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and optionally
   `ANTHROPIC_API_KEY`. Use a new, different `JWT_SECRET` for production.
3. Set these once you know your Vercel domain (step 2), e.g. `https://saige-ai.vercel.app`:
   - `FRONTEND_URL=https://saige-ai.vercel.app`
   - `CORS_ORIGINS=https://saige-ai.vercel.app`
   - `GOOGLE_REDIRECT_URI=https://saige-ai.vercel.app/api/auth/google/callback`
4. **Atlas network access:** cloud hosts don't have fixed IP addresses. In Atlas, go to
   **Network Access → Add IP Address → Allow access from anywhere** (`0.0.0.0/0`). The database
   is still protected by its username and password.
5. When the deploy finishes, open `https://<your-service>.onrender.com/api/health`. It should
   return `{"status":"ok","database":true}`.

## 2. Frontend on Vercel

1. Open the Vercel project → **Settings → General → Root Directory** and set it to `frontend`.
   The framework preset should show **Next.js**.
2. **Settings → Environment Variables**: add
   `BACKEND_URL=https://<your-service>.onrender.com` for Production.
3. Redeploy.

### "Deployment Blocked: commit author did not have contributing access"

On the Hobby plan, Vercel only builds commits whose author email belongs to the Vercel
account's linked GitHub user. Commit with that identity:

```bash
git config --global user.email "saibykani07@gmail.com"   # the email on the GitHub account linked to Vercel
```

Also make sure that email is added and verified on GitHub (**Settings → Emails**). Vercel checks
the latest commit, so the next push with the correct author deploys.

## 3. Google sign-in in production

Google Cloud Console → **APIs & Services → Credentials** → your OAuth client:

- **Authorized JavaScript origins:** add `https://saige-ai.vercel.app`
- **Authorized redirect URIs:** add `https://saige-ai.vercel.app/api/auth/google/callback`

While the consent screen is in **Testing**, only the listed test users can sign in with Google.

## 4. Gmail (Phase 5)

Gmail uses the same OAuth client and callback address as Google sign-in, so you don't need a new
redirect URI. Two one-time steps in Google Cloud Console:

1. **APIs & Services → Library → Gmail API → Enable.**
2. **Google Auth Platform → Data access → Add or remove scopes**, then add
   `https://www.googleapis.com/auth/gmail.readonly` and save.

While the app is in Testing mode, only listed test users can connect Gmail. Publishing an app
that uses the restricted Gmail scope requires Google's verification.

### Gmail without Google verification: App Password

Integrations → Connect Gmail → **Option 1** connects over Gmail IMAP with a Google App Password
(myaccount.google.com/apppasswords, requires 2-Step Verification). It needs no Google Cloud setup or
review. The password is encrypted at rest, mail is read with `BODY.PEEK` (never marked read), and
the user can revoke it in their Google account at any time.

### Jobs for you (no keys needed)

Jobs → **Jobs for you** (`GET /api/jobs/feed`, `backend/app/jobs/feed.py`) fetches every job for the
user's target roles and country with no API keys:

- Himalayas (country filter), Remotive, Jobicy and Arbeitnow job APIs,
- the public Greenhouse / Lever / Ashby career pages in `feed.CAREER_BOARDS`, plus boards the user follows,
- LinkedIn / Naukri / Indeed / other portal **job-alert emails** in the user's Gmail (`jobs/alerts.py`,
  read during Gmail sync).

The feed is cached per user for 6 hours (`job_feed` collection) and rebuilt by the daily `job_discovery`
scheduler job, which then runs the auto-applier (`jobs/auto_apply.py`) for users who turned it on.

Adzuna is optional and off by default. Only set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` if you have a working key.

### WhatsApp alerts

These are set up entirely in the app (Integrations → WhatsApp notifications) using the user's own
CallMeBot key. No server configuration is needed.

## 5. Daily scheduler (Phase 6)

`backend/vercel.json` registers a Vercel Cron job that calls `/api/cron/daily` every day at
02:30 UTC (08:00 IST). It runs, per user and in each user's timezone:
- the LinkedIn & Naukri optimisation;
- the Naukri daily freshness micro-edit;
- the job board sync;
- the Gmail sync;
- the follow-up check;
- the morning report.

1. Generate a secret: `python -c "import secrets;print(secrets.token_urlsafe(32))"`.
2. In the **backend** Vercel project (`saige-ai-api`), add `CRON_SECRET=<that value>` and redeploy.
   Vercel sends it automatically as `Authorization: Bearer <secret>`. Without it, the endpoint
   answers 503.
3. Optional, for runs more often than daily (Hobby allows one cron a day): create a job on
   https://cron-job.org that calls `https://saige-ai-api.vercel.app/api/cron/daily` hourly, with the
   header `Authorization: Bearer <secret>`. Each job still runs at most once per user per day.

## 6. "Access blocked: has not completed the Google verification process"

Your Google Cloud project is in **Testing** mode, so only listed test users can sign in. Pick one:

- **Quick (private use):** Google Auth Platform → **Audience** → **Test users** → **Add users**. Add every
  Google account that should sign in (up to 100).
- **Public:** Google Auth Platform → **Audience** → **Publish app**. Sign-in uses only `openid email profile`,
  which needs no review. For **Branding**, set:
  - the home page to `https://saige-ai.vercel.app/login`;
  - the privacy policy to `https://saige-ai.vercel.app/privacy`;
  - the terms to `https://saige-ai.vercel.app/terms`.

  Gmail's `gmail.readonly` is a *restricted* scope. Until Google verifies it (a review plus a CASA
  security assessment), people who connect Gmail see an "unverified app" warning, and the app is capped at 100 users.
  The privacy policy already includes the required Limited Use disclosure.

## Production checklist

- `ENVIRONMENT=production`: turns off the `/api/docs` page and enables HSTS.
- `COOKIE_SECURE=true`: required on HTTPS.
- Use a different `JWT_SECRET` from development.
- Change the Atlas password and the Google client secret if they were ever shared.
- Every write request is rate-limited to 180 per minute per session (or per client address), and feature
  limits are stricter. Limits are in-memory per instance: move them to Redis if you scale out.
