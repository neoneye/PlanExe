/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Captures the October 2nd stabilisation strategy for report assembly and tracks its
 *          completion status post v0.3.2 fallback rollout.
 * SRP and DRY check: Pass - Historical plan plus latest status annotation without duplicating
 *          implementation details already in code comments.
 */# 02 Oct Codex Plan - Stabilising Final Plan Assembly

## Status Update — 2025-10-03
- [x] ReportAssembler shipped in v0.3.2 with GET /api/plans/{plan_id}/fallback-report.
- [x] FastAPI and the frontend Files tab now surface recovered sections and completion metrics.
- [ ] Agent-driven remediation (Phase 5) remains optional and is still deferred.
## Current Assembly Behaviour
- The Luigi `ReportTask` stitches the final HTML (`029-report.html`) by reading dozens of prerequisite artefacts from `run/<plan_id>/` and feeding them to `planexe.report.report_generator.ReportGenerator`.
- Every upstream task also persists its payload into the `plan_content` table via `db_service.create_plan_content`, which is how the FastAPI layer serves downloads on Railway.
- `ReportTask` currently assumes every prerequisite artefact exists. If any upstream task fails, report generation raises and the entire pipeline aborts, even though most deliverables are available in `plan_content`.

## Observed Fragility
- Missing helper methods (`to_clean_json`) or imports (`time`) caused the pipeline to terminate late, leaving the user with no assembled plan despite usable partial results.
- Railway pods have ephemeral file systems; if the final report is not written before teardown, only the database copy survives.
- The current aggregation logic is all-or-nothing: one missing file breaks report generation rather than gracefully summarising what succeeded.

## Goal
Deliver a coherent business plan from whatever artefacts exist, and clearly document any gaps instead of failing the run.

## Proposed Simplification
1. **Central Aggregator Based on plan_content**
   - Read the ordered task list from `planexe.plan.run_plan_pipeline.ObtainOutputFiles` or the Luigi dependency graph.
   - For each expected filename, fetch `plan_content` for the current `plan_id`.
   - Build the report using the data that exists; collect missing entries into a "Further Research" appendix.
   - Persist both the assembled HTML and a machine-readable summary (`missing_components.json`).

2. **Graceful Degradation in ReportTask**
   - Replace hard failures with warnings when a dependency is absent.
   - Render placeholder sections (e.g. "Section unavailable; refer to appendix") so the final plan is always produced.
   - Log missing artefacts so API clients can surface them in the UI.

3. **Single Source of Truth for Artefacts**
   - Always prefer the database copy (`plan_content`) because it survives Railway restarts.
   - Only fall back to the filesystem when running locally or when streaming large files.

4. **Appendix of Missing Stages**
   - Summarise tasks that failed, including the `plan_content` record (if any) and the Luigi error message.
   - Encourage downstream users to re-run only the missing stages or request regeneration.

5. **Agent-Orchestrated Recovery (Optional)**
   - The `.agents/luigi_master_orchestrator.ts` agent already enumerates stage leads. Extend it to:
     - Inspect the appendix of missing outputs.
     - Propose re-runs or alternative prompts for the failed stage.
     - Generate user-friendly remediation guidance as part of the final report.

## Implementation Steps
1. Introduce a `ReportAssembler` utility that queries `plan_content` and returns ordered sections plus missing entries.
2. Refactor `ReportTask` to call the assembler and tolerate absent files.
3. Expose missing-stage metadata via API (`GET /api/plans/{id}` and `/details`).
4. Update UI to show a "Plan completion" summary with available sections and follow-up actions.
5. Write regression tests: intentionally skip a stage and confirm the report renders with a populated appendix instead of failing.

## Immediate Actions
- Implement the assembler + graceful ReportTask update.
- Document the retrieval workflow in README (filesystem, API, database) – completed in this iteration.
- Keep monitoring long-running plans to ensure they finish even when a late stage fails.



