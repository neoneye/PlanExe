FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLANEXE_CONFIG_PATH=/app \
    PLANEXE_RUN_DIR=/app/run \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PYTHONPATH=/app:/app/worker_plan_database:/app/database_api

WORKDIR /app

# Bring in the shared worker code, DB models, and this worker implementation.
COPY worker_plan /app/worker_plan
COPY worker_plan_database /app/worker_plan_database
COPY database_api /app/database_api
COPY README.md llm_config.json .env.example /app/

# Install the core planexe package plus Flask support and database drivers.
RUN set -eux; \
    pip install --no-cache-dir --upgrade pip; \
    pip install --no-cache-dir --prefer-binary /app/worker_plan[flask-ui]; \
    pip install --no-cache-dir --prefer-binary -r /app/worker_plan_database/requirements.txt

# Ensure output directories exist (mounted in docker-compose).
RUN mkdir -p /app/run /app/log

CMD ["python", "-m", "worker_plan_database.app"]
