/**
 * Author: ChatGPT (gpt-5-codex)
 * Date: 2025-10-30
 * PURPOSE: Manage the landing intake conversation by orchestrating Responses API
 *          streaming turns, tracking transcript state, and producing an enriched
 *          plan prompt for Luigi once the user finalises the dialogue.
 * SRP and DRY check: Pass - dedicated to conversation lifecycle management while
 *          delegating SSE plumbing to useAnalysisStreaming.
 */

'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ConversationFinalPayload,
  ConversationTurnRequestPayload,
  fastApiClient,
  EnrichedPlanIntake,
} from '@/lib/api/fastapi-client';
import { useConversationStreaming } from '@/lib/streaming/conversation-streaming';
import { RESPONSES_CONVERSATION_DEFAULTS } from '@/lib/config/responses';

export type ConversationRole = 'user' | 'assistant';

export interface ConversationMessage {
  id: string;
  role: ConversationRole;
  content: string;
  createdAt: string;
  streaming?: boolean;
}

export interface ConversationFinalizeResult {
  enrichedPrompt: string;
  transcript: ConversationMessage[];
  summary: ConversationFinalPayload | null;
  enrichedIntake: EnrichedPlanIntake | null;
}

export interface UseResponsesConversationOptions {
  initialPrompt: string;
  modelKey: string;
  taskId?: string;
  metadata?: Record<string, unknown>;
  sessionKey?: string;
  schemaName?: string;
  schemaModel?: string;
}

export interface UseResponsesConversationReturn {
  messages: ConversationMessage[];
  conversationId: string | null;
  currentResponseId: string | null;
  startConversation: () => Promise<void>;
  sendUserMessage: (content: string) => Promise<void>;
  finalizeConversation: () => ConversationFinalizeResult;
  resetConversation: () => void;
  isStreaming: boolean;
  streamFinal: ConversationFinalPayload | null;
  streamError: string | null;
  textBuffer: string;
  reasoningBuffer: string;
  jsonChunks: Array<Record<string, unknown>>;
  usage: Record<string, unknown> | null;
}

const SYSTEM_PROMPT = `You are the PlanExe intake specialist. Your goal is to quickly enrich the user's initial idea with 2-3 targeted questions, then provide a concise summary for the Luigi pipeline.

CONVERSATION STRUCTURE:
1. Acknowledge their idea and identify the 2-3 most critical gaps (scope, timeline, constraints, success metrics)
2. Ask those questions concisely (one message, bulleted list)
3. After receiving answers, provide a structured summary:
   - Project scope and deliverables
   - Timeline and milestones
   - Key constraints or dependencies
   - Success metrics
4. Confirm the summary and signal readiness to proceed

IMPORTANT:
- Keep it SHORT: 2-3 questions maximum
- Focus on what's MISSING, not what's already clear
- Use bullet points for questions
- Provide structured summary before finalizing
- Be efficient but friendly

Stop after providing the summary. The user will finalize when ready.`;

