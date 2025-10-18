/**
 * Author: Cascade using Supernova Corp
 * Date: `2025-10-18`
 * PURPOSE: Detailed implementation task list for landing page conversation-first redesign. This document outlines all files to be created or modified based on the specifications in landing-page-conversation-redesign.md and 18OctResponsesAPI.md. All implementation follows the POST→GET SSE handshake pattern and Responses API streaming guidelines provided.
 * SRP and DRY check: Pass - focuses solely on task breakdown and file impact without duplicating implementation code.
 */

/**
 * Author: Cascade using Supernova Corp
 * Date: `2025-10-18`
 * PURPOSE: Detailed implementation task list for landing page conversation-first redesign. This document outlines all files to be created or modified based on the specifications in landing-page-conversation-redesign.md and 18OctResponsesAPI.md. All implementation follows the POST→GET SSE handshake pattern and Responses API streaming guidelines provided.
 * SRP and DRY check: Pass - focuses solely on task breakdown and file impact without duplicating implementation code.
 */

# PlanExe Landing Page → Conversation-First Redesign - Detailed Task List

## Overview
This task list implements the conversation-first redesign using only the information provided in `landing-page-conversation-redesign.md` and `18OctResponsesAPI.md`. The implementation follows the POST→GET SSE handshake pattern with proper Responses API event handling.

## Phase 1: Scaffolding (Frontend-First with Mocked Backend)

### 1.1 Create `useResponsesConversation` Hook
- **File**: `planexe-frontend/src/hooks/useResponsesConversation.ts` (NEW)
- **Purpose**: Manage conversation state, streaming buffers, and modal visibility
- **Key Features**:
  - Stores `currentResponseId`, streaming buffers using `useRef`
  - Exposes `startConversation(prompt)`, `sendFollowup(message)`, `finalize()` APIs
  - Integrates with mocked SSE endpoints for initial testing
  - Uses `requestAnimationFrame` throttling for UI updates
  - Proper EventSource cleanup on unmount

### 1.2 Create `ConversationModal` Component
- **File**: `planexe-frontend/src/components/conversation/ConversationModal.tsx` (NEW)
- **Purpose**: Modal wrapper for conversation timeline and streaming displays
- **Key Features**:
  - Left column: conversation timeline with user inputs and assistant output
  - Right column: `StreamingMessageBox`-style panels for text/reasoning/JSON deltas
  - Footer: "Finalize payload" button activates once completion event received
  - Uses shadcn `Dialog` component
  - Includes advanced drawer for model overrides

### 1.3 Create `PromptLauncher` Component
- **File**: `planexe-frontend/src/components/planning/PromptLauncher.tsx` (NEW)
- **Purpose**: Replace `PlanForm` with minimal inline prompt capture
- **Key Features**:
  - Single-line command palette style input with immediate focus
  - Inline helper pills for "Add context" or "Import previous brief"
  - Submit opens `ConversationModal` (no backend call yet)
  - Collects base prompt and optional tags for modal

### 1.4 Create Mock SSE Endpoints for Testing
- **File**: `planexe-frontend/src/lib/api/mock-sse.ts` (NEW)
- **Purpose**: Simulate SSE responses for frontend development
- **Key Features**:
  - Mock `POST /api/conversations` → returns session metadata
  - Mock `GET /api/conversations/{id}/stream` → EventSource with test events
  - Simulates `response.output_text.delta`, `response.reasoning_summary_text.delta` events

## Phase 2: Backend Wiring (FastAPI + Responses API Integration)

### 2.1 Add Conversation Endpoints to API
- **File**: `planexe_api/api.py` (MODIFY)
- **Purpose**: Implement POST→GET handshake pattern endpoints
- **Key Features**:
  - `POST /api/conversations` → initializes Responses API call, returns session metadata
  - `GET /api/conversations/{id}/stream` → SSE endpoint for streaming responses
  - `POST /api/conversations/{id}/finalize` → persist enriched payload
  - Uses session registry for state management

### 2.2 Create Conversation Service Layer
- **File**: `planexe_api/services/conversation_service.py` (NEW)
- **Purpose**: Handle Responses API integration and session management
- **Key Features**:
  - Initializes OpenAI `responses.stream()` calls with proper configuration
  - Manages session registry with TTL cleanup
  - Handles event normalization for `response.output_text.delta`, `response.reasoning_summary_text.delta`
  - Integrates with existing logging/security patterns

### 2.3 Update FastAPI Client
- **File**: `planexe-frontend/src/lib/api/fastapi-client.ts` (MODIFY)
- **Purpose**: Add typed methods for conversation endpoints
- **Key Features**:
  - Add `createConversation()`, `startConversationStream()`, `finalizeConversation()` methods
  - Implement SSE consumption helpers aligned with `analysis-streaming` semantics
  - Extend existing streaming utilities for conversation SSE

### 2.4 Create SSE Manager for Conversations
- **File**: `planexe_api/streaming/conversation_sse_manager.py` (NEW)
- **Purpose**: Low-level SSE response orchestration for conversations
- **Key Features**:
  - Automatic SSE headers and heartbeat keepalives (15s interval)
  - Enriches payloads with conversationId, modelKey, sessionId
  - Lifecycle cleanup on client disconnect

### 2.5 Create Stream Harness for Conversations
- **File**: `planexe_api/streaming/conversation_harness.py` (NEW)
- **Purpose**: Domain-aware wrapper with buffering for conversation streams
- **Key Features**:
  - Buffers reasoning, content, and JSON chunks
  - Provides `pushReasoning()`, `pushContent()`, `pushJsonChunk()` methods
  - Completes with response metadata including token usage and cost

