FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLANEXE_CONFIG_PATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy dependency list early for better caching
COPY frontend_gradio/requirements.txt /app/frontend_gradio/requirements.txt

# Install dependencies for the Gradio UI using binary wheels where possible.
# Use a buildx cache mount so downloads/build artifacts don’t bloat the image layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    TMPDIR=/root/.cache/pip/tmp \
    pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefer-binary --requirement /app/frontend_gradio/requirements.txt

# Copy application code and supporting files
COPY worker_plan/worker_plan_api /app/worker_plan_api
COPY frontend_gradio /app/frontend_gradio
COPY README.md llm_config.json .env.example /app/

# Default location for generated plans
RUN mkdir -p /app/run

EXPOSE 7860

CMD ["python", "/app/frontend_gradio/app_text2plan.py"]
