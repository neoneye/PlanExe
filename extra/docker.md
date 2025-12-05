# Docker workflow for PlanExe

Basic lifecycle
---------------
- Stop everything: `docker compose down`
- Build fresh (no cache) after code moves: `docker compose build --no-cache worker_plan frontend_gradio`
- Start services: `docker compose up`
- Stop services (leave images): `docker compose down`

While developing
----------------
- Live rebuild/restart on changes: `docker compose watch` (requires Docker Desktop 4.28+).  
  If watch misses changes after file moves, rerun the no-cache build above.
- View worker logs (pipeline errors show here): `docker compose logs -f worker_plan`
- View frontend logs: `docker compose logs -f frontend_gradio`

Troubleshooting
---------------
- If the pipeline stops immediately with missing module errors, rebuild with `--no-cache` so new files are inside the images.
- If you change environment variables (e.g., `WORKER_RELAY_PROCESS_OUTPUT`), restart: `docker compose down` then `docker compose up`.
- To clean out containers, network, and orphans: `docker compose down --remove-orphans`.

Environment notes
-----------------
- The worker exports logs to stdout when `WORKER_RELAY_PROCESS_OUTPUT=true` (set in `docker-compose.yml`).
- Shared volumes: `./run` is mounted into both services; `.env` and `llm_config.json` are mounted read-only. Ensure they exist on the host before starting.***
