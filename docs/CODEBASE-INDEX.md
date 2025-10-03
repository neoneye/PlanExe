/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Fresh, accurate index of the PlanExe repository at v0.3.2 covering directory layout,
 *          ownership, and cross-cutting concerns for new contributors.
 * SRP and DRY check: Pass - High level map pointing to authoritative sources; avoids repeating
 *          deep pipeline commentary stored in run_plan_pipeline_documentation.md.
 */
# PlanExe Codebase Index (v0.3.2)

PlanExe converts vague prompts into multi-chapter execution plans through a Next.js frontend, a FastAPI API
layer, and a 61-task Luigi pipeline. This index is the entrypoint for orienting yourself in the repository.

## Top-Level Layout
```
PlanExe/
+- planexe/                # Luigi pipeline tasks, shared domain models, LLM utilities
+- planexe_api/            # FastAPI service, database layer, websocket/SSE transport
+- planexe-frontend/       # Next.js 15 app (shadcn/ui, Zustand, Tailwind)
+- docs/                   # Living documentation (current files kept here, archives in docs/old_docs)
+- run/                    # Per-plan execution artefacts (populated at runtime)
+- docker/                 # Deployment Dockerfiles (Railway builds docker/Dockerfile.railway.api)
+- CHANGELOG.md            # Release history (latest: v0.3.2 fallback report assembly)
+- README.md               # High-level project overview
```

## Core Components

### Luigi Pipeline (`planexe/`)
- `plan/run_plan_pipeline.py` defines 61 `PlanTask` subclasses orchestrated via Luigi.
- Database-first writes (v0.3.0) persist every task output via `DatabaseService.create_plan_content`.
- LLM interactions flow through `llm_util/llm_executor.py` with structured retries and token accounting.
- `plan/filenames.py` enumerates canonical artefact names consumed by ReportAssembler.
- See `docs/run_plan_pipeline_documentation.md` for an expanded stage-by-stage breakdown.

### FastAPI Backend (`planexe_api/`)
- `api.py` exposes REST endpoints, SSE and WebSocket transports, and the fallback report assembler.
- `database.py` wraps SQLAlchemy models (`Plan`, `PlanContent`, `LLMInteraction`, etc.) and provides
  scoped sessions for threads.
- `services/pipeline_execution_service.py` manages Luigi subprocess lifecycle and progress queues.
- `websocket_manager.py` guards shared progress queues; ongoing thread-safety work is tracked in
  `docs/Thread-Safety-Analysis.md`.

### Next.js Frontend (`planexe-frontend/`)
- `src/app/page.tsx` renders the main dashboard with plan creation, queue, files, and progress views.
- `src/lib/api/fastapi-client.ts` handles typed API calls (snake_case fields mirroring the backend).
- `src/app/(components)/files/FallbackPanel.tsx` surfaces recovered reports produced by v0.3.2.
- `npm run go` boots FastAPI (port 8080) and Next.js dev (port 3000) via a single command during local dev.

## Key Workflows
- **Plan Creation**: Frontend posts to `POST /api/plans` ? FastAPI seeds run dir ? Luigi pipeline executes.
- **Progress Monitoring**: UI prefers SSE (`/api/plans/{id}/stream`) with WebSocket fallback; reliability
  caveats documented in `docs/SSE-Reliability-Analysis.md`.
- **Artefact Retrieval**: Files list from `/api/plans/{id}/files`; fallback report available at
  `/api/plans/{id}/fallback-report` when Luigi cannot finish `ReportTask`.
- **Deployment**: Railway single container builds Next.js static export and serves it from FastAPI. Environment
  bootstrapping uses `PlanExeDotEnv` to merge `.env`/Railway variables for both processes.

## Supporting Documentation
- `docs/HOW-THIS-ACTUALLY-WORKS.md` explains dev vs production architecture and the Luigi subprocess model.
- `docs/RAILWAY-SETUP-GUIDE.md` is the canonical deployment playbook now that Railway is stable.
- `docs/2025-10-02-E2E-Env-Propagation-Runbook.md` verifies API key propagation end-to-end.
- `docs/SSE-Test-Plan.md` covers manual regression checks for streaming reliability.
- Historical or superseded documents live under `docs/old_docs/` to reduce noise.

## Quick Reference Tables

| Concern | Source |
| --- | --- |
| Database schema & migrations | `planexe_api/database.py`, `planexe_api/migrations/` |
| LLM configuration & overrides | `llm_config.json`, `planexe/utils/planexe_llmconfig.py` |
| Prompt catalog | `planexe/prompt/prompt_catalog.py` |
| Frontend state management | `planexe-frontend/src/lib/stores/plan-store.ts` |
| Deployment Dockerfile | `docker/Dockerfile.railway.api` |

## Active Risks & Follow-Ups
- SSE dropouts remain; track fixes in `docs/SSE-Reliability-Analysis.md` and prefer WebSocket fallback.
- WebSocket connection cleanup is being hardened; refer to `docs/Thread-Safety-Analysis.md` before refactoring.
- Agent-based report remediation (Phase 5 from the cascade plan) is deferred pending prioritisation.

Stay aligned with `CHANGELOG.md` for future releases and keep this index updated when new directories or
critical services are introduced.
