/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-10-01T19:50:00-04:00
 * PURPOSE: Diagnostic guide for luigi.build() hanging issue on Railway
 * SRP and DRY check: Pass - Focused diagnostic for specific hang scenario
 */

# Luigi Build Hang Diagnostic

## Problem

`luigi.build()` hangs after checking all task dependencies. It never starts executing tasks.

**Current symptoms**:
```
🔥 About to call luigi.build() with workers=1
[Luigi checks all 61 task dependencies - takes ~1 second]
[Then... nothing. No further logs. Process hangs forever.]
luigi_build_return_value=None
```

---

## New Diagnostic Logging (Commit 4668ee9)

### 1. Task Execution Detection
**Added to `PlanTask.run()`**:
```python
logger.error(f"🔥 {self.__class__.__name__}.run() CALLED - Luigi worker IS running!")
```

**What this tells us**:
- If you see this → Luigi worker thread IS executing tasks ✅
- If you DON'T see this → Luigi worker never started ❌

### 2. Luigi Build Exception Handling
**Wrapped `luigi.build()` in try/except**:
```python
try:
    self.luigi_build_return_value = luigi.build(...)
except Exception as e:
    logger.error(f"🔥 luigi.build() raised exception: {e}")
```

**What this tells us**:
- If you see exception → Luigi failing but error was hidden
- If you DON'T see exception → Luigi hanging in infinite loop

### 3. Luigi Verbose Logging
**Enabled Luigi's built-in logging**:
```python
log_level='INFO',
detailed_summary=True
```

**What this tells us**:
- Luigi will log its internal state
- "Informed scheduler that task X has status Y"
- "Worker X running task Y"

---

## What to Look For in Railway Logs

### Scenario A: Worker Never Starts (Most Likely)

**Logs**:
```
🔥 About to call luigi.build() with workers=1
🔥 Luigi will build task: FullPlanPipeline(...)
🔥 Task parameters: run_id_dir=..., speedvsdetail=FAST_BUT_SKIP_DETAILS
🔥 Enabled Luigi INFO logging
🔥 Calling luigi.build() NOW...
2025-10-01 19:36:35 - luigi-interface - DEBUG - Checking if StartTimeTask(...) is complete
2025-10-01 19:36:35 - luigi-interface - DEBUG - Checking if SetupTask(...) is complete
[...checks all 61 tasks...]
[NO FURTHER LOGS - HANGS HERE]
```

**What this means**:
- Luigi builds dependency graph ✅
- Luigi checks all task completions ✅
- Luigi worker thread NEVER STARTS ❌

**Root cause**:
- Worker thread deadlocked or not spawning
- Likely issue with `workers=1` in subprocess context
- May need to use `workers=0` (synchronous execution)

---

### Scenario B: Worker Starts, Task Fails

**Logs**:
```
🔥 Calling luigi.build() NOW...
[Luigi dependency checks]
2025-10-01 19:36:36 - luigi - INFO - Worker X running StartTimeTask
🔥 StartTimeTask.run() CALLED - Luigi worker IS running!
🔥 StartTimeTask.run() FAILED: [error message]
🔥 luigi.build() raised exception: ...
```

**What this means**:
- Worker started successfully ✅
- Task execution began ✅
- Task crashed ❌

**Root cause**:
- First task (StartTimeTask) is failing
- Error in task implementation or environment

---

### Scenario C: Luigi Raises Exception

**Logs**:
```
🔥 Calling luigi.build() NOW...
[Luigi dependency checks]
🔥 luigi.build() raised exception: RuntimeError: ...
```

**What this means**:
- Luigi itself crashed
- Exception was being swallowed before

**Root cause**:
- Bug in Luigi
- Incompatible Luigi version
- Configuration error

---

### Scenario D: Tasks Complete Instantly (Leftover Files)

