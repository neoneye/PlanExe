/**
 * Author: ChatGPT gpt-5-codex (updates; original by Codex using GPT-5)
 * Date: 2025-10-19
 * PURPOSE: Augment terminal monitor with Responses reasoning stream panels so operators see
 *          token deltas, reasoning traces, and final outputs alongside raw Luigi logs while
 *          sharing websocket URL construction with other realtime clients. Latest revision surfaces
 *          every usage metric emitted by the backend so the UI mirrors streamed telemetry exactly.
 * SRP and DRY check: Pass - keeps monitoring responsibilities cohesive by layering telemetry
 *          visualization without duplicating WebSocket wiring. Previous baseline provided by
 *          Claude Code using Sonnet 4 (2025-09-27).
 */

'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Copy, Download, Search, Trash2, RefreshCw } from 'lucide-react';
import { Input } from '@/components/ui/input';
import type { WebSocketLLMStreamMessage } from '@/lib/api/fastapi-client';
import { createWebSocketUrl } from '@/lib/utils/api-config';

interface TerminalProps {
  planId: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
  className?: string;
}

interface LogLine {
  timestamp: string;
  text: string;
  level?: 'info' | 'error' | 'warn' | 'debug';
}

type StreamStatus = 'running' | 'completed' | 'failed';

interface StreamEventRecord {
  sequence: number;
  event: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

interface LLMStreamState {
  interactionId: number;
  planId: string;
  stage: string;
  textDeltas: string[];
  reasoningDeltas: string[];
  textBuffer: string;
  reasoningBuffer: string;
  finalText?: string;
  finalReasoning?: string;
  usage?: Record<string, unknown>;
  rawPayload?: Record<string, unknown> | null;
  status: StreamStatus;
  error?: string;
  lastUpdated: number;
  promptPreview?: string | null;
  events: StreamEventRecord[];
}

const MAX_STREAM_DELTAS = 200;
const MAX_STREAM_EVENTS = 100;

// Utility functions for stream processing
function sanitizeStreamPayload(data: unknown): Record<string, unknown> {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return {};
  }
  return data as Record<string, unknown>;
}

function cloneEventPayload(data: Record<string, unknown>): Record<string, unknown> {
  try {
    return JSON.parse(JSON.stringify(data));
  } catch {
    return {};
  }
}

function appendReasoningChunk(buffer: { text: string; reasoning: string }, delta: string): void {
  if (buffer.reasoning) {
    buffer.reasoning = `${buffer.reasoning}\n${delta}`;
  } else {
    buffer.reasoning = delta;
  }
}
const STANDARD_USAGE_KEYS = ['input_tokens', 'output_tokens', 'total_tokens', 'reasoning_tokens'] as const;
const STANDARD_USAGE_LABELS: Record<(typeof STANDARD_USAGE_KEYS)[number], string> = {
  input_tokens: 'Input tokens',
  output_tokens: 'Output tokens',
  total_tokens: 'Total tokens',
  reasoning_tokens: 'Reasoning tokens'
};

