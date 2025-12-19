#!/usr/bin/env sh
set -e

# Make the shared API package importable
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)/worker_plan"

# Sensible defaults for the Gradio UI
export PLANEXE_CONFIG_PATH="${PLANEXE_CONFIG_PATH:-$(pwd)}"
export PLANEXE_GRADIO_SERVER_NAME="${PLANEXE_GRADIO_SERVER_NAME:-0.0.0.0}"
export PLANEXE_GRADIO_SERVER_PORT="${PLANEXE_GRADIO_SERVER_PORT:-7860}"
export PLANEXE_WORKER_PLAN_URL="${PLANEXE_WORKER_PLAN_URL:-http://worker_plan:8000}"

python frontend_gradio/app.py
