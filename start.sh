#!/usr/bin/env sh
set -e

# Make the shared API package importable
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)/worker_plan"

# Sensible defaults for the Gradio UI
export PLANEXE_CONFIG_PATH="${PLANEXE_CONFIG_PATH:-$(pwd)}"
export GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}"
export GRADIO_SERVER_PORT="${GRADIO_SERVER_PORT:-7860}"
export WORKER_PLAN_URL="${WORKER_PLAN_URL:-http://worker_plan:8000}"

python frontend_gradio/app.py
