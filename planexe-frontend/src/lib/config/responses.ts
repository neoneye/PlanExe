/**
 * Author: ChatGPT using gpt-5-codex
 * Date: 2025-10-19T00:00:00Z
 * PURPOSE: Centralised configuration for Responses API control defaults shared across the
 *          frontend. Prevents duplication of dangerous knobs like maxOutputTokens and
 *          reasoning verbosity.
 * SRP and DRY check: Pass - single source of truth for client-side AI control defaults.
 */

export const RESPONSES_STREAMING_DEFAULTS = {
  reasoningEffort: 'high' as const,
  reasoningSummary: 'detailed' as const,
  textVerbosity: 'high' as const,
  maxOutputTokens: undefined as number | undefined,
};

export const RESPONSES_CONVERSATION_DEFAULTS = {
  reasoningEffort: 'high' as const,
  reasoningSummary: 'detailed' as const,
  textVerbosity: 'high' as const,
};
