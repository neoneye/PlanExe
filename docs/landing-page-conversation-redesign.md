/**
 * Author: Codex using GPT-5
 * Date: `2025-02-14T00:00:00Z`
 * PURPOSE: End-to-end execution strategy for replacing the existing landing page with an information-dense layout that immediately routes users into a Responses API-backed enrichment conversation before triggering the Luigi pipeline. Captures impacted UI modules, API client surfaces, state stores, and backend touchpoints so downstream developers understand dependencies.
 * SRP and DRY check: Pass - file only houses the redesign plan narrative and avoids duplicating implementation once coded elsewhere.
 */

# PlanExe Landing Page → Conversation-First Redesign

## 1. Objectives & Guardrails
- **Conversation-first intake**: Replace the current auto-launch pipeline flow with a modal that starts a Responses API conversation using `gpt-5-mini` as the default model. Only launch the Luigi pipeline after the modal delivers a structured enriched payload.
- **Information-dense canvas**: Remove outer padding/margins and adopt a tight CSS grid that surfaces status, queues, and artefacts in the initial viewport.
- **Control abstraction**: Hide model selection and advanced toggles from first-run UI; keep them in a collapsible “advanced” drawer accessible inside the conversation modal for power users.
- **Streaming clarity**: Mirror Responses API semantic events (start/data/end/errors) with existing streaming utilities so deltas render with zero flicker.
- **No Luigi intrusion**: The pipeline remains untouched. We gate its invocation on the enriched payload while preserving existing FastAPI contracts.

## 2. Target Experience Overview
1. **Primary prompt strip** (top of landing page):
   - Single-line command palette style input with immediate focus.
   - Inline helper pills for “Add context” or “Import previous brief”.
   - Submit opens the conversation modal (no backend call yet).
2. **Streaming conversation modal**:
   - Left column: conversation timeline with user inputs and streamed assistant output.
   - Right column: `StreamingMessageBox`-style panels for text/reasoning/JSON deltas.
   - Footer: “Finalize payload” button activates once the Responses API marks completion.
   - Advanced drawer reveals optional model override, speed toggle, and API key.
3. **Post-conversation summary**:
   - Extracted structured payload preview (title, refined brief, constraints).
   - User confirms to launch Luigi pipeline via existing `createPlan` route.
4. **Landing surface around modal trigger**:
   - Four-up grid (System Status, Queue, Artefacts, Release Notes) visible above the fold.
   - No outer padding; use CSS grid gap of 12px; card internals use 8px spacing maximum.

## 3. Architectural Workstreams

### 3.1 UI Refactor
- Rewrite `planexe-frontend/src/app/page.tsx` layout:
  - Use full-width container with `grid-cols-[auto auto auto]` for header metrics.
  - Deduplicate PlanForm usage; convert prompt capture into a minimal inline form.
  - Slot existing `PlansQueue` and status cards into the new grid without extra wrappers.
- Replace `PlanForm` usage with new `PromptLauncher` component that only collects the base prompt and optional tags for the modal.
- Introduce `ConversationModal` component leveraging existing shadcn `Dialog`.

### 3.2 Conversation State & Streaming
- Create `useResponsesConversation` hook:
  - Stores `currentResponseId`, streaming buffers, and modal visibility.
  - Bridges to backend endpoints to call OpenAI Responses API (see §3.3).
  - Exposes `startConversation(prompt)`, `sendFollowup(message)`, `finalize()` APIs.
- Reuse `StreamingMessageBox` for delta panes; extend to support semantic events (e.g., metadata, tool calls) with badges.
- Ensure abort controller for cancel/close actions.

### 3.3 Backend/Client Integration
- **New FastAPI endpoints** (`planexe_api/api.py` + service layer):
  - `POST /api/conversations` → initializes Responses API call using default `gpt-5-mini`.
  - `POST /api/conversations/{id}/messages` → continues conversation with `previous_response_id`.
  - `POST /api/conversations/{id}/finalize` → optional endpoint to persist enriched payload.
  - Endpoints return conversation IDs, streaming URLs (Server-Sent Events) aligned with `analysis-streaming` semantics.
- **Client updates** (`fastapi-client.ts`):
  - Add typed methods for the above endpoints and SSE consumption helpers.
  - Extend existing streaming utilities or create `createConversationStream`.
- **Data contract**:
  - Standardize enriched payload shape: `{ refined_prompt, title, metadata, execution_settings }`.
  - Modal finalization triggers `createPlan` with this enriched payload, mapping to existing FastAPI fields.

### 3.4 Visual System Adjustments
- Tailwind updates:
  - Add utility classes for zero-padding containers (`landing-shell`).
  - Define compact card variants (8px inner padding).
- Audit dark mode styles to ensure contrast remains acceptable despite denser layout.

### 3.5 Telemetry & UX Validation
- Log modal open/close, conversation duration, and fallback cases (user cancels before finish).
- Capture when enriched payload differs substantially from base prompt for later analytics.
- Provide toasts for network errors and highlight resume options if streaming fails.

## 4. Implementation Phases
1. **Scaffolding**
   - Build `useResponsesConversation` hook with mocked backend responses.
   - Implement `ConversationModal` skeleton with streaming placeholders.
2. **Backend wiring**
   - Add conversation endpoints and integrate with Responses API using server-side streaming.
   - Reuse existing logging/security patterns (`pipeline_execution_service.py` references).
3. **Frontend integration**
   - Replace existing landing layout with new grid and prompt launcher.
   - Wire modal lifecycle: prompt submit → modal open → streaming → finalize → `createPlan`.
4. **Polish**
   - Tune spacing, typography, and responsive breakpoints.
   - Add advanced drawer for model overrides.
   - Localize error states and empty data fallbacks.
5. **QA & Regression**
   - Verify pipeline launch still works with enriched payload.
   - Test streaming cancellation, error handling, and reconnection.
   - Update `CHANGELOG.md` and ensure docs reflect new flow.

## 5. Impacted Files (Initial Estimate)
- `planexe-frontend/src/app/page.tsx`
- `planexe-frontend/src/components/planning/PlanForm.tsx` (likely deprecated or repurposed)
- `planexe-frontend/src/components/planning/PromptLauncher.tsx` (new)
- `planexe-frontend/src/components/conversation/ConversationModal.tsx` (new)
- `planexe-frontend/src/hooks/useResponsesConversation.ts` (new)
- `planexe-frontend/src/lib/api/fastapi-client.ts`
- `planexe-frontend/src/lib/streaming/*` (extend for conversation SSE)
- `planexe_api/api.py`, `planexe_api/services/*` (new service for Responses API conversations)
- Corresponding tests/docs.

## 6. Open Questions & Assumptions
- Assuming FastAPI backend already has credentials/config to call Responses API; otherwise need new settings in `.env`.
- Need confirmation whether enriched payload should persist server-side for audit.
- Will conversations be single-turn (prompt → refinement) or multi-turn? Plan supports multi-turn via `sendFollowup`.
- Requires UX approval for removing direct model selection; advanced drawer provides override.

## 7. Next Steps
1. Validate backend capability/credentials for Responses API streaming from FastAPI.
2. Align with stakeholders on enriched payload schema.
3. Begin Phase 1 scaffolding tasks (frontend hook + modal shell).

