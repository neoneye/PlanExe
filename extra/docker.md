# PlanExe uses Docker

I'm no fan of Docker and I tried to avoid it.
I first tried dependency hell, and it was fragile. Incompatible packages, preventing installing/upgrading things.
I had to choose between dependency hell or docker hell.
Now I'm going with Docker. Hopefully it turns out to be less fragile.

## Basic lifecycle
- Stop everything: `docker compose down`
- Build fresh (no cache) after code moves: `docker compose build --no-cache database_postgres worker_plan frontend_single_user frontend_multi_user`
- Start services: `docker compose up`
- Stop services (leave images): `docker compose down`
- Build fresh and start services: `docker compose build --no-cache database_postgres worker_plan frontend_single_user frontend_multi_user && docker compose up`

## While developing
- Live rebuild/restart on changes: `docker compose watch` (requires Docker Desktop 4.28+).  
  If watch misses changes after file moves, rerun the no-cache build above.
- View worker logs (pipeline errors show here): `docker compose logs -f worker_plan`
- View frontend logs: `docker compose logs -f frontend_single_user`
- View multiuser ping UI logs: `docker compose logs -f frontend_multi_user`

## Run individual files
- Rebuild the worker image when code or data files change: `docker compose build --no-cache worker_plan`.
- Run a one-off module inside the worker image (same deps/env as the API):  
  `docker compose run --rm worker_plan python -m worker_plan_internal.fiction.fiction_writer` (swap the module path as needed). If containers are already up, use `docker compose exec worker_plan python -m ...` instead.
- For host Ollama access, set `base_url` in `llm_config.json` to `http://host.docker.internal:11434` (default Ollama port). On Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]` under `worker_plan` if that hostname is missing, or use your bridge IP.
- Ensure required env vars (e.g., `DEFAULT_LLM`) are available via `.env` or your shell before running the command.

## Troubleshooting
- If the pipeline stops immediately with missing module errors, rebuild with `--no-cache` so new files are inside the images.
- If you change environment variables (e.g., `PLANEXE_WORKER_RELAY_PROCESS_OUTPUT`), restart: `docker compose down` then `docker compose up`.
- If `database_postgres` fails to start because host port 5432 is in use, set a host port with `export PLANEXE_POSTGRES_PORT=5435` (or any free port) before `docker compose up`.
- If `frontend_multi_user` can’t start because host port 5000 is busy, map it elsewhere: `export PLANEXE_FRONTEND_MULTIUSER_PORT=5001` (or another free port) before `docker compose up`.
- To clean out containers, network, and orphans: `docker compose down --remove-orphans`.
- To reclaim disk space when builds start failing with `No space left on device`:
  - See current usage: `docker system df`
  - Aggressively prune (images, caches, networks not in use): `docker system prune -a`
    - Expect a confirmation prompt; this removed ~37 GB here by deleting unused images and build cache.
  - If needed, prune build cache separately: `docker builder prune`

## Environment notes
- The worker exports logs to stdout when `PLANEXE_WORKER_RELAY_PROCESS_OUTPUT=true` (set in `docker-compose.yml`).
- Shared volumes: `./run` is mounted into both services; `.env` and `llm_config.json` are mounted read-only. Ensure they exist on the host before starting.***
- Database: Postgres runs in `database_postgres` and listens on host `${PLANEXE_POSTGRES_PORT:-5432}` mapped to container `5432`; data is persisted in the named volume `database_postgres_data`.
- Multiuser ping UI: binds to container port `5000`, exposed on host `${PLANEXE_FRONTEND_MULTIUSER_PORT:-5001}`.

## One-shot env setup (avoid manual exports)
Run once per terminal session to emit exports for `PLANEXE_OPEN_DIR_SERVER_URL` and related values:
```bash
eval "$(python setup_env.py)"
```
This keeps `.env` reserved for secrets while still seeding the shell for Docker commands.

## Host opener (Open Output Dir)
Because Docker containers cannot launch host apps, the `Open Output Dir` button needs a host-side service:

1) Start host opener **before** Docker (on the host):
```bash
eval "$(python setup_env.py)"
cd open_dir_server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
2) Configure the frontend container to call it:
- Set `PLANEXE_OPEN_DIR_SERVER_URL` so the container can reach the host opener (containers cannot guess this URL):
  - macOS/Windows (Docker Desktop): `http://host.docker.internal:5100`
  - Linux: often `http://172.17.0.1:5100` or add `host.docker.internal` in `/etc/hosts` pointing to the docker bridge IP.
  - If you override host/port for the opener, reflect that in the URL.
- Provide the variable via your shell env, `.env`, or docker compose environment for `frontend_single_user`.
  - macOS (zsh default shell): `export PLANEXE_OPEN_DIR_SERVER_URL=http://host.docker.internal:5100` then `docker compose up`
  - macOS example (`.env`): add `PLANEXE_OPEN_DIR_SERVER_URL=http://host.docker.internal:5100` then `docker compose up`
