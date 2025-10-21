# AGENTS.md

Guidance for agents working in this repository. Concise, non-redundant, LLM-friendly.

## File header template
Add a short header to new/edited source files. Use correct comment syntax for the language.

```
Author: {agent/model name}
Date: {UTC timestamp}
Purpose: {concise description + dependencies/inputs/outputs}
SRP/DRY: {Pass|Fail}  {explain if similar logic exists elsewhere and why this file is needed}
```

## System overview
- Frontend: `planexe-frontend/` (Next.js, TypeScript, Tailwind, shadcn/ui). Dev port 3000. In production, built and served by FastAPI.
- Backend: `planexe_api/` (FastAPI + SQLAlchemy). Port 8080. Orchestrates Luigi.
- Pipeline: `planexe/` (Luigi; 61 tasks; database-first I/O; file artefacts).
- Storage: SQLite/PostgreSQL for state and content; file outputs and HTML reports on disk.

Production (Railway): single container. FastAPI serves both API and the built Next.js export.

## Key directories
- `planexe-frontend/` — Next.js app. Direct client to FastAPI (no proxy routes). State via React hooks + Zustand.
- `planexe_api/` — FastAPI app, REST + WebSocket, DB ORM, Luigi integration.
- `planexe/` — Luigi pipeline tasks and orchestration logic.
- `docs/` — `LUIGI.md`, `CODEBASE-INDEX.md`, `run_plan_pipeline_documentation.md`.

## Run/build

Local development
```
# Start frontend (dev server on 3000)
cd planexe-frontend
npm run go

# Start API (port 8080)
uvicorn planexe_api.api:app --host 0.0.0.0 --port 8080 --reload
```

Production
```
# Build frontend
cd planexe-frontend
npm run build
npm start  # or export/static as configured

# Run API (serves built frontend)
gunicorn planexe_api.api:app
```

## API surface
- `POST /api/plans` — create plan (starts pipeline).
- WebSocket `/api/plans/{id}/stream` — real-time progress.
- `GET /api/plans/{id}/files` — list generated files.
- `GET /api/plans/{id}/report` — download HTML report.
- `GET /api/plans/{id}/artefacts` — database-driven artefact metadata.
- `GET /api/plans/{id}/fallback-report` — fallback report assembly.
- `GET /api/models` — available LLM models.
- `GET /api/prompts` — example prompts.
- `GET /health` — health check.

Verify exact routes in `planexe_api/api.py` if unsure.

## Data model (high level)
- Plans — config, status, progress, metadata.
- LLMInteractions — prompts/responses + metadata.
- PlanFiles — generated files + checksums.
- PlanContent — canonical task outputs (database-first).
- PlanMetrics — performance/analytics.

## Luigi pipeline (do not modify without approval)
- 61 tasks in strict dependency order.
- Database-first writes during execution (not after).
- File-based outputs (e.g., `001-start_time.json`, `018-wbs_level1.json`).
- Stages: Setup → Analysis → Strategy → Context → Assumptions → Planning → Execution → Structure → Output → Report.
- LLM orchestration with retries/fallbacks; structured outputs via Responses API.
- Progress/resume via DB state; real-time visibility through DB queries.

## Frontend structure
- Key components: `PlanForm`, `ProgressMonitor`, `TaskList`, `FileManager`, `PlansQueue`, `Terminal`.
- API client: `planexe-frontend/src/lib/api/fastapi-client.ts`.
- Types: `planexe-frontend/src/lib/types/forms.ts`.
- Main app: `planexe-frontend/src/app/page.tsx`.

## Development rules
General
- Prefer editing existing files; avoid creating new files unless necessary.
- Commit early/often with descriptive messages (“sudden death” assumption).
- Add rationale and task lists in `/docs` when you change behavior or architecture.
- Keep responses and changes concise; discuss tradeoffs with the product owner before large changes.

Frontend
- Use snake_case to match backend field names.
- Do not add Next.js API routes; call FastAPI directly.
- Test with both services running (`3000` and `8080`).
- Reuse shadcn/ui + TypeScript patterns.
- Use WebSocket for progress; fall back to polling only if needed.
- Integrate artefact and fallback-report endpoints where relevant.

Backend
- Preserve FastAPI endpoint compatibility with the frontend.
- Keep WebSocket implementation intact.
- Test with SQLite first; then PostgreSQL.
- Update DB migrations when schemas change.
- Support structured outputs via Responses API.
- Maintain database-first pipeline contract.

Luigi
- Do not change task graph unless you understand full dependencies.
- Use `FAST_BUT_SKIP_DETAILS` for dev-only runs.
- Verify DB writes occur during task execution.
- See `docs/run_plan_pipeline_documentation.md` for details.

## Essential references
- `CHANGELOG.md`
- `docs/run_plan_pipeline_documentation.md`
- `planexe_api/api.py`, `planexe_api/models.py`, `planexe_api/database.py`
- `planexe-frontend/src/lib/api/fastapi-client.ts`
- `planexe-frontend/src/lib/types/forms.ts`

## Troubleshooting

Common issues
- Connection refused: ensure FastAPI on port 8080 is running.
- WebSocket not connecting: verify progress endpoint path and server logs.
- Task failed: check Luigi logs in `run/` and table `plan_content`.
- Artefact loading: check `/api/plans/{id}/artefacts`.
- Report generation: use `/api/plans/{id}/fallback-report`.

Commands
```
# Ports
netstat -an | findstr :3000
netstat -an | findstr :8080

# API
curl http://localhost:8080/health
curl http://localhost:8080/api/models

# WebSocket (verify in code; path shown for reference)
# Use a WS client for testing; curl won't establish WS.

# Artefacts
curl http://localhost:8080/api/plans/{plan_id}/artefacts

# Create plan
curl -X POST http://localhost:8080/api/plans \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Create a plan for a new business","model":"<model-id>"}'

# Inspect DB (SQLite example)
sqlite3 planexe.db "SELECT * FROM plan_content WHERE plan_id='YOUR_PLAN_ID' ORDER BY created_at DESC LIMIT 5;"
```

## Testing policy
- Use existing plans/data; no mocking or simulated data.
- Do not over-engineer tests.
- Only perform testing when explicitly asked.

## PlanExe-specific reminders
- Respect the Luigi pipeline; changes require full-graph understanding.
- Backend port is `8080`.
- Database-first architecture is mandatory; all tasks write during execution.
- Keep frontend and backend field names aligned (snake_case).
- Run both services for local testing (3000 + 8080).
- Support Responses API structured outputs.