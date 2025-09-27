/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-26
 * PURPOSE: Real-time Luigi pipeline visualization showing actual 61 tasks from LUIGI.md
 * SRP and DRY check: Pass - Single responsibility for Luigi pipeline display with real SSE integration
 */

'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { TaskPhase, TaskStatus } from '@/lib/types/pipeline';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { CheckCircle, RefreshCw, XCircle, Clock, Activity, TrendingUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { createLuigiTaskPhases } from '@/lib/luigi-tasks';

// Status icons matching existing TaskList component
const statusIcons: Record<TaskStatus, React.ReactNode> = {
  pending: <Clock className="h-4 w-4 text-gray-400" />,
  running: <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
};

interface LuigiPipelineViewProps {
  planId: string;
  className?: string;
}

export const LuigiPipelineView: React.FC<LuigiPipelineViewProps> = ({
  planId,
  className = ''
}) => {
  const [phases, setPhases] = useState<TaskPhase[]>(createLuigiTaskPhases());
  const [wsConnected, setWsConnected] = useState(false);
  const [currentTask, setCurrentTask] = useState<string>('');
  const [completedCount, setCompletedCount] = useState(0);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const updateTaskStatus = useCallback((taskId: string, status: TaskStatus) => {
    setPhases(prevPhases => {
      return prevPhases.map(phase => {
        const updatedTasks = phase.tasks.map(task => {
          if (task.id === taskId) {
            return { ...task, status };
          }
          return task;
        });

        const completedTasks = updatedTasks.filter(task => task.status === 'completed').length;

        return {
          ...phase,
          tasks: updatedTasks,
          completedTasks
        };
      });
    });

    // Update overall completed count
    if (status === 'completed') {
      setCompletedCount(prev => {
        const newCount = prev + 1;
        return newCount;
      });
    }

    if (status === 'running') {
      setCurrentTask(taskId);
    }
  }, []);

  // WebSocket connection management for Luigi pipeline updates
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

      console.log(`🔌 Luigi Pipeline connecting to WebSocket: ${wsUrl}`);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        setReconnectAttempts(0);
        console.log('✅ Connected to Luigi pipeline WebSocket');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Parse Luigi log messages for task completion
          if (data.type === 'log' && data.message) {
            const message = data.message;

            // Look for Luigi task completion patterns
            // Example: "luigi-interface - DEBUG - Checking if StartTimeTask(...) is complete"
            // Example: "Task StartTimeTask(...) completed successfully"

            if (message.includes('is complete') || message.includes('completed successfully')) {
              // Extract task name from Luigi logs
              const taskMatch = message.match(/(\w+Task)/);
              if (taskMatch) {
                const taskName = taskMatch[1];
                updateTaskStatus(taskName, 'completed');
              }
            }

            // Look for running task patterns
            if (message.includes('Running task') || message.includes('Starting') || message.includes('Executing')) {
              const taskMatch = message.match(/(\w+Task)/);
              if (taskMatch) {
                const taskName = taskMatch[1];
                updateTaskStatus(taskName, 'running');
              }
            }

            // Look for failed task patterns
            if (message.includes('FAILED') || message.includes('ERROR') || message.includes('Exception')) {
              const taskMatch = message.match(/(\w+Task)/);
              if (taskMatch) {
                const taskName = taskMatch[1];
                updateTaskStatus(taskName, 'failed');
              }
            }
          }

          // Handle explicit task update events
          if (data.type === 'task_update' && data.task_id && data.status) {
            updateTaskStatus(data.task_id, data.status);
          }

          // Handle pipeline status updates
          if (data.type === 'status') {
            if (data.status === 'completed') {
              console.log('✅ Luigi pipeline completed!');
            } else if (data.status === 'failed') {
              console.log('❌ Luigi pipeline failed!');
            }
          }

          // Handle stream end
          if (data.type === 'stream_end') {
            console.log('📋 Luigi pipeline stream ended');
            setWsConnected(false);
          }

          // Heartbeat handling
          if (data.type === 'heartbeat') {
            // Heartbeat received - connection is alive
          }

        } catch (error) {
          console.warn('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('Luigi pipeline WebSocket error:', error);
        setWsConnected(false);
      };

      ws.onclose = (event) => {
        setWsConnected(false);
        wsRef.current = null;

        if (event.code === 1000) {
          // Normal closure
          console.log('🔌 Luigi pipeline WebSocket closed normally');
        } else if (event.code === 1006) {
          // Abnormal closure - attempt reconnection
          console.log(`🔌 Luigi pipeline WebSocket lost (code: ${event.code}). Attempting to reconnect...`);
          scheduleReconnect();
        } else {
          console.log(`🔌 Luigi pipeline WebSocket closed (code: ${event.code}, reason: ${event.reason})`);
          if (event.code !== 1001) { // Don't reconnect if going away
            scheduleReconnect();
          }
        }
      };

    } catch (error) {
      console.error('Failed to create Luigi pipeline WebSocket connection:', error);
      scheduleReconnect();
    }
  }, [planId, updateTaskStatus]);

  // Schedule automatic reconnection with exponential backoff
  const scheduleReconnect = useCallback(() => {
    if (reconnectAttempts >= 5) {
      console.log('❌ Maximum Luigi pipeline reconnection attempts reached');
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000); // Max 30 seconds
    console.log(`🔄 Luigi pipeline reconnecting in ${delay / 1000} seconds... (attempt ${reconnectAttempts + 1}/5)`);

    reconnectTimeoutRef.current = setTimeout(() => {
      setReconnectAttempts(prev => prev + 1);
      connectWebSocket();
    }, delay);
  }, [reconnectAttempts, connectWebSocket]);

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
    };
  }, [connectWebSocket]);

  const totalTasks = phases.reduce((sum, phase) => sum + phase.totalTasks, 0);
  const overallCompleted = phases.reduce((sum, phase) => sum + phase.completedTasks, 0);

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Activity className="h-5 w-5 text-blue-600" />
            <span>Luigi Pipeline Progress</span>
          </div>
          <div className="flex items-center space-x-3">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <div className={`w-3 h-3 rounded-full transition-colors duration-200 ${
                    wsConnected
                      ? 'bg-green-500 shadow-green-300 shadow-lg'
                      : reconnectAttempts > 0
                      ? 'bg-yellow-500 animate-pulse shadow-yellow-300 shadow-lg'
                      : 'bg-red-500 shadow-red-300 shadow-lg'
                  }`}></div>
                </TooltipTrigger>
                <TooltipContent>
                  <p>
                    {wsConnected
                      ? 'WebSocket Connected'
                      : reconnectAttempts > 0
                      ? `Reconnecting... (${reconnectAttempts}/5)`
                      : 'WebSocket Disconnected'
                    }
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <Badge variant="secondary" className="text-xs font-medium">
              {overallCompleted} / {totalTasks} tasks
            </Badge>
            {reconnectAttempts > 0 && (
              <Badge variant="destructive" className="text-xs animate-pulse">
                Retry {reconnectAttempts}/5
              </Badge>
            )}
          </div>
        </CardTitle>
        {/* Overall Progress Bar */}
        <div className="space-y-3 mt-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600 font-medium">Overall Progress</span>
            <span className="text-gray-500">
              {totalTasks > 0 ? Math.round((overallCompleted / totalTasks) * 100) : 0}% Complete
            </span>
          </div>
          <Progress
            value={totalTasks > 0 ? (overallCompleted / totalTasks) * 100 : 0}
            className="h-2"
          />
        </div>

        {currentTask && (
          <div className="flex items-center space-x-2 mt-3 p-2 bg-blue-50 rounded-lg border border-blue-200">
            <RefreshCw className="h-4 w-4 text-blue-600 animate-spin" />
            <span className="text-sm text-blue-700 font-medium">
              Currently running: {currentTask}
            </span>
          </div>
        )}
      </CardHeader>
      <CardContent>
        {phases.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500">Waiting for Luigi pipeline to initialize...</p>
          </div>
        ) : (
          <Accordion type="multiple" defaultValue={phases.map(p => p.name)} className="w-full">
            {phases.map((phase) => (
              <AccordionItem value={phase.name} key={phase.name}>
                <AccordionTrigger>
                  <div className="flex items-center justify-between w-full pr-4">
                    <div className="flex items-center space-x-3">
                      <TrendingUp className="h-4 w-4 text-gray-500" />
                      <span className="font-medium">{phase.name}</span>
                    </div>
                    <div className="flex items-center space-x-3">
                      <div className="text-right">
                        <div className="text-xs text-gray-500">
                          {phase.completedTasks} / {phase.totalTasks} completed
                        </div>
                        <div className="text-xs text-gray-400">
                          {phase.totalTasks > 0 ? Math.round((phase.completedTasks / phase.totalTasks) * 100) : 0}%
                        </div>
                      </div>
                      <div className="w-16">
                        <Progress
                          value={phase.totalTasks > 0 ? (phase.completedTasks / phase.totalTasks) * 100 : 0}
                          className="h-1.5"
                        />
                      </div>
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <ul className="space-y-2 pl-4">
                    {phase.tasks.map((task, index) => (
                      <li key={task.id} className={`flex items-center space-x-3 p-2 rounded-lg transition-all duration-200 ${
                        task.status === 'running'
                          ? 'bg-blue-50 border border-blue-200 shadow-sm'
                          : task.status === 'completed'
                          ? 'bg-green-50 border border-green-200'
                          : task.status === 'failed'
                          ? 'bg-red-50 border border-red-200'
                          : 'hover:bg-gray-50'
                      }`}>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger>
                              <span className="text-xs text-gray-400 w-8 text-center font-mono">
                                {String(phases.slice(0, phases.indexOf(phase)).reduce((sum, p) => sum + p.totalTasks, 0) + index + 1).padStart(2, '0')}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Task #{phases.slice(0, phases.indexOf(phase)).reduce((sum, p) => sum + p.totalTasks, 0) + index + 1} of {totalTasks}</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>

                        <div className={`transition-transform duration-200 ${
                          task.status === 'running' ? 'animate-pulse scale-110' : ''
                        }`}>
                          {statusIcons[task.status]}
                        </div>

                        <span className={`flex-1 transition-all duration-200 ${
                          task.status === 'completed'
                            ? 'text-gray-500 line-through'
                            : task.status === 'running'
                            ? 'font-semibold text-blue-700'
                            : task.status === 'failed'
                            ? 'text-red-600 font-medium'
                            : 'text-gray-700'
                        }`}>
                          {task.name}
                        </span>

                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger>
                              <Badge variant="outline" className="text-xs">
                                {task.id}
                              </Badge>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Luigi Task ID: {task.id}</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </li>
                    ))}
                  </ul>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </CardContent>
    </Card>
  );
};