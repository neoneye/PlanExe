# worker_plan service

This directory hosts the shared `planexe` package and the FastAPI worker that executes the pipeline for the Gradio frontend.

- `planexe/`: core planning logic (moved out of `frontend_gradio`).
- `worker_plan_api/`: FastAPI app that starts/stops pipeline runs.

The worker is packaged from this directory (see `pyproject.toml`) and the frontend installs it as an editable dependency.