function createMessageId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function useResponsesConversation(
  options: UseResponsesConversationOptions,
): UseResponsesConversationReturn {
  const { initialPrompt, modelKey, taskId, metadata, sessionKey, schemaName, schemaModel } = options;
  const conversationKey = useMemo(
    () => sessionKey ?? taskId ?? `prompt-intake-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    [sessionKey, taskId],
  );

  const { state: streamState, startStream, closeStream } = useConversationStreaming();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [initialised, setInitialised] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [currentResponseId, setCurrentResponseIdState] = useState<string | null>(null);
  const currentResponseIdRef = useRef<string | null>(null);
  const persistResponseId = useCallback((responseId: string | null) => {
    currentResponseIdRef.current = responseId;
    setCurrentResponseIdState(responseId);
  }, []);
  const [lastFinal, setLastFinal] = useState<ConversationFinalPayload | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const messagesRef = useRef<ConversationMessage[]>(messages);

  const updateMessages = useCallback((updater: (prev: ConversationMessage[]) => ConversationMessage[]) => {
    setMessages((prev) => {
      const next = updater(prev);
      messagesRef.current = next;
      return next;
    });
  }, []);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    // Reset conversation when prompt changes or modal closes
    updateMessages(() => []);
    setInitialised(false);
    setConversationId(null);
    persistResponseId(null);
    setLastFinal(null);
    setLastError(null);
    closeStream(true);
  }, [initialPrompt, conversationKey, closeStream, updateMessages, persistResponseId]);

  const ensureRemoteConversation = useCallback(async (): Promise<string> => {
    if (conversationId) {
      console.log('[useResponsesConversation] Reusing existing conversation:', conversationId);
      return conversationId;
    }
    console.log('[useResponsesConversation] Creating new conversation with model:', modelKey);
    const response = await fastApiClient.ensureConversation({ modelKey, conversationId: undefined });
    console.log('[useResponsesConversation] Conversation created:', response.conversation_id);
    setConversationId(response.conversation_id);
    return response.conversation_id;
  }, [conversationId, modelKey]);

  const streamAssistantReply = useCallback(
    async (latestUserMessage: string): Promise<void> => {
      if (!modelKey.trim()) {
        throw new Error('No model selected for conversation.');
      }
      const trimmedMessage = latestUserMessage.trim();
      if (!trimmedMessage) {
        return;
      }

      const assistantId = createMessageId();
      const nowIso = new Date().toISOString();

      const assistantMessage: ConversationMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        createdAt: nowIso,
        streaming: true,
      };

      updateMessages((prev) => [...prev, assistantMessage]);
      setLastError(null);
      setLastFinal(null);

      let remoteConversationId: string;
      try {
        remoteConversationId = await ensureRemoteConversation();
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to contact conversation service.';
        setLastError(errorMessage);
        updateMessages((prev) =>
          prev.map((entry) =>
            entry.id === assistantId
              ? {
                  ...entry,
                  streaming: false,
                  content: entry.content || `Encountered an error: ${errorMessage}`,
                }
              : entry,
          ),
        );
        throw error instanceof Error ? error : new Error(errorMessage);
      }

      const previousResponseId = currentResponseIdRef.current ?? undefined;
      const payload: ConversationTurnRequestPayload = {
        modelKey,
        userMessage: trimmedMessage,
        instructions: SYSTEM_PROMPT,
        metadata: {
          conversationKey,
          initialPrompt,
          ...(metadata ?? {}),
        },
        reasoningEffort: RESPONSES_CONVERSATION_DEFAULTS.reasoningEffort,
        reasoningSummary: RESPONSES_CONVERSATION_DEFAULTS.reasoningSummary,
        textVerbosity: RESPONSES_CONVERSATION_DEFAULTS.textVerbosity,
        store: true,
        ...(previousResponseId ? { previousResponseId } : {}),
        ...(schemaName ? { schemaName } : {}),
        ...(schemaModel ? { schemaModel } : {}),
      };

      await new Promise<void>((resolve, reject) => {
        startStream(remoteConversationId, payload, {
          onTextDelta: (chunk) => {
            const aggregated =
              typeof chunk.aggregated === 'string'
                ? chunk.aggregated
                : typeof chunk.delta === 'string'
                  ? chunk.delta
                  : '';
            if (!aggregated) {
              return;
            }
            updateMessages((prev) =>
              prev.map((entry) =>
                entry.id === assistantId
                  ? {
                      ...entry,
                      content: aggregated,
                    }
                  : entry,
              ),
            );
          },
          onCompleted: (completePayload) => {
            if (completePayload.response_id) {
              persistResponseId(completePayload.response_id);
            }
          },
          onFinal: (finalPayload) => {
            const summaryResponseId = finalPayload.summary.response_id ?? currentResponseIdRef.current;
            persistResponseId(summaryResponseId ?? null);
            setLastFinal(finalPayload);
            const finalizedText = finalPayload.summary.text?.trim() ?? '';
            updateMessages((prev) =>
              prev.map((entry) =>
                entry.id === assistantId
                  ? {
                      ...entry,
                      streaming: false,
                      content:
                        finalizedText || entry.content || 'I have captured your details and am ready to proceed.',
                    }
                  : entry,
              ),
            );
            resolve();
          },
          onError: (message) => {
            const errorMessage = message || 'Failed to stream conversation.';
            setLastError(errorMessage);
            updateMessages((prev) =>
              prev.map((entry) =>
                entry.id === assistantId
                  ? {
                      ...entry,
                      streaming: false,
                      content: entry.content || `Encountered an error: ${errorMessage}`,
                    }
                  : entry,
              ),
            );
            reject(new Error(errorMessage));
          },
        })
          .then((session) => {
            if (!conversationId) {
              setConversationId(session.conversation_id);
            }
          })
          .catch((error) => {
            const errorMessage = error instanceof Error ? error.message : 'Failed to contact conversation service.';
            setLastError(errorMessage);
            updateMessages((prev) =>
              prev.map((entry) =>
                entry.id === assistantId
                  ? {
                      ...entry,
                      streaming: false,
                      content: entry.content || `Encountered an error: ${errorMessage}`,
                    }
                  : entry,
              ),
            );
            reject(error instanceof Error ? error : new Error(errorMessage));
          });
      });
    },
    [
      modelKey,
      conversationId,
      conversationKey,
      initialPrompt,
      metadata,
      ensureRemoteConversation,
      startStream,
      updateMessages,
      persistResponseId,
      schemaName,
      schemaModel,
    ],
  );

  const startConversation = useCallback(async () => {
    if (initialised) {
      return;
    }
    const trimmed = initialPrompt.trim();
    if (!trimmed) {
      throw new Error('Cannot start conversation without an initial prompt.');
    }
    setInitialised(true);
    const userMessage: ConversationMessage = {
      id: createMessageId(),
      role: 'user',
      content: trimmed,
      createdAt: new Date().toISOString(),
    };
    updateMessages(() => [userMessage]);
    await streamAssistantReply(trimmed);
  }, [initialPrompt, initialised, streamAssistantReply, updateMessages]);

  const sendUserMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) {
        return;
      }
      const userMessage: ConversationMessage = {
        id: createMessageId(),
        role: 'user',
        content: trimmed,
        createdAt: new Date().toISOString(),
      };
      updateMessages((prev) => [...prev, userMessage]);
      await streamAssistantReply(trimmed);
    },
    [streamAssistantReply, updateMessages],
  );

  const finalizeConversation = useCallback((): ConversationFinalizeResult => {
    const transcript = messagesRef.current;
    const additionalDetails = transcript.filter((entry, index) => entry.role === 'user' && index > 0);
    const agentSummary = transcript.filter((entry) => entry.role === 'assistant').slice(-1)[0]?.content ?? '';

    const enrichedSections: string[] = [];
    const originalPrompt = initialPrompt.trim();
    if (originalPrompt) {
      enrichedSections.push(originalPrompt);
    }
    if (additionalDetails.length > 0) {
      const detailText = additionalDetails
        .map((entry, index) => `${index + 1}. ${entry.content.trim()}`)
        .join('\n');
      enrichedSections.push(`Additional intake details:\n${detailText}`);
    }
    if (agentSummary) {
      enrichedSections.push(`Assistant synthesis:\n${agentSummary.trim()}`);
    }

    const enrichedPrompt = enrichedSections.join('\n\n');

    // Extract enriched intake from JSON chunks if available
    let enrichedIntake: EnrichedPlanIntake | null = null;
    if (lastFinal?.summary?.json && lastFinal.summary.json.length > 0) {
      // The structured output should be in the last JSON chunk
      const lastJsonChunk = lastFinal.summary.json[lastFinal.summary.json.length - 1];

      // Validate it has the expected schema fields
      if (lastJsonChunk &&
          typeof lastJsonChunk === 'object' &&
          lastJsonChunk !== null &&
          'project_title' in lastJsonChunk &&
          'refined_objective' in lastJsonChunk) {
        // Safe type assertion: first to unknown, then to EnrichedPlanIntake
        enrichedIntake = lastJsonChunk as unknown as EnrichedPlanIntake;
        console.log('[useResponsesConversation] Extracted enriched intake:', enrichedIntake);
      }
    }

    return {
      enrichedPrompt,
      transcript,
      summary: lastFinal,
      enrichedIntake,
    };
  }, [initialPrompt, lastFinal]);

  const resetConversation = useCallback(() => {
    updateMessages(() => []);
    setInitialised(false);
    setConversationId(null);
    persistResponseId(null);
    setLastFinal(null);
    setLastError(null);
    closeStream(true);
  }, [closeStream, persistResponseId, updateMessages]);

  const isStreaming = streamState.status === 'connecting' || streamState.status === 'running';

  return {
    messages,
    conversationId,
    currentResponseId,
    startConversation,
    sendUserMessage,
    finalizeConversation,
    resetConversation,
    isStreaming,
    streamFinal: lastFinal,
    streamError: lastError ?? streamState.error,
    textBuffer: streamState.textBuffer,
    reasoningBuffer: streamState.reasoningBuffer,
    jsonChunks: streamState.jsonChunks,
    usage: streamState.usage,
  };
}
