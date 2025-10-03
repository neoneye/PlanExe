/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Definitive Railway deployment runbook for PlanExe v0.3.2, including fallback report checks and
 *          database validation steps.
 * SRP and DRY check: Pass - Single source for Railway setup; references other docs for deep dives.
 */
# Railway Deployment Guide for PlanExe (v0.3.2)

Railway now runs PlanExe as a single FastAPI service that serves the static Next.js export and orchestrates the
Luigi pipeline. Follow this checklist when deploying or validating the environment.

## Prerequisites
- Railway project with Postgres plugin provisioned.
- GitHub repository linked to Railway (main branch recommended for deploys).
- LLM API keys (OpenRouter, OpenAI, others as required).
- Local `.env` kept in sync with Railway variables.

## Repository Preparation
1. Ensure `docker/Dockerfile.railway.api` is up to date (it builds the UI and installs Python deps).
2. Commit and push all changes so Railway triggers a new build.
3. Run migrations locally (`alembic upgrade head` via project tooling) if schema changed.

## Configure Railway Variables
Set the following on the service:
```
OPENROUTER_API_KEY=<value>
OPENAI_API_KEY=<value>       # optional
PLANEXE_RUN_DIR=/app/run
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```
Railway injects `DATABASE_URL`, `PORT`, and `RAILWAY_ENVIRONMENT`. No further action required.

## Deploy Steps
1. Create or open the PlanExe service in Railway.
2. Settings ? Deploy: root directory `/`, Dockerfile `docker/Dockerfile.railway.api`.
3. Trigger deploy. Build stages should include:
   - `npm ci && npm run build` for Next.js (output copied to `/app/ui_static`).
   - `pip install -r requirements.txt` for FastAPI / Luigi.
   - `uvicorn planexe_api.api:app` entrypoint.
4. After deploy, check logs for:
   - `Serving static UI from: /app/ui_static`.
   - API key validation lines (`[OK] OPENROUTER_API_KEY`).
   - `ReportAssembler` ready messages (v0.3.2).

## Post-Deploy Smoke Test
```bash
curl https://<service>.up.railway.app/health
curl https://<service>.up.railway.app/api/models
```
Then open the UI at the base URL, create a plan, and confirm:
- Progress updates appear (SSE or WebSocket; expect occasional SSE drops).
- `/api/plans/{plan_id}/files` lists artefacts.
- `/api/plans/{plan_id}/fallback-report` returns HTML even if a late-stage task fails.

## Operations Cheatsheet
- Logs: Railway dashboard ? Service ? Logs (contains FastAPI + Luigi output).
- Database: Use Railway's SQL shell or connect via the provided `DATABASE_URL`.
- Redeploy: Push to the tracked branch or click Redeploy.
- Scale: Default 1x is sufficient; Luigi runs inside the same container.
- Cleanup: Delete old runs from the UI or via `DELETE /api/plans/{plan_id}`.

## Troubleshooting
| Issue | Check |
| --- | --- |
| White screen / 404 | Static export missing; inspect build phase logs |
| 502 errors | Ensure FastAPI binds to `$PORT`; rebuild if Dockerfile changed |
| Missing API keys | Verify environment variables, redeploy after updates |
| No Luigi output | Inspect `/app/run/<plan_id>/log.txt` via Railway shell |
| No report | Call fallback endpoint, review missing section list |

Keep this guide updated whenever deployment requirements change. For database migration specifics see
`docs/RailwayDatabaseMigration.md`.
