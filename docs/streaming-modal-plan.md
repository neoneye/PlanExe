<!--
/**
 * Author: ChatGPT gpt-5-codex
 * Date: 2025-10-27T00:00:00Z
 * PURPOSE: Implementation plan for aligning streaming modals with Responses API best practices.
 * SRP and DRY check: Pass - focused solely on planning streaming modal updates without duplicating existing docs.
 */
-->
# Streaming Modal Integration Plan

## Objectives
- Implement the POST→GET handshake for analysis streaming sessions with expiring cache.
- Ensure backend streaming uses the OpenAI Responses API with reasoning knobs and max token budget while persisting summaries.
- Provide frontend hooks and UI components for real-time reasoning/text buffers via SSE.
- Introduce reusable streaming message boxes for consistent modal presentation.
- Keep feature flag alignment between backend and frontend builds.

## Key Tasks
1. **Backend streaming pipeline**
   - Add session cache and handshake endpoints under `/api/stream/analyze`.
   - Normalize OpenAI responses via a stream harness that emits `stream.*` events and persists final summaries to `llm_interactions`.
   - Inject reasoning configuration, `max_output_tokens`, and payload builder reuse for both sync and streaming calls.
   - Expose streaming enablement flag derived from environment settings.

2. **Frontend streaming orchestration**
   - Create helpers to perform the handshake, open EventSource connections, and aggregate text/reasoning/JSON buffers.
   - Build hooks (`useAnalysisStreaming`, `useAnalysisResults`) that surface lifecycle status, cancellation, and persistence callbacks.
   - Implement reusable `StreamingMessageBox` component variants (text, reasoning, json) and a `StreamingAnalysisPanel` wrapper.
   - Thread feature flag awareness through the workspace UI, guarding streaming entry points when disabled.

3. **Documentation & telemetry**
   - Update CHANGELOG with streaming modal integration notes.
   - Ensure new components/files follow repository header conventions and reference token usage persistence requirements.

## Risks & Mitigations
- **API drift**: Mitigated by centralizing payload building and reusing `SimpleOpenAILLM` request args.
- **SSE lifecycle leaks**: Harness will manage connection teardown and propagate errors via `stream.error`.
- **Token starvation**: Default `max_output_tokens` set high with monitoring of reasoning token usage in final summary.
- **Feature flag mismatch**: Both FastAPI and Next.js configs will read `STREAMING_ENABLED`/`NEXT_PUBLIC_STREAMING_ENABLED` with consistent defaults.

## Validation Checklist
- Handshake returns `sessionId` and TTL, GET upgrades to SSE with immediate `stream.init`.
- `stream.chunk` events deliver text, reasoning, and JSON deltas in separate message boxes.
- Final summary includes `responseId`, `analysis`, `reasoning`, and `tokenUsage` saved to DB and forwarded to UI.
- Cancellation/error paths emit `stream.error` followed by graceful closure.
- Frontend respects feature flag and cleans up EventSource connections on unmount.
