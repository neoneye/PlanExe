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
  ConversationStreamCompletePayload,
  ConversationTurnRequestPayload,
} from '@/lib/api/fastapi-client';
import { useConversationStreaming } from '@/lib/streaming/conversation-streaming';

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
  summary: ConversationStreamCompletePayload | null;
}

export interface UseResponsesConversationOptions {
  initialPrompt: string;
  modelKey: string;
  taskId?: string;
  metadata?: Record<string, unknown>;
  sessionKey?: string;
}

export interface UseResponsesConversationReturn {
  messages: ConversationMessage[];
  startConversation: () => Promise<void>;
  sendUserMessage: (content: string) => Promise<void>;
  finalizeConversation: () => ConversationFinalizeResult;
  resetConversation: () => void;
  isStreaming: boolean;
  streamSummary: ConversationStreamCompletePayload | null;
  streamError: string | null;
  reasoningBuffer: string;
}

const SYSTEM_PROMPT = `You are the PlanExe intake specialist. Guide the user through a short,
structured discovery so the Luigi pipeline receives a rich prompt. Ask concise,
prioritised questions about scope, success metrics, timeline, stakeholders,
constraints, tooling, and risks. Summarise what you have learned, confirm missing
details, and stop once you have enough to build an actionable project brief.`;

function createMessageId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function buildTranscript(messages: ConversationMessage[]): string {
  return messages
    .map((message) => {
      const speaker = message.role === 'assistant' ? 'Assistant' : 'User';
      return `${speaker}: ${message.content.trim()}`;
    })
    .join('\n\n');
}

export function useResponsesConversation(
  options: UseResponsesConversationOptions,
): UseResponsesConversationReturn {
  const { initialPrompt, modelKey, taskId, metadata, sessionKey } = options;
  const conversationKey = useMemo(
    () => sessionKey ?? taskId ?? `prompt-intake-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    [sessionKey, taskId],
  );

  const { state: streamState, startStream, closeStream } = useConversationStreaming();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [initialised, setInitialised] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [previousResponseId, setPreviousResponseId] = useState<string | undefined>(undefined);
  const [lastSummary, setLastSummary] = useState<ConversationStreamCompletePayload | null>(null);
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
    setActiveConversationId(null);
    setPreviousResponseId(undefined);
    setLastSummary(null);
    setLastError(null);
    closeStream(true);
  }, [initialPrompt, conversationKey, closeStream, updateMessages]);

  const streamAssistantReply = useCallback(
    async (latestUserMessage: string, { initial = false } = {}): Promise<void> => {
      if (!modelKey.trim()) {
        throw new Error('No model selected for conversation.');
      }
      const trimmedMessage = latestUserMessage.trim();
      if (!trimmedMessage) {
        return;
      }

      const history = messagesRef.current;
      const transcript = buildTranscript(history);
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
      setLastSummary(null);

      const intro = initial
        ? 'Start the discovery by acknowledging the project and asking the most critical follow-up questions. Limit yourself to 2-3 questions so the user is not overwhelmed.'
        : 'Respond to the latest user update. Acknowledge what they provided and only ask for items that remain unclear. If everything is covered, confirm readiness to proceed.';

      const promptText = `${intro}\n\nLatest user message:\n${trimmedMessage}`;

      const payload: ConversationTurnRequestPayload = {
        modelKey,
        userMessage: promptText,
        conversationId: activeConversationId ?? undefined,
        previousResponseId: !initial ? previousResponseId : undefined,
        instructions: SYSTEM_PROMPT,
        metadata: {
          conversationKey,
          initialPrompt,
          ...(metadata ?? {}),
        },
        context: transcript,
        reasoningEffort: 'high',
        reasoningSummary: 'succinct',
        textVerbosity: 'concise',
      };

      await new Promise<void>((resolve, reject) => {
        startStream(payload, {
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
          onComplete: (completePayload) => {
            const aggregatedText = completePayload.summary.content_text || '';
            const responseId = completePayload.summary.metadata?.response_id as string | undefined;
            if (responseId) {
              setPreviousResponseId(responseId);
            }
            setLastSummary(completePayload);
            updateMessages((prev) =>
              prev.map((entry) =>
                entry.id === assistantId
                  ? {
                      ...entry,
                      streaming: false,
                      content: aggregatedText.trim() || entry.content || 'I have captured your details and am ready to proceed.',
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
            setActiveConversationId(session.conversation_id);
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
      activeConversationId,
      previousResponseId,
      conversationKey,
      initialPrompt,
      metadata,
      startStream,
      updateMessages,
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
    await streamAssistantReply(trimmed, { initial: true });
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
      await streamAssistantReply(trimmed, { initial: false });
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
    return {
      enrichedPrompt,
      transcript,
      summary: lastSummary,
    };
  }, [initialPrompt, lastSummary]);

  const resetConversation = useCallback(() => {
    updateMessages(() => []);
    setInitialised(false);
    setActiveConversationId(null);
    setPreviousResponseId(undefined);
    setLastSummary(null);
    setLastError(null);
    closeStream(true);
  }, [closeStream, updateMessages]);

  const isStreaming = streamState.status === 'connecting' || streamState.status === 'running';

  return {
    messages,
    startConversation,
    sendUserMessage,
    finalizeConversation,
    resetConversation,
    isStreaming,
    streamSummary: lastSummary,
    streamError: lastError ?? streamState.error,
    reasoningBuffer: streamState.reasoningBuffer,
  };
}
