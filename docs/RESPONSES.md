# OpenAI Responses API - Streaming Implementation Guide

**Author**: Claude Code
**Date**: 2025-10-15
**Target**: Developers implementing GPT-5 streaming with reasoning capture
**API**: OpenAI Responses API (`/v1/responses`) with Server-Sent Events (SSE)

---

## Overview

The **Responses API** is OpenAI's endpoint for advanced reasoning models (GPT-5, o3, o4). It differs significantly from Chat Completions API and requires special handling for streaming reasoning data.

### Key Differences from Chat Completions API

| Feature | Chat Completions (`/v1/chat/completions`) | Responses API (`/v1/responses`) |
|---------|------------------------------------------|--------------------------------|
| **Models** | GPT-4, GPT-4o, older models | GPT-5, o3, o4 reasoning models |
| **Reasoning** | Not available | Built-in reasoning tracking |
| **Output Location** | `choices[0].message.content` | `output_text` OR `output[]` array |
| **Structured Output** | `response_format` parameter | `text.format.json_schema` nested object |
| **Reasoning Control** | N/A | `reasoning.effort`, `reasoning.summary`, `text.verbosity` |
| **Token Accounting** | Combined in `completion_tokens` | Separate `reasoning_tokens` field |
| **Messages Format** | `messages` array | `input` array (same structure) |

---

## Part 1: Understanding the Responses API Structure

### Request Payload

```typescript
interface ResponsesAPIPayload {
  model: string;                        // "gpt-5-mini-2025-08-07"
  input: Array<{                        // Same as "messages" in Chat Completions
    role: "system" | "user" | "assistant";
    content: string;
  }>;

  // Reasoning configuration (GPT-5 specific)
  reasoning?: {
    effort?: "minimal" | "low" | "medium" | "high";  // Controls depth
    summary?: "auto" | "detailed" | "concise";       // Summary style
  };

  // Text configuration (verbosity + structured output)
  text?: {
    verbosity?: "low" | "medium" | "high";           // Reasoning detail in output
    format?: {
      type: "json_schema";
      name: string;
      strict: boolean;
      schema: object;                                // JSON schema for structured output
    };
  };

  // Standard parameters
  temperature?: number;                              // Only for non-reasoning models
  max_output_tokens?: number;                        // Default: 128000 for GPT-5
  store?: boolean;                                   // Enable conversation chaining
  previous_response_id?: string;                     // For multi-turn conversations
  stream?: boolean;                                  // Enable SSE streaming
}
```

### Response Structure (Non-Streaming)

```typescript
interface ResponsesAPIResponse {
  id: string;                                        // Response ID for chaining
  status: "completed" | "failed" | "incomplete";

  // Output variants (model-dependent)
  output_text?: string;                              // Preferred: Simple text output
  output_parsed?: object;                            // JSON schema enforced output
  output?: Array<{                                   // Fallback: Block-based output
    type: "reasoning" | "message" | "text";
    content?: string;
    summary?: string;
  }>;

  // Reasoning data (if reasoning model)
  output_reasoning?: {
    summary: string | string[] | object;             // Reasoning summary
    items?: Array<string | object>;                  // Reasoning steps
  };

  // Token usage
  usage: {
    input_tokens: number;
    output_tokens: number;
    output_tokens_details?: {
      reasoning_tokens?: number;                     // Separate reasoning token count
    };
  };
}
```

---

## Part 2: Implementing SSE Streaming

### Step 1: Enable Streaming in Request

```typescript
const response = await openai.responses.stream({
  model: "gpt-5-mini-2025-08-07",
  input: [
    { role: "system", content: systemPrompt },
    { role: "user", content: userPrompt }
  ],
  reasoning: {
    effort: "medium",      // Control reasoning depth
    summary: "detailed"    // Get detailed reasoning summary
  },
  text: {
    verbosity: "high",     // Emit detailed reasoning deltas
    format: {              // Structured JSON output
      type: "json_schema",
      name: "puzzle_solution",
      strict: true,
      schema: yourJsonSchema
    }
  },
  stream: true,            // CRITICAL: Enable streaming
  max_output_tokens: 128000
});
```

