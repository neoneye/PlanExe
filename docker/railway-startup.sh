#!/bin/bash
set -e

echo "=== Railway Startup Script ==="
echo "Generating .env file from Railway environment variables..."

# Create .env file from Railway environment variables
cat > /app/.env << EOF
# Generated from Railway environment variables at startup
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
OPENAI_API_KEY=${OPENAI_API_KEY:-}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
GOOGLE_API_KEY=${GOOGLE_API_KEY:-}
PLANEXE_RUN_DIR=${PLANEXE_RUN_DIR:-/app/run}
PYTHONPATH=${PYTHONPATH:-/app}
PYTHONUNBUFFERED=${PYTHONUNBUFFERED:-1}
DATABASE_URL=${DATABASE_URL:-}
PORT=${PORT:-8000}
EOF

echo "Generated .env file:"
echo "===================="
cat /app/.env
echo "===================="

echo "Starting uvicorn server with PORT=${PORT:-8000}..."
exec "$@"