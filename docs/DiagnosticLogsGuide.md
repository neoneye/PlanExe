/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-10-01T18:35:00-04:00
 * PURPOSE: Guide to interpreting diagnostic logs for Luigi task execution failure
 * SRP and DRY check: Pass - Single responsibility for diagnostic log interpretation
 */

# Diagnostic Logs Guide - Luigi Task Execution Failure

## Problem Statement

**Symptom**: Luigi checks all task dependencies but never executes any tasks. No LLM calls reach OpenAI.

**What we know**:
- ✅ FastAPI starts successfully
- ✅ Luigi subprocess starts
- ✅ Luigi checks dependencies (logs show "Checking if X is complete")
- ❌ Luigi never runs tasks (no "Running X" messages)
- ❌ No OpenAI API calls made

---

## Diagnostic Logging Added

### 🔥 Key Log Messages

All diagnostic logs are prefixed with `🔥` for easy identification in Railway logs.

#### 1. **Luigi Subprocess Startup**
```
🔥 LUIGI SUBPROCESS STARTED 🔥
🔥 DATABASE_URL in subprocess: postgresql://postgres:...
🔥 OPENAI_API_KEY in subprocess: sk-proj-...
🔥 Total environment variables: 51
🔥 RUN_ID_DIR: /tmp/planexe_run/PlanExe_xxx
🔥 Logger configured, about to start Luigi pipeline...
```

**What this tells us**:
- Subprocess started successfully
- Environment variables ARE/AREN'T being passed
- API keys ARE/AREN'T available

#### 2. **Run Directory State**
```
🔥 Run directory exists with X files: ['file1.json', 'file2.md', ...]
🔥 Created 001-start_time.json
🔥 Created 002-initial_plan.txt
🔥 Run directory now contains 2 files: ['001-start_time.json', '002-initial_plan.txt']
```

**What this tells us**:
- Directory clean → Fresh run, no leftover files
- Directory has many files → Leftover files from crashed run causing Luigi to skip tasks

#### 3. **Luigi Build Execution**
```
🔥 About to call luigi.build() with workers=1
```

**What this tells us**:
- Luigi is about to start building the task graph

**IF YOU SEE THIS BUT NOT THE NEXT MESSAGE, LUIGI IS HANGING!**

#### 4. **Luigi Build Completion**
```
🔥 luigi.build() COMPLETED with return value: True
```

**What this tells us**:
- luigi.build() finished successfully
- Return value True = all tasks completed
- Return value False = some tasks failed

#### 5. **RedlineGateTask Execution** (First real LLM task)
```
🔥 RedlineGateTask.run_with_llm() CALLED - Luigi IS executing tasks!
🔥 RedlineGateTask: plan_id = PlanExe_xxx
🔥 RedlineGateTask: About to get database service...
🔥 RedlineGateTask: Database service obtained successfully
🔥 RedlineGateTask: Read plan prompt (X chars)
🔥 RedlineGateTask: About to create LLM interaction in database...
🔥 RedlineGateTask: LLM interaction X created successfully
🔥 RedlineGateTask: About to call RedlineGate.execute() with LLM...
🔥 RedlineGateTask: RedlineGate.execute() completed in X.XXs
```

**What this tells us**:
- Task execution reached the run_with_llm() method
- Database connection succeeded/failed
- LLM call succeeded/failed

---

## Diagnostic Scenarios

### Scenario 1: DATABASE_URL Not Set

**Logs you'll see**:
```
🔥 DATABASE_URL in subprocess: NOT SET
```

**Root cause**: DATABASE_URL environment variable not being passed to subprocess

**Fix**:
- Verify `environment["DATABASE_URL"] = database_url` in pipeline_execution_service.py
- Check Railway environment variables include DATABASE_URL
- Redeploy to Railway

---

### Scenario 2: Leftover Files from Previous Run

**Logs you'll see**:
```
🔥 Run directory exists with 50 files: ['001-start_time.json', '003-redline_gate.md', ...]
🔥 luigi.build() COMPLETED with return value: True
```

**NO RedlineGateTask logs** (because Luigi thinks task already complete)

**Root cause**: Output files from previous crashed run exist, Luigi skips tasks

**Fix**:
```python
# Add to _write_pipeline_inputs() in pipeline_execution_service.py
if run_id_dir.exists():
    import shutil
    shutil.rmtree(run_id_dir)  # Delete entire directory
run_id_dir.mkdir(parents=True)
```

---

### Scenario 3: luigi.build() Hanging

**Logs you'll see**:
```
🔥 About to call luigi.build() with workers=1
[NO FURTHER LOGS]
```

**Root cause**: Luigi is stuck in an infinite loop or deadlock