### 2.6 Create OpenAI Event Handler for Conversations
- **File**: `planexe_api/streaming/conversation_event_handler.py` (NEW)
- **Purpose**: Normalize Responses API events for conversation context
- **Key Features**:
  - Handles `response.output_text.delta` → content chunks
  - Handles `response.reasoning_summary_text.delta` → reasoning chunks
  - Handles `response.output_json.delta` → structured JSON
  - Manages `response.created/in_progress/completed` status events

## Phase 3: Frontend Integration (Replace Existing Layout)

### 3.1 Update Main Landing Page Layout
- **File**: `planexe-frontend/src/app/page.tsx` (MODIFY)
- **Purpose**: Replace existing layout with conversation-first grid
- **Key Features**:
  - Use full-width container with `grid-cols-[auto auto auto]` for header metrics
  - Integrate `PromptLauncher` instead of `PlanForm`
  - Slot existing `PlansQueue` and status cards into new grid
  - Add zero-padding `landing-shell` class

### 3.2 Integrate ConversationModal with Landing Page
- **File**: `planexe-frontend/src/app/page.tsx` (MODIFY)
- **Purpose**: Wire modal lifecycle to prompt submission
- **Key Features**:
  - Prompt submit → modal open → streaming → finalize → `createPlan`
  - Pass enriched payload to existing `createPlan` route
  - Handle modal close/cancel actions

### 3.3 Update Streaming Utilities
- **File**: `planexe-frontend/src/lib/streaming/*` (MODIFY)
- **Purpose**: Extend existing streaming for conversation SSE
- **Key Features**:
  - Create `createConversationStream` helper function
  - Integrate with `useResponsesConversation` hook
  - Handle SSE event types: `stream.chunk`, `stream.complete`, `stream.error`

## Phase 4: Polish (Visual and UX Enhancements)

### 4.1 Add Tailwind Utility Classes
- **File**: `planexe-frontend/src/styles/globals.css` (MODIFY)
- **Purpose**: Define compact layout utilities
- **Key Features**:
  - Add `landing-shell` class for zero-padding containers
  - Define compact card variants (8px inner padding)
  - Ensure dark mode contrast with denser layout

### 4.2 Tune Responsive Breakpoints
- **File**: `planexe-frontend/src/components/conversation/ConversationModal.tsx` (MODIFY)
- **Purpose**: Optimize modal for different screen sizes
- **Key Features**:
  - Responsive grid for conversation timeline and streaming panels
  - Mobile-friendly drawer for advanced options
  - Typography scaling for streaming content

### 4.3 Add Advanced Drawer Component
- **File**: `planexe-frontend/src/components/conversation/ConversationModal.tsx` (MODIFY)
- **Purpose**: Hide advanced toggles in collapsible drawer
- **Key Features**:
  - Model selection override (default `gpt-5-mini`)
  - Speed toggle and API key input
  - Collapsible design for power users

## Phase 5: QA & Regression Testing

### 5.1 Test Pipeline Integration
- **File**: `planexe-frontend/src/app/page.tsx` (TEST)
- **Purpose**: Verify enriched payload launches Luigi pipeline correctly
- **Key Features**:
  - Test `createPlan` call with enriched payload shape
  - Verify existing FastAPI contracts remain intact
  - Check fallback behavior for failed enrichments

### 5.2 Test Streaming Functionality
- **File**: `planexe-frontend/src/hooks/useResponsesConversation.ts` (TEST)
- **Purpose**: Validate SSE streaming and error handling
- **Key Features**:
  - Test streaming cancellation and reconnection
  - Verify error states and resume options
  - Check EventSource cleanup on modal close

### 5.3 Update Documentation
- **File**: `CHANGELOG.md` (MODIFY)
- **Purpose**: Document new conversation-first flow
- **Key Features**:
  - Update user-facing documentation
  - Note removal of direct model selection
  - Document advanced drawer functionality

## Impacted Files Summary

### New Files (9)
- `planexe-frontend/src/hooks/useResponsesConversation.ts`
- `planexe-frontend/src/components/conversation/ConversationModal.tsx`
- `planexe-frontend/src/components/planning/PromptLauncher.tsx`
- `planexe-frontend/src/lib/api/mock-sse.ts`
- `planexe_api/services/conversation_service.py`
- `planexe_api/streaming/conversation_sse_manager.py`
- `planexe_api/streaming/conversation_harness.py`
- `planexe_api/streaming/conversation_event_handler.py`

### Modified Files (5)
- `planexe_api/api.py`
- `planexe-frontend/src/lib/api/fastapi-client.ts`
- `planexe-frontend/src/lib/streaming/*` (multiple files)
- `planexe-frontend/src/app/page.tsx`
- `planexe-frontend/src/styles/globals.css`
- `CHANGELOG.md`

## Dependencies and Prerequisites
- Ensure FastAPI backend has OpenAI API credentials configured
- Responses API integration requires `openai.responses.stream()` support
- Frontend must support EventSource for SSE connections
- Existing Luigi pipeline remains untouched

## Success Criteria
- Landing page opens conversation modal on prompt submission
- Modal streams Responses API output with proper event handling
- Enriched payload successfully launches existing Luigi pipeline
- All streaming follows documented event types and patterns
- No reliance on external training data - implementation based solely on provided documents
