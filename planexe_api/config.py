"""Centralised configuration for PlanExe AI control parameters."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _int_setting(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Environment variable {name} must be an integer, got {value!r}") from exc


def _str_setting(name: str, default: str) -> str:
    return os.getenv(name, default)


def _optional_int_setting(name: str, default: Optional[int]) -> Optional[int]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Environment variable {name} must be an integer, got {value!r}") from exc


@dataclass(frozen=True)
class ResponsesStreamingControls:
    """Configuration defaults for streaming analysis requests."""

    system_prompt: str = (
        "You are PlanExe's live analysis assistant. Provide thorough reasoning, cite assumptions,"
        " and produce structured insights while remaining concise and safe."
    )
    stage: str = "streaming_analysis_modal"
    max_output_tokens: Optional[int] = None
    min_output_tokens: int = 512
    max_output_tokens_ceiling: int = 120000
    reasoning_effort: str = "high"
    reasoning_summary: str = "detailed"
    text_verbosity: str = "high"


@dataclass(frozen=True)
class ResponsesConversationControls:
    """Configuration defaults for Conversations API requests."""

    reasoning_effort: str = "high"
    reasoning_summary: str = "succinct"
    text_verbosity: str = "concise"


def _build_streaming_controls() -> ResponsesStreamingControls:
    defaults = ResponsesStreamingControls()
    max_ceiling = _int_setting("OPENAI_MAX_OUTPUT_TOKENS_CEILING", defaults.max_output_tokens_ceiling)
    max_tokens = _optional_int_setting("OPENAI_MAX_OUTPUT_TOKENS", defaults.max_output_tokens)
    if max_tokens is not None and max_tokens > max_ceiling:
        max_tokens = max_ceiling
    min_tokens = _int_setting("OPENAI_MIN_OUTPUT_TOKENS", defaults.min_output_tokens)
    if max_tokens is not None and min_tokens > max_tokens:
        raise ValueError(
            "OPENAI_MIN_OUTPUT_TOKENS cannot be greater than the effective max output token budget"
        )
    return ResponsesStreamingControls(
        system_prompt=_str_setting("OPENAI_STREAMING_SYSTEM_PROMPT", defaults.system_prompt),
        stage=_str_setting("OPENAI_STREAMING_STAGE", defaults.stage),
        max_output_tokens=max_tokens,
        min_output_tokens=min_tokens,
        max_output_tokens_ceiling=max_ceiling,
        reasoning_effort=_str_setting("OPENAI_REASONING_EFFORT", defaults.reasoning_effort),
        reasoning_summary=_str_setting("OPENAI_REASONING_SUMMARY", defaults.reasoning_summary),
        text_verbosity=_str_setting("OPENAI_TEXT_VERBOSITY", defaults.text_verbosity),
    )


def _build_conversation_controls() -> ResponsesConversationControls:
    defaults = ResponsesConversationControls()
    return ResponsesConversationControls(
        reasoning_effort=_str_setting("OPENAI_CONVERSATION_REASONING_EFFORT", defaults.reasoning_effort),
        reasoning_summary=_str_setting("OPENAI_CONVERSATION_REASONING_SUMMARY", defaults.reasoning_summary),
        text_verbosity=_str_setting("OPENAI_CONVERSATION_TEXT_VERBOSITY", defaults.text_verbosity),
    )


RESPONSES_STREAMING_CONTROLS = _build_streaming_controls()
RESPONSES_CONVERSATION_CONTROLS = _build_conversation_controls()
