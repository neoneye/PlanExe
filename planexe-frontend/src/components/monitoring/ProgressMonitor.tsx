/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-20
 * PURPOSE: Real-time progress monitoring component with console-like output for Luigi pipeline execution
 * SRP and DRY check: Pass - Single responsibility for progress display, uses actual backend API responses
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { PipelineProgressState, PipelineStatus, TaskPhase, TaskState, TaskStatus, TaskUpdateEvent } from '@/lib/types/pipeline';
import { taskNameMapping, taskPhases } from '@/lib/pipeline-tasks';
import { TaskList } from './TaskList';
import { fastApiClient } from '@/lib/api/fastapi-client';

interface ProgressMonitorProps {
  planId: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
  onStop?: () => void;
  className?: string;
}

// Helper to initialize the state of all tasks
const initializeProgressState = (): PipelineProgressState => {
  const phases: TaskPhase[] = taskPhases.map(phaseInfo => ({
    name: phaseInfo.name,
    tasks: phaseInfo.tasks.map(taskId => ({
      id: taskId,
      name: taskNameMapping[taskId] || taskId,
      status: 'pending',
    })),
    completedTasks: 0,
    totalTasks: phaseInfo.tasks.length,
  }));

  return {
    status: 'running',
    phases,
    overallPercentage: 0,
    completedTasks: 0,
    totalTasks: Object.keys(taskNameMapping).length,
    error: null,
    duration: 0,
  };
};

export const ProgressMonitor: React.FC<ProgressMonitorProps> = ({
  planId,
  onComplete,
  onError,
  onStop,
  className = ''
}) => {
  const [progressState, setProgressState] = useState<PipelineProgressState>(initializeProgressState);
  const [isStopping, setIsStopping] = useState(false);
  const [startTime] = useState<Date>(new Date());

  // Effect to connect to the SSE stream
  useEffect(() => {
    const eventSource = fastApiClient.streamProgress(planId);

    eventSource.onmessage = (event) => {
      console.log('Raw SSE data:', event.data);
    };

    eventSource.addEventListener('task_update', (event) => {
      try {
        const taskUpdate: TaskUpdateEvent = JSON.parse(event.data);
        
        setProgressState(prevState => {
          let taskFound = false;
          const newPhases = prevState.phases.map(phase => {
            const taskIndex = phase.tasks.findIndex(t => t.id === taskUpdate.task_id);
            if (taskIndex !== -1) {
              taskFound = true;
              const newTasks = [...phase.tasks];
              newTasks[taskIndex] = { ...newTasks[taskIndex], status: taskUpdate.status };
              const completedTasks = newTasks.filter(t => t.status === 'completed').length;
              return { ...phase, tasks: newTasks, completedTasks };
            }
            return phase;
          });

          if (!taskFound) {
            console.warn(`Task update for unknown task_id: ${taskUpdate.task_id}`);
            return prevState;
          }

          const totalCompleted = newPhases.reduce((acc, phase) => acc + phase.completedTasks, 0);
          const overallPercentage = Math.round((totalCompleted / prevState.totalTasks) * 100);

          return {
            ...prevState,
            phases: newPhases,
            completedTasks: totalCompleted,
            overallPercentage,
          };
        });
      } catch (e) {
        console.error('Failed to parse task update event:', e);
      }
    });

    eventSource.addEventListener('end', () => {
      setProgressState(prevState => ({ ...prevState, status: 'completed' }));
      if (onComplete) onComplete();
      eventSource.close();
    });

    eventSource.onerror = (err) => {
      console.error('EventSource failed:', err);
      setProgressState(prevState => ({ ...prevState, status: 'failed', error: 'Connection to progress stream failed.' }));
      if (onError) onError('Connection to progress stream failed.');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [planId, onComplete, onError]);


  // Stop pipeline handler
  const handleStop = async () => {
    if (!onStop) return;

    setIsStopping(true);
    try {
      const response = await fetch(`http://localhost:8001/api/plans/${planId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        onStop();
      }
    } catch (err) {
      console.error('Failed to stop pipeline:', err);
    } finally {
      setIsStopping(false);
    }
  };

  // Get status color and variant
  const getStatusBadgeVariant = (status: PipelineStatus) => {
    switch (status) {
      case 'running':
      case 'pending':
        return 'default';
      case 'completed':
        return 'default'; // Using default for green-ish feel
      case 'failed':
        return 'destructive';
      case 'stopped':
      case 'cancelled':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  // Format duration
  const formatDuration = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    if (minutes > 0) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    return `${remainingSeconds}s`;
  };

  const { overallPercentage, completedTasks, totalTasks, status, error } = progressState;

  if (status === 'pending') {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Loading Progress...</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded w-full"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-red-600">Error Loading Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-red-600 mb-4">{error}</p>
          <Button onClick={() => window.location.reload()} variant="outline">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const elapsedSeconds = Math.floor((new Date().getTime() - startTime.getTime()) / 1000);

  return (
    <div className={`space-y-6 ${className}`}>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Pipeline Progress</CardTitle>
              <CardDescription>Plan ID: {planId}</CardDescription>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant={getStatusBadgeVariant(status)}>
                {status.toUpperCase()}
              </Badge>
              {(['running', 'pending'].includes(status)) && onStop && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleStop}
                  disabled={isStopping}
                >
                  {isStopping ? 'Stopping...' : 'Stop Pipeline'}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Overall Progress ({completedTasks} / {totalTasks})</span>
              <span>{overallPercentage}%</span>
            </div>
            <Progress value={overallPercentage} className="w-full" />
          </div>
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <div className="font-medium text-red-800 mb-2">Error:</div>
              <div className="text-sm text-red-700">{error}</div>
            </div>
          )}
        </CardContent>
      </Card>

      <TaskList phases={progressState.phases} />
    </div>
  );
};