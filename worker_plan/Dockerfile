FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLANEXE_CONFIG_PATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1

WORKDIR /app

# Copy application code and supporting files
COPY worker_plan /app/worker_plan
COPY README.md llm_config.json .env.example /app/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefer-binary /app/worker_plan

# Default location for generated plans
RUN mkdir -p /app/run

EXPOSE 8000

CMD ["uvicorn", "worker_plan.app:app", "--host", "0.0.0.0", "--port", "8000"]
