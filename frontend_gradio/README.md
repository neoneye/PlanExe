# Frontend Gradio

This directory contains the PlanExe Gradio frontend.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `PLANEXE_WORKER_PLAN_URL` | `http://worker_plan:8000` | Base URL for `worker_plan` service the UI calls. |
| `PLANEXE_WORKER_PLAN_TIMEOUT` | `30` | HTTP timeout (seconds) for `worker_plan` requests. |
| `PLANEXE_GRADIO_SERVER_NAME` | `0.0.0.0` | Host/interface Gradio binds to. |
| `PLANEXE_GRADIO_SERVER_PORT` | `7860` | Port Gradio listens on. |
| `PLANEXE_OPEN_DIR_SERVER_URL` | *(unset)* | URL of the host opener service for “Open Output Dir”; leave unset to hide the button. |
