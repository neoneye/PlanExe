# Luigi Pipeline Deadlock Investigation - Post Mortem
**Date**: October 2, 2025  
**Status**: UNRESOLVED  
**Time Invested**: ~3 hours of intensive debugging

---

## Executive Summary

The Luigi pipeline hangs indefinitely on Railway (production) after checking task dependencies. Locally, the pipeline fails with `returncode: 1` but doesn't hang. Multiple fixes were attempted including database timeouts, file locking, directory cleanup, and environment variable loading - **none resolved the core issue**.

**Critical Discovery**: The problem is **NOT** what we initially thought (leftover files, database deadlock, or missing cleanup). The Railway hang and local failure appear to be **different symptoms of the same root cause**: the Luigi subprocess cannot properly initialize or execute tasks.

---

## Timeline of Investigation

### Initial Hypothesis: Leftover Files Causing Luigi to Skip Tasks ❌
**Theory**: Luigi sees output files from previous runs, marks all tasks "complete", hangs forever  
**Evidence Against**: 
- Added directory cleanup that runs successfully (confirmed via `CLEANUP_RAN.txt` marker file)
- Only 5 files exist at startup (all input files, no output files)
- Luigi correctly identifies all tasks as "incomplete"

**Conclusion**: Directory cleanup works perfectly. This was NOT the problem.

---

### Second Hypothesis: Database Connection Deadlock ❌
**Theory**: SQLAlchemy connection pool exhaustion causing Luigi worker thread to block  
**Attempted Fix**: Added database connection timeout (5 seconds)
```python
# planexe_api/database.py
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5}  # 5 second timeout
)
```

**Result**: No change. Worker thread still blocks.

**Conclusion**: Database connections are not the bottleneck.

---

### Third Hypothesis: Luigi File Locking Deadlock in Containers ❌
**Theory**: Luigi's file-based locking mechanism fails in Railway's containerized environment  
**Attempted Fix**: Added `no_lock=True` to Luigi build
```python
# planexe/plan/run_plan_pipeline.py
luigi.build(
    [self.full_plan_pipeline_task],
    local_scheduler=True,
    workers=1,
    no_lock=True,  # Disable file locking
)
```

**Result**: No change. Worker thread still blocks.

**Conclusion**: Luigi's locking mechanism is not the problem.

---

### Fourth Hypothesis: Missing Environment Variables in Subprocess ✅ (Partial)
**Theory**: Environment variables not passed to Luigi subprocess  
**Discovery**: 
- Gradio UI (`app_text2plan.py`) never called `load_dotenv()`
- `.env` file existed but was never loaded
- Railway works because it injects env vars directly (not via `.env`)

**Attempted Fix**: Added `load_dotenv()` to Gradio
```python
# planexe/plan/app_text2plan.py
from dotenv import load_dotenv
load_dotenv()  # Load .env file for local development
```

**Result**: 
- ✅ `.env` file now loads correctly locally
- ❌ Subprocess still fails with `returncode: 1`
- ❌ Railway still hangs

**Conclusion**: Environment variables are now loaded, but something else is still broken.

---

## What We Know For Certain

### ✅ Working Correctly
1. **Directory Cleanup**: FastAPI successfully deletes old files before each run
2. **Environment Variable Loading**: `.env` file loads in Gradio after fix
3. **Luigi Dependency Graph**: Luigi successfully builds the task dependency tree
4. **Worker Thread Spawning**: Luigi's worker thread (Thread-1) spawns successfully
5. **Database Connection**: DATABASE_URL is set and accessible
6. **API Keys**: OPENAI_API_KEY and other keys are available in environment

### ❌ Broken
1. **Railway**: Luigi worker thread blocks **after** dependency checking, **before** executing any `task.run()` methods
2. **Local (Gradio)**: Luigi subprocess exits with `returncode: 1` after ~10 seconds
3. **Local (FastAPI)**: Not tested thoroughly - uvicorn startup failed due to path issues

### ⚠️ Unknown / Not Investigated
1. **What causes `returncode: 1` locally?** - No error logs because Luigi never creates `log.txt`
2. **Why different behavior on Railway vs local?** - Railway hangs, local exits with error
3. **What happens in the 10 seconds before local failure?** - No stderr captured in Gradio
4. **Does FastAPI work locally?** - Couldn't get uvicorn to start from correct directory

