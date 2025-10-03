/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: High-level redesign plan for a simplified PlanExe UI and a dedicated Workspace that assembles plans in real time from database-backed artefacts. Describes scope, UX, data flows, reliability goals, and an actionable tasklist.
 * SRP and DRY check: Pass — Single planning document; references existing API and docs (no duplication of code or pipeline details).
 */

# 3 Oct — Workspace Redesign Plan (High-Level, No Code)

## Summary
- Replace the multi-tab dashboard with a minimal entry screen and a single, focused Workspace.
- After the user submits a plan prompt, immediately navigate to the Workspace where assembly happens.
- The Workspace reflects the run_plan_pipeline_documentation.md stages and shows database population in real time (plan_content driven), not filesystem assumptions.
- Goal: zero-confusion path to recover pending/failed runs and to monitor live ones, with consistent visibility into all stored artefacts.

## Scope & Non-Goals
- In scope: Frontend redesign (Next.js), simplified main page, dedicated Workspace view, real-time progress + DB artefact explorer, fallback report surfacing, reliability of file visibility.
- Out of scope: Changing Luigi task graph, altering backend business logic beyond contracts already provided (no pipeline rewrites).

## UX Principles
- Single-flow orientation: Prompt ? Workspace (no complex tab maze).
- Always-on visibility: Progress, artefacts, and report are co-present.
- Database-first truth: Show what exists in plan_content even if Luigi fails late.
- Progressive enhancement: Prefer WebSocket; fall back to polling gracefully.
- Accessibility and clarity: Clear labels, readable statuses, and obvious actions.

## Information Architecture
- Entry (Start Page):
  - One field for prompt, optional model/speed options, lightweight context help.
  - On submit, route to Workspace with planId.
- Workspace (Plan-centric page):
  - Header: PlanId, status badge (pending/running/completed/failed/cancelled), progress percent, created timestamp, actions (refresh, cancel, retry, open report/fallback download).
  - Left Panel: Stage timeline reflecting the named stages from docs/run_plan_pipeline_documentation.md (high-level categories only). Stage rows light up as DB entries appear.
  - Center Panel: Report preview — if canonical report exists, show it; else show fallback-assembled HTML with a “missing sections” summary; toggle between them when both are available.
  - Right Panel: Artefact explorer sourced from plan_content. Filter by stage, type, and text. Download from API. Always populated for any status.

## Data & Transport
- Required API contracts (already available):
  - GET /api/plans/{plan_id}
  - GET /api/plans/{plan_id}/files
  - GET /api/plans/{plan_id}/fallback-report
  - GET /api/plans/{plan_id}/details
- Real-time: Prefer WebSocket for stage/progress, with a polling fallback every 3–5 seconds for all key views (status, details, files, fallback report freshness).
- Database-first assumption: Files endpoint must return artefacts for pending/failed plans as they arrive in plan_content.

## Reliability Targets
- Files view shows something for any plan status as soon as the first artefact exists in plan_content.
- Fallback report always available when canonical report is missing.
- Workspace loads even if streaming fails (polling degrades gracefully).
- No non-ASCII glyphs or ANSI leak-through in UI.

## Error & Recovery Design
- If progress streaming breaks, show a non-blocking banner and continue polling.
- If files list is empty while status is pending/running, present: “Waiting for first artefact…” and surface last refresh time.
- If both canonical and fallback reports are missing after tasks have produced artefacts, show a call-to-action to open a support issue with planId and latest stage.

## Acceptance Criteria
- After prompt submit, user lands on Workspace with the new layout.
- The database artefact explorer populates for pending, running, failed, and completed states.
- The stage timeline aligns with the sections described in docs/run_plan_pipeline_documentation.md and lights up as artefacts appear.
- Report area toggles between canonical and fallback; fallback is available when canonical is missing.
- No mojibake or ANSI sequences appear anywhere in the Workspace.

## Risks & Mitigations
- Streaming instability: fall back to polling and keep UI responsive.
- Contract drift in files endpoint: adopt a thin adapter on the frontend and validate shape; raise a backend ticket if essential fields are missing.
- Large plans: virtualize long lists and paginate as needed.

## Tasklist (Implement in Iterations)
1) Entry Simplification
- Remove non-essential elements from the main page; keep prompt input and model/speed options only.
- On submit, navigate to Workspace with the returned planId (no tabs).

2) Workspace Shell
- Create a dedicated plan Workspace route and page structure with header + left/center/right panels.
- Add persistent actions (refresh, cancel, retry) and basic metadata.

3) Stage Timeline (Left)
- Define user-facing stage groups based on run_plan_pipeline_documentation.md.
- Wire timeline to the progress feed and to presence of artefacts; light up as data arrives.

4) Report Area (Center)
- Show canonical report when available; otherwise show fallback report with missing section summary.
- Provide download buttons for HTML and missing-section JSON.

5) Artefact Explorer (Right)
- Fetch files for the plan from the files endpoint and display them regardless of status.
- Add filters by stage/type/text; show counts and last refresh time.

6) Real-time Data Flow
- Connect to WebSocket for progress updates; auto-reconnect with backoff.
- In parallel, poll status, files, and details every 3–5 seconds to ensure continuity.

7) Polish & Accessibility
- Replace any non-ASCII glyphs; ensure labels and focus states are accessible.
- Add empty-state prompts and compact error alerts that do not block the workflow.

8) Validation & QA
- Verify with a known pending plan: stage timeline updates, files appear, fallback report assembles.
- Verify with a failed plan: workspace loads, files present, fallback report available.
- Verify with a completed plan: canonical report available; toggling between views works.

9) Documentation & Handover
- Update README_API.md with the Workspace navigation flow and expectations for the files endpoint.
- Note behaviour and known limitations in docs/2025-10-03-documentation-audit.md.
