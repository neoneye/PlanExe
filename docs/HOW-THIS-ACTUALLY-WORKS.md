/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Accurate explanation of the PlanExe runtime topology for v0.3.2, covering local dev,
 *          Railway deployment, and fallback report behaviour.
 * SRP and DRY check: Pass - Focused on execution architecture; defers code-level detail to other docs.
 */
# How PlanExe Actually Works (v0.3.2)

PlanExe is a three-layer system: a Next.js UI, a FastAPI orchestration service, and a Luigi subprocess. This
note explains how those layers interact in development and on Railway now that the fallback report assembler
is live and Railway is stable.

## Architecture Snapshot

| Layer | Role | Location |
| --- | --- | --- |
| Next.js 15 frontend | Collects prompts, displays progress, downloads artefacts | `planexe-frontend/` |
| FastAPI backend | Launches Luigi subprocesses, streams progress, serves files | `planexe_api/` |
| Luigi pipeline | Executes 61 AI tasks, writes outputs to DB + filesystem | `planexe/` |

## Development Workflow (Local)
1. Run `npm run go` inside `planexe-frontend/`.
2. The script starts:
   - FastAPI (uvicorn) on `http://localhost:8080`.
   - Next.js dev server on `http://localhost:3000` with hot reload.
3. The UI sends direct `fetch` requests to FastAPI (no proxy routes).
4. FastAPI creates `run/PlanExe_<uuid>/`, seeds initial files, then spawns `python -m planexe.plan.run_plan_pipeline`.
5. Luigi executes tasks, writing to both the run directory and the database. Progress is published over SSE and
   WebSocket queues.
6. The frontend polls `/api/plans/{id}` and listens for SSE/WebSocket updates. If SSE drops (still a known
   issue), it reconnects or falls back to polling.

## Railway Deployment (Production)
1. Railway builds `docker/Dockerfile.railway.api` which:
   - Installs Node, builds the Next.js static export, and copies it to `/app/ui_static`.
   - Installs Python dependencies and launches FastAPI bound to Railway's `$PORT`.
2. A single Railway service serves both HTML and API requests from FastAPI.
3. `DATABASE_URL` points to the Railway Postgres instance; migrations are applied before deployment.
4. Environment variables are loaded through `PlanExeDotEnv` and merged into `os.environ` so the Luigi subprocess
   inherits API keys.
5. When a plan is created, Luigi runs identically to local mode. Because the filesystem is ephemeral, FastAPI now
   relies on the database-first writes introduced in v0.3.0 plus the fallback report assembler from v0.3.2 to
   guarantee deliverables survive pod restarts.

## Data Flow Summary
```
User -> Next.js (3000 dev / 8080 prod) -> FastAPI (spawns subprocess) -> Luigi pipeline ->
  write outputs to run/<plan_id>/ and plan_content table -> FastAPI serves artefacts -> UI downloads
```

## Key Behaviours
- **Fallback Reports**: If `ReportTask` fails, FastAPI still produces `/api/plans/{id}/fallback-report` by reading
  `plan_content`. The frontend exposes this in the Files tab with completion percentages.
- **Progress Streaming**: SSE remains default but unreliable in some networks; WebSocket endpoint
  (`/ws/plans/{id}/progress`) shares the same payloads. See `docs/SSE-Reliability-Analysis.md` for mitigations.
- **Concurrency Control**: `pipeline_execution_service.py` manages subprocess lifecycle, queues, and cleanup.
  Thread-safety hardening is tracked in `docs/Thread-Safety-Analysis.md`.
- **Database-first Writes**: Every task calls `DatabaseService.create_plan_content(...)` before touching the
  filesystem, so the API and fallback assembler always have authoritative data.

## Operational Checks
- Local dev: `curl http://localhost:8080/health` should report `database_connected=true`.
- Railway: deployment logs must show `Serving static UI from: /app/ui_static` and environment validation for
  API keys.
- Plan run: look for `/api/plans/{id}/files` entries and the fallback report endpoint even on successful runs.

## Troubleshooting Cheatsheet
| Symptom | Likely Cause | What to Inspect |
| --- | --- | --- |
| UI cannot reach API | FastAPI not on :8080 or CORS blocked | Terminal running `npm run go`, browser console |
| Plan stuck in queued | Luigi subprocess failed to start | `run/<plan_id>/log.txt`, FastAPI logs |
| SSE stops mid-run | Network or thread cleanup issue | Switch to WebSocket or poll `/api/plans/{id}` |
| No HTML report | `ReportTask` failed | Hit `/api/plans/{id}/fallback-report`, check missing sections |
| No LLM calls | Environment variables missing | `docs/2025-10-02-E2E-Env-Propagation-Runbook.md` steps |

## Takeaways for New Contributors
- Keep backend/ frontend schemas aligned (snake_case everywhere).
- Do not bypass the database service; the UI and fallback assembler depend on it.
- Use existing run outputs in `run/` for testing rather than generating mock data.
- When in doubt, start both services with `npm run go` and reproduce through the UI—the project optimises for
  Railway-first workflows.
