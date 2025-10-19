"""Domain harness for streaming conversation buffers and SSE-ready events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ConversationSummary:
    """Aggregated result for a streamed conversation."""

    conversation_id: str
    model_key: str
    session_id: str
    reasoning_text: str
    content_text: str
    json_chunks: List[Dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation of the summary."""

        return {
            "conversation_id": self.conversation_id,
            "model_key": self.model_key,
            "session_id": self.session_id,
            "reasoning_text": self.reasoning_text,
            "content_text": self.content_text,
            "json_chunks": self.json_chunks,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "usage": self.usage,
            "error": self.error,
            "metadata": self.metadata,
        }


class ConversationHarness:
    """Buffer and normalize conversation streaming payloads."""

    def __init__(
        self,
        *,
        conversation_id: str,
        model_key: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.model_key = model_key
        self.session_id = session_id
        self.started_at = datetime.now(timezone.utc)
        self.metadata = metadata or {}

        self._reasoning_parts: List[str] = []
        self._content_parts: List[str] = []
        self._json_chunks: List[Dict[str, Any]] = []
        self._events: List[Dict[str, Any]] = []
        self._usage: Dict[str, Any] = {}
        self._error: Optional[str] = None
        self._completed_at: Optional[datetime] = None
        self._response_id: Optional[str] = None

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _record_event(self, event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        envelope = {
            "event": event,
            "timestamp": self._timestamp(),
            "data": {
                "conversation_id": self.conversation_id,
                "model_key": self.model_key,
                "session_id": self.session_id,
                **payload,
            },
        }
        self._events.append(envelope)
        return envelope

    def emit_created(self, response_id: Optional[str] = None) -> Dict[str, Any]:
        """Emit the initial event once OpenAI acknowledges the stream."""

        if response_id:
            self._response_id = response_id
        payload: Dict[str, Any] = {
            "conversation_id": self.conversation_id,
            "model_key": self.model_key,
            "created_at": self.started_at.isoformat(),
        }
        if self._response_id:
            payload["response_id"] = self._response_id
        return self._record_event("response.created", payload)

    def push_reasoning(self, delta: str) -> Dict[str, Any]:
        """Append a reasoning delta and return the SSE-ready envelope."""

        if not delta:
            return {}
        self._reasoning_parts.append(delta)
        return self._record_event(
            "response.reasoning_summary_text.delta",
            {
                "response_id": self._response_id,
                "delta": delta,
                "aggregated": "".join(self._reasoning_parts),
            },
        )

    def push_content(self, delta: str) -> Dict[str, Any]:
        """Append a content delta and return the SSE-ready envelope."""

        if not delta:
            return {}
        self._content_parts.append(delta)
        return self._record_event(
            "response.output_text.delta",
            {
                "response_id": self._response_id,
                "delta": delta,
                "aggregated": "".join(self._content_parts),
            },
        )

    def push_json_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Store a JSON chunk emitted by the LLM."""

        if not chunk:
            return {}
        self._json_chunks.append(chunk)
        return self._record_event(
            "response.output_json.delta",
            {
                "response_id": self._response_id,
                "delta": chunk,
            },
        )

    def set_remote_conversation_id(self, conversation_id: str) -> Dict[str, Any]:
        """Persist the upstream conversation identifier when provided."""

        if not conversation_id:
            return {}
        if "remote_conversation_id" not in self.metadata:
            self.metadata["remote_conversation_id"] = conversation_id
        return {}

    def mark_error(self, message: str) -> Dict[str, Any]:
        """Record an error state and generate a stream event."""

        self._error = message
        return self._record_event(
            "response.error",
            {
                "response_id": self._response_id,
                "message": message,
            },
        )

    def set_usage(self, usage: Dict[str, Any]) -> None:
        """Attach token usage or billing information to the harness."""

        self._usage = usage

    def pop_events(self) -> List[Dict[str, Any]]:
        """Return and clear buffered events for dispatch."""

        events = list(self._events)
        self._events.clear()
        return events

    def complete(self) -> ConversationSummary:
        """Finalize the harness and produce a conversation summary."""

        self._completed_at = datetime.now(timezone.utc)
        summary = ConversationSummary(
            conversation_id=self.conversation_id,
            model_key=self.model_key,
            session_id=self.session_id,
            reasoning_text="".join(self._reasoning_parts),
            content_text="".join(self._content_parts),
            json_chunks=list(self._json_chunks),
            started_at=self.started_at,
            completed_at=self._completed_at,
            usage=dict(self._usage),
            error=self._error,
            metadata=self.metadata,
        )

        self._record_event(
            "response.completed",
            {
                "response_id": self._response_id,
                "conversation_id": self.conversation_id,
                "completed_at": self._completed_at.isoformat(),
                "usage": self._usage,
            },
        )
        return summary

    def emit_final_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Emit the finalResponse payload for downstream aggregation."""

        envelope_payload = {
            "response": payload,
            "summary": {
                "response_id": self._response_id,
                "text": "".join(self._content_parts),
                "reasoning": "".join(self._reasoning_parts),
                "json": list(self._json_chunks),
                "usage": self._usage,
            },
        }
        return self._record_event("final", envelope_payload)

    def snapshot(self) -> Dict[str, Any]:
        """Provide a lightweight snapshot without completing the stream."""

        return {
            "conversation_id": self.conversation_id,
            "model_key": self.model_key,
            "session_id": self.session_id,
            "reasoning_text": "".join(self._reasoning_parts),
            "content_text": "".join(self._content_parts),
            "json_chunks": list(self._json_chunks),
            "events": list(self._events),
            "usage": dict(self._usage),
            "error": self._error,
            "metadata": self.metadata,
            "started_at": self.started_at.isoformat(),
            "completed_at": self._completed_at.isoformat() if self._completed_at else None,
        }