---

## Diagnostic Tools Added

### 1. Cleanup Verification Marker
```python
# planexe_api/services/pipeline_execution_service.py
cleanup_marker = run_id_dir / "CLEANUP_RAN.txt"
with open(cleanup_marker, "w") as f:
    f.write(f"Directory cleanup executed at {datetime.utcnow().isoformat()}\n")
```

**Check in Luigi subprocess**:
```python
# planexe/plan/run_plan_pipeline.py
cleanup_marker = self.run_id_dir / "CLEANUP_RAN.txt"
if cleanup_marker.exists():
    logger.error(f"🔥✅ CLEANUP_RAN.txt EXISTS - FastAPI cleanup executed")
```

**Result**: Confirmed cleanup runs successfully every time.

### 2. Thread Monitoring
```python
# planexe/plan/run_plan_pipeline.py
def monitor_threads():
    while True:
        time.sleep(2)
        threads = threading.enumerate()
        print(f"🔥 THREAD MONITOR: {len(threads)} active threads:")
        for t in threads:
            print(f"  - {t.name}: alive={t.is_alive()}, daemon={t.daemon}")
```

**Result**: Shows 4 threads active (MainThread, ThreadMonitor, TimeoutMonitor, Thread-1), but Thread-1 never executes tasks.

### 3. Timeout Warning
```python
# planexe/plan/run_plan_pipeline.py
def timeout_monitor():
    time.sleep(30)
    if self.luigi_build_return_value is None:
        print(f"🔥 WARNING: luigi.build() has been running for 30.0s without completing!")
```

**Result**: Confirms Luigi hangs for 30+ seconds on Railway without any task execution.

---

## Code Changes Made

### Files Modified
1. **`planexe_api/database.py`** - Added database connection timeout
2. **`planexe_api/services/pipeline_execution_service.py`** - Added cleanup marker file, enhanced logging
3. **`planexe/plan/run_plan_pipeline.py`** - Added `no_lock=True`, thread monitoring, timeout warnings
4. **`planexe/plan/app_text2plan.py`** - Added `load_dotenv()`, modified subprocess to capture stderr

### Commits Made
- `fix: Add database connection timeout to prevent Luigi worker deadlock`
- `CRITICAL FIX: Clean run directory before pipeline execution`
- `debug: Add marker file to prove FastAPI cleanup execution`
- `debug: Add logger.error() for directory cleanup visibility in Railway logs`

---

## What the Next Developer Should Try

### 1. **Capture the Actual Error Message (CRITICAL)**
The local subprocess exits with `returncode: 1` but we never see the error because:
- Gradio doesn't capture stderr properly
- Luigi fails before creating `log.txt`
- FastAPI wasn't tested due to startup issues

**Action**: Run Luigi directly with environment variables to see the actual error:
```powershell
$env:RUN_ID_DIR = "D:\1Projects\PlanExe\run\PlanExe_TEST"
$env:LLM_MODEL = "gpt-4.1-nano-2025-04-14"
$env:SPEED_VS_DETAIL = "fast_but_skip_details"
python -m planexe.plan.run_plan_pipeline
```

This will show the ACTUAL error message that's being hidden.

### 2. **Test with FastAPI Locally**
FastAPI has proper error handling and logging. Get uvicorn running correctly:
```powershell
# From project root (NOT planexe_api directory)
cd D:\1Projects\PlanExe
uvicorn planexe_api.api:app --reload --port 8080
```

Then create a plan via Next.js UI or Postman and watch the FastAPI logs.

### 3. **Check Windows Path Handling**
The `RUN_ID_DIR` environment variable might have Windows vs Unix path issues:
- Gradio uses relative paths (`run\PlanExe_...`)
- FastAPI uses absolute paths (`/tmp/planexe_run/...` on Railway)
- Luigi might expect one format but receive another

### 4. **Verify PipelineEnvironmentEnum Values**
Check that all required environment variables are actually set:
```python
# In run_plan_pipeline.py, add at the very start of execute_pipeline():
required_vars = ['RUN_ID_DIR', 'LLM_MODEL', 'SPEED_VS_DETAIL']
for var in required_vars:
    value = os.environ.get(var)
    print(f"ENV CHECK: {var} = {value}")
    if not value:
        raise ValueError(f"{var} is not set")
```

