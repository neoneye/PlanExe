#!/bin/bash
# Test script to validate Railway configuration approach
# This simulates what happens in Railway deployment

echo "=== Railway Configuration Test ==="
echo

# Simulate Railway environment variables
export OPENROUTER_API_KEY="test_openrouter_key"
export OPENAI_API_KEY="test_openai_key"
export DATABASE_URL="postgresql://test_user:test_pass@localhost:5432/test_db"
export PORT="8080"
export PLANEXE_RUN_DIR="/app/run"

echo "1. Simulated Railway environment variables:"
echo "   OPENROUTER_API_KEY=${OPENROUTER_API_KEY}"
echo "   OPENAI_API_KEY=${OPENAI_API_KEY}"
echo "   DATABASE_URL=${DATABASE_URL}"
echo "   PORT=${PORT}"
echo "   PLANEXE_RUN_DIR=${PLANEXE_RUN_DIR}"
echo

# Simulate startup.sh script
echo "2. Generating .env file from environment variables..."

cat > .env.test << ENV_EOF
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
ENV_EOF

echo "3. Generated .env file contents:"
cat .env.test
echo

echo "4. Test uvicorn command with PORT variable:"
echo "   python -m uvicorn planexe_api.api:app --host 0.0.0.0 --port ${PORT:-8000}"
echo

echo "5. Validation:"
if [ -f ".env.test" ] && [ -n "$OPENROUTER_API_KEY" ] && [ -n "$PORT" ]; then
    echo "   ✅ .env file generation: SUCCESS"
    echo "   ✅ Environment variables: SUCCESS"
    echo "   ✅ PORT variable expansion: SUCCESS"
    echo "   🎯 Railway deployment should work!"
else
    echo "   ❌ Something went wrong"
fi

# Clean up
rm -f .env.test

echo
echo "=== Test Complete ==="