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
COPY frontend_gradio /app/frontend_gradio
COPY README.md llm_config.json .env.example /app/

# Install PlanExe with the Gradio UI extras
RUN pip install --upgrade pip \
    && pip install --editable ./frontend_gradio[gradio-ui]

# Default location for generated plans
RUN mkdir -p /app/run

EXPOSE 7860

CMD ["python", "-m", "planexe.plan.app_text2plan"]
