FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLANEXE_CONFIG_PATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy dependency list early for better caching
COPY frontend_single_user/requirements.txt /app/frontend_single_user/requirements.txt

# Install dependencies for the Gradio UI using binary wheels where possible.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefer-binary --requirement /app/frontend_single_user/requirements.txt

# Copy application code and supporting files
COPY worker_plan/worker_plan_api /app/worker_plan_api
COPY frontend_single_user /app/frontend_single_user
COPY README.md llm_config.json .env.example /app/

# Default location for generated plans
RUN mkdir -p /app/run

EXPOSE 7860

CMD ["python", "/app/frontend_single_user/app.py"]
