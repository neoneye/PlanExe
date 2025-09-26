# HOW PLANEXE ACTUALLY WORKS

**Updated for Railway Single-Service Deployment (v0.2.0)**

## Architecture Overview

PlanExe uses different architectures for **development** vs **production**:

### Development (Local) - 3-Layer System
- **Next.js UI**: Port 3000 (separate dev server)
- **FastAPI API**: Port 8000 (with CORS enabled)
- **Luigi Pipeline**: Python subprocess (spawned by FastAPI)

### Production (Railway) - Single-Service System
- **FastAPI Server**: Port 8080 (serves both UI and API)
- **Static UI**: Served by FastAPI from `/ui_static/`
- **Luigi Pipeline**: Python subprocess (same as dev)

## The 3 Core Components

### Component 1: Next.js Frontend
- **What it does**: Pretty UI forms where you type your plan idea
- **Development**: Runs on port 3000 as separate server
- **Production**: Built as static files, served by FastAPI
- **Location**: `planexe-frontend/` directory

### Component 2: FastAPI Backend
- **What it does**: HTTP API + subprocess management + UI serving (prod only)
- **What it DOESN'T do**: Any actual AI planning work!
- **What it ACTUALLY does**: Spawns Luigi pipeline subprocess
- **Location**: `planexe_api/` directory
- **Key file**: `planexe_api/api.py`

### Component 3: Luigi Pipeline (Python subprocess)
- **What it does**: The ACTUAL AI planning work (61 interconnected tasks)
- **How it starts**: FastAPI spawns it with `python -m planexe.plan.run_plan_pipeline`
- **Location**: `planexe/` directory (the core pipeline)
- **Key file**: `planexe/plan/run_plan_pipeline.py`

## The Data Flow (What Actually Happens)

### Development Mode
```
1. User types plan in Next.js UI (localhost:3000)
2. Next.js sends CORS request to FastAPI (localhost:8000)
3. FastAPI creates a run directory in `run/`
4. FastAPI writes initial files (START_TIME, INITIAL_PLAN)
5. FastAPI spawns subprocess: `python -m planexe.plan.run_plan_pipeline`
6. Luigi pipeline (subprocess) reads files from run directory
7. Luigi pipeline executes 61 AI tasks, writing output files
8. FastAPI streams Luigi's stdout back to frontend in real-time
9. User sees progress in the UI terminal
```

### Production Mode (Railway)
```
1. User accesses FastAPI server (Railway provides URL on port 8080)
2. FastAPI serves static Next.js UI from /ui_static/
3. UI sends relative API requests (/api/plans) to same server
4. FastAPI creates a run directory in `run/`
5. FastAPI writes initial files (START_TIME, INITIAL_PLAN)
6. FastAPI spawns subprocess: `python -m planexe.plan.run_plan_pipeline`
7. Luigi pipeline (subprocess) reads files from run directory
8. Luigi pipeline executes 61 AI tasks, writing output files
9. FastAPI streams Luigi's stdout back to UI in real-time
10. User sees progress in the UI terminal
```

## How to Actually Start This Thing

### Local Development
```bash
cd planexe-frontend
npm run go
```

This command starts:
- **FastAPI backend** on port 8000 (with CORS enabled)
- **Next.js frontend** on port 3000 (separate dev server)

**Verify it's working:**
- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health

### Production-Like Testing (Single Service)
```bash
cd planexe-frontend
npm run build               # Build Next.js static export
cp -r out ../ui_static         # Copy to expected location
npm run serve:single           # Start FastAPI serving both UI + API
```

> Next.js 15 removes the standalone `next export`; `npm run build` already writes the static site to `out/`.
**Verify it's working:**
- Single service: http://localhost:8080
- Health check: http://localhost:8080/health

## The Luigi Pipeline Subprocess

**This is the part that actually does the work:**

- **Command**: `python -m planexe.plan.run_plan_pipeline`
- **Working directory**: Project root (`D:\1Projects\PlanExe`)
- **Input**: Reads from `run/{plan_id}/` directory
- **Output**: Writes 61 task outputs to same directory
- **Environment**: Inherits API keys from FastAPI process

## Why This is Confusing

1. **The frontend doesn't directly talk to Luigi** - it talks to FastAPI
2. **FastAPI doesn't do the AI work** - it just manages Luigi subprocesses
3. **Luigi runs as a separate Python process** - not imported as a library
4. **The real work happens in the subprocess** - invisible to the user

## What Can Go Wrong

### Development Mode Issues
1. **Luigi subprocess fails to start** - check Python imports
2. **Luigi can't find API keys** - environment variable inheritance issue
3. **Luigi tasks fail** - check `run/{plan_id}/log.txt`
4. **Frontend can't connect** - FastAPI not running on port 8000
5. **CORS errors** - FastAPI CORS not configured for localhost:3000
6. **No progress updates** - Luigi subprocess died silently

### Production Mode Issues
1. **White screen** - Static UI files not found at `/ui_static/`
2. **502 errors** - FastAPI not binding to correct PORT
3. **API calls fail** - UI using absolute URLs instead of relative paths
4. **Static assets 404** - Next.js static export missing files
5. **Luigi subprocess issues** - Same as development

## Debug Commands

### Development Mode
```bash
# Check if both servers are running
netstat -an | findstr :3000  # Next.js
netstat -an | findstr :8000  # FastAPI

# Test FastAPI health
curl http://localhost:8000/health

# Test CORS
curl -H "Origin: http://localhost:3000" http://localhost:8000/api/models
```

### Production Mode
```bash
# Check single service
netstat -an | findstr :8080  # Single FastAPI service

# Test health
curl http://localhost:8080/health

# Test static UI serving
curl http://localhost:8080/

# Check static files exist
ls ui_static/
```

### Universal Debug
```bash
# Test Luigi pipeline manually (from project root)
python -m planexe.plan.run_plan_pipeline

# Check recent plan logs
dir run
type run\{latest_plan_id}\log.txt

# Check environment variables
echo $PLANEXE_CLOUD_MODE
echo $PORT
```

## The Real Problem

**Nobody documented this 3-layer architecture.** The previous developers built:
1. A Luigi pipeline (the actual AI work)
2. A FastAPI wrapper (subprocess manager)
3. A Next.js frontend (pretty UI)

But they never clearly explained that FastAPI is just a subprocess launcher, not the actual AI engine.

**Bottom Line**: You need ALL THREE layers running for anything to work.