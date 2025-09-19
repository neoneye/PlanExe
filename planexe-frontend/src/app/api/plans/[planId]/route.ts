/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-19
 * PURPOSE: API route for individual plan status and management operations
 * SRP and DRY check: Pass - Single responsibility for plan status operations, respects Luigi file patterns
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import {
  GetPlanStatusResponse,
  StopPlanRequest,
  StopPlanResponse,
  APIError,
  PipelineError
} from '@/lib/types/api';
import { PipelineStatus, PipelineProgress } from '@/lib/types/pipeline';

// Get PlanExe root directory
function getPlanExeRoot(): string {
  return path.resolve(process.cwd(), '..');
}

// Extract run ID from plan ID
function extractRunId(planId: string): string {
  // planId format: PlanExe_YYYYMMDD_HHMMSS
  return planId.replace('PlanExe_', '');
}

// Get run directory path
function getRunDirectory(planId: string): string {
  const runId = extractRunId(planId);
  return path.join(getPlanExeRoot(), 'run', runId);
}

// Check if directory exists
async function directoryExists(dirPath: string): Promise<boolean> {
  try {
    const stats = await fs.stat(dirPath);
    return stats.isDirectory();
  } catch {
    return false;
  }
}

// Check if file exists
async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

// Determine pipeline status based on files present
async function determinePipelineStatus(runDir: string): Promise<PipelineStatus> {
  // Check for completion marker
  const completeFile = path.join(runDir, '999-pipeline_complete.txt');
  if (await fileExists(completeFile)) {
    return 'completed';
  }

  // Check for stop flag
  const stopFlag = path.join(runDir, 'pipeline_stop_requested.txt');
  if (await fileExists(stopFlag)) {
    return 'stopped';
  }

  // Check for errors in log file
  const logFile = path.join(runDir, 'log.txt');
  if (await fileExists(logFile)) {
    try {
      const logContent = await fs.readFile(logFile, 'utf-8');
      if (logContent.toLowerCase().includes('error') || logContent.toLowerCase().includes('failed')) {
        return 'failed';
      }
    } catch {
      // If we can't read log, assume still running
    }
  }

  // Check if start time exists (pipeline was started)
  const startTimeFile = path.join(runDir, '001-1-start_time.json');
  if (await fileExists(startTimeFile)) {
    return 'running';
  }

  // Default to created if directory exists but no start time
  return 'created';
}

// Calculate pipeline progress based on file completion
async function calculateProgress(runDir: string): Promise<Partial<PipelineProgress>> {
  try {
    // Read expected filenames if available
    const expectedFilesPath = path.join(runDir, 'expected_filenames1.json');
    let expectedFiles: string[] = [];

    if (await fileExists(expectedFilesPath)) {
      const content = await fs.readFile(expectedFilesPath, 'utf-8');
      expectedFiles = JSON.parse(content);
    } else {
      // Default expected file count for progress estimation
      expectedFiles = Array.from({ length: 50 }, (_, i) => `file${i}.json`);
    }

    // Count actual files present
    const files = await fs.readdir(runDir);
    const actualFiles = files.filter(f =>
      f.endsWith('.json') ||
      f.endsWith('.md') ||
      f.endsWith('.html') ||
      f.endsWith('.csv') ||
      f.endsWith('.txt')
    );

    const filesCompleted = actualFiles.length;
    const totalExpectedFiles = expectedFiles.length;
    const progressPercentage = totalExpectedFiles > 0
      ? Math.round((filesCompleted / totalExpectedFiles) * 100)
      : 0;

    // Determine current phase based on latest files
    let currentPhase = 'setup';
    if (filesCompleted > 40) currentPhase = 'reporting';
    else if (filesCompleted > 30) currentPhase = 'work_breakdown';
    else if (filesCompleted > 20) currentPhase = 'resource_planning';
    else if (filesCompleted > 15) currentPhase = 'governance';
    else if (filesCompleted > 10) currentPhase = 'project_planning';
    else if (filesCompleted > 5) currentPhase = 'strategic_planning';
    else if (filesCompleted > 2) currentPhase = 'initial_analysis';

    // Calculate duration
    const startTimeFile = path.join(runDir, '001-1-start_time.json');
    let duration = 0;

    if (await fileExists(startTimeFile)) {
      const startTimeContent = await fs.readFile(startTimeFile, 'utf-8');
      const startTime = JSON.parse(startTimeContent);
      const startTimestamp = new Date(startTime.server_iso_utc).getTime();
      duration = Math.round((Date.now() - startTimestamp) / 1000); // seconds
    }

    return {
      progressPercentage,
      filesCompleted,
      totalExpectedFiles,
      currentPhase: currentPhase as any,
      duration,
      progressMessage: `${filesCompleted} of ${totalExpectedFiles}`,
      errors: [], // TODO: Parse log file for errors
      lastUpdated: new Date(),
    };

  } catch (error) {
    console.error('Progress calculation error:', error);
    return {
      progressPercentage: 0,
      filesCompleted: 0,
      totalExpectedFiles: 50,
      currentPhase: 'setup',
      duration: 0,
      progressMessage: 'Unknown',
      errors: [],
      lastUpdated: new Date(),
    };
  }
}

