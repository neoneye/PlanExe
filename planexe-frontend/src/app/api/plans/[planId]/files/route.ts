/**
 * Author: Cascade
 * Date: 2025-09-19T17:09:08-04:00
 * PURPOSE: API route for file management operations - lists and downloads Luigi pipeline output files
 * SRP and DRY check: Pass - Single responsibility for file operations, respects Luigi FilenameEnum patterns
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import {
  GetFilesResponse,
  DownloadFileResponse,
  APIError,
  PipelineError
} from '@/lib/types/api';
import { PlanFile, PipelinePhase } from '@/lib/types/pipeline';

// Get PlanExe root directory
function getPlanExeRoot(): string {
  return path.resolve(process.cwd(), '..');
}

// Extract run ID from plan ID
function extractRunId(planId: string): string {
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

// Map filename to pipeline phase based on FilenameEnum patterns
function getFilePhase(filename: string): PipelinePhase {
  const num = filename.match(/^(\d+)/)?.[1];
  if (!num) return 'setup';
  
  const fileNum = parseInt(num);
  
  if (fileNum <= 5) return 'initial_analysis';
  if (fileNum <= 13) return 'strategic_planning';
  if (fileNum <= 16) return 'contextual_analysis';  
  if (fileNum <= 22) return 'project_planning';
  if (fileNum <= 25) return 'governance';
  if (fileNum <= 33) return 'resource_planning';
  if (fileNum <= 39) return 'work_breakdown';
  if (fileNum <= 42) return 'scheduling';
  if (fileNum <= 47) return 'reporting';
  return 'completion';
}

// Get task name from filename
function getTaskName(filename: string): string {
  // Map common filename patterns to readable task names
  const taskMappings: Record<string, string> = {
    'start_time': 'Pipeline Startup',
    'redline_gate': 'Content Safety Check',
    'premise_attack': 'Assumption Validation',
    'identify_purpose': 'Purpose Analysis',
    'plan_type': 'Plan Type Detection',
    'potential_levers': 'Strategic Levers Identification',
    'deduplicate_levers': 'Strategic Levers Deduplication',
    'enriched_levers': 'Strategic Levers Enrichment',
    'focus_vital_few': 'Vital Few Focus',
    'strategic_decisions': 'Strategic Decisions Summary',
    'candidate_scenarios': 'Scenario Generation',
    'select_scenario': 'Scenario Selection',
    'scenarios': 'Scenario Planning',
    'physical_locations': 'Location Analysis',
    'currency_strategy': 'Currency Strategy',
    'identify_risks': 'Risk Identification',
    'make_assumptions': 'Assumptions Creation',
    'distill_assumptions': 'Assumptions Distillation',
    'review_assumptions': 'Assumptions Review',
    'consolidate_assumptions': 'Assumptions Consolidation',
    'pre_project_assessment': 'Pre-Project Assessment',
    'project_plan': 'Project Planning',
    'governance': 'Governance Framework',
    'related_resources': 'Resource Research',
    'find_team_members': 'Team Planning',
    'team': 'Team Structure',
    'swot': 'SWOT Analysis',
    'expert_criticism': 'Expert Review',
    'data_collection': 'Data Requirements',
    'identified_documents': 'Document Planning',
    'documents_to_create_and_find': 'Document Strategy',
    'wbs_level1': 'WBS Level 1',
    'wbs_level2': 'WBS Level 2', 
    'wbs_level3': 'WBS Level 3',
    'task_dependencies': 'Task Dependencies',
    'task_durations': 'Duration Estimation',
    'wbs_project': 'Complete WBS',
    'schedule_gantt': 'Schedule Generation',
    'pitch': 'Project Pitch',
    'review_plan': 'Plan Review',
    'executive_summary': 'Executive Summary',
    'questions_and_answers': 'Q&A Generation',
    'premortem': 'Premortem Analysis',
    'report': 'Final Report',
    'pipeline_complete': 'Pipeline Completion'
  };

  // Find matching task name
  for (const [key, taskName] of Object.entries(taskMappings)) {
    if (filename.toLowerCase().includes(key)) {
      return taskName;
    }
  }

  return filename.replace(/^\d+-\d+-/, '').replace(/\.(json|md|html|csv|txt)$/, '');
}

// Get file description
function getFileDescription(filename: string): string {
  const taskName = getTaskName(filename);
  const fileType = path.extname(filename).substring(1).toLowerCase();
  
  switch (fileType) {
    case 'json':
      return `${taskName} - Raw data output`;
    case 'md':
      return `${taskName} - Formatted report`;
    case 'html':
      return `${taskName} - Interactive report`;
    case 'csv':
      return `${taskName} - Tabular data`;
    case 'txt':
      return `${taskName} - Plain text output`;
    default:
      return taskName;
  }
}

// List all files in run directory
async function listPlanFiles(runDir: string, planId: string): Promise<PlanFile[]> {
  try {
    const files = await fs.readdir(runDir);
    const planFiles: PlanFile[] = [];

    for (const filename of files) {
      // Skip directories and non-output files
      if (filename.startsWith('.') || filename === 'log.txt') {
        continue;
      }

      const filePath = path.join(runDir, filename);
      const stats = await fs.stat(filePath);
      
      if (stats.isFile()) {
        const fileType = path.extname(filename).substring(1).toLowerCase();
        
        // Only include recognized output files
        if (['json', 'md', 'html', 'csv', 'txt'].includes(fileType)) {
          const planFile: PlanFile = {
            filename,
            relativePath: filename,
            absolutePath: filePath,
            size: stats.size,
            type: fileType as 'json' | 'md' | 'html' | 'csv' | 'txt',
            stage: getFilePhase(filename),
            taskName: getTaskName(filename),
            outputType: filename.includes('_raw') ? 'raw' : 'clean',
            lastModified: stats.mtime,
            isRequired: filename.includes('001-') || filename.includes('999-'),
            description: getFileDescription(filename)
          };
          
          planFiles.push(planFile);
        }
      }
    }

    // Sort files by number prefix
    planFiles.sort((a, b) => {
      const aNum = parseInt(a.filename.match(/^(\d+)/)?.[1] || '999');
      const bNum = parseInt(b.filename.match(/^(\d+)/)?.[1] || '999');
      return aNum - bNum;
    });

    return planFiles;
  } catch (error) {
    console.error('Error listing files:', error);
    throw new Error('Failed to list plan files');
  }
}

// GET /api/plans/[planId]/files - List all files
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

    // List all files
    const files = await listPlanFiles(runDir, planId);
    
    // Group files by phase
    const phases: Record<PipelinePhase, PlanFile[]> = {} as Record<PipelinePhase, PlanFile[]>;
    files.forEach(file => {
      if (!phases[file.stage]) {
        phases[file.stage] = [];
      }
      phases[file.stage].push(file);
    });

    // Calculate total size
    const totalSize = files.reduce((sum, file) => sum + file.size, 0);

    const response: GetFilesResponse = {
      success: true,
      planId,
      files: {
        planId,
        files,
        phases,
        totalSize,
        lastUpdated: new Date()
      }
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('Files listing error:', error);

    const apiError: PipelineError = {
      success: false,
      error: {
        code: 'PIPELINE_ERROR',
        message: error instanceof Error ? error.message : 'Failed to list files',
        timestamp: new Date().toISOString(),
        retryable: true,
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}

// GET /api/plans/[planId]/files/[filename] - Download specific file (handled by dynamic route)
// This will be handled by /api/plans/[planId]/files/[filename]/route.ts