### Step 2: Handle Stream Events

The stream emits different event types. You MUST handle all of them:

```typescript
// Use async iteration (OpenAI SDK v4+)
for await (const event of response) {
  switch (event.type) {
    case "response.reasoning_summary_text.delta":
      // Real-time reasoning summary chunks
      const reasoningDelta = event.delta;
      console.log("[Reasoning]", reasoningDelta);
      aggregatedReasoning += reasoningDelta;
      // Emit to SSE client: send("stream.chunk", { type: "reasoning", delta: reasoningDelta })
      break;

    case "response.reasoning_summary_part.added":
      // Complete reasoning parts (alternative format)
      const reasoningPart = event.part?.text;
      aggregatedReasoning += reasoningPart;
      break;

    case "response.content_part.added":
      // Output text chunks
      const textDelta = event.part?.text;
      aggregatedOutput += textDelta;
      // Emit to SSE client: send("stream.chunk", { type: "text", delta: textDelta })
      break;

    case "response.in_progress":
      // Status update (optional)
      console.log("[Status] Processing...");
      break;

    case "response.completed":
      // Stream finished successfully
      console.log("[Status] Stream completed");
      break;

    case "response.failed":
    case "error":
      // Handle errors
      const errorMsg = event.error?.message || "Stream failed";
      console.error("[Error]", errorMsg);
      throw new Error(errorMsg);
      break;
  }
}
```

### Step 3: Extract Final Response

After streaming completes, get the final response:

```typescript
const finalResponse = await response.finalResponse();

// Extract output (priority order)
let outputText: string;
if (finalResponse.output_text) {
  outputText = finalResponse.output_text;           // Preferred
} else if (finalResponse.output_parsed) {
  outputText = JSON.stringify(finalResponse.output_parsed);  // Structured output
} else if (finalResponse.output && Array.isArray(finalResponse.output)) {
  // Extract from output[] array (gpt-5-nano format)
  const textBlock = finalResponse.output.find(block => block.type === "text");
  outputText = textBlock?.text || "";
}

// Extract reasoning (priority order)
let reasoningLog: string = "";
if (finalResponse.output_reasoning?.summary) {
  const summary = finalResponse.output_reasoning.summary;

  if (typeof summary === "string") {
    reasoningLog = summary;
  } else if (Array.isArray(summary)) {
    reasoningLog = summary.map(s =>
      typeof s === "string" ? s : (s?.text || s?.content || JSON.stringify(s))
    ).join("\n\n");
  } else if (typeof summary === "object") {
    reasoningLog = summary.text || summary.content || JSON.stringify(summary, null, 2);
  }
}

// Fallback: Scan output[] for reasoning blocks
if (!reasoningLog && finalResponse.output) {
  const reasoningBlocks = finalResponse.output.filter(block =>
    block.type === "reasoning" || block.type === "Reasoning"
  );
  reasoningLog = reasoningBlocks.map(block =>
    block.content || block.summary || JSON.stringify(block)
  ).join("\n\n");
}

// Extract token usage
const tokenUsage = {
  input: finalResponse.usage.input_tokens,
  output: finalResponse.usage.output_tokens,
  reasoning: finalResponse.usage.output_tokens_details?.reasoning_tokens || 0
};
```

---

## Part 3: Critical Configuration Requirements

### For GPT-5 Models to Emit Reasoning Deltas

You MUST set ALL three parameters:

```typescript
reasoning: {
  effort: "medium" | "high",        // NOT "minimal" or "low" - those hide deltas
  summary: "detailed"               // Required for summary emission
},
text: {
  verbosity: "high"                 // CRITICAL: Without this, NO reasoning deltas emit
}
```

