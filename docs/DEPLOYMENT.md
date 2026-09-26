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

## Production checklist

- `ENVIRONMENT=production`: turns off the `/api/docs` page and enables HSTS.
- `COOKIE_SECURE=true`: required on HTTPS.
- Use a different `JWT_SECRET` from development.
- Change the Atlas password and the Google client secret if they were ever shared.
