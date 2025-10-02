# Luigi Pipeline Hang Root Cause Analysis

**Date:** October 1, 2025
**Issue:** Luigi tasks stuck in PENDING status forever
**Root Cause:** `workers=0` parameter in `luigi.build()`   THIS MEANS NO WORKERS SPAWN!!!!

## The Problem

When running a plan, all 61 Luigi tasks would be scheduled as PENDING but never execute:

```
Luigi: 2025-10-01 23:25:08 - luigi-interface - INFO - Informed scheduler that task FullPlanPipeline has status PENDING
Luigi: 2025-10-01 23:25:08 - luigi-interface - INFO - Informed scheduler that task ReportTask has status PENDING  
Luigi: 2025-10-01 23:25:08 - luigi-interface - INFO - Informed scheduler that task PremortemTask has status PENDING
... [infinite hang, no tasks ever execute]
```

## Root Cause

In `planexe/plan/run_plan_pipeline.py` line 4668, the Luigi build was configured with:

```python
self.luigi_build_return_value = luigi.build(
    [self.full_plan_pipeline_task],
    local_scheduler=True,
    workers=0,  # ❌ THIS IS THE BUG
    log_level='INFO',
    detailed_summary=True
)
```

**The issue:** `workers=0` literally means **"no workers"** in Luigi, not "synchronous execution".

With zero workers:
- Luigi scheduler starts and analyzes the task dependency graph ✅
- Tasks are scheduled as PENDING ✅  
- **BUT** there are no worker threads to actually execute the tasks ❌
- Pipeline hangs forever waiting for workers that don't exist ❌

## The Fix

Changed `workers=0` to `workers=1`:

```python
self.luigi_build_return_value = luigi.build(
    [self.full_plan_pipeline_task],
    local_scheduler=True,
    workers=1,  # ✅ FIXED: One single worker executes tasks synchronously
    log_level='INFO',
    detailed_summary=True
)
```

**Why `workers=1` is correct:**
- Creates **one single worker thread**
- Worker executes tasks **synchronously** in dependency order
- Compatible with Railway subprocess environment
- Tasks actually get executed instead of hanging

## Previous Misunderstanding

The previous developer thought:
- `workers=0` = "synchronous execution" ❌ WRONG
- `workers=1` = "would spawn worker thread that fails in Railway" ❌ WRONG

**Reality:**
- `workers=0` = "no workers at all, nothing executes" ✅
- `workers=1` = "single worker, synchronous execution, works everywhere" ✅

## Verification

After the fix, Luigi should:
1. Schedule tasks as PENDING ✅
2. **Immediately start executing** the first task (StartTimeTask) ✅
3. Progress through dependency graph ✅
4. Complete all 61 tasks ✅

## Related Documents

- `docs/LuigiHangDiagnostic.md` - Diagnostic scenarios (this was Scenario A)
- `docs/LUIGI.md` - Luigi pipeline architecture
- `CHANGELOG.md` - Version history

## Commit Message

```
fix: Change Luigi workers=0 to workers=1 to enable task execution

ROOT CAUSE: workers=0 means "no workers" not "synchronous".
Tasks were scheduled but never executed (infinite PENDING hang).

FIX: workers=1 creates single synchronous worker that actually
executes tasks in dependency order.

🤖 Generated with Codebuff
Co-Authored-By: Codebuff <noreply@codebuff.com>
```