**What happens if you miss these:**
- ❌ No `reasoning` → No reasoning captured at all
- ❌ `effort: "minimal"` → Reasoning computed but not emitted
- ❌ No `text.verbosity` → Reasoning summary only at END, no real-time deltas
- ❌ `verbosity: "low"` → Sparse reasoning, poor UX

### For o3/o4 Models

```typescript
reasoning: {
  summary: "auto"      // o3/o4 don't support effort or verbosity
}
// No text.verbosity for o3/o4
```

---

## Part 4: SSE Server Implementation

### Express SSE Endpoint

```typescript
app.get("/api/stream/analyze/:taskId/:modelKey", async (req, res) => {
  const { taskId, modelKey } = req.params;
  const sessionId = req.query.sessionId || nanoid();

  // Set SSE headers
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  // Send initial event
  res.write(`event: stream.init\n`);
  res.write(`data: ${JSON.stringify({ sessionId, taskId, modelKey })}\n\n`);

  try {
    // Get puzzle data
    const puzzle = await getPuzzle(taskId);
    const prompt = buildPrompt(puzzle);

    // Start OpenAI stream
    const stream = await openai.responses.stream({
      model: getApiModelName(modelKey),
      input: [
        { role: "system", content: prompt.system },
        { role: "user", content: prompt.user }
      ],
      reasoning: {
        effort: "medium",
        summary: "detailed"
      },
      text: {
        verbosity: "high",
        format: { type: "json_schema", name: "solution", strict: true, schema: yourSchema }
      },
      stream: true
    });

    // Forward events to client
    for await (const event of stream) {
      switch (event.type) {
        case "response.reasoning_summary_text.delta":
          res.write(`event: stream.chunk\n`);
          res.write(`data: ${JSON.stringify({
            type: "reasoning",
            delta: event.delta,
            timestamp: Date.now()
          })}\n\n`);
          break;

        case "response.content_part.added":
          res.write(`event: stream.chunk\n`);
          res.write(`data: ${JSON.stringify({
            type: "text",
            delta: event.part?.text,
            timestamp: Date.now()
          })}\n\n`);
          break;

        case "response.completed":
          res.write(`event: stream.status\n`);
          res.write(`data: ${JSON.stringify({ state: "completed" })}\n\n`);
          break;
      }
    }

    // Get final response and save to database
    const finalResponse = await stream.finalResponse();
    const analysis = extractAnalysis(finalResponse);
    await saveToDatabase(analysis);

    // Send completion event
    res.write(`event: stream.complete\n`);
    res.write(`data: ${JSON.stringify({
      status: "success",
      analysisId: analysis.id,
      tokenUsage: analysis.tokenUsage
    })}\n\n`);

    res.end();

  } catch (error) {
    res.write(`event: stream.error\n`);
    res.write(`data: ${JSON.stringify({
      error: error.message
    })}\n\n`);
    res.end();
  }
});
```

---

## Part 5: Client-Side SSE Consumption

### JavaScript/TypeScript Client

```typescript
const eventSource = new EventSource(
  `/api/stream/analyze/${taskId}/${modelKey}?reasoningEffort=medium&reasoningVerbosity=high`
);

let reasoningBuffer = "";
let outputBuffer = "";

eventSource.addEventListener("stream.init", (event) => {
  const data = JSON.parse(event.data);
  console.log("Stream started:", data.sessionId);
});

eventSource.addEventListener("stream.chunk", (event) => {
  const chunk = JSON.parse(event.data);

  if (chunk.type === "reasoning") {
    reasoningBuffer += chunk.delta;
    updateReasoningDisplay(reasoningBuffer);  // Update UI in real-time
  } else if (chunk.type === "text") {
    outputBuffer += chunk.delta;
    updateOutputDisplay(outputBuffer);
  }
});

eventSource.addEventListener("stream.complete", (event) => {
  const result = JSON.parse(event.data);
  console.log("Analysis complete:", result.analysisId);
  console.log("Total tokens:", result.tokenUsage);
  eventSource.close();
});

eventSource.addEventListener("stream.error", (event) => {
  const error = JSON.parse(event.data);
  console.error("Stream error:", error);
  eventSource.close();
});

// Handle connection errors
eventSource.onerror = (error) => {
  console.error("SSE connection error:", error);
  eventSource.close();
};
```

