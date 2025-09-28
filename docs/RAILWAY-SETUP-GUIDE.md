# Railway Deployment Guide for PlanExe

## Overview
PlanExe now deploys as a single Railway service: the Docker build compiles the Next.js UI and bundles the static export into the FastAPI container, which in turn serves both the REST API and the frontend. This eliminates cross-origin headaches and keeps the deployment identical to production.

## Prerequisites
- Railway account with a project ready
- GitHub repository that Railway can access
- API keys for your preferred LLM providers (OPENROUTER_API_KEY, OPENAI_API_KEY, etc.)
- PostgreSQL database provisioned inside the Railway project (Railway does this automatically when you add a Postgres plugin)

## 1. Prepare the Repository
1. Ensure main (or your deployment branch) contains the latest code.
2. Push all changes so Railway can see the new Dockerfile logic.
3. Confirm that docker/Dockerfile.railway.api is the file Railway should build (no separate UI Dockerfile is needed anymore).

## 2. Configure Railway Environment Variables
In the Railway dashboard for your PlanExe service, open the Variables tab and set:
```
OPENROUTER_API_KEY=your_key
OPENAI_API_KEY=your_key   # optional if you only use OpenRouter
PLANEXE_RUN_DIR=/app/run
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```
Railway automatically injects:
- PORT: the HTTP port the container must listen on
- DATABASE_URL: connection string for the attached PostgreSQL instance
- RAILWAY_ENVIRONMENT=production

## 3. Deploy the Single Service
1. In Railway click New -> GitHub Repo, choose the PlanExe repository, and pick the branch to deploy.
2. In the service settings, set:
   - Root Directory: /
   - Dockerfile Path: docker/Dockerfile.railway.api
   - Build Context: /
3. Trigger a deploy. The Dockerfile now performs these stages automatically:
   - Installs Node and builds the Next.js static export (npm run build:static -> places the export in /app/ui_static).
   - Installs Python dependencies and sets up FastAPI/Luigi.
   - Exposes FastAPI on Railway's assigned PORT and serves the bundled UI.
4. Once the deploy succeeds, open the logs to confirm the "Serving static UI from: /app/ui_static" message from FastAPI.

## 4. Smoke Tests
1. Visit https://<your-service>.up.railway.app/ - the PlanExe UI should load without a secondary service.
2. Hit the health check directly:
   ```bash
   curl https://<your-service>.up.railway.app/health
   curl https://<your-service>.up.railway.app/api/models
   ```
   Both should return 200 responses.
3. Create a test plan from the UI and monitor logs to ensure Luigi tasks execute.

## 5. Operations Cheatsheet
- Deploy updates: push commits -> Railway rebuilds automatically.
- View logs: Railway dashboard -> Service -> Logs (shows both API and Luigi output).
- Database access: Railway's Postgres plugin provides a connection string; use psql or a GUI if needed.
- Environment changes: edit variables and redeploy so processes pick them up.

## 6. Troubleshooting
- Frontend 404s: indicates the static assets did not copy. Check the build log for npm run build:static failures.
- Missing API keys: FastAPI prints [MISSING] warnings during startup. Set the environment variables and redeploy.
- Database errors: confirm the DATABASE_URL variable is present and the database service is running.
- Luigi pipeline failures: open the service logs and inspect /app/run/<plan-id> inside the container (Railway provides a shell).

## 7. Retiring the Legacy Frontend Service
If your Railway project still has the old planexe-frontend service, remove it to avoid confusion. The single API service now serves all traffic.

---
Remember: The UI is just a thin layer over the Python pipeline. Treat Railway as the development environment: commit, push, deploy, and debug directly in production-like conditions.
