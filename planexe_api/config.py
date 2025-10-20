"""Centralised configuration for PlanExe AI control parameters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponsesStreamingControls:
    """Configuration defaults for streaming analysis requests."""

    system_prompt: str = (
        "You are PlanExe's live analysis assistant. Provide thorough reasoning, cite assumptions,"
        " and produce structured insights while remaining concise and safe."
    )
    stage: str = "streaming_analysis_modal"
    max_output_tokens: int = 16024
    min_output_tokens: int = 512
    max_output_tokens_ceiling: int = 32768
    reasoning_effort: str = "high"
    reasoning_summary: str = "detailed"
    text_verbosity: str = "high"


@dataclass(frozen=True)
class ResponsesConversationControls:
    """Configuration defaults for Conversations API requests."""

    reasoning_effort: str = "high"
    reasoning_summary: str = "succinct"
    text_verbosity: str = "concise"


RESPONSES_STREAMING_CONTROLS = ResponsesStreamingControls()
RESPONSES_CONVERSATION_CONTROLS = ResponsesConversationControls()
