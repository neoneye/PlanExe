/**
 * Author: ChatGPT gpt-5-codex
 * Date: 2025-10-27T00:00:00Z
 * PURPOSE: React hooks for orchestrating analysis streaming handshakes and EventSource
 *          lifecycles using the Responses API SSE contract.
 * SRP and DRY check: Pass - centralises streaming state management and avoids duplicating
 *          handshake logic across components.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  fastApiClient,
  AnalysisStreamRequestPayload,
  AnalysisStreamSession,
  AnalysisStreamServerEvent,
  AnalysisStreamChunkPayload,
  AnalysisStreamCompletePayload,
  AnalysisStreamErrorPayload,
  AnalysisStreamStatusPayload,
  STREAMING_ENABLED,
} from '@/lib/api/fastapi-client';
import { createApiUrl } from '@/lib/utils/api-config';

// Re-export types for component convenience
export type { AnalysisStreamCompletePayload, AnalysisStreamChunkPayload, AnalysisStreamErrorPayload };

export type AnalysisStreamStatus = 'idle' | 'connecting' | 'running' | 'completed' | 'error';

export interface AnalysisStreamHandlers {
  onInit?: (payload: AnalysisStreamServerEvent & { event: 'stream.init' }) => void;
  onStatus?: (payload: AnalysisStreamStatusPayload) => void;
  onChunk?: (payload: AnalysisStreamChunkPayload) => void;
  onComplete?: (payload: AnalysisStreamCompletePayload) => void;
  onError?: (payload: AnalysisStreamErrorPayload) => void;
}

interface InternalHandlers extends AnalysisStreamHandlers {
  lastStatus?: string;
}

export interface AnalysisStreamingState {
  status: AnalysisStreamStatus;
  session: AnalysisStreamSession | null;
  textBuffer: string;
  reasoningBuffer: string;
  jsonChunks: string[];
  summary: AnalysisStreamCompletePayload | null;
  error: string | null;
  lastEventAt: string | null;
}

const INITIAL_STATE: AnalysisStreamingState = {
  status: 'idle',
  session: null,
  textBuffer: '',
  reasoningBuffer: '',
  jsonChunks: [],
  summary: null,
  error: null,
  lastEventAt: null,
};

export function useAnalysisStreaming() {
  const [state, setState] = useState<AnalysisStreamingState>(INITIAL_STATE);
  const eventSourceRef = useRef<EventSource | null>(null);
  const handlersRef = useRef<InternalHandlers>({});
  const sessionRef = useRef<AnalysisStreamSession | null>(null);

  const closeStream = useCallback((reset = false) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    sessionRef.current = reset ? null : sessionRef.current;
    handlersRef.current = {};
    setState((prev) => {
      if (reset) {
        return { ...INITIAL_STATE };
      }
      return { ...prev, status: 'idle', session: sessionRef.current };
    });
  }, []);

  const startStream = useCallback(
    async (
      payload: AnalysisStreamRequestPayload,
      handlers?: AnalysisStreamHandlers,
    ): Promise<AnalysisStreamSession> => {
      if (!STREAMING_ENABLED) {
        const message = 'Streaming is disabled by configuration.';
        setState((prev) => ({ ...prev, status: 'error', error: message }));
        throw new Error(message);
      }

      closeStream(true);
      setState({ ...INITIAL_STATE, status: 'connecting' });
      handlersRef.current = handlers ?? {};

      try {
        const session = await fastApiClient.createAnalysisStream(payload);
        sessionRef.current = session;
        setState((prev) => ({ ...prev, session }));

        const streamUrl = createApiUrl(
          `/api/stream/analyze/${encodeURIComponent(session.taskId)}/${encodeURIComponent(
            session.modelKey,
          )}/${encodeURIComponent(session.sessionId)}`,
        );
        const source = new EventSource(streamUrl);
        eventSourceRef.current = source;

        const parseEvent = (event: MessageEvent): AnalysisStreamServerEvent => {
          const data = JSON.parse(event.data);
          return { event: event.type as AnalysisStreamServerEvent['event'], data } as AnalysisStreamServerEvent;
        };

        source.addEventListener('stream.init', (event) => {
          const parsed = parseEvent(event as MessageEvent);
          const initPayload = parsed.data as import('@/lib/api/fastapi-client').AnalysisStreamInitPayload;
          handlersRef.current.onInit?.(parsed as AnalysisStreamServerEvent & { event: 'stream.init' });
          setState((prev) => ({ ...prev, status: 'running', lastEventAt: initPayload.connectedAt }));
        });

        source.addEventListener('stream.status', (event) => {
          const parsed = parseEvent(event as MessageEvent);
          const payloadStatus = parsed.data as AnalysisStreamStatusPayload;
          handlersRef.current.onStatus?.(payloadStatus);
          handlersRef.current.lastStatus = payloadStatus.status;
          setState((prev) => ({ ...prev, status: 'running', lastEventAt: payloadStatus.startedAt ?? prev.lastEventAt }));
        });

        source.addEventListener('stream.chunk', (event) => {
          const parsed = parseEvent(event as MessageEvent);
          const payloadChunk = parsed.data as AnalysisStreamChunkPayload;
          handlersRef.current.onChunk?.(payloadChunk);
          setState((prev) => {
            const nextText =
              payloadChunk.kind === 'text' ? prev.textBuffer + payloadChunk.delta : prev.textBuffer;
            const nextReasoning =
              payloadChunk.kind === 'reasoning'
                ? `${prev.reasoningBuffer}${prev.reasoningBuffer ? '\n' : ''}${payloadChunk.delta}`
                : prev.reasoningBuffer;
            const nextJson = payloadChunk.kind === 'json' ? [...prev.jsonChunks, payloadChunk.delta] : prev.jsonChunks;
            return {
              ...prev,
              textBuffer: nextText,
              reasoningBuffer: nextReasoning,
              jsonChunks: nextJson,
              lastEventAt: payloadChunk.timestamp,
            };
          });
        });

        source.addEventListener('stream.complete', (event) => {
          const parsed = parseEvent(event as MessageEvent);
          const payloadComplete = parsed.data as AnalysisStreamCompletePayload;
          handlersRef.current.onComplete?.(payloadComplete);
          setState((prev) => ({
            ...prev,
            status: 'completed',
            summary: payloadComplete,
            lastEventAt: new Date().toISOString(),
          }));
          source.close();
          eventSourceRef.current = null;
        });

        source.addEventListener('stream.error', (event) => {
          const parsed = parseEvent(event as MessageEvent);
          const payloadError = parsed.data as AnalysisStreamErrorPayload;
          const errorMessage =
            typeof payloadError.error === 'string'
              ? payloadError.error
              : JSON.stringify(payloadError.error ?? { message: 'Unknown streaming error' });
          handlersRef.current.onError?.(payloadError);
          setState((prev) => ({
            ...prev,
            status: 'error',
            error: errorMessage,
            lastEventAt: payloadError.timestamp,
          }));
          source.close();
          eventSourceRef.current = null;
        });

        source.onerror = () => {
          const message = 'Streaming connection lost.';
          setState((prev) => ({ ...prev, status: 'error', error: message }));
          handlersRef.current.onError?.({
            error: message,
            timestamp: new Date().toISOString(),
            taskId: payload.taskId,
            modelKey: payload.modelKey,
          });
          source.close();
          eventSourceRef.current = null;
        };

        return session;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to start streaming session.';
        setState((prev) => ({ ...prev, status: 'error', error: message }));
        handlersRef.current.onError?.({
          error: message,
          timestamp: new Date().toISOString(),
          taskId: payload.taskId,
          modelKey: payload.modelKey,
        });
        throw error;
      }
    },
    [closeStream],
  );

  useEffect(() => () => closeStream(true), [closeStream]);

  return {
    state,
    startStream,
    closeStream,
  };
}

export interface UseAnalysisResultsConfig {
  taskId: string;
  modelKey: string;
  systemPrompt?: string;
  stage?: string;
  metadata?: Record<string, unknown>;
  onPersist?: (payload: AnalysisStreamCompletePayload) => void | Promise<void>;
}

export interface StartAnalysisOptions {
  prompt: string;
  context?: string;
  metadata?: Record<string, unknown>;
  reasoningEffort?: 'medium' | 'high';
  reasoningSummary?: string;
  textVerbosity?: string;
}

export function useAnalysisResults(config: UseAnalysisResultsConfig) {
  const { state, startStream, closeStream } = useAnalysisStreaming();
  const persistRef = useRef(config.onPersist);

  useEffect(() => {
    persistRef.current = config.onPersist;
  }, [config.onPersist]);

  useEffect(() => {
    if (state.summary && persistRef.current) {
      void persistRef.current(state.summary);
    }
  }, [state.summary]);

  const startAnalysis = useCallback(
    async (options: StartAnalysisOptions, handlers?: AnalysisStreamHandlers) => {
      const payload: AnalysisStreamRequestPayload = {
        taskId: config.taskId,
        modelKey: config.modelKey,
        prompt: options.prompt,
        context: options.context,
        metadata: { ...config.metadata, ...options.metadata },
        reasoningEffort: options.reasoningEffort,
        reasoningSummary: options.reasoningSummary,
        textVerbosity: options.textVerbosity,
        systemPrompt: config.systemPrompt,
        stage: config.stage,
      };
      return startStream(payload, handlers);
    },
    [config.modelKey, config.stage, config.systemPrompt, config.metadata, config.taskId, startStream],
  );

  return {
    state,
    supportsStreaming: STREAMING_ENABLED,
    startAnalysis,
    cancelAnalysis: (reset = true) => closeStream(reset),
  };
}
