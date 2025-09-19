/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-19
 * PURPOSE: API route for creating new plans and starting Luigi pipeline execution
 * SRP and DRY check: Pass - Single responsibility for plan creation, interfaces with existing Luigi pipeline
 */

import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { spawn } from 'child_process';
import { promises as fs } from 'fs';
import path from 'path';
import {
  CreatePlanRequest,
  CreatePlanResponse,
  APIError,
  ValidationError
} from '@/lib/types/api';
import { PlanFormSchema } from '@/lib/types/forms';

// Validation schema for create plan request
const CreatePlanRequestSchema = PlanFormSchema.extend({
  // Additional API-specific validation
  sessionId: z.string().optional(),
  clientInfo: z.object({
    userAgent: z.string(),
    timestamp: z.string(),
    timezone: z.string()
  }).optional()
});

// Generate unique run ID based on timestamp
function generateRunId(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hour = String(now.getHours()).padStart(2, '0');
  const minute = String(now.getMinutes()).padStart(2, '0');
  const second = String(now.getSeconds()).padStart(2, '0');

  return `${year}${month}${day}_${hour}${minute}${second}`;
}

// Get PlanExe root directory (parent of planexe-frontend)
function getPlanExeRoot(): string {
  return path.resolve(process.cwd(), '..');
}

// Create run directory structure
async function createRunDirectory(runId: string): Promise<string> {
  const planExeRoot = getPlanExeRoot();
  const runDir = path.join(planExeRoot, 'run', runId);

  try {
    await fs.mkdir(runDir, { recursive: true });
    return runDir;
  } catch (error) {
    throw new Error(`Failed to create run directory: ${error}`);
  }
}

// Write start time file
async function writeStartTimeFile(runDir: string): Promise<void> {
  const startTime = {
    server_iso_utc: new Date().toISOString(),
    server_timestamp: Date.now(),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
  };

  const startTimeFile = path.join(runDir, '001-1-start_time.json');
  await fs.writeFile(startTimeFile, JSON.stringify(startTime, null, 2));
}

// Write initial plan file
async function writeInitialPlanFile(runDir: string, prompt: string): Promise<void> {
  const planFile = path.join(runDir, 'plan.txt');
  await fs.writeFile(planFile, prompt.trim());
}

// Start Luigi pipeline subprocess
async function startLuigiPipeline(runDir: string, config: {
  speedVsDetail: string;
  llmModel: string;
  openrouterApiKey?: string;
}): Promise<void> {
  const planExeRoot = getPlanExeRoot();
  const pythonScript = path.join(planExeRoot, 'planexe', 'plan', 'run_plan_pipeline.py');

  // Set environment variables for Luigi pipeline
  const env = {
    ...process.env,
    RUN_ID_DIR: runDir,
    SPEED_VS_DETAIL: config.speedVsDetail,
    LLM_MODEL: config.llmModel,
  };

  // Add OpenRouter API key if provided
  if (config.openrouterApiKey) {
    env.OPENROUTER_API_KEY = config.openrouterApiKey;
  }

  return new Promise((resolve, reject) => {
    // Start Python subprocess
    const pythonProcess = spawn('python', ['-m', 'planexe.plan.run_plan_pipeline'], {
      cwd: planExeRoot,
      env,
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    // Handle process startup
    pythonProcess.on('spawn', () => {
      console.log(`Luigi pipeline started for run ${path.basename(runDir)}`);
      resolve();
    });

    pythonProcess.on('error', (error) => {
      console.error(`Failed to start Luigi pipeline: ${error}`);
      reject(new Error(`Pipeline startup failed: ${error.message}`));
    });

    // Log output for debugging
    pythonProcess.stdout?.on('data', (data) => {
      console.log(`Pipeline stdout: ${data.toString()}`);
    });

    pythonProcess.stderr?.on('data', (data) => {
      console.error(`Pipeline stderr: ${data.toString()}`);
    });

    // Don't wait for process completion - it runs in background
    pythonProcess.unref();
  });
}

// Estimate pipeline duration based on speed setting
function estimateDuration(speedVsDetail: string): number {
  // Duration in minutes
  return speedVsDetail === 'FAST_BUT_SKIP_DETAILS' ? 15 : 60;
}

// POST /api/plans - Create new plan
export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    // Parse and validate request body
    const body = await request.json();
    const validatedData = CreatePlanRequestSchema.parse(body);

    // Generate unique identifiers
    const runId = generateRunId();
    const planId = `plan_${runId}`;

    // Create run directory structure
    const runDir = await createRunDirectory(runId);

    // Write required files for Luigi pipeline
    await writeStartTimeFile(runDir);
    await writeInitialPlanFile(runDir, validatedData.prompt);

    // Start Luigi pipeline in background
    await startLuigiPipeline(runDir, {
      speedVsDetail: validatedData.speedVsDetail,
      llmModel: validatedData.llmModel,
      openrouterApiKey: validatedData.openrouterApiKey,
    });

    // Prepare response
    const response: CreatePlanResponse = {
      success: true,
      planId,
      runId,
      runDir,
      status: 'running',
      estimatedDuration: estimateDuration(validatedData.speedVsDetail),
    };

    return NextResponse.json(response, { status: 201 });

  } catch (error) {
    console.error('Plan creation error:', error);

    // Handle validation errors
    if (error instanceof z.ZodError) {
      const validationError: ValidationError = {
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Invalid request data',
          fieldErrors: error.flatten().fieldErrors,
          timestamp: new Date().toISOString(),
        },
      };
      return NextResponse.json(validationError, { status: 400 });
    }

    // Handle other errors
    const apiError: APIError = {
      success: false,
      error: {
        code: 'PLAN_CREATION_ERROR',
        message: error instanceof Error ? error.message : 'Failed to create plan',
        timestamp: new Date().toISOString(),
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}

// GET /api/plans - List recent plans (for future implementation)
export async function GET(request: NextRequest): Promise<NextResponse> {
  // TODO: Implement plan listing functionality
  // This would read from session storage or database to list user's plans

  const response = {
    success: true,
    plans: [],
    message: 'Plan listing not yet implemented',
  };

  return NextResponse.json(response, { status: 200 });
}