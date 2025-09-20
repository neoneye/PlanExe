# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## File Header Template
Every file you create or edit should start with:
```
/**
 * Author: Your NAME  (Example: Claude Code using Sonnet 4)
 * Date: `timestamp`
 * PURPOSE: VERBOSE DETAILS ABOUT HOW THIS WORKS AND WHAT ELSE IT TOUCHES
 * SRP and DRY check: Pass/Fail Is this file violating either? Do these things already exist in the project?  Did you look??
 */
```

## Common Commands

### Python Backend Commands
```bash
# Install development dependencies
pip install -e '.[gradio-ui,flask-ui]'

# Run main Gradio interface (primary UI)
python -m planexe.plan.app_text2plan

# Run Flask interface (experimental)
python -m planexe.ui_flask.app

# Start FastAPI server (production backend)
# Run from project root:
DATABASE_URL="sqlite:///./planexe.db" uvicorn planexe_api.api:app --reload --port 8000

# Run all tests
python test.py

# Run planning pipeline directly
python -m planexe.plan.run_plan_pipeline

# Resume existing pipeline run
RUN_ID_DIR=/path/to/run python -m planexe.plan.run_plan_pipeline
```

### Frontend Commands (NextJS)
```bash
cd planexe-frontend

# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build

# Start production server
npm run start

# Lint code
npm run lint

# Run tests
npm run test

# Run integration tests
npm run test:integration
```

### Git Commands
You need to Git add and commit any changes you make to the codebase. Be detailed in your commit messages.


## Project Overview

PlanExe is an AI-powered planning system that transforms high-level ideas into detailed strategic and tactical plans. The system consists of a Python backend with Luigi pipeline orchestration and a NextJS frontend.

## Multi-Tier Architecture

```
┌─────────────────────────┐
│   NextJS Frontend       │  ← React UI (planexe-frontend/)
│   (port 3000)          │
└─────────┬───────────────┘
          │ HTTP/SSE
┌─────────▼───────────────┐
│   FastAPI Backend       │  ← REST API (planexe_api/)
│   (port 8000)          │
└─────────┬───────────────┘
          │ Subprocess
┌─────────▼───────────────┐
│   Luigi Pipeline        │  ← Core processing (planexe/plan/)
│   (47 orchestrated     │
│    tasks)               │
└─────────┬───────────────┘
          │ File I/O
┌─────────▼───────────────┐
│   File System          │  ← Generated outputs (run/)
│   + PostgreSQL         │
└─────────────────────────┘
```

### Core Components

1. **NextJS Frontend** (`planexe-frontend/`)
   - React-based web interface
   - Real-time progress monitoring via Server-Sent Events
   - Direct API client (no proxy routes)
   - TypeScript with Zod validation

2. **FastAPI Backend** (`planexe_api/`)
   - Production-grade REST API
   - Server-Sent Events for real-time progress
   - PostgreSQL integration with SQLAlchemy
   - Subprocess orchestration of Luigi pipeline

3. **Luigi Pipeline** (`planexe/plan/`)
   - 47 orchestrated tasks for plan generation
   - File-based I/O for all artifacts
   - Multi-provider LLM integration
   - Comprehensive report generation

### Key Modules
- `planexe/plan/` - Core planning logic and Luigi pipeline orchestration
- `planexe/prompt/` - Prompt catalog and management
- `planexe/llm_util/` - LLM abstraction and utilities
- `planexe/expert/` - Expert-based cost estimation and analysis
- `planexe/report/` - Report generation (HTML, PDF)
- `planexe/schedule/` - Timeline and Gantt chart generation
- `planexe/ui_flask/` - Alternative Flask web interface (experimental)
- `planexe/assume/` - Assumption identification and validation

## Development Workflow

### Full-Stack Development Setup
```bash
# 1. Install Python dependencies
pip install -e '.[gradio-ui,flask-ui]'

# 2. Start FastAPI backend (Terminal 1)
# Run from project root:
DATABASE_URL="sqlite:///./planexe.db" uvicorn planexe_api.api:app --reload --port 8000

# 3. Start NextJS frontend (Terminal 2)
cd planexe-frontend
npm install && npm run dev
```

### Alternative UI Options
```bash
# Gradio interface (standalone)
python -m planexe.plan.app_text2plan

# Flask interface (experimental)
python -m planexe.ui_flask.app
```

### Testing
```bash
# Python tests
python test.py

# Frontend tests
cd planexe-frontend
npm run test
npm run test:integration

# Test files located in:
# - planexe/plan/tests/
# - planexe/prompt/tests/
# - planexe/llm_util/tests/
# - planexe-frontend/test/
```

## Configuration

### Environment Setup
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys and settings
```

### Key Configuration Files
- **`llm_config.json`** - LLM providers and models configuration
- **`.env`** - Environment variables and API keys
- **`planexe_api/alembic.ini`** - Database migration configuration

### Important Environment Variables
- `OPENROUTER_API_KEY` - For OpenRouter LLM provider
- `RUN_ID_DIR` - For resuming pipeline runs
- `IS_HUGGINGFACE_SPACES` - Deployment mode flag
- `DATABASE_URL` - PostgreSQL connection string (FastAPI only)

## Critical Architecture Notes

### Frontend-Backend Communication
**IMPORTANT**: The NextJS frontend should connect **directly** to the FastAPI backend. Do not create NextJS API proxy routes - they duplicate functionality and break the architecture.

```typescript
// CORRECT: Direct FastAPI client
const response = await fetch('http://localhost:8000/api/plans', {
  method: 'POST',
  body: JSON.stringify({
    prompt: userInput,
    llm_model: selectedModel,
    speed_vs_detail: "FAST_BUT_BASIC"  // Use snake_case
  })
});

// WRONG: NextJS API proxy routes
// These should not exist in app/api/ directory
```

### Field Name Conventions
The FastAPI backend uses **snake_case** field names. Frontend should match this exactly:

| Use This (snake_case) | Not This (camelCase) |
|---------------------|---------------------|
| `llm_model` | `llmModel` |
| `speed_vs_detail` | `speedVsDetail` |
| `openrouter_api_key` | `openrouterApiKey` |
| `plan_id` | `planId` |

### Real-Time Progress
Use Server-Sent Events for real-time progress updates:
```typescript
const eventSource = new EventSource(`/api/plans/${planId}/stream`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  setProgress(data.progress_percentage);
};
```

### Key Entry Points
- **FastAPI Server**: `planexe_api/api.py` (501 lines) - Production backend
- **Luigi Pipeline**: `planexe/plan/run_plan_pipeline.py` (3520 lines) - Core processing
- **NextJS Frontend**: `planexe-frontend/src/` - React UI
- **Gradio Alternative**: `planexe/plan/app_text2plan.py` - Standalone UI

### Pipeline Data Flow
1. **HTTP Request** → FastAPI backend receives plan creation request
2. **Subprocess Launch** → FastAPI spawns Luigi pipeline as subprocess
3. **File-Based Processing** → 47 Luigi tasks generate artifacts in `run/` directory
4. **Server-Sent Events** → Real-time progress streamed to frontend
5. **File Downloads** → Generated reports and files served via FastAPI

### Critical Files to Understand
- `docs/FRONTEND-ARCHITECTURE-FIX-PLAN.md` - Frontend connection guide
- `planexe_api/models.py` - Pydantic schemas for API
- `planexe/llm_factory.py` - LLM provider abstraction
- `llm_config.json` - LLM provider configurations