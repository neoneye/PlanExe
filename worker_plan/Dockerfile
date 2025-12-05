FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLANEXE_CONFIG_PATH=/app \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies required for audio processing and building Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy application code and supporting files
COPY worker_plan /app/worker_plan
COPY README.md llm_config.json .env.example /app/

# Install PlanExe worker
RUN pip install --upgrade pip \
    && pip install --editable ./worker_plan

# Default location for generated plans
RUN mkdir -p /app/run

EXPOSE 8000

CMD ["uvicorn", "worker_plan.app:app", "--host", "0.0.0.0", "--port", "8000"]