**Logs**:
```
🔥 Calling luigi.build() NOW...
[Luigi dependency checks]
2025-10-01 19:36:36 - luigi - INFO - All tasks completed successfully
🔥 luigi.build() returned!
🔥 luigi.build() COMPLETED with return value: True
```

**NO task run() logs**

**What this means**:
- Luigi thinks all tasks already complete
- Output files exist from previous run

**Root cause**:
- `/tmp/planexe_run/` has leftover files
- Luigi checks file existence, sees files, skips tasks

---

## Fixes for Each Scenario

### Fix for Scenario A (Worker Not Starting)

**Problem**: `workers=1` not spawning worker thread in subprocess

**Solution**: Use synchronous execution instead

```python
# Change this:
luigi.build([task], local_scheduler=True, workers=1)

# To this:
luigi.build([task], local_scheduler=True, workers=0)  # Synchronous
```

Or use Luigi's WorkerSchedulerFactory:
```python
from luigi.worker import Worker
worker = Worker(scheduler=scheduler, worker_processes=1)
worker.run()
```

---

### Fix for Scenario B (Task Failing)

**Problem**: Task crashes during execution

**Solution**: Fix the specific task error shown in logs

Check:
1. Database connection working?
2. API keys set?
3. File permissions correct?

---

### Fix for Scenario C (Luigi Exception)

**Problem**: Luigi itself crashing

**Solution**: Update Luigi or fix configuration

```bash
# Check Luigi version
pip show luigi

# Update if needed
pip install --upgrade luigi
```

---

### Fix for Scenario D (Leftover Files)

**Problem**: Output files exist, Luigi skips tasks

**Solution**: Clear run directory before each plan

```python
# In pipeline_execution_service.py, _write_pipeline_inputs():
if run_id_dir.exists():
    import shutil
    shutil.rmtree(run_id_dir)
run_id_dir.mkdir(parents=True)
```

---

## Immediate Next Steps

### 1. Deploy to Railway
```bash
git push origin ui
# Railway auto-deploys
```

### 2. Create Test Plan

Use Railway UI or curl:
```bash
railway run curl -X POST http://localhost:8080/api/plans \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Test plan", "llm_model": "gpt-4o-mini"}'
```

### 3. Watch Logs

Railway logs console:
```bash
railway logs --tail | grep "🔥"
```

Look for these critical messages:

| Message | Meaning |
|---------|---------|
| `🔥 Calling luigi.build() NOW...` | Luigi about to start |
| `🔥 XTask.run() CALLED` | Worker executing tasks ✅ |
| `🔥 luigi.build() raised exception` | Luigi crashed |
| `🔥 luigi.build() COMPLETED` | Luigi finished successfully |

### 4. Identify Scenario

Compare your logs to Scenarios A-D above.

### 5. Apply Fix

Implement the fix for your identified scenario.

---

## My Hypothesis

Based on the logs you provided, I believe this is **Scenario A: Worker Never Starts**.

**Evidence**:
- ✅ Luigi checks all dependencies (completes dependency graph)
- ❌ No task run() logs (worker never executes)
- ❌ No luigi.build() completion (hangs indefinitely)
- ❌ luigi_build_return_value=None (never returns)

**Most Likely Fix**:
Change `workers=1` to `workers=0` (synchronous execution) to avoid worker thread issues in subprocess.

---

## Quick Command Reference

```bash
# Deploy
git push origin ui

# Watch logs
railway logs --tail | grep "🔥"

# Test plan creation
railway run curl -X POST http://localhost:8080/api/plans \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Test", "llm_model": "gpt-4o-mini"}'

# Check DATABASE_URL
railway run python -c "import os; print(os.environ.get('DATABASE_URL')[:50])"

# List run directory contents
railway run ls -la /tmp/planexe_run/
```

---

**Status**: ⏳ Ready for Railway deployment and log analysis
**Expected Resolution Time**: 5-10 minutes to identify scenario
**Priority**: 🔴 CRITICAL - Blocking all plan generation
