/**
 * Author: ChatGPT (gpt-5-codex)
 * Date: 2025-10-30
 * PURPOSE: React hook encapsulating the Conversations API streaming handshake,
 *          EventSource lifecycle, and throttled delta aggregation for the intake modal.
 * SRP and DRY check: Pass - keeps streaming orchestration isolated from UI components
 *          while reusing the central FastAPI client.
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ConversationSession,
  ConversationStreamChunkPayload,
  ConversationStreamCompletePayload,
  ConversationStreamErrorPayload,
  ConversationStreamServerEvent,
  ConversationTurnRequestPayload,
  fastApiClient,
} from '@/lib/api/fastapi-client';

export type ConversationStreamingStatus = 'idle' | 'connecting' | 'running' | 'completed' | 'error';

export interface ConversationStreamHandlers {
  onTextDelta?: (payload: ConversationStreamChunkPayload) => void;
  onReasoningDelta?: (payload: ConversationStreamChunkPayload) => void;
  onJsonDelta?: (payload: ConversationStreamChunkPayload) => void;
  onComplete?: (payload: ConversationStreamCompletePayload) => void;
  onError?: (message: string) => void;
}

export interface ConversationStreamingState {
  status: ConversationStreamingStatus;
  session: ConversationSession | null;
  responseId: string | null;
  textBuffer: string;
  reasoningBuffer: string;
  jsonChunks: Array<Record<string, unknown>>;
  summary: ConversationStreamCompletePayload | null;
  error: string | null;
  lastEventAt: string | null;
}

const INITIAL_STATE: ConversationStreamingState = {
  status: 'idle',
  session: null,
  responseId: null,
  textBuffer: '',
  reasoningBuffer: '',
  jsonChunks: [],
  summary: null,
  error: null,
  lastEventAt: null,
};

export function useConversationStreaming() {
  const [state, setState] = useState<ConversationStreamingState>(INITIAL_STATE);
  const eventSourceRef = useRef<EventSource | null>(null);
  const handlersRef = useRef<ConversationStreamHandlers>({});
  const rafRef = useRef<number | null>(null);
  const pendingBuffersRef = useRef<{ text?: string; reasoning?: string }>({});

  const closeStream = useCallback((reset = false) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      pendingBuffersRef.current = {};
    }
    handlersRef.current = {};
    setState((prev) => {
      if (reset) {
        return { ...INITIAL_STATE };
      }
      return { ...prev, status: 'idle' };
    });
  }, []);

  useEffect(() => () => closeStream(), [closeStream]);

  const flushBuffers = useCallback(() => {
    const { text, reasoning } = pendingBuffersRef.current;
    pendingBuffersRef.current = {};
    rafRef.current = null;
    if (typeof text === 'undefined' && typeof reasoning === 'undefined') {
      return;
    }
    setState((prev) => ({
      ...prev,
      textBuffer: typeof text === 'string' ? text : prev.textBuffer,
      reasoningBuffer: typeof reasoning === 'string' ? reasoning : prev.reasoningBuffer,
    }));
  }, []);

  const scheduleFlush = useCallback(() => {
    if (rafRef.current !== null) {
      return;
    }
    rafRef.current = requestAnimationFrame(flushBuffers);
  }, [flushBuffers]);

  const startStream = useCallback(
    async (payload: ConversationTurnRequestPayload, handlers?: ConversationStreamHandlers): Promise<ConversationSession> => {
      closeStream(true);
      setState((prev) => ({ ...INITIAL_STATE, status: 'connecting' }));
      handlersRef.current = handlers ?? {};

      const session = await fastApiClient.createConversationTurn(payload);
      setState((prev) => ({
        ...prev,
        session,
      }));

      const source = fastApiClient.startConversationStream(
        session.conversationId,
        session.sessionId,
        session.modelKey,
      );
      eventSourceRef.current = source;

      const handleEvent = (event: MessageEvent) => {
        const parsed: ConversationStreamServerEvent = {
          event: event.type as ConversationStreamServerEvent['event'],
          data: JSON.parse(event.data),
        } as ConversationStreamServerEvent;

        if (parsed.event === 'stream.init') {
          const initData = parsed.data;
          setState((prev) => ({
            ...prev,
            status: 'running',
            responseId: initData.responseId ?? prev.responseId,
            lastEventAt: initData.connectedAt,
          }));
        } else if (parsed.event === 'stream.chunk') {
          const chunk = parsed.data as ConversationStreamChunkPayload;
          if (chunk.kind === 'text') {
            if (typeof chunk.aggregated === 'string') {
              pendingBuffersRef.current.text = chunk.aggregated;
              scheduleFlush();
            }
            handlersRef.current.onTextDelta?.(chunk);
          } else if (chunk.kind === 'reasoning') {
            if (typeof chunk.aggregated === 'string') {
              pendingBuffersRef.current.reasoning = chunk.aggregated;
              scheduleFlush();
            }
            handlersRef.current.onReasoningDelta?.(chunk);
          } else if (chunk.kind === 'json') {
            if (typeof chunk.delta === 'object' && chunk.delta !== null) {
              setState((prev) => ({
                ...prev,
                jsonChunks: [...prev.jsonChunks, chunk.delta as Record<string, unknown>],
                lastEventAt: new Date().toISOString(),
              }));
            }
            handlersRef.current.onJsonDelta?.(chunk);
          }
        } else if (parsed.event === 'stream.complete') {
          const complete = parsed.data as ConversationStreamCompletePayload;
          const responseId = complete.summary.metadata?.responseId as string | undefined;
          setState((prev) => ({
            ...prev,
            status: 'completed',
            summary: complete,
            responseId: responseId ?? prev.responseId,
            lastEventAt: complete.summary.completedAt ?? new Date().toISOString(),
          }));
          handlersRef.current.onComplete?.(complete);
          source.close();
          eventSourceRef.current = null;
        } else if (parsed.event === 'stream.error') {
          const errorPayload = parsed.data as ConversationStreamErrorPayload;
          const message = errorPayload.message || 'Conversation stream failed';
          setState((prev) => ({
            ...prev,
            status: 'error',
            error: message,
            lastEventAt: new Date().toISOString(),
          }));
          handlersRef.current.onError?.(message);
          source.close();
          eventSourceRef.current = null;
        }
      };

      source.addEventListener('stream.init', handleEvent);
      source.addEventListener('stream.chunk', handleEvent);
      source.addEventListener('stream.complete', handleEvent);
      source.addEventListener('stream.error', handleEvent);
      source.onerror = () => {
        const message = 'Conversation streaming connection lost.';
        setState((prev) => ({ ...prev, status: 'error', error: message }));
        handlersRef.current.onError?.(message);
        source.close();
        eventSourceRef.current = null;
      };

      return session;
    },
    [closeStream, scheduleFlush],
  );

  return {
    state,
    startStream,
    closeStream,
  };
}
