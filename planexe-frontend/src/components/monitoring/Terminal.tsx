/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-27
 * PURPOSE: Terminal-like UI component for displaying real-time Luigi pipeline logs via WebSocket
 * SRP and DRY check: Pass - Single responsibility for terminal display with thread-safe WebSocket connection
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Copy, Download, Search, Trash2, RefreshCw } from 'lucide-react';
import { Input } from '@/components/ui/input';

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

  const terminalRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const addLog = useCallback((text: string, level: LogLine['level'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { timestamp, text, level }]);
  }, []);

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
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/plans/${planId}/progress`;

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
          if (data.type === 'log' && data.message) {
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
  }, [planId, addLog, onComplete, onError]);

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
      </CardContent>
    </Card>
  );
};
