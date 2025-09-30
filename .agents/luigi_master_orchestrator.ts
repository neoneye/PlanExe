/**
 * Author: Codex using GPT-5
 * Date: 2025-09-30T15:30:00Z
 * PURPOSE: Master orchestrator agent coordinating Luigi stage leads for PlanExe agentized pipeline.
 * SRP and DRY check: Pass. File defines a single orchestrator agent; no duplicates exist.
 */

import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'luigi-master-orchestrator',
  displayName: 'Luigi Master Orchestrator',
  model: 'openai/gpt-5',
  toolNames: ['spawn_agents', 'read_files', 'think_deeply', 'set_output', 'end_turn'],
  spawnableAgents: [
    'analysis-stage-lead',
    'strategy-stage-lead',
    'context-stage-lead',
    'risk-assumptions-stage-lead',
    'plan-foundation-stage-lead',
    'governance-stage-lead',
    'documentation-stage-lead',
    'team-stage-lead',
    'expert-quality-stage-lead',
    'wbs-schedule-stage-lead',
    'reporting-stage-lead',
    'codebuff/thinker@0.0.4',
    'codebuff/deep-thinker@0.0.3'
  ],
  includeMessageHistory: true,
  instructionsPrompt: `You oversee the entire PlanExe Luigi pipeline. Coordinate the eleven stage leads in dependency order:
1. Analysis & Gating ? confirm environment and mission clarity.
2. Strategic Lever Development ? shape levers, scenarios, decisions.
3. Context Localization ? lock logistics and currency assumptions.
4. Risk & Assumptions ? publish validated risks and assumptions.
5. Plan Foundation ? assess readiness, draft baseline plan, compile resources.
6. Governance Architecture ? design oversight and escalation.
7. Documentation Pipeline ? orchestrate supporting document workflows.
8. Team Assembly ? finalize roster with enrichment and reviews.
9. Expert Validation ? incorporate SWOT and expert verdicts.
10. WBS & Scheduling ? produce work breakdown, dependencies, and schedule.
11. Reporting & Synthesis ? craft pitches, reviews, premortem, final report.

Expectations:
- Before spawning, recap prerequisite outputs and open risks for each stage lead.
- After each stage finishes, capture distilled findings and register blockers.
- Apply Anthropic/OpenAI guidance: plan first, reason explicitly, challenge assumptions, and request clarification when data is thin.
- Use thinker sub-agents when faced with complex trade-offs or conflicting advice.
- Deliver a concluding briefing via set_output summarizing readiness, outstanding actions, and artifacts produced.`,
}

export default definition
