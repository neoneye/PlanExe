"""Service layer for managing Responses API conversations and SSE streaming."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
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
from planexe.llm_util.schema_registry import (
    get_schema_entry,
    import_schema_model,
    sanitize_schema_label,
)


INTAKE_STAGE = "intake_conversation"


class ConversationService:
    """Coordinate Conversations API handshakes, streaming, and persistence."""

    def __init__(self, *, session_store: ConversationSessionStore) -> None:
        self._sessions = session_store
        self._summaries: Dict[str, ConversationFinalizeResponse] = {}
        self._lock = asyncio.Lock()

    async def ensure_conversation(
        self,
        *,
        model_key: str,
        conversation_id: Optional[str] = None,
    ) -> str:
        """Create a new OpenAI conversation when none exists."""

        if conversation_id and conversation_id.startswith("conv_"):
            return conversation_id

        if not is_valid_llm_name(model_key):
            raise HTTPException(status_code=422, detail="MODEL_UNAVAILABLE")

        llm = get_llm(model_key)
        try:
            conversation = llm._client.conversations.create()  # type: ignore[attr-defined]
        except AttributeError as exc:  # pragma: no cover - defensive against SDK drift
            raise HTTPException(status_code=500, detail="CONVERSATIONS_UNSUPPORTED") from exc

        remote_id = getattr(conversation, "id", None)
        if not remote_id and isinstance(conversation, dict):
            remote_id = conversation.get("id")
        if not isinstance(remote_id, str) or not remote_id:
            raise HTTPException(status_code=500, detail="CONVERSATION_CREATE_FAILED")
        return remote_id

    async def create_session(
        self,
        *,
        conversation_id: str,
        request: ConversationTurnRequest,
    ) -> CachedConversationSession:
        """Validate request, ensure conversation exists, and cache streaming payload."""

        if not is_valid_llm_name(request.model_key):
            raise HTTPException(status_code=422, detail="MODEL_UNAVAILABLE")

        llm = get_llm(request.model_key)
        if not conversation_id:
            raise HTTPException(status_code=400, detail="CONVERSATION_ID_REQUIRED")

        # Validate structured output schema early so the POST request surfaces errors
        self._resolve_schema_descriptor(request)

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
        token: str,
    ) -> AsyncGenerator[Dict[str, str], None]:
        """Upgrade a cached session into a live SSE stream."""

        try:
            cached = await self._sessions.pop_session(
                conversation_id=conversation_id,
                model_key=model_key,
                token=token,
            )
        except KeyError as exc:
            detail = exc.args[0] if exc.args else "SESSION_ERROR"
            raise HTTPException(status_code=404, detail=detail)

        request = ConversationTurnRequest.model_validate(cached.payload["request"])
        schema_descriptor = self._resolve_schema_descriptor(request)
        metadata = dict(request.metadata or {})
        metadata.update(
            {
                "context": request.context,
                "previous_response_id": request.previous_response_id,
            }
        )
        if schema_descriptor:
            metadata.update(
                {
                    "schema_model": request.schema_model,
                    "schema_name": request.schema_name or schema_descriptor.sanitized_name,
                    "schema_sanitized_name": schema_descriptor.sanitized_name,
                    "schema_canonical_name": schema_descriptor.canonical_name,
                }
            )

        harness = ConversationHarness(
            conversation_id=conversation_id,
            model_key=model_key,
            session_id=cached.token,
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
                schema_descriptor=schema_descriptor,
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
            completed_at = metadata.get("completed_at")
            if isinstance(completed_at, str):
                try:
                    completed_at = datetime.fromisoformat(completed_at)
                except ValueError:
                    completed_at = None
            summary = ConversationFinalizeResponse(
                conversation_id=conversation_id,
                response_id=metadata.get("response_id"),
                model_key=interaction.llm_model,
                aggregated_text=(interaction.response_text or ""),
                reasoning_text=metadata.get("reasoning_text", ""),
                json_chunks=metadata.get("json_chunks", []),
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
        schema_descriptor: Optional[SimpleNamespace],
    ) -> None:
        llm = get_llm(request.model_key)
        request_args = self._build_request_args(
            llm_model=llm.model,
            conversation_id=harness.conversation_id,
            request=request,
            schema_descriptor=schema_descriptor,
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
                        "schema_model": request.schema_model,
                        "schema_name": request.schema_name,
                        "schema_sanitized_name": schema_descriptor.sanitized_name
                        if schema_descriptor
                        else None,
                        "schema_canonical_name": schema_descriptor.canonical_name
                        if schema_descriptor
                        else None,
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
            remote_conversation = final_payload.get("conversation_id")
            if (
                isinstance(remote_conversation, str)
                and remote_conversation
                and "remote_conversation_id" not in harness.metadata
            ):
                harness.metadata["remote_conversation_id"] = remote_conversation
            usage = SimpleOpenAILLM._normalize_usage(final_payload.get("usage"))
            harness.set_usage(usage)
            summary = harness.complete()
            summary.metadata.setdefault("response_id", handler.response_id)
            if summary.completed_at:
                summary.metadata.setdefault("completed_at", summary.completed_at.isoformat())
            manager.push(handler.emit_completion())

            final_event = harness.emit_final_response(final_payload)
            if final_event:
                manager.push([final_event])

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
                        "reasoning_text": summary.reasoning_text,
                        "json_chunks": summary.json_chunks,
                        "usage": usage,
                        "metadata": summary.metadata,
                        "response_id": handler.response_id,
                        "completed_at": summary.completed_at.isoformat()
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
            summary = harness.complete()
            manager.push(handler.emit_completion())
            error_final = harness.emit_final_response({})
            if error_final:
                manager.push([error_final])
            try:
                await self._persist_summary(
                    summary=summary,
                    response_id=handler.response_id,
                    model_key=llm.model,
                )
            except Exception as persist_exc:  # pylint: disable=broad-except
                print(
                    "[ConversationService] Failed to persist error summary:",
                    persist_exc,
                )
            db_service.update_llm_interaction(
                interaction.id,
                {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc),
                    "error_message": message,
                },
            )
            return
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
            # Modern SDKs expose conversation-aware streaming directly on client.responses
            responses_client = getattr(llm._client, "responses", None)  # pylint: disable=protected-access
            if responses_client is None:
                raise AttributeError("OpenAI client is missing the 'responses' accessor")
            with responses_client.stream(**request_args) as stream:
                for event in stream:
                    envelopes = handler.handle(event)
                    if envelopes:
                        manager.push(envelopes)
                final_response = self._resolve_final_response(stream)
            if final_response is not None:
                final_payload = SimpleOpenAILLM._payload_to_dict(final_response)
        except AttributeError as attr_error:
            handler.handle({"type": "response.error", "message": str(attr_error)})
            manager.push(handler.emit_completion())
            raise
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
        schema_descriptor: Optional[SimpleNamespace],
    ) -> Dict[str, Any]:
        input_segments = [{"role": "user", "content": [{"type": "input_text", "text": request.user_message}]}]
        text_payload: Dict[str, Any] = {"verbosity": request.text_verbosity}
        if schema_descriptor:
            text_format = SimpleOpenAILLM.build_text_format_from_schema(
                schema=schema_descriptor.schema,
                name=schema_descriptor.sanitized_name,
            )
            if text_format:
                text_payload["format"] = text_format
        payload: Dict[str, Any] = {
            "model": llm_model,
            "input": input_segments,
            "text": text_payload,
            "reasoning": {
                "effort": request.reasoning_effort.value if hasattr(request.reasoning_effort, "value") else request.reasoning_effort,
                "summary": request.reasoning_summary,
            },
            "store": request.store,
        }
        if ConversationService._should_forward_conversation_id(conversation_id):
            payload["conversation"] = conversation_id
        if request.instructions:
            payload["instructions"] = request.instructions
        if request.previous_response_id:
            payload["previous_response_id"] = request.previous_response_id
        if request.metadata:
            payload["metadata"] = request.metadata
        return payload

    @staticmethod
    def _resolve_schema_descriptor(
        request: ConversationTurnRequest,
    ) -> Optional[SimpleNamespace]:
        if not request.schema_model:
            return None
        try:
            model = import_schema_model(request.schema_model)
        except (ImportError, AttributeError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="SCHEMA_MODEL_INVALID") from exc
        entry = get_schema_entry(model)
        alias = request.schema_name or entry.qualified_name
        sanitized = sanitize_schema_label(alias, entry.sanitized_name)
        return SimpleNamespace(
            schema=entry.schema,
            qualified_name=alias,
            sanitized_name=sanitized,
            canonical_name=entry.qualified_name,
        )

    async def followup(
        self,
        *,
        conversation_id: str,
        request: ConversationTurnRequest,
    ) -> ConversationFinalizeResponse:
        """Execute a non-streaming follow-up by internally consuming the stream."""

        cached = await self.create_session(conversation_id=conversation_id, request=request)
        last_error: Optional[str] = None

        async for event in self.stream(
            conversation_id=conversation_id,
            model_key=request.model_key,
            token=cached.token,
        ):
            name = event.get("event")
            data_payload: Dict[str, Any] = {}
            if "data" in event:
                raw_data = event.get("data")
                if isinstance(raw_data, str):
                    try:
                        data_payload = json.loads(raw_data)
                    except json.JSONDecodeError:
                        data_payload = {}
            if name == "response.error":
                last_error = str(data_payload.get("message") or data_payload or "Conversation stream failed")
            if name == "final":
                break

        if last_error:
            raise HTTPException(status_code=502, detail=last_error)

        return await self.finalize(conversation_id)

    @staticmethod
    def _should_forward_conversation_id(conversation_id: Optional[str]) -> bool:
        if not conversation_id:
            return False
        normalized = str(conversation_id)
        return normalized.startswith("conv_")

    @staticmethod
    def _generate_local_conversation_id() -> str:
        return f"local-{uuid.uuid4()}"
