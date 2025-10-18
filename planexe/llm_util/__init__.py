"""Thread-local LLM streaming context helpers shared across PlanExe components."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

_STREAM_STATE = threading.local()


def _get_stack() -> List[Dict[str, Any]]:
    stack: Optional[List[Dict[str, Any]]] = getattr(_STREAM_STATE, "stack", None)
    if stack is None:
        stack = []
        _STREAM_STATE.stack = stack
    return stack


def _emit_stream_event(kind: str, context: Dict[str, Any], payload: Dict[str, Any]) -> None:
    envelope = {
        "type": "llm_stream",
        "plan_id": context["plan_id"],
        "stage": context["stage"],
        "interaction_id": context["interaction_id"],
        "event": kind,
        "sequence": context.setdefault("sequence", 0),
        "timestamp": datetime.utcnow().isoformat(),
        "data": payload,
    }
    context["sequence"] = envelope["sequence"] + 1
    try:
        print(f"LLM_STREAM|{json.dumps(envelope, ensure_ascii=False)}", flush=True)
    except Exception:
        # Streaming should never crash the worker; fall back to debug print.
        print(f"LLM_STREAM|{{\"error\": \"failed_to_serialize\", \"event\": \"{kind}\"}}", flush=True)


def push_llm_stream_context(
    *,
    plan_id: str,
    stage: str,
    interaction_id: int,
    prompt_preview: Optional[str] = None,
) -> None:
    stack = _get_stack()
    context = {
        "plan_id": plan_id,
        "stage": stage,
        "interaction_id": interaction_id,
        "prompt_preview": prompt_preview,
        "text_deltas": [],
        "reasoning_deltas": [],
        "final_text": None,
        "final_reasoning": None,
        "usage": {},
        "raw_payload": None,
        "sequence": 0,
        "final_emitted": False,
    }
    stack.append(context)
    start_payload = {"prompt_preview": prompt_preview}
    _emit_stream_event("start", context, start_payload)


def _current_context() -> Optional[Dict[str, Any]]:
    stack = _get_stack()
    if not stack:
        return None
    return stack[-1]


def record_text_delta(delta: str) -> None:
    if not delta:
        return
    context = _current_context()
    if not context:
        return
    context["text_deltas"].append(delta)
    _emit_stream_event("text_delta", context, {"delta": delta})


def record_reasoning_delta(delta: str) -> None:
    if not delta:
        return
    context = _current_context()
    if not context:
        return
    context["reasoning_deltas"].append(delta)
    _emit_stream_event("reasoning_delta", context, {"delta": delta})


def record_final_payload(
    *,
    text: Optional[str],
    reasoning: Optional[str],
    usage: Optional[Dict[str, Any]],
    raw_payload: Optional[Dict[str, Any]],
) -> None:
    context = _current_context()
    if not context:
        return
    if text and not context["text_deltas"]:
        context["text_deltas"].append(text)
    if reasoning and not context["reasoning_deltas"]:
        context["reasoning_deltas"].append(reasoning)
    if text:
        context["final_text"] = text
    if reasoning:
        context["final_reasoning"] = reasoning
    if usage:
        context["usage"] = usage
    if raw_payload:
        context["raw_payload"] = raw_payload
    if not context.get("final_emitted"):
        _emit_stream_event(
            "final",
            context,
            {
                "text": text,
                "reasoning": reasoning,
                "usage": usage,
                "raw_payload": raw_payload,
            },
        )
        context["final_emitted"] = True


def pop_llm_stream_context(
    interaction_id: Optional[int],
    *,
    status: str,
    error: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    stack = _get_stack()
    if not stack:
        return None
    index = None
    if interaction_id is not None:
        for idx in range(len(stack) - 1, -1, -1):
            if stack[idx]["interaction_id"] == interaction_id:
                index = idx
                break
    if index is None:
        index = len(stack) - 1
    context = stack.pop(index)
    if not context.get("final_emitted"):
        record_final_payload(
            text=context.get("final_text") or "".join(context["text_deltas"]),
            reasoning=context.get("final_reasoning") or "\n".join(context["reasoning_deltas"]),
            usage=context.get("usage"),
            raw_payload=context.get("raw_payload"),
        )
    _emit_stream_event("end", context, {"status": status, "error": error})
    aggregated_text = context.get("final_text")
    if not aggregated_text and context["text_deltas"]:
        aggregated_text = "".join(context["text_deltas"])
    aggregated_reasoning = context.get("final_reasoning")
    if not aggregated_reasoning and context["reasoning_deltas"]:
        aggregated_reasoning = "\n".join(context["reasoning_deltas"])
    usage = context.get("usage") or {}
    metadata = {
        "plan_id": context["plan_id"],
        "stage": context["stage"],
        "interaction_id": context["interaction_id"],
        "final_text": aggregated_text,
        "final_reasoning": aggregated_reasoning,
        "text_deltas": context["text_deltas"],
        "reasoning_deltas": context["reasoning_deltas"],
        "usage": usage,
        "raw_payload": context.get("raw_payload"),
        "prompt_preview": context.get("prompt_preview"),
    }
    return metadata


__all__ = [
    "push_llm_stream_context",
    "record_text_delta",
    "record_reasoning_delta",
    "record_final_payload",
    "pop_llm_stream_context",
]