# OpenAI Responses API Streaming Implementation Guide

**Author:** Cascade AI  
**Date:** 2025-10-18  
**For:** External Developer Working on Similar Projects

---

## Executive Summary

This guide documents how we successfully implemented real-time streaming with the OpenAI Responses API in ModelCompare. After fixing critical bugs in our initial implementation, we built a robust architecture using a **POST→GET SSE handshake pattern** with specialized streaming infrastructure. This guide will help you implement a similar modal-based streaming system in your project.

---

## Background: The Problem We Solved

### Initial Challenges

Our initial Responses API implementation had three critical bugs:

1. **Message Array Conversion Bug**: We incorrectly converted structured message arrays into concatenated strings
2. **Non-Existent Event Types**: We listened for event types that don't exist in the Responses API (`response.reasoning_summary_text.delta`, `response.content_part.added`)
3. **Overly Complex Response Parsing**: We used complex fallback logic instead of direct property access

### The Solution

We completely refactored to use:
- OpenAI's official `responses.stream()` SDK method
- Correct event types from the actual Responses API specification
- A centralized event handler that normalizes all streaming events
- A POST→GET handshake pattern for reliable SSE connections

---

## Architecture Overview

### The POST→GET Handshake Pattern

```
Client                    Server
  │                         │
  │  POST /stream/init      │
  │  ────────────────────>  │  Create session,
  │                         │  validate payload,
  │  { sessionId,           │  return session ID
  │    taskId,              │
  │    modelKey }           │
  │  <────────────────────  │
  │                         │
  │  GET /stream/{task}/{model}/{session}
  │  ────────────────────>  │  Open EventSource,
  │                         │  start streaming
  │  SSE events...          │
  │  <────────────────────  │
  │                         │
```

### Why This Pattern?

1. **Separation of Concerns**: POST validates and initializes, GET streams
2. **Better Error Handling**: Validation errors return immediately via POST
3. **Session Management**: Unique session IDs prevent collisions
4. **Proxy Compatibility**: Standard SSE GET requests work with reverse proxies

---

## Core Components

### 1. SSE Manager (`server/streaming/sse-manager.ts`)

**Purpose**: Low-level SSE response orchestration

```typescript
const manager = new SseStreamManager(res, {
  taskId: 'debate',
  modelKey: 'gpt-5-nano',
  sessionId: 'unique-session-id',
  heartbeatIntervalMs: 15000  // 15s keepalives
});

// Send events
manager.init({ debateSessionId: 'abc123' });
manager.status({ phase: 'streaming' });
manager.chunk({ type: 'text', delta: 'Hello' });
manager.complete({ responseId: 'resp_123' });
manager.error({ error: 'Something failed' });
```

**Key Features**:
- Automatic SSE headers
- Heartbeat keepalives (prevents proxy timeouts)
- Enriches all payloads with taskId/modelKey/sessionId
- Lifecycle cleanup on client disconnect

### 2. Stream Harness (`server/streaming/stream-harness.ts`)

**Purpose**: Domain-aware wrapper with buffering

```typescript
const harness = new StreamHarness(manager);

harness.init({
  debateSessionId: 'abc123',
  turnNumber: 3,
  modelId: 'gpt-5-nano',
  role: 'AFFIRMATIVE'
});

// Buffer and emit chunks
harness.pushReasoning('Thinking about...');
harness.pushContent('The answer is...');
harness.pushJsonChunk({ structured: 'data' });

// Complete with metadata
harness.complete({
  responseId: 'resp_123',
  tokenUsage: { input: 100, output: 200 },
  cost: { total: 0.0015 }
});

// Access final aggregates
const reasoning = harness.getReasoning();
const content = harness.getContent();
```

### 3. OpenAI Event Handler (`server/streaming/openai-event-handler.ts`)

**Purpose**: Normalize Responses API events

```typescript
import { handleResponsesStreamEvent } from './streaming/openai-event-handler.js';

for await (const event of stream) {
  handleResponsesStreamEvent(event, {
    onReasoningDelta: (delta) => harness.pushReasoning(delta),
    onContentDelta: (delta) => harness.pushContent(delta),
    onJsonDelta: (json) => harness.pushJsonChunk(json),
    onStatus: (phase) => harness.status(phase),
    onRefusal: (payload) => handleRefusal(payload),
    onError: (error) => harness.error(error)
  });
}
```

