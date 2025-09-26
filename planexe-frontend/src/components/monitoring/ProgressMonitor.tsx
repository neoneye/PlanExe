/**
 * Author: Cascade using Claude Sonnet 4
 * Date: 2025-09-23
 * PURPOSE: Progress monitoring with real terminal view of Luigi pipeline execution
 * SRP and DRY check: Pass - Single responsibility for progress display with actual terminal output
 */

'use client';

import React, { useState } from 'react';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Terminal } from './Terminal';

interface ProgressMonitorProps {
  planId: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
  onStop?: () => void;
  className?: string;
}

export const ProgressMonitor: React.FC<ProgressMonitorProps> = ({
  planId,
  onComplete,
  onError,
  onStop,
  className = ''
}) => {
  const [isStopping, setIsStopping] = useState(false);

  // Stop pipeline handler
  const handleStop = async () => {
    if (!onStop) return;

    setIsStopping(true);
    try {
      const response = await fetch(`http://localhost:8080/api/plans/${planId}`, {
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

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header with stop button */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Pipeline Execution Monitor</CardTitle>
              <CardDescription>Real-time Luigi pipeline logs for Plan ID: {planId}</CardDescription>
            </div>
            <div className="flex items-center space-x-2">
              {onStop && (
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
      </Card>

      {/* Terminal component showing raw logs */}
      <Terminal
        planId={planId}
        onComplete={onComplete}
        onError={onError}
        className="w-full"
      />
    </div>
  );
};