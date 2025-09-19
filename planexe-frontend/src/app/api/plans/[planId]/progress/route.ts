/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-19
 * PURPOSE: API route for detailed pipeline progress monitoring with task-level tracking
 * SRP and DRY check: Pass - Single responsibility for progress monitoring, respects Luigi file completion patterns
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import {
  GetProgressResponse,
  TaskProgressInfo,
  APIError,
  PipelineError
} from '@/lib/types/api';
import { PipelineProgress, PipelinePhase, LuigiTask } from '@/lib/types/pipeline';

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

// Check if file exists
async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

// Get file modification time
async function getFileModTime(filePath: string): Promise<Date | null> {
  try {
    const stats = await fs.stat(filePath);
    return stats.mtime;
  } catch {
    return null;
  }
}

// Luigi task definitions based on FilenameEnum patterns
const LUIGI_TASKS: Array<{
  filename: string;
  taskName: string;
  phase: PipelinePhase;
  dependencies: string[];
}> = [
  // Setup and Initial Analysis
  { filename: '001-1-start_time.json', taskName: 'StartTimeTask', phase: 'setup', dependencies: [] },
  { filename: '002-1-redline_gate_raw.json', taskName: 'RedlineGateTask', phase: 'initial_analysis', dependencies: ['StartTimeTask'] },
  { filename: '003-1-premise_attack_raw.json', taskName: 'PremiseAttackTask', phase: 'initial_analysis', dependencies: ['RedlineGateTask'] },
  { filename: '004-1-identify_purpose_raw.json', taskName: 'IdentifyPurposeTask', phase: 'initial_analysis', dependencies: ['PremiseAttackTask'] },
  { filename: '005-1-plan_type_raw.json', taskName: 'PlanTypeTask', phase: 'initial_analysis', dependencies: ['IdentifyPurposeTask'] },

  // Strategic Planning
  { filename: '006-1-potential_levers_raw.json', taskName: 'PotentialLeversTask', phase: 'strategic_planning', dependencies: ['PlanTypeTask'] },
  { filename: '007-1-deduplicate_levers_raw.json', taskName: 'DeduplicateLeversTask', phase: 'strategic_planning', dependencies: ['PotentialLeversTask'] },
  { filename: '008-1-enriched_levers_raw.json', taskName: 'EnrichLeversTask', phase: 'strategic_planning', dependencies: ['DeduplicateLeversTask'] },
  { filename: '009-1-focus_vital_few_levers_raw.json', taskName: 'FocusOnVitalFewLeversTask', phase: 'strategic_planning', dependencies: ['EnrichLeversTask'] },
  { filename: '010-1-strategic_decisions.md', taskName: 'StrategicDecisionsMarkdownTask', phase: 'strategic_planning', dependencies: ['FocusOnVitalFewLeversTask'] },

  // Scenario Planning
  { filename: '011-1-candidate_scenarios_raw.json', taskName: 'CandidateScenariosTask', phase: 'scenario_planning', dependencies: ['StrategicDecisionsMarkdownTask'] },
  { filename: '012-1-select_scenario_raw.json', taskName: 'SelectScenarioTask', phase: 'scenario_planning', dependencies: ['CandidateScenariosTask'] },
  { filename: '013-1-scenarios.md', taskName: 'ScenariosMarkdownTask', phase: 'scenario_planning', dependencies: ['SelectScenarioTask'] },

  // Contextual Analysis
  { filename: '014-1-physical_locations_raw.json', taskName: 'PhysicalLocationsTask', phase: 'contextual_analysis', dependencies: ['ScenariosMarkdownTask'] },
  { filename: '015-1-currency_strategy_raw.json', taskName: 'CurrencyStrategyTask', phase: 'contextual_analysis', dependencies: ['PhysicalLocationsTask'] },
  { filename: '016-1-identify_risks_raw.json', taskName: 'IdentifyRisksTask', phase: 'contextual_analysis', dependencies: ['CurrencyStrategyTask'] },

  // Assumption Management
  { filename: '017-1-make_assumptions_raw.json', taskName: 'MakeAssumptionsTask', phase: 'assumption_management', dependencies: ['IdentifyRisksTask'] },
  { filename: '018-1-distill_assumptions_raw.json', taskName: 'DistillAssumptionsTask', phase: 'assumption_management', dependencies: ['MakeAssumptionsTask'] },
  { filename: '019-1-review_assumptions_raw.json', taskName: 'ReviewAssumptionsTask', phase: 'assumption_management', dependencies: ['DistillAssumptionsTask'] },
  { filename: '020-1-consolidate_assumptions_full.md', taskName: 'ConsolidateAssumptionsMarkdownTask', phase: 'assumption_management', dependencies: ['ReviewAssumptionsTask'] },

  // Project Planning
  { filename: '021-1-pre_project_assessment_raw.json', taskName: 'PreProjectAssessmentTask', phase: 'project_planning', dependencies: ['ConsolidateAssumptionsMarkdownTask'] },
  { filename: '022-1-project_plan_raw.json', taskName: 'ProjectPlanTask', phase: 'project_planning', dependencies: ['PreProjectAssessmentTask'] },

  // Governance (simplified representation)
  { filename: '023-1-governance_phase1_audit_raw.json', taskName: 'GovernancePhase1AuditTask', phase: 'governance', dependencies: ['ProjectPlanTask'] },
  { filename: '024-1-governance_phase2_bodies_raw.json', taskName: 'GovernancePhase2BodiesTask', phase: 'governance', dependencies: ['GovernancePhase1AuditTask'] },
  { filename: '025-1-consolidate_governance.md', taskName: 'ConsolidateGovernanceTask', phase: 'governance', dependencies: ['GovernancePhase2BodiesTask'] },

  // Resource Planning
  { filename: '026-1-related_resources_raw.json', taskName: 'RelatedResourcesTask', phase: 'resource_planning', dependencies: ['ConsolidateGovernanceTask'] },
  { filename: '027-1-find_team_members_raw.json', taskName: 'FindTeamMembersTask', phase: 'resource_planning', dependencies: ['RelatedResourcesTask'] },
  { filename: '028-1-team.md', taskName: 'TeamMarkdownTask', phase: 'resource_planning', dependencies: ['FindTeamMembersTask'] },
  { filename: '029-1-swot_raw.json', taskName: 'SWOTAnalysisTask', phase: 'resource_planning', dependencies: ['TeamMarkdownTask'] },
  { filename: '030-1-expert_criticism.md', taskName: 'ExpertReviewTask', phase: 'resource_planning', dependencies: ['SWOTAnalysisTask'] },

  // Documentation
  { filename: '031-1-data_collection_raw.json', taskName: 'DataCollectionTask', phase: 'documentation', dependencies: ['ExpertReviewTask'] },
  { filename: '032-1-identified_documents_raw.json', taskName: 'IdentifyDocumentsTask', phase: 'documentation', dependencies: ['DataCollectionTask'] },
  { filename: '033-1-documents_to_create_and_find.md', taskName: 'MarkdownWithDocumentsToCreateAndFindTask', phase: 'documentation', dependencies: ['IdentifyDocumentsTask'] },

  // Work Breakdown Structure
  { filename: '034-1-wbs_level1_raw.json', taskName: 'CreateWBSLevel1Task', phase: 'work_breakdown', dependencies: ['MarkdownWithDocumentsToCreateAndFindTask'] },
  { filename: '035-1-wbs_level2_raw.json', taskName: 'CreateWBSLevel2Task', phase: 'work_breakdown', dependencies: ['CreateWBSLevel1Task'] },
  { filename: '036-1-task_dependencies_raw.json', taskName: 'IdentifyTaskDependenciesTask', phase: 'work_breakdown', dependencies: ['CreateWBSLevel2Task'] },
  { filename: '037-1-task_durations.json', taskName: 'EstimateTaskDurationsTask', phase: 'work_breakdown', dependencies: ['IdentifyTaskDependenciesTask'] },
  { filename: '038-1-wbs_level3.json', taskName: 'CreateWBSLevel3Task', phase: 'work_breakdown', dependencies: ['EstimateTaskDurationsTask'] },
  { filename: '039-1-wbs_project123_full.json', taskName: 'WBSProjectLevel1AndLevel2AndLevel3Task', phase: 'work_breakdown', dependencies: ['CreateWBSLevel3Task'] },

  // Scheduling
  { filename: '040-1-schedule_gantt_dhtmlx.html', taskName: 'CreateScheduleTask', phase: 'scheduling', dependencies: ['WBSProjectLevel1AndLevel2AndLevel3Task'] },
  { filename: '041-1-pitch_raw.json', taskName: 'CreatePitchTask', phase: 'scheduling', dependencies: ['CreateScheduleTask'] },
  { filename: '042-1-pitch.md', taskName: 'ConvertPitchToMarkdownTask', phase: 'scheduling', dependencies: ['CreatePitchTask'] },

  // Reporting
  { filename: '043-1-review_plan_raw.json', taskName: 'ReviewPlanTask', phase: 'reporting', dependencies: ['ConvertPitchToMarkdownTask'] },
  { filename: '044-1-executive_summary_raw.json', taskName: 'ExecutiveSummaryTask', phase: 'reporting', dependencies: ['ReviewPlanTask'] },
  { filename: '045-1-questions_and_answers_raw.json', taskName: 'QuestionsAndAnswersTask', phase: 'reporting', dependencies: ['ExecutiveSummaryTask'] },
  { filename: '046-1-premortem_raw.json', taskName: 'PremortemTask', phase: 'reporting', dependencies: ['QuestionsAndAnswersTask'] },
  { filename: '047-1-report.html', taskName: 'ReportTask', phase: 'reporting', dependencies: ['PremortemTask'] },

  // Completion
  { filename: '999-pipeline_complete.txt', taskName: 'FullPlanPipeline', phase: 'completion', dependencies: ['ReportTask'] },
];

