"""Streaming analysis orchestration bridging the Responses API to SSE clients."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from fastapi import HTTPException
from openai import APIError

from planexe_api.config import RESPONSES_STREAMING_CONTROLS
from planexe_api.database import DatabaseService, SessionLocal
from planexe_api.models import AnalysisStreamRequest
from planexe_api.streaming.session_store import (
    AnalysisStreamSessionStore,
    CachedAnalysisSession,
)
from planexe.llm_factory import get_llm, is_valid_llm_name
from planexe.llm_util.simple_openai_llm import SimpleOpenAILLM


@dataclass
class PreparedAnalysisPayload:
    """Payload cached between handshake and SSE connection."""

    request: AnalysisStreamRequest
    messages: List[Dict[str, Any]]
    request_options: Dict[str, Any]
    prompt_text: str
    context_text: Optional[str]
    metadata: Dict[str, Any]


class StreamHarness:
    """Utility that enriches SSE events with contextual metadata."""

    def __init__(self, *, task_id: str, model_key: str) -> None:
        self.task_id = task_id
        self.model_key = model_key
        self._queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()
        self._loop = asyncio.get_event_loop()
        self._closed = False

    def _enrich(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(payload)
        data.setdefault("taskId", self.task_id)
        data.setdefault("modelKey", self.model_key)
        return data

    async def emit(self, event: str, payload: Dict[str, Any]) -> None:
        await self._queue.put({"event": event, "data": json.dumps(self._enrich(payload))})

    def emit_from_worker(self, event: str, payload: Dict[str, Any]) -> None:
        asyncio.run_coroutine_threadsafe(self.emit(event, payload), self._loop)

    async def events(self) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._queue.put(None)


class AnalysisStreamService:
    """Coordinates analysis streaming sessions and SSE relays."""

    def __init__(
        self,
        *,
        session_store: AnalysisStreamSessionStore,
    ) -> None:
        self._sessions = session_store

    async def create_session(self, request: AnalysisStreamRequest) -> CachedAnalysisSession:
        """Validate payload, build OpenAI request, and cache for SSE retrieval."""

        if not is_valid_llm_name(request.model_key):
            raise HTTPException(status_code=422, detail="MODEL_UNAVAILABLE")

        messages = self._build_messages(request)
        options = self._build_request_options(request)
        metadata = request.metadata or {}

        prepared = PreparedAnalysisPayload(
            request=request,
            messages=messages,
            request_options=options,
            prompt_text=request.prompt,
            context_text=request.context,
            metadata=metadata,
        )

        cached = await self._sessions.create_session(
            task_id=request.task_id,
            model_key=request.model_key,
            payload={
                "prepared": prepared,
            },
        )
        return cached

    async def stream(
        self,
        *,
        task_id: str,
        model_key: str,
        session_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield SSE events for the requested analysis session."""

        try:
            cached = await self._sessions.pop_session(
                task_id=task_id,
                model_key=model_key,
                session_id=session_id,
            )
        except KeyError as exc:
            detail = exc.args[0] if exc.args else "SESSION_ERROR"
            raise HTTPException(status_code=404, detail=detail)

        prepared: PreparedAnalysisPayload = cached.payload["prepared"]
        harness = StreamHarness(task_id=task_id, model_key=model_key)

        await harness.emit(
            "stream.init",
            {
                "sessionId": session_id,
                "connectedAt": datetime.now(timezone.utc).isoformat(),
                "expiresAt": cached.expires_at.isoformat(),
            },
        )

        stream_task = asyncio.create_task(
            self._run_stream(prepared=prepared, harness=harness, session=cached)
        )

        try:
            async for event in harness.events():
                yield event
        finally:
            await harness.close()
            await asyncio.gather(stream_task, return_exceptions=True)

    async def _run_stream(
        self,
        *,
        prepared: PreparedAnalysisPayload,
        harness: StreamHarness,
        session: CachedAnalysisSession,
    ) -> None:
        db = SessionLocal()
        db_service = DatabaseService(db)
        start_time = datetime.now(timezone.utc)
        interaction_id: Optional[int] = None
        try:
            llm = get_llm(prepared.request.model_key)
            interaction = db_service.create_llm_interaction(
                {
                    "plan_id": prepared.request.task_id,
                    "stage": prepared.request.stage or RESPONSES_STREAMING_CONTROLS.stage,
                    "llm_model": llm.model,
                    "prompt_text": prepared.prompt_text,
                    "prompt_metadata": {
                        "context": prepared.context_text,
                        "metadata": prepared.metadata,
                        "model_key": prepared.request.model_key,
                        "analysis_type": prepared.request.stage or RESPONSES_STREAMING_CONTROLS.stage,
                    },
                    "status": "running",
                    "started_at": start_time,
                }
            )
            interaction_id = interaction.id

            await harness.emit(
                "stream.status",
                {
                    "status": "running",
                    "message": "Analysis stream started",
                    "startedAt": start_time.isoformat(),
                    "interactionId": interaction_id,
                },
            )

            final_payload, aggregates = await self._stream_openai(
                llm=llm,
                prepared=prepared,
                harness=harness,
            )

            summary = self._build_summary(
                final_payload=final_payload,
                aggregates=aggregates,
                prepared=prepared,
                session=session,
            )

            await harness.emit("stream.complete", summary)

            db_service.update_llm_interaction(
                interaction_id,
                {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc),
                    "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
                    "response_text": summary["responseSummary"].get("analysis"),
                    "response_metadata": {
                        "reasoning": summary["responseSummary"].get("reasoning"),
                        "token_usage": summary["responseSummary"].get("tokenUsage"),
                        "response_id": summary["responseSummary"].get("responseId"),
                        "deltas": summary.get("deltas"),
                    },
                },
            )
        except Exception as exc:  # pylint: disable=broad-except
            message = str(exc)
            await harness.emit(
                "stream.error",
                {
                    "error": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            if interaction_id is not None:
                db_service.update_llm_interaction(
                    interaction_id,
                    {
                        "status": "failed",
                        "completed_at": datetime.now(timezone.utc),
                        "error_message": message,
                    },
                )
            raise
        finally:
            try:
                db.close()
            except Exception:  # pragma: no cover
                pass

    async def _stream_openai(
        self,
        *,
        llm: SimpleOpenAILLM,
        prepared: PreparedAnalysisPayload,
        harness: StreamHarness,
    ) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
        aggregates: Dict[str, List[str]] = {
            "text": [],
            "reasoning": [],
            "json": [],
        }
        final_payload: Dict[str, Any] = {}

        request_args = llm._request_args(  # pylint: disable=protected-access
            prepared.messages,
            schema_entry=None,
            stream=True,
        )

        request_args["reasoning"]["effort"] = prepared.request.reasoning_effort
        request_args["reasoning"]["summary"] = prepared.request.reasoning_summary
        request_args["text"]["verbosity"] = prepared.request.text_verbosity
        request_args["max_output_tokens"] = (
            prepared.request.max_output_tokens
            or RESPONSES_STREAMING_CONTROLS.max_output_tokens
        )
        if prepared.request.temperature is not None:
            request_args["temperature"] = prepared.request.temperature
        if prepared.request.previous_response_id:
            request_args["previous_response_id"] = prepared.request.previous_response_id
        if prepared.request.output_schema is not None:
            request_args["text"]["format"] = {
                "type": "json_schema",
                "name": prepared.request.schema_name or "analysis_result",
                "schema": prepared.request.output_schema,
                "strict": True,
            }

        def _worker() -> None:
            nonlocal final_payload
            timestamp = datetime.now(timezone.utc).isoformat
            try:
                with llm._client.responses.stream(**request_args) as stream:  # pylint: disable=protected-access
                    for event in stream:
                        event_type = getattr(event, "type", None)
                        if event_type is None and isinstance(event, dict):
                            event_type = event.get("type")

                        if event_type in {
                            "response.output_text.delta",
                            "response.text.delta",
                            "response.content_part.delta",
                            "response.content_part.added",
                        }:
                            text_delta = self._extract_text_delta(event)
                            if text_delta:
                                aggregates["text"].append(text_delta)
                                harness.emit_from_worker(
                                    "stream.chunk",
                                    {
                                        "kind": "text",
                                        "delta": text_delta,
                                        "timestamp": timestamp(),
                                    },
                                )
                        elif event_type and "reasoning" in event_type and "delta" in event_type:
                            reasoning_delta = self._extract_reasoning_delta(event)
                            if reasoning_delta:
                                aggregates["reasoning"].append(reasoning_delta)
                                harness.emit_from_worker(
                                    "stream.chunk",
                                    {
                                        "kind": "reasoning",
                                        "delta": reasoning_delta,
                                        "timestamp": timestamp(),
                                    },
                                )
                        elif event_type in {
                            "response.output_parsed.delta",
                            "response.content_part.delta",
                        }:
                            json_delta = self._extract_json_delta(event)
                            if json_delta:
                                aggregates["json"].append(json_delta)
                                harness.emit_from_worker(
                                    "stream.chunk",
                                    {
                                        "kind": "json",
                                        "delta": json_delta,
                                        "timestamp": timestamp(),
                                    },
                                )
                        elif event_type in {"response.failed", "response.error"}:
                            error_payload = self._extract_error(event)
                            harness.emit_from_worker(
                                "stream.error",
                                {
                                    "error": error_payload,
                                    "timestamp": timestamp(),
                                },
                            )
                            raise RuntimeError(str(error_payload))

                    final_response_attr = getattr(stream, "final_response", None)
                    if callable(final_response_attr):
                        final_response = final_response_attr()
                    else:
                        final_response = final_response_attr
                    if final_response is None:
                        getter = getattr(stream, "get_final_response", None)
                        if callable(getter):
                            final_response = getter()

                if final_response is not None:
                    final_payload = llm._payload_to_dict(final_response)  # pylint: disable=protected-access
            except APIError as api_error:
                harness.emit_from_worker(
                    "stream.error",
                    {
                        "error": getattr(api_error, "message", str(api_error)),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                raise

        await asyncio.to_thread(_worker)
        return final_payload, aggregates

    def _build_summary(
        self,
        *,
        final_payload: Dict[str, Any],
        aggregates: Dict[str, List[str]],
        prepared: PreparedAnalysisPayload,
        session: CachedAnalysisSession,
    ) -> Dict[str, Any]:
        extracted = SimpleOpenAILLM._extract_output(final_payload) if final_payload else {}
        final_text = extracted.get("text")
        reasoning_text = extracted.get("reasoning")
        parsed_candidates = extracted.get("parsed_candidates") or []
        usage = extracted.get("usage") or {}

        summary = {
            "sessionId": session.session_id,
            "taskId": prepared.request.task_id,
            "modelKey": prepared.request.model_key,
            "responseSummary": {
                "analysis": final_text,
                "reasoning": reasoning_text,
                "parsed": parsed_candidates[0] if parsed_candidates else None,
                "tokenUsage": usage,
                "responseId": final_payload.get("id"),
                "previousResponseId": prepared.request.previous_response_id,
            },
            "deltas": aggregates,
            "metadata": {
                "prompt": prepared.prompt_text,
                "context": prepared.context_text,
                "createdAt": session.created_at.isoformat(),
            },
        }
        return summary

    def _build_messages(self, request: AnalysisStreamRequest) -> List[Dict[str, Any]]:
        system_prompt = request.system_prompt or RESPONSES_STREAMING_CONTROLS.system_prompt
        user_segments: List[Dict[str, Any]] = []
        if request.context:
            user_segments.append(
                {
                    "type": "text",
                    "text": f"Context:\n{request.context.strip()}\n\nRespond to the analysis instructions below.",
                }
            )
        user_segments.append({"type": "text", "text": request.prompt})
        return [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": user_segments},
        ]

    def _build_request_options(self, request: AnalysisStreamRequest) -> Dict[str, Any]:
        return {
            "temperature": request.temperature,
            "max_output_tokens": (
                request.max_output_tokens or RESPONSES_STREAMING_CONTROLS.max_output_tokens
            ),
            "reasoning_effort": request.reasoning_effort,
            "reasoning_summary": request.reasoning_summary,
            "text_verbosity": request.text_verbosity,
            "schema": request.output_schema,
            "schema_name": request.schema_name,
            "previous_response_id": request.previous_response_id,
        }

    @staticmethod
    def _extract_text_delta(event: Any) -> Optional[str]:
        part = getattr(event, "part", None)
        if part is None and isinstance(event, dict):
            part = event.get("part")
        if isinstance(part, dict):
            part_type = str(part.get("type", "")).lower()
            if "parsed" in part_type or "json" in part_type:
                return None
            text_value = part.get("text") or part.get("content") or part.get("value")
            if isinstance(text_value, list):
                return "".join(str(item) for item in text_value if item)
            if isinstance(text_value, str):
                return text_value
        delta = getattr(event, "delta", None)
        if delta is None and isinstance(event, dict):
            delta = event.get("delta") or event.get("text")
        if isinstance(delta, dict):
            text_value = delta.get("text") or delta.get("value") or delta.get("content")
            if isinstance(text_value, list):
                return "".join(str(item) for item in text_value if item)
            if isinstance(text_value, str):
                return text_value
        elif isinstance(delta, str):
            return delta
        return None

    @staticmethod
    def _extract_reasoning_delta(event: Any) -> Optional[str]:
        delta = getattr(event, "delta", None)
        if delta is None and isinstance(event, dict):
            delta = event.get("delta") or event.get("text") or event.get("part")
        if isinstance(delta, dict):
            text_value = delta.get("text") or delta.get("value")
            if isinstance(text_value, list):
                return "".join(str(item) for item in text_value if item)
            if isinstance(text_value, str):
                return text_value
        elif isinstance(delta, str):
            return delta
        return None

    @staticmethod
    def _extract_json_delta(event: Any) -> Optional[str]:
        part = getattr(event, "part", None)
        if part is None and isinstance(event, dict):
            part = event.get("part")
        if isinstance(part, dict):
            part_type = str(part.get("type", "")).lower()
            if "parsed" in part_type or "json" in part_type:
                parsed_value = part.get("parsed") or part.get("value") or part.get("text")
                if isinstance(parsed_value, (dict, list)):
                    return json.dumps(parsed_value)
                if isinstance(parsed_value, str):
                    return parsed_value
        delta = getattr(event, "delta", None)
        if delta is None and isinstance(event, dict):
            delta = event.get("delta") or event.get("parsed")
        if isinstance(delta, (dict, list)):
            return json.dumps(delta)
        if isinstance(delta, str):
            return delta
        return None

    @staticmethod
    def _extract_error(event: Any) -> Dict[str, Any]:
        if isinstance(event, dict):
            return {
                "type": event.get("type"),
                "message": event.get("message") or event.get("error"),
                "code": event.get("code"),
            }
        return {"message": getattr(event, "message", str(event))}