export const Terminal: React.FC<TerminalProps> = ({
  planId,
  onComplete,
  onError,
  className = ''
}) => {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [status, setStatus] = useState<'connecting' | 'running' | 'completed' | 'failed'>('connecting');
  const [searchFilter, setSearchFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [fallbackToPolling, setFallbackToPolling] = useState(false);
  const [llmStreams, setLlmStreams] = useState<Record<number, LLMStreamState>>({});

  const terminalRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const streamBuffersRef = useRef<Map<number, { text: string; reasoning: string }>>(new Map());

  const addLog = useCallback((text: string, level: LogLine['level'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { timestamp, text, level }]);
  }, []);

  const handleLlmStreamMessage = useCallback((message: WebSocketLLMStreamMessage) => {
    const sanitizedData = sanitizeStreamPayload(message.data);
    const buffer = streamBuffersRef.current.get(message.interaction_id) ?? { text: '', reasoning: '' };

    setLlmStreams(prev => {
      const existing = prev[message.interaction_id];
      const promptPreview = typeof sanitizedData.prompt_preview === 'string' ? sanitizedData.prompt_preview : undefined;
      const baseState: LLMStreamState = existing ?? {
        interactionId: message.interaction_id,
        planId: message.plan_id,
        stage: message.stage,
        textDeltas: [],
        reasoningDeltas: [],
        textBuffer: buffer.text,
        reasoningBuffer: buffer.reasoning,
        status: 'running',
        lastUpdated: Date.now(),
        promptPreview: promptPreview ?? null,
        rawPayload: null,
        events: [],
      };

      const updated: LLMStreamState = {
        ...baseState,
        lastUpdated: Date.now(),
        promptPreview: baseState.promptPreview ?? promptPreview ?? null,
        textBuffer: buffer.text,
        reasoningBuffer: buffer.reasoning,
        rawPayload: baseState.rawPayload ?? null,
      };

      switch (message.event) {
        case 'start':
          updated.status = 'running';
          break;
        case 'text_delta': {
          const delta = typeof sanitizedData.delta === 'string' ? sanitizedData.delta : '';
          if (delta) {
            const next = [...updated.textDeltas, delta];
            if (next.length > MAX_STREAM_DELTAS) {
              next.splice(0, next.length - MAX_STREAM_DELTAS);
            }
            updated.textDeltas = next;
            buffer.text = `${buffer.text}${delta}`;
          }
          break;
        }
        case 'reasoning_delta': {
          const delta = typeof sanitizedData.delta === 'string' ? sanitizedData.delta : '';
          if (delta) {
            const next = [...updated.reasoningDeltas, delta];
            if (next.length > MAX_STREAM_DELTAS) {
              next.splice(0, next.length - MAX_STREAM_DELTAS);
            }
            updated.reasoningDeltas = next;
            appendReasoningChunk(buffer, delta);
          }
          break;
        }
        case 'final': {
          if (typeof sanitizedData.text === 'string') {
            updated.finalText = sanitizedData.text;
            buffer.text = sanitizedData.text;
          }
          if (typeof sanitizedData.reasoning === 'string') {
            updated.finalReasoning = sanitizedData.reasoning;
            buffer.reasoning = sanitizedData.reasoning;
          }
          if (sanitizedData.usage && typeof sanitizedData.usage === 'object' && !Array.isArray(sanitizedData.usage)) {
            updated.usage = sanitizedData.usage as Record<string, unknown>;
          }
          const rawPayload = sanitizeStreamPayload((sanitizedData as Record<string, unknown>).raw_payload);
          if (Object.keys(rawPayload).length > 0) {
            updated.rawPayload = rawPayload;
          }
          break;
        }
        case 'end': {
          const status = typeof sanitizedData.status === 'string' ? sanitizedData.status.toLowerCase() : 'completed';
          updated.status = status === 'failed' ? 'failed' : 'completed';
          updated.error = typeof sanitizedData.error === 'string' ? sanitizedData.error : undefined;
          break;
        }
        default:
          break;
      }

      streamBuffersRef.current.set(message.interaction_id, {
        text: buffer.text,
        reasoning: buffer.reasoning,
      });

      updated.textBuffer = buffer.text;
      updated.reasoningBuffer = buffer.reasoning;

      const eventRecord: StreamEventRecord = {
        sequence: typeof message.sequence === 'number' ? message.sequence : Date.now(),
        event: message.event,
        timestamp: message.timestamp,
        payload: cloneEventPayload(sanitizedData),
      };

      const nextEvents = [...baseState.events, eventRecord];
      if (nextEvents.length > MAX_STREAM_EVENTS) {
        nextEvents.splice(0, nextEvents.length - MAX_STREAM_EVENTS);
      }
      updated.events = nextEvents;

      return { ...prev, [message.interaction_id]: updated };
    });

    if (message.event === 'final') {
      const fullText = typeof sanitizedData.text === 'string' ? sanitizedData.text : '';
      const snippet = fullText.slice(0, 160);
      if (snippet) {
        addLog(`🧠 [${message.stage}] Final output received: ${snippet}${snippet.length < fullText.length ? '…' : ''}`, 'info');
      } else {
        addLog(`🧠 [${message.stage}] Final output payload received.`, 'info');
      }
    } else if (message.event === 'end') {
      const statusLabel = typeof sanitizedData.status === 'string' ? sanitizedData.status.toUpperCase() : 'COMPLETED';
      if (statusLabel === 'FAILED') {
        addLog(`❌ [${message.stage}] LLM stream failed: ${typeof sanitizedData.error === 'string' ? sanitizedData.error : 'unknown error'}`, 'error');
      } else {
        addLog(`✅ [${message.stage}] LLM stream ${statusLabel.toLowerCase()}.`, 'info');
      }
    }
  }, [addLog]);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // WebSocket connection management with automatic reconnection
  const connectWebSocket = useCallback(() => {
    if (!planId) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Clear any pending reconnection
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    try {
      const wsUrl = createWebSocketUrl(planId);

      addLog(`🔌 Connecting to WebSocket: ${wsUrl}`, 'info');

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        setStatus('running');
        setReconnectAttempts(0);
        addLog('✅ Connected to pipeline WebSocket stream.', 'info');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle different message types from WebSocket
          if (data.type === 'llm_stream') {
            handleLlmStreamMessage(data as WebSocketLLMStreamMessage);
          } else if (data.type === 'log' && data.message) {
            addLog(data.message, detectLogLevel(data.message));
          } else if (data.type === 'error' && data.message) {
            addLog(`ERROR: ${data.message}`, 'error');
          } else if (data.type === 'status') {
            if (data.status === 'completed') {
              setStatus('completed');
              addLog('✅ Pipeline completed successfully!', 'info');
              if (onComplete) onComplete();
            } else if (data.status === 'failed') {
              setStatus('failed');
              addLog(`❌ Pipeline failed: ${data.message || 'Unknown error'}`, 'error');
              if (onError) onError(data.message || 'Pipeline execution failed');
            } else if (data.status === 'running') {
              setStatus('running');
              if (data.message) {
                addLog(data.message, 'info');
              }
            }
          } else if (data.type === 'stream_end') {
            addLog('📋 Pipeline execution completed - stream ended', 'info');
            setWsConnected(false);
          } else if (data.type === 'heartbeat') {
            // Heartbeat - no need to log
          } else {
            // Fallback for any other message format
            const logText = data.message || data.text || JSON.stringify(data);
            addLog(logText, detectLogLevel(logText));
          }
        } catch (error) {
          // If not JSON, treat as raw log line
          addLog(event.data, detectLogLevel(event.data));
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addLog('❌ WebSocket connection error', 'error');
        setWsConnected(false);
      };

      ws.onclose = (event) => {
        setWsConnected(false);
        wsRef.current = null;

        if (event.code === 1000) {
          // Normal closure
          addLog('🔌 WebSocket connection closed normally', 'info');
        } else if (event.code === 1006) {
          // Abnormal closure - attempt reconnection
          addLog(`🔌 WebSocket connection lost (code: ${event.code}). Attempting to reconnect...`, 'warn');
          scheduleReconnect();
        } else {
          addLog(`🔌 WebSocket connection closed (code: ${event.code}, reason: ${event.reason})`, 'warn');
          if (event.code !== 1001) { // Don't reconnect if going away
            scheduleReconnect();
          }
        }
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      addLog(`❌ Failed to create WebSocket connection: ${error}`, 'error');
      scheduleReconnect();
    }
  }, [planId, addLog, onComplete, onError, handleLlmStreamMessage]);

  // REST polling fallback when WebSocket fails
  const startPollingFallback = useCallback(() => {
    if (fallbackToPolling) return; // Already polling

    setFallbackToPolling(true);
    addLog('🔄 WebSocket failed, falling back to REST polling...', 'warn');

    const pollPlanStatus = async () => {
      try {
        const response = await fetch(`/api/plans/${planId}`);
        if (response.ok) {
          const plan = await response.json();

          // Update status based on plan status
          if (plan.status === 'completed') {
            setStatus('completed');
            addLog('✅ Pipeline completed (via polling)', 'info');
            if (onComplete) onComplete();
            stopPolling();
            return;
          } else if (plan.status === 'failed') {
            setStatus('failed');
            addLog('❌ Pipeline failed (via polling)', 'error');
            if (onError) onError('Pipeline failed');
            stopPolling();
            return;
          } else if (plan.status === 'running') {
            setStatus('running');
            if (plan.progress_message) {
              addLog(`📊 ${plan.progress_message} (${plan.progress_percentage || 0}%)`, 'info');
            }
          }
        }
      } catch (error) {
        addLog(`❌ Polling error: ${error}`, 'error');
      }
    };

    // Start polling every 5 seconds
    pollingIntervalRef.current = setInterval(pollPlanStatus, 5000);
    pollPlanStatus(); // Initial poll
  }, [planId, fallbackToPolling, addLog, onComplete, onError]);

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setFallbackToPolling(false);
  }, []);

  // Schedule automatic reconnection with exponential backoff
  const scheduleReconnect = useCallback(() => {
    if (reconnectAttempts >= 5) {
      addLog('❌ Maximum WebSocket reconnection attempts reached. Switching to polling fallback.', 'error');
      startPollingFallback();
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000); // Max 30 seconds
    addLog(`🔄 Reconnecting in ${delay / 1000} seconds... (attempt ${reconnectAttempts + 1}/5)`, 'warn');

    reconnectTimeoutRef.current = setTimeout(() => {
      setReconnectAttempts(prev => prev + 1);
      connectWebSocket();
    }, delay);
  }, [reconnectAttempts, addLog, connectWebSocket, startPollingFallback]);

  // Connect to WebSocket on component mount
  useEffect(() => {
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      stopPolling();
    };
  }, [connectWebSocket, stopPolling]);

  const detectLogLevel = (text: string): LogLine['level'] => {
    const upperText = text.toLowerCase();
    if (upperText.includes('error') || upperText.includes('failed') || upperText.includes('exception')) {
      return 'error';
    }
    if (upperText.includes('warn') || upperText.includes('warning')) {
      return 'warn';
    }
    if (upperText.includes('debug')) {
      return 'debug';
    }
    return 'info';
  };

  const copyLogsToClipboard = () => {
    const logText = filteredLogs.map(log => `[${log.timestamp}] ${log.text}`).join('\n');
    navigator.clipboard.writeText(logText);
  };

  const downloadLogs = () => {
    const logText = filteredLogs.map(log => `[${log.timestamp}] ${log.text}`).join('\n');
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `planexe_logs_${planId}_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const getStatusColor = () => {
    if (fallbackToPolling) {
      switch (status) {
        case 'running': return 'bg-purple-500 animate-pulse';
        case 'completed': return 'bg-green-500';
        case 'failed': return 'bg-red-500';
        default: return 'bg-purple-400';
      }
    }
    if (!wsConnected && status === 'connecting') {
      return 'bg-yellow-500 animate-pulse';
    }
    switch (status) {
      case 'connecting': return 'bg-yellow-500';
      case 'running': return wsConnected ? 'bg-blue-500 animate-pulse' : 'bg-orange-500';
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusText = () => {
    if (fallbackToPolling) {
      return `${status.toUpperCase()} (POLLING MODE)`;
    }
    if (!wsConnected && status !== 'completed' && status !== 'failed') {
      return `${status.toUpperCase()} (WS: DISCONNECTED)`;
    }
    return status.toUpperCase();
  };

  const getLogLineColor = (level: LogLine['level']) => {
    switch (level) {
      case 'error': return 'text-red-400';
      case 'warn': return 'text-yellow-400';
      case 'debug': return 'text-gray-400';
      default: return 'text-green-400';
    }
  };

  const streamEntries = useMemo(() => {
    return Object.values(llmStreams).sort((a, b) => b.lastUpdated - a.lastUpdated);
  }, [llmStreams]);

  const formatTokenValue = (value: unknown) => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value.toLocaleString();
    }
    if (typeof value === 'string' && value.trim().length > 0) {
      return value;
    }
    if (typeof value === 'boolean') {
      return value ? 'true' : 'false';
    }
    if (value === 0) {
      return '0';
    }
    return '—';
  };

  const renderUsageDetailValue = (value: unknown) => {
    if (value === null || value === undefined) {
      return <span className="text-slate-400">—</span>;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return <span className="text-slate-300">{value.toLocaleString()}</span>;
    }
    if (typeof value === 'string') {
      return <span className="text-slate-300">{value}</span>;
    }
    if (typeof value === 'boolean') {
      return <span className="text-slate-300">{value ? 'true' : 'false'}</span>;
    }
    try {
      return (
        <pre className="mt-1 rounded bg-slate-950/70 p-2 text-[11px] text-slate-300 whitespace-pre-wrap break-words">
          {JSON.stringify(value, null, 2)}
        </pre>
      );
    } catch (error) {
      return <span className="text-slate-300">{String(value)}</span>;
    }
  };

  // Filter logs based on search
  const filteredLogs = searchFilter
    ? logs.filter(log => log.text.toLowerCase().includes(searchFilter.toLowerCase()))
    : logs;

  return (
    <Card className={`${className} font-mono`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <CardTitle className="text-lg">Luigi Pipeline Logs</CardTitle>
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${getStatusColor()}`}></div>
              <Badge variant="outline" className="text-xs">
                {getStatusText()}
              </Badge>
              {reconnectAttempts > 0 && (
                <Badge variant="destructive" className="text-xs">
                  Retry {reconnectAttempts}/5
                </Badge>
              )}
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={connectWebSocket}
              title="Reconnect WebSocket"
              disabled={wsConnected}
            >
              <RefreshCw className={`h-4 w-4 ${!wsConnected ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={copyLogsToClipboard}
              title="Copy logs to clipboard"
            >
              <Copy className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={downloadLogs}
              title="Download logs"
            >
              <Download className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearLogs}
              title="Clear logs"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        <div className="flex items-center space-x-2 mt-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
            <Input
              placeholder="Filter logs..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="pl-10 h-8 text-sm"
            />
          </div>
          <div className="text-xs text-gray-500">
            {filteredLogs.length} / {logs.length} lines
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="p-0">
        <div
          ref={terminalRef}
          className="bg-gray-900 text-green-400 h-96 overflow-y-auto p-4 rounded-b-lg font-mono text-sm leading-relaxed"
          onScroll={() => {
            const terminal = terminalRef.current;
            if (terminal) {
              const isAtBottom = terminal.scrollHeight - terminal.scrollTop === terminal.clientHeight;
              setAutoScroll(isAtBottom);
            }
          }}
        >
          {filteredLogs.length === 0 ? (
            <div className="text-gray-500 italic">
              {!wsConnected && status === 'connecting'
                ? 'Connecting to WebSocket pipeline stream...'
                : wsConnected && status === 'running'
                ? 'WebSocket connected, waiting for pipeline logs...'
                : 'No logs yet...'}
            </div>
          ) : (
            filteredLogs.map((log, index) => (
              <div key={index} className="mb-1">
                <span className="text-gray-400 mr-2">[{log.timestamp}]</span>
                <span className={getLogLineColor(log.level)}>{log.text}</span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
        
        {!autoScroll && (
          <div className="bg-blue-100 border-t border-blue-200 px-4 py-2 text-sm text-blue-800">
            <Button
              variant="link"
              size="sm"
              onClick={() => {
                setAutoScroll(true);
                bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="p-0 h-auto text-blue-600"
            >
              New logs available - click to scroll to bottom
            </Button>
          </div>
        )}

        {streamEntries.length > 0 && (
          <div className="border-t border-gray-800 bg-gray-950/60">
            <div className="px-4 py-3 border-b border-gray-800">
              <h3 className="text-sm font-semibold text-slate-200">Live LLM Streams</h3>
              <p className="text-xs text-slate-400">
                Structured deltas arrive before the model finalizes JSON output so you can audit reasoning in-flight.
              </p>
            </div>
            <div className="divide-y divide-gray-800">
              {streamEntries.map((entry) => {
                const statusStyles =
                  entry.status === 'completed'
                    ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/40'
                    : entry.status === 'failed'
                    ? 'bg-red-600/20 text-red-300 border border-red-500/40'
                    : 'bg-blue-600/20 text-blue-300 border border-blue-500/40 animate-pulse';
                const assembledText = entry.finalText ?? entry.textBuffer ?? entry.textDeltas.join('');
                const assembledReasoning = entry.finalReasoning ?? entry.reasoningBuffer ?? entry.reasoningDeltas.join('\n');
                const usageRecord = (entry.usage ?? {}) as Record<string, unknown>;
                const extraUsageEntries = Object.entries(usageRecord).filter(
                  ([key]) => !STANDARD_USAGE_KEYS.includes(key as (typeof STANDARD_USAGE_KEYS)[number])
                );
                const hasUsageData = Object.keys(usageRecord).length > 0;

                return (
                  <div key={entry.interactionId} className="px-4 py-3 grid gap-4 md:grid-cols-2">
                    <div>
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span className="font-semibold text-slate-100">{entry.stage}</span>
                        <span className={`px-2 py-0.5 rounded-full uppercase tracking-wide text-[10px] ${statusStyles}`}>
                          {entry.status}
                        </span>
                      </div>
                      {entry.promptPreview && (
                        <p className="mt-1 text-[11px] text-slate-500 truncate">
                          Prompt: {entry.promptPreview}
                        </p>
                      )}
                      <div className="mt-3 space-y-1">
                        <p className="text-[11px] uppercase text-slate-500 tracking-wide">Model Output</p>
                        <div className="bg-slate-950/80 border border-slate-800 rounded p-2 text-xs text-slate-200 whitespace-pre-wrap max-h-40 overflow-y-auto">
                          {assembledText || '—'}
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2 md:border-l md:border-gray-800 md:pl-4">
                      <div>
                        <p className="text-[11px] uppercase text-slate-500 tracking-wide">Reasoning Trace</p>
                        <div className="bg-slate-950/80 border border-slate-800 rounded p-2 text-xs text-slate-300 whitespace-pre-wrap max-h-40 overflow-y-auto">
                          {assembledReasoning || '—'}
                        </div>
                      </div>
                      {hasUsageData && (
                        <div className="space-y-2">
                          <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-500">
                            {STANDARD_USAGE_KEYS.map((key) => (
                              <div key={key}>
                                {STANDARD_USAGE_LABELS[key]}:
                                <span className="ml-1 text-slate-300">{formatTokenValue(usageRecord[key])}</span>
                              </div>
                            ))}
                          </div>
                          {extraUsageEntries.length > 0 && (
                            <div>
                              <p className="text-[10px] uppercase tracking-wide text-slate-600">Additional usage telemetry</p>
                              <div className="mt-1 space-y-1 text-[11px] text-slate-500">
                                {extraUsageEntries.map(([key, value]) => (
                                  <div key={key}>
                                    <span className="font-semibold text-slate-400">{key}</span>
                                    <div>{renderUsageDetailValue(value)}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                      {entry.error && (
                        <p className="text-[11px] text-red-400">Error: {entry.error}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