---

## Part 6: Testing & Debugging

### Test with curl

```bash
curl -N -H "Accept: text/event-stream" \
  "http://localhost:5000/api/stream/analyze/PUZZLE_ID/gpt-5-mini?reasoningEffort=medium&reasoningVerbosity=high&reasoningSummaryType=detailed"
```

**Expected output:**
```
event: stream.init
data: {"sessionId":"abc123","taskId":"puzzle_001","modelKey":"gpt-5-mini"}

event: stream.chunk
data: {"type":"reasoning","delta":"Let me analyze the pattern...","timestamp":1234567890}

event: stream.chunk
data: {"type":"reasoning","delta":" The transformation appears to...","timestamp":1234567891}

...

event: stream.complete
data: {"status":"success","analysisId":42,"tokenUsage":{"input":1500,"output":800,"reasoning":6784}}
```

### Debug Checklist

1. **Check server logs for configuration**:
   ```
   [OpenAI-PayloadBuilder] Has reasoning: true     ← MUST be true
   [OpenAI-PayloadBuilder] - verbosity: high       ← MUST be "high"
   [OpenAI-PayloadBuilder] - effort: medium        ← NOT "minimal"
   ```

2. **Verify reasoning tokens are tracked**:
   ```typescript
   console.log("Reasoning tokens:", finalResponse.usage.output_tokens_details?.reasoning_tokens);
   // Should be > 0 for reasoning models
   ```

3. **Check for empty reasoning**:
   ```typescript
   if (!reasoningLog || reasoningLog === "[]" || reasoningLog === "") {
     console.error("Reasoning extraction failed - check configuration!");
   }
   ```

---

## Part 7: Common Pitfalls

### ❌ Pitfall 1: Using Chat Completions API for GPT-5
```typescript
// WRONG - GPT-5 doesn't work with Chat Completions
const response = await openai.chat.completions.create({
  model: "gpt-5-mini-2025-08-07",  // Will fail or use wrong API
  messages: [...]
});
```

### ❌ Pitfall 2: Missing verbosity Parameter
```typescript
// WRONG - No reasoning deltas will emit
text: {
  format: { type: "json_schema", ... }
  // Missing: verbosity: "high"
}
```

### ❌ Pitfall 3: Wrong Token Extraction
```typescript
// WRONG - Reasoning tokens are nested
const tokens = response.usage.reasoning_tokens;  // undefined

// CORRECT
const tokens = response.usage.output_tokens_details?.reasoning_tokens || 0;
```

### ❌ Pitfall 4: Not Handling output[] Array Format
```typescript
// WRONG - Assumes output_text always exists
const text = response.output_text;  // Can be undefined for some models

// CORRECT - Check all formats
const text = response.output_text
  || extractFromOutputArray(response.output)
  || JSON.stringify(response.output_parsed);
```

---

## Summary Checklist

✅ Use `/v1/responses` endpoint, NOT `/v1/chat/completions`
✅ Set `reasoning.effort` to "medium" or "high" (not "minimal")
✅ Set `reasoning.summary` to "detailed"
✅ Set `text.verbosity` to "high" for real-time deltas
✅ Handle ALL stream event types (reasoning, content, status, error)
✅ Extract reasoning from `output_reasoning.summary` with fallbacks
✅ Track reasoning tokens in `output_tokens_details.reasoning_tokens`
✅ Test with curl to verify SSE events emit correctly
✅ Check server logs confirm `Has reasoning: true`

---

**Reference Implementation**: `arc-explainer/server/services/openai.ts` (GPT-5 streaming with full reasoning capture)

**OpenAI Docs**: https://platform.openai.com/docs/api-reference/responses
