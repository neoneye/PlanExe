# frontend_multiuser

Flask-based multi-user UI for PlanExe. Runs in Docker, uses Postgres (defaults to the `database_postgres` service), and installs the PlanExe/worker_plan package so the in-process pipeline keeps working.

## Quickstart (Docker)
- Ensure `.env` and `llm_config.json` exist in the repo root (they are mounted into the container).
- `docker compose up frontend_multiuser`
- Open http://localhost:${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001}/ (container listens on 5000). Health endpoint: `/health`.

## Config (env)
- `PLANEXE_FRONTEND_MULTIUSER_DB_HOST|PORT|NAME|USER|PASSWORD`: Postgres target (defaults follow `database_postgres` / `planexe` values).
- `PLANEXE_FRONTEND_MULTIUSER_HOST`: bind address inside the container (default 0.0.0.0).
- `PLANEXE_FRONTEND_MULTIUSER_APP_PORT`: Flask port inside the container (default 5000).
- `PLANEXE_FRONTEND_MULTIUSER_DEBUG`: set `true` to enable Flask debug.
- `PLANEXE_CONFIG_PATH`: defaults to `/app` so PlanExe picks up `.env` + `llm_config.json` that compose mounts.

## Local dev (without compose)
```bash
cd frontend_multiuser
python -m venv .venv
source .venv/bin/activate
pip install --prefer-binary ../worker_plan
python - <<'PY'
import tomllib, pathlib
deps = tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["dependencies"]
pathlib.Path(".tmp-frontend-reqs.txt").write_text("\n".join(deps))
PY
pip install --prefer-binary -r .tmp-frontend-reqs.txt
PLANEXE_FRONTEND_MULTIUSER_DB_HOST=localhost PLANEXE_FRONTEND_MULTIUSER_DB_PORT=${PLANEXE_POSTGRES_PORT:-5432} python src/app.py
```