// Get detailed progress information
async function getDetailedProgress(runDir: string, planId: string): Promise<{
  progress: PipelineProgress;
  recentTasks: TaskProgressInfo[];
  nextTasks: TaskProgressInfo[];
}> {
  const runId = extractRunId(planId);

  // Check which files exist and get their timestamps
  const taskStatuses: Map<string, {
    status: 'pending' | 'running' | 'completed' | 'failed';
    startTime?: Date;
    endTime?: Date;
    duration?: number;
  }> = new Map();

  for (const task of LUIGI_TASKS) {
    const filePath = path.join(runDir, task.filename);
    const exists = await fileExists(filePath);

    if (exists) {
      const modTime = await getFileModTime(filePath);
      taskStatuses.set(task.taskName, {
        status: 'completed',
        endTime: modTime || undefined,
        duration: 0, // Would need more sophisticated tracking for actual duration
      });
    } else {
      // Check if dependencies are completed to determine if task should be running
      const depsCompleted = task.dependencies.every(dep => taskStatuses.get(dep)?.status === 'completed');
      taskStatuses.set(task.taskName, {
        status: depsCompleted ? 'pending' : 'pending',
      });
    }
  }

  // Calculate overall progress
  const completedTasks = Array.from(taskStatuses.values()).filter(t => t.status === 'completed').length;
  const totalTasks = LUIGI_TASKS.length;
  const progressPercentage = Math.round((completedTasks / totalTasks) * 100);

  // Determine current phase
  let currentPhase: PipelinePhase = 'setup';
  for (let i = LUIGI_TASKS.length - 1; i >= 0; i--) {
    const task = LUIGI_TASKS[i];
    if (taskStatuses.get(task.taskName)?.status === 'completed') {
      currentPhase = task.phase;
      break;
    }
  }

  // Calculate duration
  const startTimeFile = path.join(runDir, '001-1-start_time.json');
  let duration = 0;
  let startTime: Date | null = null;

  if (await fileExists(startTimeFile)) {
    try {
      const startTimeContent = await fs.readFile(startTimeFile, 'utf-8');
      const startTimeData = JSON.parse(startTimeContent);
      startTime = new Date(startTimeData.server_iso_utc);
      duration = Math.round((Date.now() - startTime.getTime()) / 1000);
    } catch {
      // Ignore parsing errors
    }
  }

  // Determine overall status
  let status: 'created' | 'running' | 'completed' | 'failed' | 'stopped' = 'created';

  if (await fileExists(path.join(runDir, '999-pipeline_complete.txt'))) {
    status = 'completed';
  } else if (await fileExists(path.join(runDir, 'pipeline_stop_requested.txt'))) {
    status = 'stopped';
  } else if (startTime) {
    status = 'running';
  }

  const progress: PipelineProgress = {
    planId,
    runId,
    status,
    progressPercentage,
    progressMessage: `${completedTasks} of ${totalTasks} tasks completed`,
    filesCompleted: completedTasks,
    totalExpectedFiles: totalTasks,
    currentPhase,
    duration,
    errors: [], // TODO: Parse log file for errors
    lastUpdated: new Date(),
  };

  // Get recent completed tasks (last 5)
  const recentTasks: TaskProgressInfo[] = LUIGI_TASKS
    .filter(task => taskStatuses.get(task.taskName)?.status === 'completed')
    .slice(-5)
    .map(task => {
      const taskStatus = taskStatuses.get(task.taskName)!;
      return {
        taskId: task.taskName,
        taskName: task.taskName,
        status: taskStatus.status,
        endTime: taskStatus.endTime?.toISOString(),
        duration: taskStatus.duration,
        progress: 100,
      };
    });

  // Get next pending tasks (next 5)
  const nextTasks: TaskProgressInfo[] = LUIGI_TASKS
    .filter(task => taskStatuses.get(task.taskName)?.status === 'pending')
    .slice(0, 5)
    .map(task => {
      const taskStatus = taskStatuses.get(task.taskName)!;
      return {
        taskId: task.taskName,
        taskName: task.taskName,
        status: taskStatus.status,
        progress: 0,
      };
    });

  return { progress, recentTasks, nextTasks };
}

// GET /api/plans/[planId]/progress - Get detailed progress
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

    // Check if directory exists
    try {
      await fs.access(runDir);
    } catch {
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

    // Get detailed progress
    const { progress, recentTasks, nextTasks } = await getDetailedProgress(runDir, planId);

    const response: GetProgressResponse = {
      success: true,
      planId,
      progress,
      recentTasks,
      nextTasks,
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('Progress monitoring error:', error);

    const apiError: PipelineError = {
      success: false,
      error: {
        code: 'PIPELINE_ERROR',
        message: error instanceof Error ? error.message : 'Failed to get progress',
        timestamp: new Date().toISOString(),
        retryable: true,
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}