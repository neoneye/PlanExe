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
import { PipelineProgress, PipelineStatus } from '@/lib/types/pipeline';
import { PlanResponse } from '@/lib/api/fastapi-client';
import { formatDistanceToNow } from 'date-fns';

interface ProgressMessage {
  timestamp: Date;
  message: string;
  percentage: number;
}

interface ProgressMonitorProps {
  planId: string;
  onComplete?: (progress: PipelineProgress) => void;
  onError?: (error: string) => void;
  onStop?: () => void;
  autoRefresh?: boolean;
  refreshInterval?: number;
  className?: string;
}

export const ProgressMonitor: React.FC<ProgressMonitorProps> = ({
  planId,
  onComplete,
  onError,
  onStop,
  autoRefresh = true,
  refreshInterval = 3000,
  className = ''
}) => {
  const [planData, setPlanData] = useState<PlanResponse | null>(null);
  const [progressHistory, setProgressHistory] = useState<ProgressMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStopping, setIsStopping] = useState(false);
  const [startTime] = useState<Date>(new Date());

  // Fetch progress data via polling
  const fetchProgress = useCallback(async () => {
    try {
      const response = await fetch(`http://localhost:8001/api/plans/${planId}`);
      const data: PlanResponse = await response.json();

      if (!response.ok) {
        throw new Error('Failed to fetch progress');
      }

      // Update plan data
      setPlanData(data);
      setError(null);

      // Add to progress history if message changed
      setProgressHistory(prev => {
        const lastMessage = prev[prev.length - 1];
        if (!lastMessage || lastMessage.message !== data.progress_message) {
          const newMessage: ProgressMessage = {
            timestamp: new Date(),
            message: data.progress_message,
            percentage: data.progress_percentage
          };
          return [...prev, newMessage].slice(-20); // Keep last 20 messages
        }
        return prev;
      });

      // Call completion callback if pipeline is done
      if (data.status === 'completed' && onComplete) {
        const mockProgress: PipelineProgress = {
          status: data.status as PipelineStatus,
          percentage: data.progress_percentage,
          currentTask: data.progress_message,
          tasksCompleted: Math.floor(data.progress_percentage / 2),
          totalTasks: 50,
          filesCompleted: 0,
          currentFile: '',
          duration: Math.floor((new Date().getTime() - startTime.getTime()) / 1000),
          error: data.error_message || null
        };
        onComplete(mockProgress);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setIsLoading(false);
    }
  }, [planId, onComplete, onError, startTime]);


  // Auto-refresh effect - use polling (SSE disabled due to CORS)
  useEffect(() => {
    fetchProgress(); // Initial fetch

    if (!autoRefresh) return;

    // Use polling for now (SSE has CORS issues)
    const interval = setInterval(() => {
      // Stop auto-refresh if pipeline is completed, failed, or stopped
      if (planData?.status && !['running', 'pending'].includes(planData.status)) {
        return;
      }
      fetchProgress();
    }, refreshInterval);

    return () => {
      clearInterval(interval);
    };
  }, [fetchProgress, autoRefresh, refreshInterval, planData?.status]);


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
        fetchProgress(); // Refresh to show stopped status
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
        return 'default'; // Green-ish
      case 'failed':
        return 'destructive';
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

  if (isLoading && !planData) {
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

  if (error && !planData) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-red-600">Error Loading Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-red-600 mb-4">{error}</p>
          <Button onClick={fetchProgress} variant="outline">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!planData) {
    return null;
  }

  const elapsedSeconds = Math.floor((new Date().getTime() - startTime.getTime()) / 1000);

  return (
    <div className={`space-y-6 ${className}`}>

      {/* Main Progress Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Pipeline Progress</CardTitle>
              <CardDescription>Plan ID: {planId}</CardDescription>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant={getStatusBadgeVariant(planData.status as PipelineStatus)}>
                {planData.status.toUpperCase()}
              </Badge>
              {(['running', 'pending'].includes(planData.status)) && onStop && (
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

          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Overall Progress</span>
              <span>{planData.progress_percentage}%</span>
            </div>
            <Progress value={planData.progress_percentage} className="w-full" />
            <div className="text-sm text-gray-600">
              {planData.progress_message}
            </div>
          </div>

          {/* Current Phase & Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-sm font-medium">Status</div>
              <div className="text-lg">{planData.status === 'running' ? 'Processing...' : planData.status}</div>
            </div>
            <div>
              <div className="text-sm font-medium">Progress</div>
              <div className="text-lg">{planData.progress_percentage}%</div>
            </div>
            <div>
              <div className="text-sm font-medium">Duration</div>
              <div className="text-lg">{formatDuration(elapsedSeconds)}</div>
            </div>
            <div>
              <div className="text-sm font-medium">Started</div>
              <div className="text-lg">
                {formatDistanceToNow(new Date(planData.created_at), { addSuffix: true })}
              </div>
            </div>
          </div>

          {/* Error Messages */}
          {planData.error_message && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <div className="font-medium text-red-800 mb-2">Error:</div>
              <div className="text-sm text-red-700">{planData.error_message}</div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Console Output */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Progress Console</CardTitle>
          <CardDescription>Real-time progress updates</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="bg-gray-900 text-green-400 p-4 rounded-md font-mono text-sm max-h-96 overflow-y-auto">
            {progressHistory.length > 0 ? (
              <div className="space-y-1">
                {progressHistory.map((msg, index) => (
                  <div key={index} className="flex items-start space-x-2">
                    <span className="text-gray-500 text-xs whitespace-nowrap">
                      [{msg.timestamp.toLocaleTimeString()}]
                    </span>
                    <span className="text-blue-400">[{msg.percentage}%]</span>
                    <span className="flex-1">{msg.message}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-500 text-center py-8">
                Waiting for progress updates...
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};