**Possible causes**:
- Database connection timeout (trying to connect to unreachable PostgreSQL)
- Worker thread deadlock
- Infinite dependency loop (shouldn't happen with Luigi)

**Fix**:
- Check PostgreSQL is accessible from Railway container
- Add timeout to database connection
- Check Luigi version for known bugs

---

### Scenario 4: Database Tables Missing

**Logs you'll see**:
```
🔥 RedlineGateTask: About to create LLM interaction in database...
[ERROR] SQLAlchemy error: table plan_content does not exist
```

**Root cause**: Database migration not run on Railway PostgreSQL

**Fix**:
```bash
railway run alembic upgrade head
```

Verify tables exist:
```bash
railway run python -c "from sqlalchemy import inspect; from planexe_api.database import engine; print(inspect(engine).get_table_names())"
```

---

### Scenario 5: API Keys Missing

**Logs you'll see**:
```
🔥 OPENAI_API_KEY in subprocess: NOT SET
🔥 RedlineGateTask: About to call RedlineGate.execute() with LLM...
[ERROR] OpenAI API key not set
```

**Root cause**: OPENAI_API_KEY not passed to subprocess

**Fix**:
- Verify `environment["OPENAI_API_KEY"] = value` in pipeline_execution_service.py
- Check Railway environment variables
- Redeploy

---

### Scenario 6: Tasks Already Complete

**Logs you'll see**:
```
🔥 luigi.build() COMPLETED with return value: True
```

**NO task execution logs** (no "RedlineGateTask.run_with_llm() CALLED")

**Root cause**: All output files exist, Luigi considers all tasks complete

**Why this happens**:
- Previous run completed successfully
- Output files persist in `/tmp/planexe_run/`
- Luigi checks file existence, sees all files, skips all tasks

**Fix**: Clean run directory before each plan (see Scenario 2)

---

## How to Use This Guide

### Step 1: Deploy to Railway
```bash
git push origin ui
# Railway auto-deploys
```

### Step 2: Create Test Plan

Use Railway logs console or CLI:
```bash
railway logs --tail
```

### Step 3: Search for 🔥 Messages

In Railway logs, filter for: `🔥`

### Step 4: Identify Scenario

Compare your logs to the scenarios above.

### Step 5: Apply Fix

Implement the fix for your scenario, commit, and redeploy.

---

## Expected Successful Flow

When everything works correctly, you'll see this sequence:

```
🔥 LUIGI SUBPROCESS STARTED 🔥
🔥 DATABASE_URL in subprocess: postgresql://postgres:xxx...
🔥 OPENAI_API_KEY in subprocess: sk-proj-xxx...
🔥 Total environment variables: 51
🔥 RUN_ID_DIR: /tmp/planexe_run/PlanExe_xxx
🔥 Logger configured, about to start Luigi pipeline...
🔥 Creating run directory: /tmp/planexe_run/PlanExe_xxx
🔥 Created 001-start_time.json
🔥 Created 002-initial_plan.txt
🔥 Run directory now contains 2 files: ['001-start_time.json', '002-initial_plan.txt']
🔥 About to call luigi.build() with workers=1

[Luigi logs: "Running StartTimeTask..."]
[Luigi logs: "Running SetupTask..."]
[Luigi logs: "Running RedlineGateTask..."]

🔥 RedlineGateTask.run_with_llm() CALLED - Luigi IS executing tasks!
🔥 RedlineGateTask: plan_id = PlanExe_xxx
🔥 RedlineGateTask: About to get database service...
🔥 RedlineGateTask: Database service obtained successfully
🔥 RedlineGateTask: Read plan prompt (150 chars)
🔥 RedlineGateTask: About to create LLM interaction in database...
🔥 RedlineGateTask: LLM interaction 123 created successfully
🔥 RedlineGateTask: About to call RedlineGate.execute() with LLM: OpenAI
🔥 RedlineGateTask: RedlineGate.execute() completed in 3.45s

[More task execution logs...]

🔥 luigi.build() COMPLETED with return value: True
```

---

## Quick Reference

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `DATABASE_URL: NOT SET` | Env var not passed | Check pipeline_execution_service.py |
| `Run directory exists with 50 files` | Leftover files | Clear directory before run |
| `About to call luigi.build()` but no completion | Luigi hanging | Check DB connection timeout |
| No RedlineGateTask logs | Tasks not running | Check output files exist |
| SQLAlchemy table error | Missing migration | Run `alembic upgrade head` |
| `OPENAI_API_KEY: NOT SET` | API key not passed | Check env vars in Railway |

---

## Next Steps

1. **Deploy diagnostic version to Railway**
2. **Create test plan via UI**
3. **Watch Railway logs** for 🔥 messages
4. **Identify which scenario matches** your logs
5. **Apply the fix** for that scenario
6. **Redeploy and test again**

Once the issue is fixed, we can remove the 🔥 diagnostic logs and add proper error handling.

---

**Status**: ⏳ Ready for Railway testing
**Expected time**: 5-10 minutes to identify root cause via logs
**Priority**: 🔴 CRITICAL - Blocking all plan generation on Railway
