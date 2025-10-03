/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Authoritative guide for the PlanExe REST API and its Next.js client, reflecting the v0.3.2
 *          database-first pipeline with fallback report assembly and Railway-first deployment.
 * SRP and DRY check: Pass - Centralises API onboarding, runtime operations, and integration notes without
 *          duplicating pipeline internals documented elsewhere.
 */
# PlanExe REST API & Frontend Integration (v0.3.2)

PlanExe pairs a FastAPI backend with a Next.js 15 frontend to orchestrate the 61-task Luigi planning pipeline.
The API launches pipeline runs, streams progress, persists plan artefacts to SQLite/PostgreSQL, and now exposes
fallback report assembly so partially successful runs still deliver a coherent plan.

## What Changed in v0.3.x
- Database-first Luigi architecture (v0.3.0) writes every task output to `plan_content` during execution.
- Structured OpenAI/OpenRouter fallback logic keeps long runs stable under schema drifts (v0.3.1).
- New fallback report assembler (v0.3.2) produces HTML + JSON summaries even when `ReportTask` fails.
- Frontend files tab surfaces recovered reports and completion percentages, sorted newest-first.
- Railway deployment is single-container: FastAPI serves both API and the static Next.js export.

## Quick Start

### Single Command Dev Loop
```bash
cd planexe-frontend
npm install
npm run go            # Starts FastAPI on :8080 and Next.js dev on :3000
```
Verify:
- UI: http://localhost:3000
- API health: http://localhost:8080/health

### Backend Only (FastAPI + Luigi)
```bash
cd planexe_api
set DATABASE_URL=sqlite:///./planexe.db   # PowerShell
uvicorn api:app --reload --port 8080
```
The server automatically loads `.env` (via `PlanExeDotEnv`) and merges values into `os.environ` for Luigi.

### Frontend Only (Next.js 15)
```bash
cd planexe-frontend
npm run dev          # UI on http://localhost:3000
```
Uses direct `fetch` calls to FastAPI—no Next.js API routes.

### Production Build / Railway
```bash
cd planexe-frontend
npm run build                    # Builds static export to ./out
```
Railway deploy uses `docker/Dockerfile.railway.api`, which:
1. Builds the Next.js export and copies it to `/app/ui_static`.
2. Installs Python deps, starts FastAPI on `$PORT`, and serves `/app/ui_static` directly.

## Environment & Database
- `DATABASE_URL` is mandatory (SQLite for local, Railway Postgres in prod).
- Plan output directory defaults to `./run` locally; override with `PLANEXE_RUN_DIR` if needed.
- API keys (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) are loaded via
  the hybrid dotenv loader and propagated to the Luigi subprocess.

## API Surface

### Health & Metadata
- `GET /health` ? `HealthResponse` (version, DB connectivity, queue status).
- `GET /ping` ? plain text heartbeat.
- `GET /api/models` ? ordered LLM catalogue (id, label, provider, latency tier).
- `GET /api/prompts` ? curated example prompts for UI seeding.

### Plan Lifecycle
- `POST /api/plans` ? create plan; body matches `CreatePlanRequest` with snake_case fields.
- `GET /api/plans/{plan_id}` ? latest persisted status (progress %, speed_vs_detail, error message).
- `GET /api/plans/{plan_id}/stream` ? SSE stream of `PlanProgressEvent` (known to drop occasionally).
- `GET /ws/plans/{plan_id}/progress` ? WebSocket alternative using same payload schema.
- `GET /api/plans/{plan_id}/stream-status` ? discover available transports (`sse`, `websocket`).
- `DELETE /api/plans/{plan_id}` ? stop pipeline and mark plan cancelled.
- `GET /api/plans` ? reverse chronological plan list (newest first) for the queue view.

### Artefacts & Reports
- `GET /api/plans/{plan_id}/files` ? file manifest with checksum + size metadata.
- `GET /api/plans/{plan_id}/files/{filename}` ? download persisted artefact.
- `GET /api/plans/{plan_id}/content/{filename}` ? raw stored content.
- `GET /api/plans/{plan_id}/details` ? Luigi stage map + dependency information.
- `GET /api/plans/{plan_id}/report` ? canonical HTML report (Luigi `ReportTask`).
- `GET /api/plans/{plan_id}/fallback-report` ? new assembled HTML + missing-section JSON when the
  canonical task fails; response includes completion percentage and section inventory.

## Example Usage

### Create a Plan
```bash
curl -X POST http://localhost:8080/api/plans \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Launch a community makerspace in Austin",
    "speed_vs_detail": "ALL_DETAILS_BUT_SLOW",
    "model": "gpt-4.1-mini"
  }'
```
Response:
```json
{
  "plan_id": "PlanExe_1234abcd-...",
  "status": "queued",
  "progress_percentage": 0,
  "created_at": "2025-10-03T00:01:05Z"
}
```

### Stream Progress (SSE)
```bash
curl http://localhost:8080/api/plans/PlanExe_1234/stream
```
If SSE disconnects (known issue), attempt the WebSocket endpoint or poll `/api/plans/{id}`.

### Fetch Fallback Report
```bash
curl http://localhost:8080/api/plans/PlanExe_1234/fallback-report
```
Returns HTML, missing sections, and computed completion percentage derived from `plan_content` rows.

## Data Persistence Model
- Every Luigi task writes to both filesystem (`run/<plan_id>/...`) and `plan_content` via
  `DatabaseService.create_plan_content`.
- Plan metadata (`plans` table) tracks status, timestamps, and speed/detail choices.
- `llm_interactions` table stores prompts/responses for audit.
- Fallback report assembler reads database-first, guaranteeing deliverables survive Railway pod restarts.

## Progress Transport Notes
- SSE remains default but unreliable on some corporate proxies (bug tracked in `SSE-Reliability-Analysis.md`).
- WebSocket endpoint shares queues managed by `websocket_manager`; cleanup is protected by locks but still
  under observation (see `Thread-Safety-Analysis.md`).

## Speed vs Detail Options
| Enum | Description |
| --- | --- |
| `FAST_BUT_SKIP_DETAILS` | Uses lightweight prompt templates for a rapid draft. |
| `BALANCED_SPEED_AND_DETAIL` | Balanced throughput vs coverage (default). |
| `ALL_DETAILS_BUT_SLOW` | Executes full-detail prompts for every stage. |

## Recovery Workspace
- Frontend route `/recovery?planId=PlanExe_<uuid>` opens the self-service plan recovery UI.
- Uses existing API endpoints: `GET /api/plans/{plan_id}`, `/api/plans/{plan_id}/files`, `/api/plans/{plan_id}/fallback-report`, and `/api/plans/{plan_id}/details`.
- `FileManager` expects `/api/plans/{plan_id}/files` to surface every persisted artefact from `plan_content`; ensure the backend responds even for pending/failed plans.
- Ideal during plan retries or investigations when the primary report is unavailable.
## Testing
- Python: `pytest -q` (runs FastAPI + pipeline utility tests).
- Frontend: `npm test` and `npm run test:integration` inside `planexe-frontend`.
- Real pipeline validation: reuse historical plan logs under `run/` instead of fabricating data.

## Operational Checklist
- Verify Railway deploy logs include `Serving static UI from: /app/ui_static`.
- Confirm database migrations have run (see `docs/RailwayDatabaseMigration.md`).
- Monitor `/api/plans/{id}/fallback-report` metrics for partial completions.
- Keep `.env` synchronised with Railway variables before each deploy.

---
The backend remains backward compatible with existing clients; legacy Node SDK docs now live in
`docs/old_docs/`. Use this README as the living reference for all API integrations.
