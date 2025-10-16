/**
 * Author: Codex using GPT-5
 * Date: 2024-05-11
 * PURPOSE: Document the migration plan for replacing the Luigi pipeline with the agent hierarchy using the Responses API, summarizing architecture, tasks, and milestones.
 * SRP and DRY check: Pass - this file consolidates plan details referenced from prior analysis without duplicating existing docs.
 */

# Responses API + Agent Orchestration Migration Plan

## Overview
- The existing `.agents` hierarchy mirrors the Luigi pipeline with a `luigi-master-orchestrator` supervising eleven stage-lead agents that in turn manage the individual task agents.
- Each agent definition specifies GPT-5-class models, prompts, and tool allowances, preserving the responsibility boundaries formerly enforced by Luigi tasks.
- The repository ships with Responses API implementation notes that cover streaming, reasoning control, and SSE relays—critical features for replicating Luigi’s progress reporting and logging.

## Goals
1. Replace Luigi’s scheduler/orchestrator with an agent runner that drives the prebuilt agent hierarchy through the Responses API.
2. Preserve real-time visibility of reasoning and text deltas for the frontend monitor.
3. Maintain artefact persistence, auditability, and token accounting per execution stage.

## Proposed Phases

### Phase 1: Agent Runner Prototype
- Implement a lightweight Node/TypeScript service that instantiates the `luigi-master-orchestrator` agent and lets it spawn stage leads/tasks.
- Use `openai.responses.stream` with the required `reasoning` and `text.verbosity` controls to replicate Luigi task logging.
- Persist each agent invocation’s `response.id` so downstream phases can resume conversations.

### Phase 2: Conversation State & Handoff
- Leverage `previous_response_id` or the Conversations API to stitch context between stage leads and their subtasks.
- Ensure each stage lead resumes its prior context when orchestrating retries or subsequent steps.
- Record reasoning summaries and outputs as structured artefacts for traceability.

### Phase 3: Streaming Integration
- Replace the current Luigi log forwarder with the SSE streaming pattern from the Responses API guide.
- Bridge streamed reasoning/text deltas into the existing FastAPI/WebSocket layer so the frontend continues to show live updates.
- Verify that failure cases propagate meaningful status messages to the UI.

### Phase 4: Persistence & Metrics
- Store per-agent execution metadata: streamed reasoning, token usage, generated files, and status.
- Align storage schema with existing expectations for plan artefacts and audit logs.
- Validate that archived runs can be replayed or inspected without Luigi involvement.

## Risks & Considerations
- **Parity Assurance**: Need comprehensive validation to ensure agent outputs match the deterministic expectations encoded in Luigi tasks.
- **Tooling Limits**: Confirm each agent’s tool permissions align with required capabilities (file system, HTTP, etc.).
- **Operational Readiness**: Monitor Responses API rate limits and cost impacts when replacing Luigi’s batch scheduling.

## Next Steps
- Draft acceptance criteria for the agent runner prototype (success metrics, failure handling, recovery).
- Identify environment/config changes required to deploy the agent runner alongside FastAPI.
- Plan incremental rollouts (shadow mode -> partial -> full cutover) to mitigate migration risk.

