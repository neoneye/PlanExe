/**
 * Author: Codex using GPT-4o (CLI)
 * Date: 2025-10-02T00:00:00Z
 * PURPOSE: Findings + fixes to get PlanExe running locally on Windows and clarify Railway implications.
 *          Root issue locally: Unicode/console encoding crash in Luigi subprocess before logger setup.
 *          Fix: Force UTF-8 in subprocess and set OS-appropriate HOME/cache paths on Windows. Keep LUIGI_WORKERS=1.
 * SRP and DRY check: Pass. Single document summarizing today’s diagnosis and concrete remediation steps.
 */

# 2025-10-02 Windows Subprocess Encoding + Env Fix

## Summary

Local Windows runs via FastAPI → subprocess failed immediately (exit code 3221225794) before `log.txt` was created. Manual runs of the same pipeline module succeed when Python’s IO is forced to UTF-8 and a valid model id from `llm_config.json` is used. The early crash is caused by Unicode emoji prints at Luigi startup encountering a non‑UTF‑8 console encoding inside the subprocess.

Additionally, the current subprocess environment unconditionally sets Linux paths for `HOME`, `OPENAI_CACHE_DIR`, and `LUIGI_CONFIG_PATH` (`/tmp/...`), which is not ideal on Windows and can contribute to early failures.

## What I Observed

- API health: OK at `http://127.0.0.1:8080/health`.
- Plan creation works; run directory is created with input files.
- API‑run subprocess on Windows: immediate failure `exit code 3221225794`, no `log.txt`.
- Manual module run with env set:
  - Setting `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` avoids Unicode crash.
  - Using a valid model id from `llm_config.json` (e.g., `gpt-4.1-nano-2025-04-14`) proceeds until LLM calls.
  - `log.txt` and early outputs are produced.

## Root Cause (Local)

Unicode prints (emoji) at pipeline startup combined with non‑UTF‑8 console encoding in Windows subprocess cause a crash before logging is initialized. Also, Linux‑specific `HOME`/cache paths aren’t appropriate on Windows.

## Fix Implemented

In `planexe_api/services/pipeline_execution_service.py` we now:
- Always set `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` in the subprocess environment.
- On Windows, set `HOME`, `OPENAI_CACHE_DIR`, and `LUIGI_CONFIG_PATH` to safe, writable Windows paths using `%USERPROFILE%`/`%TEMP%` and ensure directories exist.
- Preserve existing Railway‑friendly `/tmp` paths for Linux.
- Keep `LUIGI_WORKERS=1` as the reliable default and `no_lock=True` in Luigi build.

This avoids touching the Luigi pipeline (which is flagged Do‑Not‑Modify).

## Railway Notes

- Use `PLANEXE_RUN_DIR=/tmp/planexe/run` to avoid writing under `/app` at runtime.
- Set `LUIGI_WORKERS=1` and keep `no_lock=True`.
- Real API keys required for full runs.

## How To Test Locally (Windows)

1) Start backend from repo root:
   - `uvicorn planexe_api.api:app --reload --port 8080`

2) Submit a plan:
   - POST `http://127.0.0.1:8080/api/plans`
   - `{ "prompt": "Local verification", "llm_model": "gpt-4.1-nano-2025-04-14", "speed_vs_detail": "fast_but_skip_details" }`

3) Verify outputs:
   - `run/<plan_id>/log.txt` exists and shows early Luigi logs.
   - With real API keys, tasks proceed beyond LLM stages.

If you still want to run the module manually for diagnosis:
- Set env: `RUN_ID_DIR`, `SPEED_VS_DETAIL`, `LLM_MODEL`
- Ensure `PYTHONIOENCODING=utf-8`/`PYTHONUTF8=1`
- Run: `python -m planexe.plan.run_plan_pipeline`

## Status

- Local Windows: Subprocess now avoids Unicode crashes; pipeline initializes and logs.
- Railway: Use `/tmp` run dir, workers=1; should be consistent with prior deployment docs.

