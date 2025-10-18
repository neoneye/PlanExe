"""OpenAI Responses API client with reasoning-aware streaming hooks for PlanExe."""

from __future__ import annotations

import json
import logging
import os
from contextlib import suppress
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Type

from llama_index.core.llms.llm import LLM
from openai import OpenAI
from pydantic import BaseModel, Field, PrivateAttr, ValidationError

from planexe.llm_util.schema_registry import get_schema_entry
from planexe.llm_util import (
    record_final_payload,
    record_reasoning_delta,
    record_text_delta,
)

logger = logging.getLogger(__name__)


def _ensure_message_dict(message: Any) -> Dict[str, Any]:
    if isinstance(message, dict):
        return message

    if hasattr(message, "role") and hasattr(message, "content"):
        role = getattr(message.role, "value", message.role)
        return {"role": str(role).lower(), "content": getattr(message, "content")}

    raise TypeError(f"Unsupported message format: {message!r}")


def _normalize_content(content: Any) -> List[Dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]

    if isinstance(content, list):
        normalized: List[Dict[str, Any]] = []
        for item in content:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append({"type": "text", "text": str(item)})
        return normalized

    return [{"type": "text", "text": str(content)}]


class SimpleOpenAILLM(LLM):
    """Responses API-powered OpenAI adapter used throughout the Luigi pipeline."""

    model: str = Field(description="The OpenAI model identifier")
    provider: str = Field(description="Only 'openai' is supported after Responses migration")
    _client: OpenAI = PrivateAttr()
    _responses_client: Any = PrivateAttr(default=None)
    _last_response_payload: Optional[Dict[str, Any]] = PrivateAttr(default=None)
    _last_extracted_output: Optional[Dict[str, Any]] = PrivateAttr(default=None)

    def __init__(self, model: str, provider: str, **kwargs: Any):
        super().__init__(model=model, provider=provider, **kwargs)

        if provider != "openai":
            raise ValueError(
                "SimpleOpenAILLM only supports provider='openai' now that OpenRouter is deprecated for GPT-5 streaming"
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            error_msg = "OPENAI_API_KEY environment variable not set; cannot create OpenAI client"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug("Creating OpenAI Responses client for model %s", model)
        self._client = OpenAI(api_key=api_key)
        self._responses_client = self._resolve_responses_client(self._client)
        if self._responses_client is None:
            raise RuntimeError(
                "OpenAI client does not expose the Responses API; verify openai>=1.3 and that the Responses beta header is enabled."
            )

    @staticmethod
    def _resolve_responses_client(client: OpenAI) -> Optional[Any]:
        candidate_paths = (("responses",), ("beta", "responses"))
        for path in candidate_paths:
            resource: Any = client
            for attr in path:
                resource = getattr(resource, attr, None)
                if resource is None:
                    break
            else:
                if resource is not None:
                    return resource

        with suppress(ImportError, AttributeError, TypeError):
            from openai.resources import responses as responses_module

            responses_cls = getattr(responses_module, "Responses", None)
            if responses_cls is not None:
                return responses_cls(client)

        return None

    # ------------------------------------------------------------------
    # Core request/response plumbing
    # ------------------------------------------------------------------
    def _prepare_input(self, messages: Sequence[Any]) -> List[Dict[str, Any]]:
        normalized = []
        for message in messages:
            message_dict = _ensure_message_dict(message)
            role = message_dict.get("role", "user")
            content = _normalize_content(message_dict.get("content", ""))
            normalized.append({"role": role, "content": content})
        return normalized

    @staticmethod
    def _build_text_format(schema_entry: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        if schema_entry is None:
            return None

        return {
            "type": "json_schema",
            "name": schema_entry.qualified_name,
            "strict": True,
            "schema": schema_entry.schema,
        }

    def _request_args(
        self,
        messages: Sequence[Any],
        *,
        schema_entry: Optional[Any] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "model": self.model,
            "input": self._prepare_input(messages),
            "reasoning": {"effort": "high", "summary": "detailed"},
            "text": {"verbosity": "high"},
        }

        text_format = self._build_text_format(schema_entry)
        if text_format:
            request["text"]["format"] = text_format

        if stream:
            request["stream"] = True

        return request

    @staticmethod
    def _payload_to_dict(response: Any) -> Dict[str, Any]:
        if response is None:
            return {}
        if isinstance(response, dict):
            return response
        for attr in ("model_dump", "to_dict"):
            method = getattr(response, attr, None)
            if callable(method):
                with suppress(TypeError):
                    return method()
        json_method = getattr(response, "model_dump_json", None)
        if callable(json_method):
            return json.loads(json_method())
        json_text = getattr(response, "json", None)
        if callable(json_text):
            return json.loads(json_text())
        raise TypeError(f"Unsupported response payload type: {type(response)!r}")

    @staticmethod
    def _collect_text_values(value: Any) -> List[str]:
        texts: List[str] = []
        if value is None:
            return texts
        if isinstance(value, str):
            if value:
                texts.append(value)
            return texts
        if isinstance(value, (int, float)):
            texts.append(str(value))
            return texts
        if isinstance(value, list):
            for item in value:
                texts.extend(SimpleOpenAILLM._collect_text_values(item))
            return [text for text in texts if text]
        if isinstance(value, dict):
            for key in (
                "text",
                "content",
                "value",
                "summary",
                "delta",
                "message",
                "part",
            ):
                if key in value:
                    texts.extend(SimpleOpenAILLM._collect_text_values(value[key]))
            if "parts" in value:
                texts.extend(SimpleOpenAILLM._collect_text_values(value["parts"]))
            return [text for text in texts if text]
        return texts

    @classmethod
    def _extract_reasoning_chunks(cls, block: Dict[str, Any]) -> List[str]:
        chunks: List[str] = []
        reasoning = block.get("reasoning")
        if reasoning is not None:
            chunks.extend(cls._collect_text_values(reasoning))
        summary = block.get("summary")
        if summary is not None:
            chunks.extend(cls._collect_text_values(summary))
        content = block.get("content")
        if content is not None:
            chunks.extend(cls._collect_text_values(content))
        text = block.get("text")
        if text is not None:
            chunks.extend(cls._collect_text_values(text))
        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def _normalize_usage(usage: Any) -> Dict[str, Any]:
        if not isinstance(usage, dict):
            return {}

        normalized: Dict[str, Any] = dict(usage)
        details = normalized.get("output_tokens_details")
        if isinstance(details, dict):
            for key, value in details.items():
                if key not in normalized and value is not None:
                    normalized[key] = value
            reasoning_tokens = details.get("reasoning_tokens")
            if reasoning_tokens is not None:
                normalized.setdefault("reasoning_tokens", reasoning_tokens)

        input_tokens = normalized.get("input_tokens")
        output_tokens = normalized.get("output_tokens")
        if (
            normalized.get("total_tokens") is None
            and isinstance(input_tokens, (int, float))
            and isinstance(output_tokens, (int, float))
        ):
            normalized["total_tokens"] = input_tokens + output_tokens

        return normalized

    @classmethod
    def _extract_output(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        text_parts: List[str] = []
        parsed_candidates: List[Any] = []
        reasoning_parts: List[str] = []

        output = payload.get("output", [])
        if isinstance(output, dict):
            output = [output]
        if isinstance(output, list):
            for block in output:
                if not isinstance(block, dict):
                    continue
                block_type = str(block.get("type", "")).lower()
                if block_type in {"message", "text"}:
                    contents = block.get("content")
                    if isinstance(contents, list):
                        for part in contents:
                            if isinstance(part, dict):
                                part_type = str(part.get("type", "")).lower()
                                if part_type in {"output_text", "text"}:
                                    text_parts.extend(
                                        cls._collect_text_values(part.get("text") or part.get("content"))
                                    )
                                elif part_type in {"output_parsed", "parsed"}:
                                    parsed_value = part.get("parsed")
                                    if parsed_value is not None:
                                        parsed_candidates.append(parsed_value)
                                elif "reasoning" in part_type:
                                    reasoning_parts.extend(cls._collect_text_values(part))
                                else:
                                    text_parts.extend(cls._collect_text_values(part))
                            elif isinstance(part, str):
                                text_parts.append(part)
                    else:
                        text_parts.extend(cls._collect_text_values(contents))
                elif block_type == "reasoning":
                    reasoning_parts.extend(cls._extract_reasoning_chunks(block))
                elif block_type in {"output_text", "assistant"}:
                    text_parts.extend(cls._collect_text_values(block.get("text") or block.get("content")))
                elif block_type in {"output_parsed", "parsed"}:
                    parsed_value = block.get("parsed")
                    if parsed_value is not None:
                        parsed_candidates.append(parsed_value)
                else:
                    text_parts.extend(cls._collect_text_values(block.get("content") or block.get("text")))

        if not text_parts:
            fallback_text = payload.get("output_text")
            if isinstance(fallback_text, list):
                text_parts.extend(str(item) for item in fallback_text)
            elif isinstance(fallback_text, str):
                text_parts.append(fallback_text)

        if not parsed_candidates:
            parsed_value = payload.get("output_parsed")
            if isinstance(parsed_value, list):
                parsed_candidates.extend(parsed_value)
            elif parsed_value is not None:
                parsed_candidates.append(parsed_value)

        reasoning_summary = payload.get("output_reasoning")
        if isinstance(reasoning_summary, dict):
            reasoning_parts.extend(cls._collect_text_values(reasoning_summary.get("summary")))
            reasoning_parts.extend(cls._collect_text_values(reasoning_summary.get("items")))
        elif isinstance(reasoning_summary, list):
            reasoning_parts.extend(cls._collect_text_values(reasoning_summary))
        elif isinstance(reasoning_summary, str):
            reasoning_parts.append(reasoning_summary)

        reasoning_text = "\n\n".join([chunk for chunk in reasoning_parts if chunk]).strip() or None

        usage = cls._normalize_usage(payload.get("usage"))

        return {
            "text": "".join(text_parts),
            "parsed_candidates": [candidate for candidate in parsed_candidates if candidate is not None],
            "reasoning": reasoning_text,
            "usage": usage,
        }

    def _invoke_responses(
        self,
        messages: Sequence[Any],
        *,
        schema_entry: Optional[Any] = None,
    ) -> Dict[str, Any]:
        self._last_response_payload = None
        self._last_extracted_output = None
        if self._responses_client is None:
            raise RuntimeError("Responses client unavailable; cannot perform invoke.")

        response = self._responses_client.create(
            **self._request_args(messages, schema_entry=schema_entry, stream=False)
        )
        payload = self._payload_to_dict(response)
        self._last_response_payload = payload
        extracted = self._extract_output(payload)
        extracted["raw"] = payload
        self._last_extracted_output = extracted
        record_final_payload(
            text=extracted.get("text"),
            reasoning=extracted.get("reasoning"),
            usage=extracted.get("usage"),
            raw_payload=payload,
        )
        return extracted

    # ------------------------------------------------------------------
    # Public LLM interface methods
    # ------------------------------------------------------------------
    def chat(self, messages: Sequence[Any], **kwargs: Any) -> str:
        chunks: List[str] = []
        for piece in self.stream_chat(messages, **kwargs):
            if piece:
                chunks.append(piece)

        if chunks:
            return "".join(chunks)

        if self._last_extracted_output:
            text = self._last_extracted_output.get("text")
            if text:
                return text

        return ""

    def complete(self, prompt: str, **kwargs: Any) -> str:
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)

    def stream_chat(
        self,
        messages: Sequence[Any],
        *,
        schema_entry: Optional[Any] = None,
        **_: Any,
    ) -> Generator[str, None, None]:
        self._last_response_payload = None
        self._last_extracted_output = None
        request_args = self._request_args(messages, schema_entry=schema_entry, stream=True)
        responses_client = self._responses_client
        if responses_client is None:
            raise RuntimeError("Responses client unavailable; cannot stream.")

        stream_callable = getattr(responses_client, "stream", None)

        if not callable(stream_callable):
            result = self._invoke_responses(messages, schema_entry=schema_entry)
            text = result.get("text")
            if text:
                yield text
            return

        aggregated_text: List[str] = []
        final_payload: Optional[Dict[str, Any]] = None
        final_response: Optional[Any] = None

        with stream_callable(**request_args) as stream:
            for event in stream:
                event_type = getattr(event, "type", None)
                if event_type is None and isinstance(event, dict):
                    event_type = event.get("type")

                if event_type in {"response.content_part.added", "response.content_part.delta"}:
                    part = getattr(event, "part", None)
                    if part is None and isinstance(event, dict):
                        part = event.get("part")
                    text_chunks: List[str] = []
                    reasoning_chunks: List[str] = []
                    if part is not None:
                        if isinstance(part, dict):
                            part_type = str(part.get("type", "")).lower()
                            if part_type in {"output_text", "text", "assistant"}:
                                text_chunks = self._collect_text_values(part.get("text") or part.get("content"))
                            elif "reasoning" in part_type:
                                reasoning_chunks = self._collect_text_values(part)
                            else:
                                text_chunks = self._collect_text_values(part.get("text") or part)
                        else:
                            text_attr = getattr(part, "text", None)
                            if text_attr:
                                text_chunks = [str(text_attr)]
                            elif isinstance(part, str):
                                text_chunks = [part]
                    if text_chunks:
                        text_delta = "".join(text_chunks)
                        aggregated_text.append(text_delta)
                        record_text_delta(text_delta)
                        yield text_delta
                    for chunk in reasoning_chunks:
                        record_reasoning_delta(chunk)
                elif event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", None)
                    if delta is None and isinstance(event, dict):
                        delta = event.get("delta") or event.get("text")

                    if isinstance(delta, dict):
                        text_delta = delta.get("text")
                    else:
                        text_delta = str(delta) if delta else None

                    if text_delta:
                        aggregated_text.append(text_delta)
                        record_text_delta(text_delta)
                        yield text_delta
                elif event_type == "response.reasoning_summary_text.delta":
                    reasoning_delta = getattr(event, "delta", None)
                    if reasoning_delta is None and isinstance(event, dict):
                        reasoning_delta = event.get("delta") or event.get("text")
                    if isinstance(reasoning_delta, dict):
                        reasoning_text = reasoning_delta.get("text") or reasoning_delta.get("value")
                    else:
                        reasoning_text = str(reasoning_delta) if reasoning_delta else None
                    if reasoning_text:
                        record_reasoning_delta(reasoning_text)
                elif event_type == "response.reasoning_summary_part.added":
                    part = getattr(event, "part", None)
                    if part is None and isinstance(event, dict):
                        part = event.get("part")
                    for chunk in self._collect_text_values(part):
                        record_reasoning_delta(chunk)
                elif event_type and "reasoning" in event_type and "delta" in event_type:
                    reasoning_delta = getattr(event, "delta", None)
                    if reasoning_delta is None and isinstance(event, dict):
                        reasoning_delta = event.get("delta") or event.get("text")
                    if isinstance(reasoning_delta, dict):
                        reasoning_text = reasoning_delta.get("text") or reasoning_delta.get("value")
                    else:
                        reasoning_text = str(reasoning_delta) if reasoning_delta else None
                    if reasoning_text:
                        record_reasoning_delta(reasoning_text)
                elif event_type in {"response.failed", "response.error", "error"}:
                    message = (
                        getattr(event, "error", None)
                        or getattr(event, "message", None)
                        or (
                            event.get("error")
                            if isinstance(event, dict)
                            else None
                        )
                    )
                    raise RuntimeError(f"OpenAI streaming error: {message}")

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
            final_payload = self._payload_to_dict(final_response)
            self._last_response_payload = final_payload
            extracted = self._extract_output(final_payload)
            extracted["raw"] = final_payload
            self._last_extracted_output = extracted
            record_final_payload(
                text=extracted.get("text"),
                reasoning=extracted.get("reasoning"),
                usage=extracted.get("usage"),
                raw_payload=final_payload,
            )

        if final_payload is not None and not aggregated_text:
            extracted = self._extract_output(final_payload)
            text = extracted.get("text")
            if text:
                yield text

    def stream_complete(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        messages = [{"role": "user", "content": prompt}]
        yield from self.stream_chat(messages, **kwargs)

    async def achat(self, messages: Sequence[Any], **kwargs: Any) -> str:
        return self.chat(messages, **kwargs)

    async def acomplete(self, prompt: str, **kwargs: Any) -> str:
        return self.complete(prompt, **kwargs)

    async def astream_chat(self, messages: Sequence[Any], **kwargs: Any) -> Generator[str, None, None]:
        for chunk in self.stream_chat(messages, **kwargs):
            yield chunk

    async def astream_complete(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        for chunk in self.stream_complete(prompt, **kwargs):
            yield chunk

    # ------------------------------------------------------------------
    # Helpers for compatibility with legacy LlamaIndex expectations
    # ------------------------------------------------------------------
    @property
    def model_name(self) -> str:
        return self.model

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "provider": self.provider,
            "model_name": self.model,
            "max_tokens": None,
            "temperature": None,
        }

    def class_name(self) -> str:
        return self.__class__.__name__

    def __str__(self) -> str:
        return f"SimpleOpenAILLM(model={self.model}, provider={self.provider})"

    def __repr__(self) -> str:
        return self.__str__()

    def as_structured_llm(self, output_cls: Type[BaseModel]):
        return StructuredSimpleOpenAILLM(self, output_cls)


class StructuredLLMResponse:
    """LlamaIndex compatible wrapper for structured responses."""

    def __init__(
        self,
        parsed_model: BaseModel,
        raw_text: str,
        *,
        reasoning: Optional[str] = None,
        usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.raw = parsed_model
        self.text = raw_text
        self.message = type("Message", (), {"content": raw_text})()
        self.reasoning = reasoning
        self.token_usage = usage

    def __str__(self) -> str:
        return str(self.raw)

    def __repr__(self) -> str:
        return f"StructuredLLMResponse(raw={self.raw})"


class StructuredSimpleOpenAILLM:
    """Structured output adapter that leverages the schema registry."""

    def __init__(self, base_llm: SimpleOpenAILLM, output_cls: Type[BaseModel]):
        self.base_llm = base_llm
        self.output_cls = output_cls

    def _format_messages(self, messages: Sequence[Any]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for message in messages:
            formatted.append(_ensure_message_dict(message))
        return formatted

    def _parse_candidates(self, candidates: Iterable[Any], response_text: str) -> BaseModel:
        errors: List[Exception] = []
        for candidate in candidates:
            if candidate is None:
                continue
            try:
                return self.output_cls.model_validate(candidate)
            except ValidationError as exc:
                errors.append(exc)

        if response_text:
            try:
                json_payload = json.loads(response_text)
                return self.output_cls.model_validate(json_payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                errors.append(exc)

        if errors:
            raise ValueError(
                f"Failed to parse structured response for {self.output_cls.__name__}: {errors[-1]}"
            )
        raise ValueError(f"Structured response for {self.output_cls.__name__} was empty")

    def chat(self, messages: Sequence[Any], **_: Any) -> StructuredLLMResponse:
        formatted_messages = self._format_messages(messages)
        schema_entry = get_schema_entry(self.output_cls)
        text_chunks: List[str] = []

        for delta in self.base_llm.stream_chat(formatted_messages, schema_entry=schema_entry):
            if delta:
                text_chunks.append(delta)

        last_payload = self.base_llm._last_response_payload or {}
        last_extracted = getattr(self.base_llm, "_last_extracted_output", None)

        if last_extracted is None and last_payload:
            extracted = self.base_llm._extract_output(last_payload)
            extracted["raw"] = last_payload
            last_extracted = extracted

        aggregated_text = "".join(text_chunks)
        if not aggregated_text and last_extracted:
            aggregated_text = last_extracted.get("text", "")

        parsed_candidates = []
        if last_extracted:
            parsed_candidates = last_extracted.get("parsed_candidates", []) or []

        parsed_model = self._parse_candidates(parsed_candidates, aggregated_text)
        raw_text = aggregated_text or json.dumps(parsed_model.model_dump())

        reasoning = last_extracted.get("reasoning") if last_extracted else None
        usage = last_extracted.get("usage") if last_extracted else None

        return StructuredLLMResponse(
            parsed_model,
            raw_text,
            reasoning=reasoning,
            usage=usage,
        )

    def complete(self, prompt: str, **kwargs: Any) -> StructuredLLMResponse:
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)

