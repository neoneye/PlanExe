"""Map OpenAI Responses streaming events onto ConversationHarness actions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .conversation_harness import ConversationHarness


class ConversationEventHandler:
    """Translate Responses event payloads into harness updates."""

    def __init__(self, harness: ConversationHarness) -> None:
        self._harness = harness
        self._response_id: Optional[str] = None

    @property
    def response_id(self) -> Optional[str]:
        """Most recent response identifier observed from the stream."""

        return self._response_id

    def handle(self, event: Any) -> List[Dict[str, Any]]:
        """Process a streaming event and return emitted SSE envelopes."""

        event_type = getattr(event, "type", None)
        if event_type is None and isinstance(event, dict):
            event_type = event.get("type")
        if not event_type:
            return []

        dispatch: List[Dict[str, Any]] = []
        normalized_type = str(event_type)

        if normalized_type == "response.created":
            self._response_id = self._extract_response_id(event)
            self._harness.emit_init(self._response_id)
            dispatch.extend(self._drain_events())
        elif normalized_type == "response.output_text.delta":
            delta = self._extract_text_delta(event)
            if delta:
                self._harness.push_content(delta)
                dispatch.extend(self._drain_events())
        elif normalized_type == "response.reasoning_summary_text.delta":
            delta = self._extract_reasoning_delta(event)
            if delta:
                self._harness.push_reasoning(delta)
                dispatch.extend(self._drain_events())
        elif normalized_type == "response.output_json.delta":
            delta = self._extract_json_delta(event)
            if delta is not None:
                self._harness.push_json_chunk(delta)
                dispatch.extend(self._drain_events())
        elif normalized_type in {"response.error", "response.failed"}:
            message = self._extract_error_message(event)
            self._harness.mark_error(message)
            dispatch.extend(self._drain_events())

        return dispatch

    def emit_completion(self) -> List[Dict[str, Any]]:
        """Emit buffered completion events as SSE envelopes."""

        return self._drain_events()

    @staticmethod
    def _as_sse_payload(envelope: Dict[str, Any]) -> Dict[str, Any]:
        return {"event": envelope["event"], "data": envelope["data"]}

    def _drain_events(self) -> List[Dict[str, Any]]:
        drained: List[Dict[str, Any]] = []
        for envelope in self._harness.pop_events():
            drained.append(self._as_sse_payload(envelope))
        return drained

    @staticmethod
    def _extract_response_id(event: Any) -> Optional[str]:
        response = getattr(event, "response", None)
        if response is None and isinstance(event, dict):
            response = event.get("response") or event.get("data")
        if isinstance(response, dict):
            response_id = response.get("id")
            if response_id:
                return str(response_id)
        potential = getattr(event, "id", None)
        if isinstance(potential, str):
            return potential
        if isinstance(event, dict):
            candidate = event.get("id")
            if isinstance(candidate, str):
                return candidate
        return None

    @staticmethod
    def _extract_text_delta(event: Any) -> Optional[str]:
        part = getattr(event, "delta", None)
        if part is None and isinstance(event, dict):
            part = event.get("delta") or event.get("text") or event.get("value")
        if isinstance(part, dict):
            text_value = part.get("text") or part.get("value") or part.get("content")
            if isinstance(text_value, list):
                return "".join(str(item) for item in text_value if item)
            if isinstance(text_value, str):
                return text_value
        elif isinstance(part, str):
            return part
        return None

    @staticmethod
    def _extract_reasoning_delta(event: Any) -> Optional[str]:
        delta = getattr(event, "delta", None)
        if delta is None and isinstance(event, dict):
            delta = event.get("delta") or event.get("text") or event.get("value")
        if isinstance(delta, dict):
            reasoning_value = delta.get("text") or delta.get("value") or delta.get("summary")
            if isinstance(reasoning_value, list):
                return "".join(str(item) for item in reasoning_value if item)
            if isinstance(reasoning_value, str):
                return reasoning_value
        elif isinstance(delta, str):
            return delta
        return None

    @staticmethod
    def _extract_json_delta(event: Any) -> Optional[Dict[str, Any]]:
        delta = getattr(event, "delta", None)
        if delta is None and isinstance(event, dict):
            delta = event.get("delta") or event.get("parsed")
        if isinstance(delta, dict):
            return delta
        return None

    @staticmethod
    def _extract_error_message(event: Any) -> str:
        if isinstance(event, dict):
            for key in ("message", "error", "detail"):
                value = event.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        message = getattr(event, "message", None)
        if isinstance(message, str) and message.strip():
            return message
        return "Conversation stream failed"
