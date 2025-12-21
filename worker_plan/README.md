# worker_plan service

This directory hosts the shared `planexe` package and the FastAPI worker that executes the pipeline for the Gradio frontend.

- `planexe/`: core planning logic.
- `worker_plan_api/`: shared types (e.g., filenames) used by both the worker and frontend.

## Run locally with a venv

For a faster edit/run loop without Docker. Work from inside `worker_plan` so its dependencies stay isolated (they may be incompatible with `frontend_gradio`):

```bash
cd worker_plan
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
uvicorn worker_plan.app:app --host 0.0.0.0 --port 8000
```

The frontend can then point at `http://localhost:8000` via `PLANEXE_WORKER_PLAN_URL`.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `PLANEXE_RUN_DIR` | `run` | Directory under which run output folders are created. |
| `PLANEXE_HOST_RUN_DIR` | *(unset)* | Optional host path base returned in `display_run_dir` to hint where runs live on the host. |
| `PLANEXE_CONFIG_PATH` | `.` | Working directory for the pipeline; used as the `cwd` when spawning `planexe.plan.run_plan_pipeline`. |
| `PLANEXE_WORKER_RELAY_PROCESS_OUTPUT` | `false` | When `true`, pipe pipeline stdout/stderr to the worker logs instead of suppressing them. |
| `PLANEXE_PURGE_ENABLED` | `false` | Enable the background scheduler that purges old run directories. |
| `PLANEXE_PURGE_MAX_AGE_HOURS` | `1` | Maximum age (hours) of runs to delete when purging (scheduler and manual default). |
| `PLANEXE_PURGE_INTERVAL_SECONDS` | `3600` | How often the purge scheduler runs when enabled. |
| `PLANEXE_PURGE_RUN_PREFIX` | `PlanExe_` | Only purge runs whose IDs start with this prefix. |
