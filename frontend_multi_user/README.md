# Frontend multi user - Experimental

**My recommendation: Avoid this, instead go with `frontend_single_user`.** This multi user UI is the bare minimum, unpolished. It has a queue mechanism, admin UI, but it has no user account management. I use it for handling multiple users. It requires lots of setup to get working. It's not something that simply works out of the box. Save yourself the trouble, go with `frontend_single_user` instead.

Flask-based multi-user UI for PlanExe. Runs in Docker, uses Postgres (defaults to the `database_postgres` service), and only needs the lightweight `worker_plan_api` helpers (no full `worker_plan` install).

## Quickstart with Docker
- Ensure `.env` and `llm_config.json` exist in the repo root (they are mounted into the container).
- `docker compose up frontend_multi_user`
- Open http://localhost:${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001}/ (container listens on 5000). Health endpoint: `/health`.

## Config (env)
- `PLANEXE_FRONTEND_MULTIUSER_DB_HOST|PORT|NAME|USER|PASSWORD`: Postgres target (defaults follow `database_postgres` / `planexe` values).
- `PLANEXE_FRONTEND_MULTIUSER_ADMIN_USERNAME` / `PLANEXE_FRONTEND_MULTIUSER_ADMIN_PASSWORD`: Admin login for the UI; must be set (service fails to start if missing).
- `PLANEXE_FRONTEND_MULTIUSER_HOST`: bind address inside the container (default 0.0.0.0).
- `PLANEXE_FRONTEND_MULTIUSER_APP_PORT`: Flask port inside the container (default 5000).
- `PLANEXE_FRONTEND_MULTIUSER_DEBUG`: set `true` to enable Flask debug.
- `PLANEXE_CONFIG_PATH`: defaults to `/app` so PlanExe picks up `.env` + `llm_config.json` that compose mounts.

## Local devevelopment without Docker
The container sets `PYTHONPATH=/app:/app/frontend_multi_user:/app/frontend_multi_user/src`, so `worker_plan_api` is importable without hacks. Locally you need to mirror that.

```bash
cd frontend_multi_user
python -m venv .venv
source .venv/bin/activate
# Option A (recommended): install the shared code once
pip install --prefer-binary -e ../worker_plan

# Option B: use PYTHONPATH if you don't want to install worker_plan locally
export PYTHONPATH="$(pwd):$(pwd)/src:$(pwd)/../worker_plan"

pip install --prefer-binary -e .
PLANEXE_FRONTEND_MULTIUSER_DB_HOST=localhost PLANEXE_FRONTEND_MULTIUSER_DB_PORT=${PLANEXE_POSTGRES_PORT:-5432} python src/app.py
```
If you want pipeline-backed routes locally, also install the full `worker_plan` package in a separate environment or set `PLANEXE_WORKER_PLAN_URL` to a running worker service.