**Supported Event Types**:
- `response.output_text.delta` → Content
- `response.reasoning_summary_text.delta` → Reasoning
- `response.output_json.delta` → Structured JSON
- `response.created/in_progress/completed` → Status
- `response.failed/error` → Errors

### 4. OpenAI Provider (`server/providers/openai.ts`)

**Purpose**: Call Responses API with proper configuration

```typescript
async callModelStreaming(options: StreamingCallOptions): Promise<void> {
  const stream = await openai.responses.stream({
    model: 'gpt-5-nano-2025-04-14',
    input: this.mapMessagesToResponsesInput(messages),
    max_output_tokens: 128000,
    stream: true,
    store: true,
    reasoning: {
      summary: 'detailed',
      effort: 'medium'
    },
    text: {
      verbosity: 'high'
    }
  });

  let aggregatedContent = "";
  let aggregatedReasoning = "";

  for await (const event of stream) {
    handleResponsesStreamEvent(event, {
      onContentDelta: delta => {
        aggregatedContent += delta;
        options.onContentChunk(delta);
      },
      onReasoningDelta: delta => {
        aggregatedReasoning += delta;
        options.onReasoningChunk(delta);
      },
      onError: options.onError
    });
  }

  const finalResponse = await stream.finalResponse();
  options.onComplete(
    finalResponse.id,
    finalResponse.usage,
    calculateCost(finalResponse.usage),
    {
      content: aggregatedContent,
      reasoning: aggregatedReasoning
    }
  );
}
```

---

## Client-Side Implementation

### 1. React Hook (`client/src/hooks/useAdvancedStreaming.ts`)

**Purpose**: Manage streaming state with ref-backed buffers

```typescript
const {
  reasoning,
  content,
  isStreaming,
  error,
  responseId,
  tokenUsage,
  cost,
  progress,
  startStream,
  cancelStream
} = useAdvancedStreaming();

// Start streaming
await startStream({
  modelId: 'gpt-5-nano-2025-04-14',
  topic: 'AI Ethics',
  role: 'AFFIRMATIVE',
  intensity: 7,
  turnNumber: 3,
  previousResponseId: 'resp_prev',
  sessionId: 'existing-session-id'
});
```

**Key Implementation Details**:
- Uses `useRef` for buffers to avoid stale closures
- `requestAnimationFrame` throttling for UI updates
- Proper EventSource cleanup on unmount
- Handles all SSE event types (`stream.chunk`, `stream.complete`, etc.)

### 2. Display Component (`client/src/components/StreamingDisplay.tsx`)

**Purpose**: Render live streaming content

```tsx
<StreamingDisplay
  reasoning={reasoning}
  content={content}
  isStreaming={isStreaming}
  error={error}
  modelName="GPT-5 Nano"
  modelProvider="OpenAI"
  progress={progress}
  estimatedCost={estimatedCost}
/>
```

**Browser Extension Protection**:
```tsx
<div
  data-gramm="false"
  data-gramm_editor="false"
  data-enable-grammarly="false"
  data-lpignore="true"
  data-form-type="other"
>
  {/* Streaming content */}
</div>
```

---

## Implementation Guide for Your Modal

### Step 1: Server Routes

Create two endpoints:

```typescript
// POST /api/your-feature/stream/init
router.post('/stream/init', async (req, res) => {
  try {
    const payload = validateYourPayload(req.body);
    
    const sessionId = generateSessionId();
    const taskId = 'your-feature';
    const modelKey = payload.modelId;
    
    // Store session metadata
    sessionRegistry.set(sessionId, {
      payload,
      createdAt: Date.now(),
      expiresAt: Date.now() + 300000 // 5 minutes
    });
    
    res.json({
      sessionId,
      taskId,
      modelKey,
      expiresAt: new Date(Date.now() + 300000).toISOString()
    });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// GET /api/your-feature/stream/:taskId/:modelKey/:sessionId
router.get('/stream/:taskId/:modelKey/:sessionId', async (req, res) => {
  const { taskId, modelKey, sessionId } = req.params;
  
  const session = sessionRegistry.get(sessionId);
  if (!session) {
    return res.status(404).json({ error: 'Session not found' });
  }
  
  const manager = new SseStreamManager(res, {
    taskId,
    modelKey,
    sessionId
  });
  
  const harness = new StreamHarness(manager);
  
  try {
    await yourStreamingLogic(harness, session.payload);
  } catch (error) {
    harness.error(error);
  } finally {
    sessionRegistry.delete(sessionId);
  }
});
```

