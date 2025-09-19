/**
 * Author: Cascade
 * Date: 2025-09-19T17:09:08-04:00
 * PURPOSE: API route for individual file downloads from Luigi pipeline output directory
 * SRP and DRY check: Pass - Single responsibility for file downloads, secure file access
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { APIError } from '@/lib/types/api';

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

// Check if file exists and is safe to access
async function validateFileAccess(filePath: string, runDir: string): Promise<boolean> {
  try {
    // Security check: ensure file is within run directory
    const resolvedPath = path.resolve(filePath);
    const resolvedRunDir = path.resolve(runDir);
    
    if (!resolvedPath.startsWith(resolvedRunDir)) {
      return false; // Path traversal attempt
    }

    // Check if file exists and is readable
    await fs.access(filePath, fs.constants.R_OK);
    const stats = await fs.stat(filePath);
    return stats.isFile();
  } catch {
    return false;
  }
}

// Get MIME type for file
function getMimeType(filename: string): string {
  const ext = path.extname(filename).toLowerCase();
  switch (ext) {
    case '.json':
      return 'application/json';
    case '.md':
      return 'text/markdown';
    case '.html':
      return 'text/html';
    case '.csv':
      return 'text/csv';
    case '.txt':
      return 'text/plain';
    default:
      return 'application/octet-stream';
  }
}

// GET /api/plans/[planId]/files/[filename] - Download file
export async function GET(
  request: NextRequest,
  { params }: { params: { planId: string; filename: string } }
): Promise<NextResponse> {
  try {
    const { planId, filename } = params;

    if (!planId || !filename) {
      const error: APIError = {
        success: false,
        error: {
          code: 'MISSING_PARAMETERS',
          message: 'Plan ID and filename are required',
          timestamp: new Date().toISOString(),
        },
      };
      return NextResponse.json(error, { status: 400 });
    }

    // Get run directory and file path
    const runDir = getRunDirectory(planId);
    const filePath = path.join(runDir, filename);

    // Validate file access
    if (!(await validateFileAccess(filePath, runDir))) {
      const error: APIError = {
        success: false,
        error: {
          code: 'FILE_NOT_FOUND',
          message: `File ${filename} not found or access denied`,
          timestamp: new Date().toISOString(),
        },
      };
      return NextResponse.json(error, { status: 404 });
    }

    // Read file
    const fileBuffer = await fs.readFile(filePath);
    const stats = await fs.stat(filePath);
    
    // Determine content type
    const mimeType = getMimeType(filename);
    
    // Create response headers
    const headers = new Headers({
      'Content-Type': mimeType,
      'Content-Length': stats.size.toString(),
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0'
    });

    return new NextResponse(fileBuffer, {
      status: 200,
      headers
    });

  } catch (error) {
    console.error('File download error:', error);

    const apiError: APIError = {
      success: false,
      error: {
        code: 'DOWNLOAD_ERROR',
        message: error instanceof Error ? error.message : 'Failed to download file',
        timestamp: new Date().toISOString(),
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}
