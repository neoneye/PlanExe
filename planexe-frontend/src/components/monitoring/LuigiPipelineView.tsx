/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-26
 * PURPOSE: Real-time Luigi pipeline visualization showing actual 61 tasks from LUIGI.md
 * SRP and DRY check: Pass - Single responsibility for Luigi pipeline display with real SSE integration
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { TaskPhase, TaskStatus } from '@/lib/types/pipeline';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { CheckCircle, RefreshCw, XCircle, Clock } from 'lucide-react';
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
  const [isConnected, setIsConnected] = useState(false);
  const [currentTask, setCurrentTask] = useState<string>('');
  const [completedCount, setCompletedCount] = useState(0);

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

  // Connect to SSE stream and parse Luigi task updates
  useEffect(() => {
    if (!planId) return;

    let eventSource: EventSource | null = null;
    let retryTimeout: NodeJS.Timeout;

    const connectToStream = () => {
      try {
        eventSource = new EventSource(`/api/plans/${planId}/stream`);

        eventSource.onopen = () => {
          setIsConnected(true);
          console.log('Connected to Luigi pipeline stream');
        };

        eventSource.onmessage = (event) => {
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
                console.log('Luigi pipeline completed!');
              } else if (data.status === 'failed') {
                console.log('Luigi pipeline failed!');
              }
            }

          } catch (error) {
            console.warn('Failed to parse SSE message:', error);
          }
        };

        eventSource.onerror = (error) => {
          console.error('Luigi pipeline stream error:', error);
          setIsConnected(false);
          eventSource?.close();

          // Retry connection after 5 seconds
          retryTimeout = setTimeout(connectToStream, 5000);
        };

      } catch (error) {
        console.error('Failed to connect to Luigi pipeline stream:', error);
        retryTimeout = setTimeout(connectToStream, 5000);
      }
    };

    connectToStream();

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (retryTimeout) {
        clearTimeout(retryTimeout);
      }
    };
  }, [planId, updateTaskStatus]);

  const totalTasks = phases.reduce((sum, phase) => sum + phase.totalTasks, 0);
  const overallCompleted = phases.reduce((sum, phase) => sum + phase.completedTasks, 0);

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Luigi Pipeline Progress</span>
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="text-sm text-gray-500">
              {overallCompleted} / {totalTasks} tasks
            </span>
          </div>
        </CardTitle>
        {currentTask && (
          <div className="text-sm text-blue-600">
            Currently running: {currentTask}
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
                    <span className="font-medium">{phase.name}</span>
                    <span className="text-sm text-gray-500">
                      {phase.completedTasks} / {phase.totalTasks} completed
                    </span>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <ul className="space-y-2 pl-4">
                    {phase.tasks.map((task, index) => (
                      <li key={task.id} className="flex items-center space-x-3">
                        <span className="text-xs text-gray-400 w-6">
                          {String(phases.slice(0, phases.indexOf(phase)).reduce((sum, p) => sum + p.totalTasks, 0) + index + 1).padStart(2, '0')}
                        </span>
                        {statusIcons[task.status]}
                        <span className={`flex-1 ${task.status === 'completed' ? 'text-gray-500 line-through' : task.status === 'running' ? 'font-semibold text-blue-600' : ''}`}>
                          {task.name}
                        </span>
                        <span className="text-xs text-gray-400">
                          {task.id}
                        </span>
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