// Stop pipeline execution
async function stopPipeline(runDir: string, reason?: string): Promise<void> {
  const stopFlagFile = path.join(runDir, 'pipeline_stop_requested.txt');
  const stopData = {
    timestamp: new Date().toISOString(),
    reason: reason || 'User requested stop',
    requestedBy: 'NextJS UI'
  };

  await fs.writeFile(stopFlagFile, JSON.stringify(stopData, null, 2));
}

// GET /api/plans/[planId] - Get plan status
export async function GET(
  request: NextRequest,
  { params }: { params: { planId: string } }
): Promise<NextResponse> {
  try {
    const { planId } = params;

    if (!planId) {
      const error: APIError = {
        success: false,
        error: {
          code: 'MISSING_PLAN_ID',
          message: 'Plan ID is required',
          timestamp: new Date().toISOString(),
        },
      };
      return NextResponse.json(error, { status: 400 });
    }

    // Get run directory
    const runDir = getRunDirectory(planId);

    // Check if plan exists
    if (!(await directoryExists(runDir))) {
      const error: APIError = {
        success: false,
        error: {
          code: 'PLAN_NOT_FOUND',
          message: `Plan ${planId} not found`,
          timestamp: new Date().toISOString(),
        },
      };
      return NextResponse.json(error, { status: 404 });
    }

    // Determine status and calculate progress
    const status = await determinePipelineStatus(runDir);
    const progressData = await calculateProgress(runDir);

    const progress: PipelineProgress = {
      planId,
      runId: extractRunId(planId),
      status,
      progressPercentage: progressData.progressPercentage || 0,
      progressMessage: progressData.progressMessage || 'Unknown',
      filesCompleted: progressData.filesCompleted || 0,
      totalExpectedFiles: progressData.totalExpectedFiles || 50,
      currentPhase: progressData.currentPhase,
      duration: progressData.duration || 0,
      errors: progressData.errors || [],
      lastUpdated: progressData.lastUpdated || new Date(),
    };

    const response: GetPlanStatusResponse = {
      success: true,
      planId,
      status,
      progress,
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('Plan status error:', error);

    const apiError: PipelineError = {
      success: false,
      error: {
        code: 'PIPELINE_ERROR',
        message: error instanceof Error ? error.message : 'Failed to get plan status',
        timestamp: new Date().toISOString(),
        retryable: true,
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}

// POST /api/plans/[planId] - Stop plan execution
export async function POST(
  request: NextRequest,
  { params }: { params: { planId: string } }
): Promise<NextResponse> {
  try {
    const { planId } = params;
    const body = await request.json() as StopPlanRequest;

    if (!planId) {
      const error: APIError = {
        success: false,
        error: {
          code: 'MISSING_PLAN_ID',
          message: 'Plan ID is required',
          timestamp: new Date().toISOString(),
        },
      };
      return NextResponse.json(error, { status: 400 });
    }

    // Get run directory
    const runDir = getRunDirectory(planId);

    // Check if plan exists
    if (!(await directoryExists(runDir))) {
      const error: APIError = {
        success: false,
        error: {
          code: 'PLAN_NOT_FOUND',
          message: `Plan ${planId} not found`,
          timestamp: new Date().toISOString(),
        },
      };
      return NextResponse.json(error, { status: 404 });
    }

    // Check current status
    const currentStatus = await determinePipelineStatus(runDir);

    if (currentStatus === 'completed' || currentStatus === 'stopped' || currentStatus === 'failed') {
      const response: StopPlanResponse = {
        success: true,
        planId,
        message: `Plan is already ${currentStatus}`,
        finalStatus: currentStatus,
      };
      return NextResponse.json(response);
    }

    // Stop the pipeline
    await stopPipeline(runDir, body.reason);

    const response: StopPlanResponse = {
      success: true,
      planId,
      message: 'Stop request sent to pipeline',
      finalStatus: 'stopped',
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('Plan stop error:', error);

    const apiError: PipelineError = {
      success: false,
      error: {
        code: 'PIPELINE_ERROR',
        message: error instanceof Error ? error.message : 'Failed to stop plan',
        timestamp: new Date().toISOString(),
        retryable: true,
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}

// DELETE /api/plans/[planId] - Delete plan (for future implementation)
export async function DELETE(
  request: NextRequest,
  { params }: { params: { planId: string } }
): Promise<NextResponse> {
  // TODO: Implement plan deletion
  // This would remove the run directory and all files

  const response = {
    success: false,
    error: {
      code: 'NOT_IMPLEMENTED',
      message: 'Plan deletion not yet implemented',
      timestamp: new Date().toISOString(),
    },
  };

  return NextResponse.json(response, { status: 501 });
}