# Railway Single-Service Deployment Plan

## Architecture Decision

We now deploy PlanExe as a **single Railway service**. FastAPI renders the static Next.js UI export and exposes the REST API from the same container. Removing the standalone frontend service simplifies deployments and avoids cross-origin issues.

### Key Components
- **FastAPI + Luigi**: Runs inside the container built from `docker/Dockerfile.railway.api`.
- **Static Next.js UI**: Generated during the Docker build and copied to `/app/ui_static`.
- **Database**: Railway PostgreSQL plugin (provides `DATABASE_URL`).
- **Port**: FastAPI listens on `PORT` supplied by Railway.

### Benefits
- Single deployment target to manage.
- No CORS or base-URL drift between services.
- Identical runtime between staging and production.
- Less room for documentation drift or misconfigured env vars.

## Build Pipeline Summary

1. **Node build stage** (`frontend-builder`)
   - Runs `npm ci` and `npm run build` inside `planexe-frontend/`.
   - Produces the static export in `/app/planexe-frontend/out`.
2. **Python runtime stage**
   - Installs Python deps via `pyproject.toml` and `planexe_api/requirements.txt`.
   - Copies the repo and the static export into `/app/ui_static`.
   - Sets environment variables so FastAPI picks up the correct run directory and Python path.
3. **Runtime**
   - `uvicorn planexe_api.api:app` binds to `0.0.0.0:${PORT}`.
   - FastAPI serves `/` and static assets from `/app/ui_static` and exposes the API routes under `/api/*`.

## Deployment Checklist

1. Push commits to GitHub (Railway watches the branch you configured).
2. On Railway, ensure the service uses `docker/Dockerfile.railway.api` with root context.
3. Set environment variables:
   - `OPENROUTER_API_KEY`, `OPENAI_API_KEY` (optional but recommended).
   - `PLANEXE_RUN_DIR=/app/run`
   - `PYTHONPATH=/app`
   - `PYTHONUNBUFFERED=1`
4. Verify the PostgreSQL plugin is attached so `DATABASE_URL` is available.
5. Trigger a deployment (push or manual redeploy).
6. After deploy, hit:
   - `https://<service>.up.railway.app/` for the UI.
   - `https://<service>.up.railway.app/health` for health status.
   - `https://<service>.up.railway.app/api/models` for model availability.

## Operational Guidance

- Use `railway-deploy.sh` locally to confirm required files exist before pushing.
- `railway-env-template.txt` lists the variables that must be set per environment.
- Keep running `npm run build` locally when changing frontend code to catch build issues early.
- When migrating from the old dual-service setup, delete the legacy `planexe-frontend` service in Railway to prevent orphaned deployments.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| UI shows 404 in production | Static export failed or `/app/ui_static` missing | Check Railway build logs for the Node build stage. |
| API returns 500 on `/api/models` | Missing LLM API keys | Confirm `OPENROUTER_API_KEY` and/or `OPENAI_API_KEY` are set and redeploy. |
| Database errors on startup | `DATABASE_URL` missing | Ensure the Railway Postgres plugin is attached and redeploy. |
| Old UI still visible | Multiple services running | Delete any old `planexe-frontend` Railway service and redeploy the API. |

## Future Considerations

- Add CI to run `npm run build` and backend tests before pushing to Railway.
- Consider uploading build artifacts to a cache to speed up Docker builds.
- Document any per-environment secrets in the Railway dashboard notes to keep onboarding simple.
