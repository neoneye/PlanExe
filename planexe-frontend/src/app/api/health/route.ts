/**
 * Author: Cascade
 * Date: 2025-09-19T17:40:43-04:00
 * PURPOSE: Health check endpoint for system monitoring and integration testing
 * SRP and DRY check: Pass - Single responsibility for health monitoring, checks critical system components
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { HealthCheckResponse, APIError } from '@/lib/types/api';

// Get PlanExe root directory
function getPlanExeRoot(): string {
  return path.resolve(process.cwd(), '..');
}

// Check if file/directory exists
async function checkPath(targetPath: string): Promise<boolean> {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

// Check LLM configuration
async function checkLLMConfig(): Promise<'up' | 'down'> {
  try {
    const planExeRoot = getPlanExeRoot();
    const configPath = path.join(planExeRoot, 'llm_config.json');
    
    if (await checkPath(configPath)) {
      const configContent = await fs.readFile(configPath, 'utf-8');
      const config = JSON.parse(configContent);
      
      // Check if any models are configured
      if (config.ollama_models?.length > 0 || config.openrouter_paid_models?.length > 0 || config.lmstudio_models?.length > 0) {
        return 'up';
      }
    }
    return 'down';
  } catch {
    return 'down';
  }
}

// Check Luigi pipeline
async function checkLuigiPipeline(): Promise<'up' | 'down'> {
  try {
    const planExeRoot = getPlanExeRoot();
    const pipelinePath = path.join(planExeRoot, 'planexe', 'plan', 'run_plan_pipeline.py');
    
    return (await checkPath(pipelinePath)) ? 'up' : 'down';
  } catch {
    return 'down';
  }
}

// Check file system (run directory)
async function checkFileSystem(): Promise<'up' | 'down'> {
  try {
    const planExeRoot = getPlanExeRoot();
    const runDir = path.join(planExeRoot, 'run');
    
    // Try to create run directory if it doesn't exist
    await fs.mkdir(runDir, { recursive: true });
    
    // Test write permissions
    const testFile = path.join(runDir, 'health_check_test.tmp');
    await fs.writeFile(testFile, 'test');
    await fs.unlink(testFile);
    
    return 'up';
  } catch {
    return 'down';
  }
}

// Check database (session storage simulation)
async function checkDatabase(): Promise<'up' | 'down'> {
  try {
    // For now, we're using localStorage, so always up if we can access process
    return typeof process !== 'undefined' ? 'up' : 'down';
  } catch {
    return 'down';
  }
}

// Get system metrics
async function getSystemMetrics(): Promise<{
  activePlans: number;
  totalPlans: number;
  avgPlanDuration: number;
  errorRate: number;
}> {
  try {
    const planExeRoot = getPlanExeRoot();
    const runDir = path.join(planExeRoot, 'run');
    
    // Count active and total plans
    let activePlans = 0;
    let totalPlans = 0;
    let totalDuration = 0;
    let completedPlans = 0;

    if (await checkPath(runDir)) {
      const runDirs = await fs.readdir(runDir);
      totalPlans = runDirs.length;

      for (const dir of runDirs) {
        const planDir = path.join(runDir, dir);
        const stats = await fs.stat(planDir);
        
        if (stats.isDirectory()) {
          // Check if plan is active
          const completeFile = path.join(planDir, '999-pipeline_complete.txt');
          const stopFile = path.join(planDir, 'pipeline_stop_requested.txt');
          
          if (!(await checkPath(completeFile)) && !(await checkPath(stopFile))) {
            activePlans++;
          } else if (await checkPath(completeFile)) {
            completedPlans++;
            
            // Calculate duration
            const startFile = path.join(planDir, '001-1-start_time.json');
            if (await checkPath(startFile)) {
              try {
                const startContent = await fs.readFile(startFile, 'utf-8');
                const startData = JSON.parse(startContent);
                const startTime = new Date(startData.server_iso_utc);
                const completeStats = await fs.stat(completeFile);
                const duration = (completeStats.mtime.getTime() - startTime.getTime()) / 1000 / 60; // minutes
                totalDuration += duration;
              } catch {
                // Ignore parsing errors
              }
            }
          }
        }
      }
    }

    const avgPlanDuration = completedPlans > 0 ? totalDuration / completedPlans : 0;
    const errorRate = 0; // TODO: Implement error tracking

    return {
      activePlans,
      totalPlans,
      avgPlanDuration: Math.round(avgPlanDuration),
      errorRate
    };
  } catch {
    return {
      activePlans: 0,
      totalPlans: 0,
      avgPlanDuration: 0,
      errorRate: 0
    };
  }
}

// GET /api/health - Health check
export async function GET(request: NextRequest): Promise<NextResponse> {
  try {
    const { searchParams } = new URL(request.url);
    const includeDetails = searchParams.get('includeDetails') === 'true';

    // Check all services
    const [database, fileSystem, llmModels, luigiScheduler] = await Promise.all([
      checkDatabase(),
      checkFileSystem(),
      checkLLMConfig(),
      checkLuigiPipeline()
    ]);

    const services = {
      database,
      fileSystem,
      llmModels: { 'default': llmModels },
      luigiScheduler
    };

    // Determine overall status
    const allServicesUp = Object.values(services).every(service => {
      return typeof service === 'string' ? service === 'up' : Object.values(service).every(s => s === 'up');
    });

    const status = allServicesUp ? 'healthy' : 'degraded';

    // Get metrics if requested
    let metrics;
    if (includeDetails) {
      metrics = await getSystemMetrics();
    }

    const response: HealthCheckResponse = {
      success: true,
      status,
      timestamp: new Date().toISOString(),
      version: '1.0.0',
      services: {
        database: services.database,
        fileSystem: services.fileSystem,
        llmModels: services.llmModels,
        luigiScheduler: services.luigiScheduler
      },
      ...(metrics && { metrics })
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('Health check error:', error);

    const apiError: APIError = {
      success: false,
      error: {
        code: 'HEALTH_CHECK_ERROR',
        message: error instanceof Error ? error.message : 'Health check failed',
        timestamp: new Date().toISOString(),
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}
