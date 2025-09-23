# HOW PLANEXE ACTUALLY WORKS

**THE BRUTAL TRUTH: This is way more complicated than it should be.**

## The 3-Layer System

### Layer 1: Next.js Frontend (Port 3000)
- **What it does**: Pretty UI forms where you type your plan idea
- **What it DOESN'T do**: Any actual AI planning work
- **Location**: `planexe-frontend/` directory

### Layer 2: FastAPI Backend (Port 8000)
- **What it does**: HTTP API that receives plan requests from frontend
- **What it DOESN'T do**: Any actual AI planning work either!
- **What it ACTUALLY does**: Spawns a Python subprocess to run the Luigi pipeline
- **Location**: `planexe_api/` directory
- **Key file**: `planexe_api/api.py` line 215-239 spawns the subprocess

### Layer 3: Luigi Pipeline (Python subprocess)
- **What it does**: The ACTUAL AI planning work (61 interconnected tasks)
- **How it starts**: FastAPI spawns it with `python -m planexe.plan.run_plan_pipeline`
- **Location**: `planexe/` directory (the core pipeline)
- **Key file**: `planexe/plan/run_plan_pipeline.py`

## The Data Flow (What Actually Happens)

```
1. User types plan in Next.js UI
2. Next.js sends HTTP request to FastAPI (port 8000)
3. FastAPI creates a run directory in `run/`
4. FastAPI writes initial files (START_TIME, INITIAL_PLAN)
5. FastAPI spawns subprocess: `python -m planexe.plan.run_plan_pipeline`
6. Luigi pipeline (subprocess) reads files from run directory
7. Luigi pipeline executes 61 AI tasks, writing output files
8. FastAPI streams Luigi's stdout back to frontend in real-time
9. User sees progress in the UI terminal
```

## How to Actually Start This Thing

### Step 1: Start Both Servers
```bash
cd planexe-frontend
npm run go
```

This single command starts:
- **FastAPI backend** on port 8000 (from project root)
- **Next.js frontend** on port 3000 (from planexe-frontend)

### Step 2: Verify It's Working
- Open browser to http://localhost:3000
- Check that FastAPI is running: http://localhost:8000/health

### Step 3: Create a Plan
- Fill out the form in the UI
- Submit it
- Watch the terminal in the UI for Luigi pipeline output

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

1. **Luigi subprocess fails to start** - check Python imports
2. **Luigi can't find API keys** - environment variable inheritance issue
3. **Luigi tasks fail** - check `run/{plan_id}/log.txt`
4. **Frontend can't connect** - FastAPI not running on port 8000
5. **No progress updates** - Luigi subprocess died silently

## Debug Commands

```bash
# Check if both servers are running
netstat -an | findstr :3000  # Next.js
netstat -an | findstr :8000  # FastAPI

# Test FastAPI health
curl http://localhost:8000/health

# Test Luigi pipeline manually (from project root)
python -m planexe.plan.run_plan_pipeline

# Check recent plan logs
dir run
type run\{latest_plan_id}\log.txt
```

## The Real Problem

**Nobody documented this 3-layer architecture.** The previous developers built:
1. A Luigi pipeline (the actual AI work)
2. A FastAPI wrapper (subprocess manager)
3. A Next.js frontend (pretty UI)

But they never clearly explained that FastAPI is just a subprocess launcher, not the actual AI engine.

**Bottom Line**: You need ALL THREE layers running for anything to work.