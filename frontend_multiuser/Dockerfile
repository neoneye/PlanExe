FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1

WORKDIR /app

# Install runtime dependencies
COPY frontend_multiuser/requirements.txt /app/frontend_multiuser/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/frontend_multiuser/requirements.txt

# Copy the Flask app into the image
COPY frontend_multiuser /app/frontend_multiuser

WORKDIR /app/frontend_multiuser

EXPOSE 5000

CMD ["python", "/app/frontend_multiuser/app.py"]