### 5. **Test Railway with Maximum Logging**
The Railway logs show Luigi checking dependencies but not executing. Add logging to EVERY task's `run()` method to see which task actually starts:
```python
def run(self):
    logger.error(f"🔥 {self.__class__.__name__}.run() CALLED")
    # ... rest of task code
```

If NO tasks show this message, Luigi's worker is deadlocked before ANY execution.

### 6. **Consider Luigi Version Issues**
Check if Luigi 3.6.0 has known issues with:
- Python 3.13 (requires-python = ">=3.13" in pyproject.toml)
- Windows multiprocessing
- Containerized environments

Try downgrading Luigi:
```bash
pip install luigi==3.5.0  # or earlier
```

### 7. **Nuclear Option: Bypass Luigi Threading Completely**
If all else fails, manually execute tasks in dependency order without Luigi's worker:
```python
# Instead of luigi.build()
task = FullPlanPipeline(...)
task.run()  # Execute directly in main thread
```

This is NOT recommended (breaks Luigi's dependency management) but would confirm if it's a threading issue.

---

## Relevant File Locations

### Logs to Check
- **Local Gradio**: No stderr captured (this is the problem!)
- **Local FastAPI**: Not tested
- **Railway**: Check Railway dashboard logs, search for "🔥" emojis
- **Luigi Pipeline**: `D:\1Projects\PlanExe\run\{run_id}\log.txt` (only exists if Luigi initializes)

### Key Code Files
- **Luigi Pipeline**: `planexe/plan/run_plan_pipeline.py` (5471 lines - DO NOT MODIFY TASK LOGIC)
- **FastAPI Subprocess**: `planexe_api/services/pipeline_execution_service.py`
- **Gradio UI**: `planexe/plan/app_text2plan.py`
- **Environment Loading**: `planexe/utils/planexe_dotenv.py`

### Configuration
- **Environment Variables**: `.env` file (not in git)
- **LLM Models**: `llm_config.json`
- **Database**: `DATABASE_URL` in `.env`

---

## Why This Is So Hard to Debug

1. **No Error Visibility**: Subprocess errors are swallowed by Gradio
2. **Different Symptoms**: Railway hangs, local exits - same root cause?
3. **Complex Architecture**: 3 layers (UI → FastAPI → Luigi subprocess)
4. **Logging Gaps**: Luigi logs don't appear until after initialization
5. **Environment Differences**: Railway (Linux, containerized) vs Local (Windows, native)

---

## Resources for Next Developer

### Documentation
- **`docs/LUIGI.md`** - Luigi pipeline documentation
- **`docs/RUN_PLAN_PIPELINE_DOCUMENTATION.md`** - Detailed pipeline guide
- **`docs/HOW-THIS-ACTUALLY-WORKS.md`** - System architecture overview
- **`docs/01Oct-LuigiWorkers0-RootCause.md`** - Previous worker debugging
- **`docs/1OctRailwayDebug.md`** - Railway-specific debugging notes

### Historical Context
- **Sep 23-27**: Multiple attempts to fix Railway hang (see `run/` directory for old plans)
- **Oct 1**: Extensive Luigi worker investigation (documented in `docs/01Oct-*.md`)
- **Oct 2**: This investigation (directory cleanup, env vars, locking)

### Old Test Plans
Directory `D:\1Projects\PlanExe\run` contains ~30 failed plan attempts with logs. Use these for testing - do NOT create fake data!

---

## Conclusion

**We made progress** in understanding what's NOT broken (cleanup, env vars, database), but we **did not** identify the root cause of the Luigi subprocess failure. The next developer needs to:

1. **See the actual error** (run Luigi directly with env vars)
2. **Test FastAPI locally** (better error handling than Gradio)
3. **Verify all environment variables** are correct format/values
4. **Check Luigi/Python version compatibility**

**This is a solvable problem** - the pipeline worked previously (there are successful plans in the repo). Something changed in the environment, configuration, or dependencies that broke Luigi subprocess execution.

---

**Document Author**: Cascade (Claude Sonnet 4)  
**Date**: October 2, 2025  
**Status**: Investigation incomplete - handoff to next developer