### Step 2: Streaming Logic

```typescript
async function yourStreamingLogic(harness, payload) {
  harness.init({
    // Your metadata
  });
  
  harness.status('resolving_provider');
  
  const provider = getProviderForModel(payload.modelId);
  
  harness.status('stream_start');
  
  await provider.callModelStreaming({
    modelId: payload.modelId,
    messages: payload.messages,
    onReasoningChunk: (chunk) => harness.pushReasoning(chunk),
    onContentChunk: (chunk) => harness.pushContent(chunk),
    onJsonChunk: (json) => harness.pushJsonChunk(json),
    onComplete: async (responseId, usage, cost, extras) => {
      // Save to database
      await saveResults({
        content: extras?.content ?? harness.getContent(),
        reasoning: extras?.reasoning ?? harness.getReasoning(),
        responseId,
        usage,
        cost
      });
      
      harness.complete({
        responseId,
        tokenUsage: usage,
        cost
      });
    },
    onError: (error) => harness.error(error)
  });
}
```

### Step 3: Client Hook

```typescript
export function useYourFeatureStreaming() {
  const [state, setState] = useState({
    reasoning: '',
    content: '',
    isStreaming: false,
    error: null,
    responseId: null
  });
  
  const eventSourceRef = useRef(null);
  
  const startStream = useCallback(async (options) => {
    // POST to init
    const initRes = await fetch('/api/your-feature/stream/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options)
    });
    
    const { sessionId, taskId, modelKey } = await initRes.json();
    
    // Open EventSource
    const url = `/api/your-feature/stream/${taskId}/${modelKey}/${sessionId}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;
    
    eventSource.addEventListener('stream.chunk', (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'reasoning') {
        setState(prev => ({
          ...prev,
          reasoning: prev.reasoning + data.delta
        }));
      } else if (data.type === 'text') {
        setState(prev => ({
          ...prev,
          content: prev.content + data.delta
        }));
      }
    });
    
    eventSource.addEventListener('stream.complete', (event) => {
      const data = JSON.parse(event.data);
      setState(prev => ({
        ...prev,
        isStreaming: false,
        responseId: data.responseId
      }));
      eventSource.close();
    });
  }, []);
  
  return { ...state, startStream };
}
```

### Step 4: Modal Component

```tsx
export function YourFeatureModal({ isOpen, onClose, options }) {
  const { reasoning, content, isStreaming, startStream } =
    useYourFeatureStreaming();
  
  useEffect(() => {
    if (isOpen) {
      startStream(options);
    }
  }, [isOpen]);
  
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Streaming Results</DialogTitle>
        </DialogHeader>
        
        <StreamingDisplay
          reasoning={reasoning}
          content={content}
          isStreaming={isStreaming}
        />
      </DialogContent>
    </Dialog>
  );
}
```

---

## Key Lessons Learned

### 1. **Message Array Formatting**
✅ **DO**: Pass message arrays directly to Responses API
```typescript
input: [
  { role: 'system', content: 'You are a helpful assistant' },
  { role: 'user', content: 'Hello!' }
]
```

❌ **DON'T**: Concatenate into strings
```typescript
input: 'System: You are a helpful assistant\nUser: Hello!'
```

### 2. **Event Types Are Specific**
✅ **DO**: Use actual Responses API event types
```typescript
'response.output_text.delta'
'response.reasoning_summary_text.delta'
'response.output_json.delta'
```

❌ **DON'T**: Invent event types
```typescript
'response.content_part.added'  // Doesn't exist!
```

### 3. **Use SDK Streaming Helper**
✅ **DO**: Use official SDK method
```typescript
const stream = await openai.responses.stream(payload);
```

❌ **DON'T**: Parse fetch streams manually
```typescript
const response = await fetch(...);
const reader = response.body.getReader();
```

### 4. **Buffer Aggregation**
Always aggregate chunks on the server AND pass through onComplete:
```typescript
onComplete: (id, usage, cost, extras) => {
  const finalContent = extras?.content ?? harness.getContent();
  const finalReasoning = extras?.reasoning ?? harness.getReasoning();
  // Save to database with BOTH
}
```

### 5. **Ref-Backed State**
Use refs for streaming buffers to avoid React stale closures:
```typescript
const contentBufferRef = useRef('');
const scheduleFlush = useCallback(() => {
  requestAnimationFrame(() => {
    setState({ content: contentBufferRef.current });
  });
}, []);
```

---

## Environment Variables

Streaming defaults are now centralised in `planexe_api/config.py`. The optional
environment variables below override the runtime configuration that both the
FastAPI request model and the streaming harness consume.

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_TIMEOUT_MS=600000               # 10 minutes
DEBUG_SAVE_RAW=true                    # Save raw responses

# Streaming analysis overrides (all optional)
OPENAI_MAX_OUTPUT_TOKENS=16024         # Overrides runtime + validation defaults
OPENAI_MAX_OUTPUT_TOKENS_CEILING=32768 # Hard ceiling enforced in validation
OPENAI_MIN_OUTPUT_TOKENS=512           # Lower bound for streaming responses
OPENAI_REASONING_EFFORT=high           # Maps to AnalysisStreamRequest.reasoning_effort
OPENAI_REASONING_SUMMARY=detailed      # Maps to reasoning_summary
OPENAI_TEXT_VERBOSITY=high             # Maps to text_verbosity
```

