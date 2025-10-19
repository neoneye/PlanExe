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
  ConversationRequestSession,
  ConversationResponseCompletedPayload,
  ConversationResponseErrorPayload,
  ConversationResponseJsonDeltaPayload,
  ConversationResponseReasoningDeltaPayload,
  ConversationResponseTextDeltaPayload,
  ConversationStreamServerEvent,
  ConversationTurnRequestPayload,
  ConversationFinalPayload,
  fastApiClient,
} from '@/lib/api/fastapi-client';

export type ConversationStreamingStatus = 'idle' | 'connecting' | 'running' | 'completed' | 'error';

export interface ConversationStreamHandlers {
  onTextDelta?: (payload: ConversationResponseTextDeltaPayload) => void;
  onReasoningDelta?: (payload: ConversationResponseReasoningDeltaPayload) => void;
  onJsonDelta?: (payload: ConversationResponseJsonDeltaPayload) => void;
  onCompleted?: (payload: ConversationResponseCompletedPayload) => void;
  onFinal?: (payload: ConversationFinalPayload) => void;
  onError?: (message: string) => void;
}

export interface ConversationStreamingState {
  status: ConversationStreamingStatus;
  session: ConversationRequestSession | null;
  responseId: string | null;
  textBuffer: string;
  reasoningBuffer: string;
  jsonChunks: Array<Record<string, unknown>>;
  final: ConversationFinalPayload | null;
  usage: Record<string, unknown> | null;
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
  final: null,
  usage: null,
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
    async (
      conversationId: string,
      payload: ConversationTurnRequestPayload,
      handlers?: ConversationStreamHandlers,
    ): Promise<ConversationRequestSession> => {
      closeStream(true);
      setState((prev) => ({ ...INITIAL_STATE, status: 'connecting' }));
      handlersRef.current = handlers ?? {};

      const session = await fastApiClient.createConversationRequest(conversationId, payload);
      setState((prev) => ({
        ...prev,
        session,
      }));

      const source = fastApiClient.startConversationStream(session.conversation_id, session.token, session.model_key);
      eventSourceRef.current = source;

      const handleEvent = (event: MessageEvent) => {
        const parsed: ConversationStreamServerEvent = {
          event: event.type as ConversationStreamServerEvent['event'],
          data: JSON.parse(event.data),
        } as ConversationStreamServerEvent;

        if (parsed.event === 'response.created') {
          const initData = parsed.data;
          setState((prev) => ({
            ...prev,
            status: 'running',
            responseId: initData.response_id ?? prev.responseId,
            lastEventAt: initData.created_at,
          }));
        } else if (parsed.event === 'response.output_text.delta') {
          const chunk = parsed.data as ConversationResponseTextDeltaPayload;
          if (typeof chunk.aggregated === 'string') {
            pendingBuffersRef.current.text = chunk.aggregated;
            scheduleFlush();
          }
          handlersRef.current.onTextDelta?.(chunk);
        } else if (parsed.event === 'response.reasoning_summary_text.delta') {
          const chunk = parsed.data as ConversationResponseReasoningDeltaPayload;
          if (typeof chunk.aggregated === 'string') {
            pendingBuffersRef.current.reasoning = chunk.aggregated;
            scheduleFlush();
          }
          handlersRef.current.onReasoningDelta?.(chunk);
        } else if (parsed.event === 'response.output_json.delta') {
          const chunk = parsed.data as ConversationResponseJsonDeltaPayload;
          if (chunk.delta && typeof chunk.delta === 'object') {
            setState((prev) => ({
              ...prev,
              jsonChunks: [...prev.jsonChunks, chunk.delta as Record<string, unknown>],
              lastEventAt: new Date().toISOString(),
            }));
          }
          handlersRef.current.onJsonDelta?.(chunk);
        } else if (parsed.event === 'response.completed') {
          const complete = parsed.data as ConversationResponseCompletedPayload;
          setState((prev) => ({
            ...prev,
            status: 'completed',
            responseId: complete.response_id ?? prev.responseId,
            usage: complete.usage ?? prev.usage,
            lastEventAt: complete.completed_at ?? new Date().toISOString(),
          }));
          handlersRef.current.onCompleted?.(complete);
        } else if (parsed.event === 'response.error') {
          const errorPayload = parsed.data as ConversationResponseErrorPayload;
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
        } else if (parsed.event === 'final') {
          const finalPayload = parsed.data as ConversationFinalPayload;
          setState((prev) => ({
            ...prev,
            final: finalPayload,
            usage: finalPayload.summary.usage ?? prev.usage,
            lastEventAt: new Date().toISOString(),
          }));
          handlersRef.current.onFinal?.(finalPayload);
          source.close();
          eventSourceRef.current = null;
        }
      };

      source.addEventListener('response.created', handleEvent);
      source.addEventListener('response.output_text.delta', handleEvent);
      source.addEventListener('response.reasoning_summary_text.delta', handleEvent);
      source.addEventListener('response.output_json.delta', handleEvent);
      source.addEventListener('response.completed', handleEvent);
      source.addEventListener('response.error', handleEvent);
      source.addEventListener('final', handleEvent);
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
