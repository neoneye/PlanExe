/**
 * Author: Cascade using Claude Sonnet 4
 * Date: 2025-09-23
 * PURPOSE: Terminal-like UI component for displaying real-time Luigi pipeline logs
 * SRP and DRY check: Pass - Single responsibility for terminal display, minimal dependencies
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Copy, Download, Search, Trash2 } from 'lucide-react';
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
  const [isStreamReady, setIsStreamReady] = useState(false);
  const [status, setStatus] = useState<'connecting' | 'running' | 'completed' | 'failed'>('connecting');
  const [searchFilter, setSearchFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  
  const terminalRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

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

  // Poll for stream readiness
  useEffect(() => {
    if (!planId) return;

    const checkStreamStatus = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/plans/${planId}/stream-status`);
        const data = await response.json();
        if (data.status === 'ready') {
          setIsStreamReady(true);
        }
      } catch (error) {
        console.error('Failed to check stream status:', error);
      }
    };

    // Start polling if the stream isn't ready yet
    if (!isStreamReady) {
      const intervalId = setInterval(checkStreamStatus, 500);
      // Cleanup function to clear the interval
      return () => clearInterval(intervalId);
    }
  }, [planId, isStreamReady]);

  // Connect to SSE stream for raw logs once it's ready
  useEffect(() => {
    if (!isStreamReady) return;

    const eventSource = new EventSource(`http://localhost:8000/api/plans/${planId}/stream`);

    eventSource.onopen = () => {
      setStatus('running');
      addLog('✅ Connected to pipeline log stream.', 'info');
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Handle different event types
        if (data.type === 'log' || data.message) {
          const logText = data.message || data.text || data.line || event.data;
          addLog(logText, detectLogLevel(logText));
        } else if (data.type === 'status') {
          if (data.status === 'completed') {
            setStatus('completed');
            addLog('Pipeline completed successfully!', 'info');
            if (onComplete) onComplete();
          } else if (data.status === 'failed') {
            setStatus('failed');
            addLog('Pipeline failed!', 'error');
            if (onError) onError('Pipeline execution failed');
          }
        }
      } catch (_e) {
        // If not JSON, treat as raw log line
        addLog(event.data, detectLogLevel(event.data));
      }
    };

    eventSource.onerror = (err) => {
      console.error('EventSource failed:', err);
      setStatus('failed');
      addLog('❌ Connection to log stream lost. Please check the server logs.', 'error');
      if (onError) onError('Connection to log stream failed');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [isStreamReady, planId, onComplete, onError, addLog]);

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
    switch (status) {
      case 'connecting': return 'bg-yellow-500';
      case 'running': return 'bg-blue-500 animate-pulse';
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
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
                {status.toUpperCase()}
              </Badge>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
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
              {status === 'connecting' ? 'Connecting to pipeline...' : 'No logs yet...'}
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