---

## Debugging Tips

### 1. Enable Raw Response Logging
```typescript
if (process.env.DEBUG_SAVE_RAW === 'true') {
  fs.writeFileSync(
    `./debug-${Date.now()}.json`,
    JSON.stringify(finalResponse, null, 2)
  );
}
```

### 2. Monitor Event Types
```typescript
handleResponsesStreamEvent(event, {
  ...callbacks,
  onStatus: (phase, data) => {
    console.log(`Event: ${event.type} → ${phase}`, data);
    callbacks.onStatus?.(phase, data);
  }
});
```

### 3. Check Session Registry
```typescript
console.log('Active sessions:', sessionRegistry.size);
console.log('Session TTL:', session.expiresAt - Date.now());
```

---

## Common Pitfalls

1. **Forgetting finalResponse()**: Always call `await stream.finalResponse()` to get usage/cost data
2. **Missing Heartbeats**: Add keepalives or proxies will kill the connection
3. **Browser Extensions**: Add Grammarly/LastPass protection attributes
4. **State Leaks**: Clean up EventSource on unmount
5. **Session Expiry**: Implement TTL cleanup for session registry

---

## Performance Optimizations

1. **RAF Throttling**: Use `requestAnimationFrame` for UI updates (60fps)
2. **Batch Writes**: Buffer small deltas before setState
3. **Selective Re-renders**: Memoize selectors with Zustand
4. **Cleanup Timers**: Use AbortController for fetch requests
5. **Memory Management**: Delete sessions after completion

---

## References

- **Changelog**: `CHANGELOG.md` v0.4.9, v0.4.10
- **Provider Code**: `server/providers/openai.ts` lines 600-773
- **Streaming Hook**: `client/src/hooks/useAdvancedStreaming.ts`
- **Event Handler**: `server/streaming/openai-event-handler.ts`
- **SSE Manager**: `server/streaming/sse-manager.ts`
- **Harness**: `server/streaming/stream-harness.ts`

---

## Support

For questions about this implementation:
1. Check the changelog for version-specific changes
2. Review the codemap trace for request flow
3. Test with the debate mode `/debate` endpoint
4. Examine debug logs with `DEBUG_SAVE_RAW=true`

**Last Updated**: 2025-10-18  
**Implementation Status**: ✅ Production Ready
