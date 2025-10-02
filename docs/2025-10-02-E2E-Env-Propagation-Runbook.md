/**
 * Author: Codex using GPT-4o (CLI)
 * Date: 2025-10-02T00:00:00Z
 * PURPOSE: End-to-end environment propagation runbook and verification plan. Documents the three
 *          checkpoints (API -> handoff -> subprocess), the exact logs to expect, the Docker/Railway
 *          defaults we set today, and the local + Railway steps to prove real LLM calls occur.
 * SRP and DRY check: Pass. Single source for E2E env propagation & test procedure. References existing code
 *          (no duplication of logic), and complements docs/2025-10-02-Windows-Unicode-Subprocess-Fix.md.
 */

# 2025-10-02 E2E Env Propagation Runbook

## Goal

Prove/env‑trace that real API keys make it from:
- Parent FastAPI process → Subprocess environment → Luigi → OpenAI client.
Confirm we see a real request in the OpenAI dashboard for the prompt: “start a Danish restaurant in Vietnam”.

## What We Changed Today (To Remove Ambiguity)

- Docker defaults (both single + api images):
  - `PLANEXE_RUN_DIR=/tmp/planexe_run`, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`, `LUIGI_WORKERS=1`.
- Subprocess env (Windows + Linux):
  - Forces UTF‑8, OS‑appropriate `HOME`/cache (`/tmp` on Linux; USERPROFILE/TEMP on Windows).
  - Emits a debug line just before `Popen`: `DEBUG ENV: OPENAI_API_KEY present? True len=...`.
  - Captures child `stderr` to `run/<plan_id>/stderr.txt`.
  - Sets `OPENAI_LOG=debug` in the child so the OpenAI client logs requests.

## The Three Checkpoints (What to See)

1) API startup (parent has keys):
   - File: `planexe_api/api.py`
   - Logs: `[OK] OPENAI_API_KEY: Available` (and similarly for OpenRouter if set)

2) Handoff (parent → child):
   - File: `planexe_api/services/pipeline_execution_service.py`
   - Logs just before `Popen`:
     - `DEBUG ENV: OPENAI_API_KEY present? True len=…`
     - `DEBUG ENV: OPENROUTER_API_KEY present? True len=…` (if using OpenRouter)

3) Subprocess (child received keys and calls LLM):
   - File: `planexe/plan/run_plan_pipeline.py`
   - Logs: `🔥 LUIGI SUBPROCESS STARTED 🔥` … then OpenAI client debug lines (since `OPENAI_LOG=debug`).
   - If anything fails early, see `run/<plan_id>/stderr.txt`.

## Local Test Procedure (Windows or Linux)

1) Start API from repo root:
   - `uvicorn planexe_api.api:app --host 127.0.0.1 --port 8080 --log-level debug`
   - Confirm startup log shows `[OK] OPENAI_API_KEY: Available`.

2) Submit a plan (model must exist in `llm_config.json`):
   - `POST /api/plans` with JSON:
     ```json
     {
       "prompt": "start a Danish restaurant in Vietnam",
       "llm_model": "gpt-4.1-nano-2025-04-14",
       "speed_vs_detail": "fast_but_skip_details"
     }
     ```

3) Watch logs in this order:
   - API logs should print the `DEBUG ENV: OPENAI_API_KEY present? True len=…` lines immediately.
   - Within ~2–10s, the child logs should show `🔥 LUIGI SUBPROCESS STARTED 🔥` and then OpenAI client debug lines (HTTP).
   - On disk: `run/<plan_id>/log.txt` and, if errors, `run/<plan_id>/stderr.txt`.

4) OpenAI Dashboard timing:
   - The first LLM call typically occurs in one of the earliest tasks (RedlineGateTask/PremiseAttack), within ~5–20s after `/api/plans` returns.
   - Filter by model `gpt-4.1-nano-2025-04-14` (or your configured model) and keyword `Danish`/`Vietnam` in the prompt.

## Railway Test Procedure (Single Service)

1) Ensure the service builds from `docker/Dockerfile.railway.single`.

2) Set required variables in Railway (not .env):
   - `OPENAI_API_KEY` (or `OPENROUTER_API_KEY`), `DATABASE_URL`.

3) Deploy and create a plan from the UI with the exact prompt above.

4) Watch the three checkpoints in Railway logs:
   - `[OK] OPENAI_API_KEY: Available`.
   - `DEBUG ENV: OPENAI_API_KEY present? True len=…`.
   - `🔥 LUIGI SUBPROCESS STARTED 🔥` and OpenAI client debug lines.

## If Something Still Fails

- No `[OK] OPENAI_API_KEY: Available` on startup → the API process doesn’t see your keys. Fix service variables.
- No `DEBUG ENV: … present? True` before `Popen` → parent isn’t passing keys to child. This log exists now to prove/diagnose that.
- No `🔥 LUIGI SUBPROCESS STARTED 🔥` in child → inspect `run/<plan_id>/stderr.txt`.
- Child shows keys but no OpenAI logs → verify `llm_config.json` provider/model correctness and outbound network.

## Notes from Historical Behavior

- Working evidence: Sep 22–23 logs in `run/*/log.txt` showing successful OpenAI calls and task progression.
- Post Sep 23 changes: Simplified LLM config + factory, stronger env management, Railway single-service deployment. Today’s changes eliminate env ambiguity and add deterministic diagnostics.

## Definition of Done (E2E)

1) All three checkpoints show keys present.
2) OpenAI Dashboard displays requests for the exact test prompt.
3) `run/<plan_id>/log.txt` shows Luigi task progression.
4) Final plan completes without env‑related failures.

