Docker Compose for PlanExe
==========================

TL;DR
-----
- Four containers: `database_postgres` (DB on `${PLANEXE_POSTGRES_PORT:-5432}`), `frontend_gradio` (UI on 7860), `worker_plan` (API on 8000), and `frontend_multiuser` (UI on `${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001}`); `frontend_gradio` waits for the worker to be healthy and `frontend_multiuser` waits for Postgres health.
- Shared host files: `.env` and `llm_config.json` mounted read-only; `./run` bind-mounted so outputs/logs persist; `.env` is also loaded via `env_file`.
- Postgres defaults to user/db/password `planexe`; override via env or `.env`; data lives in the `database_postgres_data` volume.
- Env defaults live in `docker-compose.yml` but can be overridden in `.env` or your shell (URLs, timeouts, run dirs, optional auth and opener URL).
- `develop.watch` syncs code/config for both services; rebuild with `--no-cache` after big moves or dependency changes; restart policy is `unless-stopped`.

Quickstart (run from repo root)
-------------------------------
- Up: `docker compose up` (or `docker compose watch` if supported).
- Down: `docker compose down` (add `--remove-orphans` if stray containers linger).
- Rebuild clean: `docker compose build --no-cache database_postgres worker_plan frontend_gradio frontend_multiuser`.
- Ping UI: http://localhost:${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001} (multiuser DB check) after the stack is up.
- Logs: `docker compose logs -f worker_plan` or `... frontend_gradio`.
- One-off inside a container: `docker compose run --rm worker_plan python -m planexe.fiction.fiction_writer` (use `exec` if already running).
- Ensure `.env` and `llm_config.json` exist; copy `.env.example` to `.env` if you need a starter.

Why compose (escaping dependency hell)
--------------------------------------
- Dependency hell: when one Python package requires version A of a dependency while another requires version B (or a different Python), so `pip` cannot satisfy everything in one environment; the resolver loops, pins conflict, or installs a set that breaks another part of the app. System-level deps (libssl) can also clash, and "fixes" often mean uninstalling or downgrading unrelated packages.
- I want to experiment with the `uv` package manager; to try it, install `uv` during the image build and replace the `pip install ...` lines with `uv pip install ...`. Compose keeps that change isolated per service so it doesn’t spill onto the other containers or host Python.
- Compose solves this by isolating environments per service: each image pins its own base Python, OS libs, and `requirements.txt`, so the frontend and worker no longer fight over versions.
- Builds are reproducible: the `Dockerfile` installs a clean env from scratch, so you avoid ghosts from previous virtualenvs or globally-installed wheels.
- If a dependency change fails, you can rebuild from zero or switch base images without nuking your host Python setup.

What compose sets up
--------------------
- Reusable local stack with consistent env/paths under `/app` in each container.
- Shared run dir: `PLANEXE_RUN_DIR=/app/run` in the containers, bound to `${PLANEXE_HOST_RUN_DIR:-${PWD}/run}` on the host so outputs persist.
- Postgres data volume: `database_postgres_data` keeps the database files outside the repo tree.

Service: `database_postgres` (Postgres DB)
------------------------------------------
- Purpose: Storage in a Postgres database for future queue + event logging work; exposes `${PLANEXE_POSTGRES_PORT:-5432}` on the host mapped to 5432 in the container.
- Build: `database_postgres/Dockerfile` (uses the official Postgres image).
- Env defaults: `POSTGRES_USER=planexe`, `POSTGRES_PASSWORD=planexe`, `POSTGRES_DB=planexe`, `PLANEXE_POSTGRES_PORT=5432` (override with env/.env).
- Data/health: data in the named volume `database_postgres_data`; healthcheck uses `pg_isready`.

Service: `frontend_gradio` (single user UI)
------------------------------------
- Purpose: Single user Gradio UI; waits for a healthy worker and serves on port 7860. Does not use database.
- Build: `frontend_gradio/Dockerfile`.
- Env defaults: `PLANEXE_WORKER_PLAN_URL=http://worker_plan:8000`, timeout, server host/port, optional password, optional `PLANEXE_OPEN_DIR_SERVER_URL` for the host opener.
- Volumes: mirrors the worker (`.env` ro, `llm_config.json` ro, `run/` rw) so both share config and outputs.
- Watch: sync frontend code, shared API code in `worker_plan/`, and config files; rebuild on `worker_plan/pyproject.toml`; restart on compose edits.

Service: `frontend_multiuser` (multi user UI)
------------------------------------------
- Purpose: Multi-user Flask UI with admin views (tasks/events/nonce/workers) backed by Postgres.
- Build: `frontend_multiuser/Dockerfile`.
- Env defaults: DB host `database_postgres`, port `5432`, db/user/password `planexe` (follows `POSTGRES_*`); container listens on fixed port `5000`, host maps `${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001}`.
- Health: depends on `database_postgres` health; its own healthcheck hits `/health` on port 5000.

Service: `worker_plan` (pipeline API)
-------------------------------------
- Purpose: runs the PlanExe pipeline and exposes the API on port 8000; the frontend depends on its health.
- Build: `worker_plan/Dockerfile`.
- Env: `PLANEXE_CONFIG_PATH=/app`, `PLANEXE_RUN_DIR=/app/run`, `PLANEXE_HOST_RUN_DIR=${PWD}/run`, `PLANEXE_WORKER_RELAY_PROCESS_OUTPUT=true`.
- Health: `http://localhost:8000/healthz` checked via the compose healthcheck.
- Volumes: `.env` (ro), `llm_config.json` (ro), `run/` (rw).
- Watch: sync `worker_plan/` into `/app/worker_plan`, rebuild on `worker_plan/pyproject.toml`, restart on compose edits.

Usage notes
-----------
- Ports: host `8000->worker_plan`, `7860->frontend_gradio`, `${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001}->frontend_multiuser`, `PLANEXE_POSTGRES_PORT (default 5432)->database_postgres`; change mappings in `docker-compose.yml` if needed.
- `.env` must exist before `docker compose up`; it is both loaded and mounted read-only. Same for `llm_config.json`. If missing, start from `.env.example`.
- Host opener: set `PLANEXE_OPEN_DIR_SERVER_URL` so the frontend can reach your host opener service (see `extra/docker.md` for OS-specific URLs and optional `extra_hosts` on Linux).
- To relocate outputs, set `PLANEXE_HOST_RUN_DIR` (or edit the bind mount) to another host path.
- Database: connect on `localhost:${PLANEXE_POSTGRES_PORT:-5432}` with `planexe/planexe` by default; data persists via the `database_postgres_data` volume.
