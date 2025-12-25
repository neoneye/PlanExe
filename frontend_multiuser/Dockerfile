FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLANEXE_CONFIG_PATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1

WORKDIR /app

# Copy application code and supporting files
COPY worker_plan /app/worker_plan
COPY frontend_multiuser /app/frontend_multiuser
COPY README.md llm_config.json .env.example /app/

# Install dependencies from worker_plan (PlanExe) and frontend_multiuser pyproject
RUN set -eux; \
    pip install --no-cache-dir --upgrade pip; \
    pip install --no-cache-dir --prefer-binary /app/worker_plan; \
    python -c "import tomllib, pathlib; deps=tomllib.loads(pathlib.Path('/app/frontend_multiuser/pyproject.toml').read_text())['project']['dependencies']; pathlib.Path('/tmp/frontend_multiuser-requirements.txt').write_text('\\n'.join(deps))"; \
    pip install --no-cache-dir --prefer-binary -r /tmp/frontend_multiuser-requirements.txt; \
    rm /tmp/frontend_multiuser-requirements.txt

# Default location for generated plans
RUN mkdir -p /app/run

WORKDIR /app/frontend_multiuser

EXPOSE 5000

CMD ["python", "/app/frontend_multiuser/src/app.py"]
