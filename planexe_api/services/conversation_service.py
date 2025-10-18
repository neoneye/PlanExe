"""Service layer for managing Responses API conversations and SSE streaming."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import HTTPException
from openai import APIError

from planexe_api.database import DatabaseService, SessionLocal, LLMInteraction
from planexe_api.models import ConversationFinalizeResponse, ConversationTurnRequest
from planexe_api.streaming import (
    CachedConversationSession,
    ConversationEventHandler,
    ConversationHarness,
    ConversationSSEManager,
    ConversationSessionStore,
    ConversationSummary,
)
from planexe.llm_factory import get_llm, is_valid_llm_name
from planexe.llm_util.simple_openai_llm import SimpleOpenAILLM


INTAKE_STAGE = "intake_conversation"


class ConversationService:
    """Coordinate Conversations API handshakes, streaming, and persistence."""

    def __init__(self, *, session_store: ConversationSessionStore) -> None:
        self._sessions = session_store
        self._summaries: Dict[str, ConversationFinalizeResponse] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, request: ConversationTurnRequest) -> CachedConversationSession:
        """Validate request, ensure conversation exists, and cache streaming payload."""

        if not is_valid_llm_name(request.model_key):
            raise HTTPException(status_code=422, detail="MODEL_UNAVAILABLE")

        llm = get_llm(request.model_key)
        conversation_id = request.conversation_id or self._create_conversation_id(llm, request.metadata)
        if not conversation_id:
            raise HTTPException(status_code=502, detail="CONVERSATION_INIT_FAILED")

        payload = {
            "request": request.model_dump(mode="python"),
            "conversation_id": conversation_id,
            "model": llm.model,
        }

        cached = await self._sessions.create_session(
            conversation_id=conversation_id,
            model_key=request.model_key,
            payload=payload,
        )
        return cached

    async def stream(
        self,
        *,
        conversation_id: str,
        model_key: str,
        session_id: str,
    ) -> AsyncGenerator[Dict[str, str], None]:
        """Upgrade a cached session into a live SSE stream."""

        try:
            cached = await self._sessions.pop_session(
                conversation_id=conversation_id,
                model_key=model_key,
                session_id=session_id,
            )
        except KeyError as exc:
            detail = exc.args[0] if exc.args else "SESSION_ERROR"
            raise HTTPException(status_code=404, detail=detail)

        request = ConversationTurnRequest.model_validate(cached.payload["request"])
        metadata = dict(request.metadata or {})
        metadata.update(
            {
                "context": request.context,
                "previousResponseId": request.previous_response_id,
            }
        )

        harness = ConversationHarness(
            conversation_id=conversation_id,
            model_key=model_key,
            session_id=cached.session_id,
            metadata=metadata,
        )
        manager = ConversationSSEManager()
        handler = ConversationEventHandler(harness)

        stream_task = asyncio.create_task(
            self._run_stream(
                request=request,
                handler=handler,
                harness=harness,
                manager=manager,
            )
        )

        try:
            async for event in manager.stream():
                yield event
        finally:
            await manager.close()
            await asyncio.gather(stream_task, return_exceptions=True)

    async def finalize(self, conversation_id: str) -> ConversationFinalizeResponse:
        """Return the last known summary for a conversation."""

        async with self._lock:
            if conversation_id in self._summaries:
                return self._summaries[conversation_id]

        db = SessionLocal()
        try:
            interaction = (
                db.query(LLMInteraction)
                .filter(
                    LLMInteraction.plan_id == conversation_id,
                    LLMInteraction.stage == INTAKE_STAGE,
                )
                .order_by(LLMInteraction.started_at.desc())
                .first()
            )
            if not interaction:
                raise HTTPException(status_code=404, detail="CONVERSATION_NOT_FOUND")
            metadata = interaction.response_metadata or {}
            completed_at = metadata.get("completedAt")
            if isinstance(completed_at, str):
                try:
                    completed_at = datetime.fromisoformat(completed_at)
                except ValueError:
                    completed_at = None
            summary = ConversationFinalizeResponse(
                conversation_id=conversation_id,
                response_id=metadata.get("responseId"),
                model_key=interaction.llm_model,
                aggregated_text=(interaction.response_text or ""),
                reasoning_text=metadata.get("reasoningText", ""),
                json_chunks=metadata.get("json", []),
                usage=metadata.get("usage", {}),
                completed_at=completed_at,
            )
            async with self._lock:
                self._summaries[conversation_id] = summary
            return summary
        finally:
            db.close()

    async def _run_stream(
        self,
        *,
        request: ConversationTurnRequest,
        handler: ConversationEventHandler,
        harness: ConversationHarness,
        manager: ConversationSSEManager,
    ) -> None:
        llm = get_llm(request.model_key)
        request_args = self._build_request_args(
            llm_model=llm.model,
            conversation_id=harness.conversation_id,
            request=request,
        )

        db = SessionLocal()
        db_service = DatabaseService(db)
        start_time = datetime.now(timezone.utc)
        interaction = db_service.create_llm_interaction(
            {
                "plan_id": harness.conversation_id,
                "stage": INTAKE_STAGE,
                "llm_model": llm.model,
                "prompt_text": request.user_message,
                "prompt_metadata": {
                    "conversation_id": harness.conversation_id,
                    "metadata": request.metadata,
                    "context": request.context,
                    "previous_response_id": request.previous_response_id,
                    "instructions": request.instructions,
                },
                "status": "running",
                "started_at": start_time,
            }
        )

        try:
            final_payload = await asyncio.to_thread(
                self._execute_stream,
                llm,
                request_args,
                handler,
                manager,
            )
            usage = SimpleOpenAILLM._normalize_usage(final_payload.get("usage"))
            harness.set_usage(usage)
            summary = harness.complete()
            summary.metadata.setdefault("responseId", handler.response_id)
            if summary.completed_at:
                summary.metadata.setdefault("completedAt", summary.completed_at.isoformat())
            manager.push(handler.emit_completion())

            await self._persist_summary(
                summary=summary,
                response_id=handler.response_id,
                model_key=llm.model,
            )

            duration = None
            if summary.completed_at:
                duration = (summary.completed_at - start_time).total_seconds()

            db_service.update_llm_interaction(
                interaction.id,
                {
                    "status": "completed",
                    "completed_at": summary.completed_at,
                    "duration_seconds": duration,
                    "response_text": summary.content_text,
                    "response_metadata": {
                        "reasoningText": summary.reasoning_text,
                        "json": summary.json_chunks,
                        "usage": usage,
                        "metadata": summary.metadata,
                        "responseId": handler.response_id,
                        "completedAt": summary.completed_at.isoformat()
                        if summary.completed_at
                        else None,
                    },
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
            )
        except Exception as exc:  # pylint: disable=broad-except
            message = str(exc)
            harness.mark_error(message)
            manager.push(handler.emit_completion())
            db_service.update_llm_interaction(
                interaction.id,
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

    def _execute_stream(
        self,
        llm: SimpleOpenAILLM,
        request_args: Dict[str, Any],
        handler: ConversationEventHandler,
        manager: ConversationSSEManager,
    ) -> Dict[str, Any]:
        final_payload: Dict[str, Any] = {}
        try:
            with llm._client.responses.stream(**request_args) as stream:  # pylint: disable=protected-access
                for event in stream:
                    envelopes = handler.handle(event)
                    if envelopes:
                        manager.push(envelopes)
                final_response = self._resolve_final_response(stream)
            if final_response is not None:
                final_payload = SimpleOpenAILLM._payload_to_dict(final_response)
        except APIError as api_error:
            handler.handle({"type": "response.error", "message": getattr(api_error, "message", str(api_error))})
            manager.push(handler.emit_completion())
            raise
        return final_payload

    @staticmethod
    def _resolve_final_response(stream: Any) -> Any:
        for attr in ("final_response", "get_final_response"):
            candidate = getattr(stream, attr, None)
            if callable(candidate):
                try:
                    result = candidate()
                    if result is not None:
                        return result
                except TypeError:  # pragma: no cover - defensive
                    continue
            elif candidate is not None:
                return candidate
        return None

    async def _persist_summary(
        self,
        *,
        summary: ConversationSummary,
        response_id: Optional[str],
        model_key: str,
    ) -> None:
        finalize = ConversationFinalizeResponse(
            conversation_id=summary.conversation_id,
            response_id=response_id,
            model_key=model_key,
            aggregated_text=summary.content_text,
            reasoning_text=summary.reasoning_text,
            json_chunks=summary.json_chunks,
            usage=summary.usage,
            completed_at=summary.completed_at,
        )
        async with self._lock:
            self._summaries[summary.conversation_id] = finalize

    @staticmethod
    def _build_request_args(
        *,
        llm_model: str,
        conversation_id: str,
        request: ConversationTurnRequest,
    ) -> Dict[str, Any]:
        input_segments = [{"role": "user", "content": [{"type": "text", "text": request.user_message}]}]
        payload: Dict[str, Any] = {
            "model": llm_model,
            "conversation": conversation_id,
            "input": input_segments,
            "text": {"verbosity": request.text_verbosity},
            "reasoning": {
                "effort": request.reasoning_effort.value if hasattr(request.reasoning_effort, "value") else request.reasoning_effort,
                "summary": request.reasoning_summary,
            },
        }
        if request.instructions:
            payload["instructions"] = request.instructions
        if request.previous_response_id:
            payload["previous_response_id"] = request.previous_response_id
        if request.metadata:
            payload["metadata"] = request.metadata
        return payload

    @staticmethod
    def _create_conversation_id(llm: SimpleOpenAILLM, metadata: Optional[Dict[str, Any]]) -> Optional[str]:
        client = getattr(llm._client, "conversations", None)  # pylint: disable=protected-access
        if client is None:
            beta = getattr(getattr(llm._client, "beta", None), "conversations", None)  # pylint: disable=protected-access
            client = beta
        if client is None:
            return None
        response = client.create(metadata=metadata or {})  # type: ignore[call-arg]
        conversation_id = getattr(response, "id", None)
        if isinstance(conversation_id, str):
            return conversation_id
        if isinstance(response, dict):
            conv_id = response.get("id")
            if isinstance(conv_id, str):
                return conv_id
        return None
*** End
