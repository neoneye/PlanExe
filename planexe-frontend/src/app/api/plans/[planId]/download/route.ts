/**
 * Author: Cascade
 * Date: 2025-09-19T17:09:08-04:00
 * PURPOSE: API route for ZIP archive download of all Luigi pipeline output files
 * SRP and DRY check: Pass - Single responsibility for ZIP creation and download
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import { APIError } from '@/lib/types/api';

const execAsync = promisify(exec);

// Get PlanExe root directory
function getPlanExeRoot(): string {
  return path.resolve(process.cwd(), '..');
}

// Extract run ID from plan ID
function extractRunId(planId: string): string {
  return planId.replace('plan_', '');
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

// Create ZIP archive using native tools
async function createZipArchive(sourceDir: string, outputPath: string): Promise<void> {
  try {
    // Use PowerShell on Windows to create ZIP archive
    const powershellCommand = `Compress-Archive -Path "${sourceDir}\\*" -DestinationPath "${outputPath}" -Force`;
    
    await execAsync(powershellCommand, { shell: 'powershell.exe' });
  } catch (error) {
    console.error('ZIP creation failed:', error);
    throw new Error('Failed to create ZIP archive');
  }
}

// Clean up old ZIP files (older than 1 hour)
async function cleanupOldZips(tempDir: string): Promise<void> {
  try {
    const files = await fs.readdir(tempDir);
    const oneHourAgo = Date.now() - (60 * 60 * 1000);

    for (const file of files) {
      if (file.endsWith('.zip')) {
        const filePath = path.join(tempDir, file);
        const stats = await fs.stat(filePath);
        
        if (stats.mtime.getTime() < oneHourAgo) {
          await fs.unlink(filePath);
        }
      }
    }
  } catch (error) {
    console.error('Cleanup failed:', error);
    // Don't throw - cleanup is best effort
  }
}

// GET /api/plans/[planId]/download - Download ZIP archive
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

    // Create temporary directory for ZIP files
    const tempDir = path.join(getPlanExeRoot(), 'temp');
    await fs.mkdir(tempDir, { recursive: true });

    // Clean up old ZIP files
    await cleanupOldZips(tempDir);

    // Generate ZIP filename
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const zipFilename = `plan-${planId}-${timestamp}.zip`;
    const zipPath = path.join(tempDir, zipFilename);

    // Create ZIP archive
    await createZipArchive(runDir, zipPath);

    // Check if ZIP was created successfully
    const zipStats = await fs.stat(zipPath);
    if (!zipStats.isFile()) {
      throw new Error('ZIP file was not created successfully');
    }

    // Read ZIP file
    const zipBuffer = await fs.readFile(zipPath);
    
    // Create response headers
    const headers = new Headers({
      'Content-Type': 'application/zip',
      'Content-Length': zipStats.size.toString(),
      'Content-Disposition': `attachment; filename="plan-${planId}-files.zip"`,
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0'
    });

    // Schedule cleanup of ZIP file (don't await)
    setTimeout(async () => {
      try {
        await fs.unlink(zipPath);
      } catch (error) {
        console.error('Failed to cleanup ZIP file:', error);
      }
    }, 60000); // Delete after 1 minute

    return new NextResponse(zipBuffer, {
      status: 200,
      headers
    });

  } catch (error) {
    console.error('ZIP download error:', error);

    const apiError: APIError = {
      success: false,
      error: {
        code: 'DOWNLOAD_ERROR',
        message: error instanceof Error ? error.message : 'Failed to create ZIP archive',
        timestamp: new Date().toISOString(),
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}
