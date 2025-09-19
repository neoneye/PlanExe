/**
 * Author: Cascade
 * Date: 2025-09-19T16:59:36-04:00
 * PURPOSE: Real-time progress monitoring component that tracks Luigi pipeline execution with file-based progress
 * SRP and DRY check: Pass - Single responsibility for progress display, respects Luigi pipeline file patterns
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { PipelineProgress, PipelineStatus, PipelinePhase } from '@/lib/types/pipeline';
import { TaskProgressInfo } from '@/lib/types/api';
import { formatDistanceToNow } from 'date-fns';

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
  const [progress, setProgress] = useState<PipelineProgress | null>(null);
  const [recentTasks, setRecentTasks] = useState<TaskProgressInfo[]>([]);
  const [nextTasks, setNextTasks] = useState<TaskProgressInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStopping, setIsStopping] = useState(false);

  // Fetch progress data
  const fetchProgress = useCallback(async () => {
    try {
      const response = await fetch(`/api/plans/${planId}/progress`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error?.message || 'Failed to fetch progress');
      }

      if (data.success) {
        setProgress(data.progress);
        setRecentTasks(data.recentTasks || []);
        setNextTasks(data.nextTasks || []);
        setError(null);

        // Call completion callback if pipeline is done
        if (data.progress.status === 'completed' && onComplete) {
          onComplete(data.progress);
        }
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
  }, [planId, onComplete, onError]);

  // Auto-refresh effect
  useEffect(() => {
    fetchProgress(); // Initial fetch

    if (!autoRefresh) return;

    const interval = setInterval(() => {
      // Stop auto-refresh if pipeline is completed, failed, or stopped
      if (progress?.status && !['running', 'created'].includes(progress.status)) {
        return;
      }
      fetchProgress();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [fetchProgress, autoRefresh, refreshInterval, progress?.status]);

  // Stop pipeline handler
  const handleStop = async () => {
    if (!onStop) return;

    setIsStopping(true);
    try {
      const response = await fetch(`/api/plans/${planId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'User requested stop' })
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
      case 'created':
        return 'default';
      case 'completed':
        return 'default'; // Green-ish
      case 'failed':
        return 'destructive';
      case 'stopped':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  // Get phase display name
  const getPhaseDisplayName = (phase: PipelinePhase) => {
    const phaseNames: Record<PipelinePhase, string> = {
      setup: 'Setup',
      initial_analysis: 'Initial Analysis', 
      strategic_planning: 'Strategic Planning',
      scenario_planning: 'Scenario Planning',
      contextual_analysis: 'Contextual Analysis',
      assumption_management: 'Assumption Management',
      project_planning: 'Project Planning',
      governance: 'Governance Framework',
      resource_planning: 'Resource Planning',
      documentation: 'Documentation',
      work_breakdown: 'Work Breakdown',
      scheduling: 'Scheduling',
      reporting: 'Report Generation',
      completion: 'Completion'
    };
    return phaseNames[phase] || phase;
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

  if (isLoading && !progress) {
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

  if (error && !progress) {
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

  if (!progress) {
    return null;
  }

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
              <Badge variant={getStatusBadgeVariant(progress.status)}>
                {progress.status.toUpperCase()}
              </Badge>
              {(['running', 'created'].includes(progress.status)) && onStop && (
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
              <span>{progress.progressPercentage}%</span>
            </div>
            <Progress value={progress.progressPercentage} className="w-full" />
            <div className="text-sm text-gray-600">
              {progress.progressMessage}
            </div>
          </div>

          {/* Current Phase & Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-sm font-medium">Current Phase</div>
              <div className="text-lg">{progress.currentPhase ? getPhaseDisplayName(progress.currentPhase) : 'Starting...'}</div>
            </div>
            <div>
              <div className="text-sm font-medium">Files Completed</div>
              <div className="text-lg">{progress.filesCompleted} / {progress.totalExpectedFiles}</div>
            </div>
            <div>
              <div className="text-sm font-medium">Duration</div>
              <div className="text-lg">{formatDuration(progress.duration)}</div>
            </div>
            <div>
              <div className="text-sm font-medium">Last Updated</div>
              <div className="text-lg">
                {formatDistanceToNow(new Date(progress.lastUpdated), { addSuffix: true })}
              </div>
            </div>
          </div>

          {/* Error Messages */}
          {progress.errors && progress.errors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <div className="font-medium text-red-800 mb-2">Errors:</div>
              <ul className="text-sm text-red-700 space-y-1">
                {progress.errors.map((error, index) => (
                  <li key={index}>• {typeof error === 'string' ? error : error.message}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Task Details */}
      <div className="grid md:grid-cols-2 gap-6">
        
        {/* Recent Tasks */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Completed Tasks</CardTitle>
            <CardDescription>Last 5 completed pipeline tasks</CardDescription>
          </CardHeader>
          <CardContent>
            {recentTasks.length > 0 ? (
              <div className="space-y-3">
                {recentTasks.map((task, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-green-50 rounded-md">
                    <div>
                      <div className="font-medium text-sm">{task.taskName}</div>
                      {task.endTime && (
                        <div className="text-xs text-gray-600">
                          Completed {formatDistanceToNow(new Date(task.endTime), { addSuffix: true })}
                        </div>
                      )}
                    </div>
                    <Badge variant="outline" className="text-green-700 border-green-300">
                      ✓ Done
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                No completed tasks yet
              </div>
            )}
          </CardContent>
        </Card>

        {/* Next Tasks */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Upcoming Tasks</CardTitle>
            <CardDescription>Next 5 pending pipeline tasks</CardDescription>
          </CardHeader>
          <CardContent>
            {nextTasks.length > 0 ? (
              <div className="space-y-3">
                {nextTasks.map((task, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-blue-50 rounded-md">
                    <div>
                      <div className="font-medium text-sm">{task.taskName}</div>
                      <div className="text-xs text-gray-600">Waiting to start</div>
                    </div>
                    <Badge variant="outline" className="text-blue-700 border-blue-300">
                      Pending
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                No upcoming tasks
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
