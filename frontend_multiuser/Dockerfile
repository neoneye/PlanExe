FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLANEXE_CONFIG_PATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PYTHONPATH=/app/frontend_multiuser:/app/frontend_multiuser/src:/app/worker_plan_api

WORKDIR /app

# Copy application code and supporting files
COPY worker_plan/worker_plan_api /app/worker_plan_api
COPY worker_plan/worker_plan_api /app/frontend_multiuser/worker_plan_api
COPY database_api /app/database_api
COPY frontend_multiuser /app/frontend_multiuser
COPY README.md llm_config.json .env.example /app/

# Install dependencies from frontend_multiuser pyproject
RUN set -eux; \
    pip install --no-cache-dir --upgrade pip; \
    pip install --no-cache-dir --prefer-binary /app/frontend_multiuser

# Default location for generated plans
RUN mkdir -p /app/run

WORKDIR /app/frontend_multiuser

EXPOSE 5000

CMD ["python", "/app/frontend_multiuser/src/app.py"]
