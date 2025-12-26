# frontend_multiuser

Flask-based multi-user UI for PlanExe. Runs in Docker, uses Postgres (defaults to the `database_postgres` service), and only needs the lightweight `worker_plan_api` helpers (no full `worker_plan` install).

## Quickstart with Docker
- Ensure `.env` and `llm_config.json` exist in the repo root (they are mounted into the container).
- `docker compose up frontend_multiuser`
- Open http://localhost:${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001}/ (container listens on 5000). Health endpoint: `/health`.

## Config (env)
- `PLANEXE_FRONTEND_MULTIUSER_DB_HOST|PORT|NAME|USER|PASSWORD`: Postgres target (defaults follow `database_postgres` / `planexe` values).
- `PLANEXE_FRONTEND_MULTIUSER_HOST`: bind address inside the container (default 0.0.0.0).
- `PLANEXE_FRONTEND_MULTIUSER_APP_PORT`: Flask port inside the container (default 5000).
- `PLANEXE_FRONTEND_MULTIUSER_DEBUG`: set `true` to enable Flask debug.
- `PLANEXE_CONFIG_PATH`: defaults to `/app` so PlanExe picks up `.env` + `llm_config.json` that compose mounts.

## Local devevelopment without Docker
```bash
cd frontend_multiuser
python -m venv .venv
source .venv/bin/activate
export PYTHONPATH="$(pwd):$(pwd)/src:$(pwd)/../worker_plan/worker_plan_api"
pip install --prefer-binary -e .
PLANEXE_FRONTEND_MULTIUSER_DB_HOST=localhost PLANEXE_FRONTEND_MULTIUSER_DB_PORT=${PLANEXE_POSTGRES_PORT:-5432} python src/app.py
```
If you want pipeline-backed routes locally, also install the full `worker_plan` package in a separate environment or set `PLANEXE_WORKER_PLAN_URL` to a running worker service.
