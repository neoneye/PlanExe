/**
 * Author: Codex using GPT-5
 * Date: 2025-09-30T15:30:00Z
 * PURPOSE: Detailed notes on Luigi task agentization research plus actionable plan for constructing agent hierarchy and sub-agents aligned with pipeline structure.
 * SRP and DRY check: Pass. Documentation centralizes research/plan; no existing doc covers agentization strategy.
 */

# Luigi Agentization Research Notes

## Source Material Reviewed
- `.agents/agentize.ts` primary template for agent builder utilities.
- `.agents/types/agent-definition.ts` for Codebuff agent schema and tool catalog.
- `.agents/README.md` and example agents for best practices.
- `docs/LUIGI.md` for current Luigi task dependency outline.
- Skimmed `planexe/plan/run_plan_pipeline.py` for concrete task definitions and grouping cues.

## Key Findings
- Luigi pipeline spans 61 tasks covering analysis, levers, assumptions, WBS, governance, reporting, and exports; many tasks share domains suitable for sub-agent specialization.
- Certain tasks (e.g., IdentifyPurposeTask, IdentifyRisksTask) map cleanly to domain-specific analyses; others (e.g., ExportGantt*) are mechanical outputs that can be grouped under a shared exporter agent.
- Existing agent framework supports spawnable sub-agents; instructions emphasize minimal tool sets and reuse of published agents when possible.
- We must avoid modifying pipeline code; agents should operate as planning/conversational abstractions mirroring task outputs.

## Proposed Agentization Strategy
1. **Top-Level Orchestrator**: `luigi-master-orchestrator` agent coordinating stage leads, referencing Luigi dependency phases.
2. **Stage Leads**: Create agents for major domains:
   - `analysis-stage-lead` (StartTime through IdentifyPurpose).
   - `assumptions-stage-lead` (Make/Distill/Review/Consolidate assumptions & risks).
   - `lever-strategy-stage-lead` (Potential levers, scenarios, strategic docs).
   - `wbs-schedule-stage-lead` (WBS creation, dependencies, durations, schedules, exports).
   - `team-governance-stage-lead` (team building, governance phases).
   - `reporting-stage-lead` (pitch, executive summary, final report, exporters).
3. **Sub-Agents**: For dense phases (e.g., WBS pipeline) define sub-agents like `wbs-generator`, `schedule-exporter`, `risk-manager`, etc., to encapsulate specific task clusters.
4. **Shared Utilities**: Reference external Codebuff agents (`codebuff/file-explorer@0.0.6`, etc.) for research support.
5. **Communication Protocol**: Each agent will summarize status, required hand-offs, and spawn sub-agents when dependencies resolved.

## Next Steps
1. Finalize mapping from each Luigi task to responsible agent or sub-agent.
2. Draft agent definitions in `.agents/` adhering to header template and minimal toolsets.
3. Ensure orchestrator instructions cover inter-agent communication and dependency enforcement.
4. Update `CHANGELOG.md` after implementation; create commits per instruction.
