# GPT-5 Streaming Integration Plan

PlanExe still routes all GPT calls through the legacy Chat Completions client and forwards raw Luigi stdout over WebSockets, so the real-time reasoning stream from the Responses API never reaches the UI. The new Responses guide requires streaming with `reasoning.effort`, `reasoning.summary`, and `text.verbosity` set explicitly, otherwise no reasoning deltas are emitted.

To adopt the "GPT-5 mini primary / GPT-5 nano fallback" direction while showing live reasoning, we need coordinated backend, pipeline, and frontend changes outlined below.

### 1. Align the model catalog with "mini primary, nano fallback"

`llm_config.json` still maps the UI's `gpt-5-mini-2025-08-07` entry to the nano model, and the Luigi default is hard-coded to that ID. The form also labels it "Default: GPT-5 Nano," so the intended hierarchy is inconsistent.

Fixing this ensures the executor starts with GPT-5 mini and automatically falls back to GPT-5 nano when needed.

### 2. Replace Chat Completions with Responses API streaming in `SimpleOpenAILLM`

`SimpleOpenAILLM` invokes `client.chat.completions.create()` and fakes streaming by yielding the final response, so no reasoning deltas ever surface. This class must switch to `client.responses.stream()` and enforce the reasoning/verbosity knobs from the guide.

### 3. Emit structured LLM streaming events from the Luigi process

Luigi tasks still call `RedlineGate.execute()` (and dozens of similar helpers) synchronously, with no channel to push intermediate reasoning out. To surface real-time deltas, inject a lightweight event emitter that each task can use without breaking the existing interfaces.

### 4. Bridge streaming events through FastAPI's WebSocket layer

`PipelineExecutionService` currently forwards each stdout line to WebSocket clients as a generic "log" message. It needs to recognize the new `LLM_STREAM` markers, parse the JSON, and broadcast a dedicated message type so the UI can render reasoning separately.

### 5. Present real-time reasoning and content deltas in the UI

The React monitor only watches for log/status strings and has no notion of streaming text. Extend it to visualize the new message type and buffer reasoning/output separately, similar to the client example in the Responses guide.

### 6. Persist reasoning summaries and token metrics

`LLMInteraction` already has `response_metadata`, `input_tokens`, and `output_tokens`, but today tasks only store final JSON bodies after the stream finishes. Capture the aggregated reasoning and token counts so operators can audit model behavior after the run.

### 7. Documentation and regression coverage

Once streaming is wired end-to-end, update developer docs so future contributors know how to work with the Responses API flow, and add smoke/regression tests where feasible.

Implementing these tasks will promote GPT-5 mini to the primary slot, stream GPT-5 reasoning in real time, and preserve full traces for audits—all while staying aligned with the Responses API guide.

## File Path Normalization

All file paths in this document have been normalized to use absolute paths from the workspace root (`d:\GitHub\PlanExe\`).
