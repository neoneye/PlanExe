/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-26
 * PURPOSE: Extract and map the real 61 Luigi tasks from LUIGI.md dependency chain
 * SRP and DRY check: Pass - Single responsibility for Luigi task data extraction
 */

import { TaskPhase } from '@/lib/types/pipeline';

// Real Luigi tasks extracted from docs/LUIGI.md dependency chain
export const LUIGI_TASKS = [
  // Phase 1: Pipeline Setup
  'StartTimeTask',
  'SetupTask',

  // Phase 2: Initial Analysis
  'RedlineGateTask',
  'PremiseAttackTask',
  'IdentifyPurposeTask',

  // Phase 3: Strategic Foundation
  'MakeAssumptionsTask',
  'DistillAssumptionsTask',
  'ReviewAssumptionsTask',
  'IdentifyRisksTask',
  'RiskMatrixTask',
  'RiskMitigationPlanTask',
  'CurrencyStrategyTask',
  'PhysicalLocationsTask',

  // Phase 4: Strategic Planning
  'StrategicDecisionsMarkdownTask',
  'ScenariosMarkdownTask',
  'ExpertFinder',
  'ExpertCriticism',
  'ExpertOrchestrator',

  // Phase 5: Work Breakdown Structure
  'CreateWBSLevel1',
  'CreateWBSLevel2',
  'CreateWBSLevel3',
  'IdentifyWBSTaskDependencies',
  'EstimateWBSTaskDurations',
  'WBSPopulate',
  'WBSTaskTooltip',
  'WBSTask',
  'WBSProject',

  // Phase 6: Scheduling & Exports
  'ProjectSchedulePopulator',
  'ProjectSchedule',
  'ExportGanttDHTMLX',
  'ExportGanttCSV',
  'ExportGanttMermaid',

  // Phase 7: Team Planning
  'FindTeamMembers',
  'EnrichTeamMembersWithContractType',
  'EnrichTeamMembersWithBackgroundStory',
  'EnrichTeamMembersWithEnvironmentInfo',
  'TeamMarkdownDocumentBuilder',
  'ReviewTeam',

  // Phase 8: Project Documents
  'CreatePitch',
  'ConvertPitchToMarkdown',
  'ExecutiveSummary',
  'ReviewPlan',
  'ReportGenerator',

  // Phase 9: Governance
  'GovernancePhase1AuditTask',
  'GovernancePhase2InternalBodiesTask',
  'GovernancePhase3ImplementationPlanTask',
  'GovernancePhase4DecisionMatrixTask',
  'GovernancePhase5MonitoringTask',
  'GovernancePhase6ExtraTask',
  'ConsolidateGovernanceTask',

  // Phase 10: Data & Environment
  'DataCollection',
  'ObtainOutputFiles',
  'PipelineEnvironment',
  'LLMExecutor',

  // Phase 11: WBS Exports
  'WBSJSONExporter',
  'WBSDotExporter',
  'WBSPNGExporter',
  'WBSPDFExporter',

  // Phase 12: Financial Planning
  'BudgetEstimationTask',
  'CashflowProjectionTask',

  // Phase 13: Final Assembly
  'FinalReportAssembler'
];

// Convert task names to user-friendly display names
export const getTaskDisplayName = (taskId: string): string => {
  const nameMap: Record<string, string> = {
    'StartTimeTask': 'Initialize Pipeline',
    'SetupTask': 'Setup Environment',
    'RedlineGateTask': 'Safety & Quality Check',
    'PremiseAttackTask': 'Challenge Plan Premise',
    'IdentifyPurposeTask': 'Identify Plan Purpose',
    'MakeAssumptionsTask': 'Define Key Assumptions',
    'DistillAssumptionsTask': 'Refine Assumptions',
    'ReviewAssumptionsTask': 'Review Assumptions',
    'IdentifyRisksTask': 'Identify Risks',
    'RiskMatrixTask': 'Create Risk Matrix',
    'RiskMitigationPlanTask': 'Plan Risk Mitigation',
    'CurrencyStrategyTask': 'Define Currency Strategy',
    'PhysicalLocationsTask': 'Identify Physical Locations',
    'StrategicDecisionsMarkdownTask': 'Document Strategic Decisions',
    'ScenariosMarkdownTask': 'Document Scenarios',
    'ExpertFinder': 'Find Domain Experts',
    'ExpertCriticism': 'Expert Review & Criticism',
    'ExpertOrchestrator': 'Orchestrate Expert Feedback',
    'CreateWBSLevel1': 'Create Work Breakdown (Level 1)',
    'CreateWBSLevel2': 'Create Work Breakdown (Level 2)',
    'CreateWBSLevel3': 'Create Work Breakdown (Level 3)',
    'IdentifyWBSTaskDependencies': 'Identify Task Dependencies',
    'EstimateWBSTaskDurations': 'Estimate Task Durations',
    'WBSPopulate': 'Populate WBS Data',
    'WBSTaskTooltip': 'Add WBS Tooltips',
    'WBSTask': 'Finalize WBS Tasks',
    'WBSProject': 'Assemble WBS Project',
    'ProjectSchedulePopulator': 'Populate Project Schedule',
    'ProjectSchedule': 'Generate Project Schedule',
    'ExportGanttDHTMLX': 'Export Gantt Chart (DHTMLX)',
    'ExportGanttCSV': 'Export Gantt Chart (CSV)',
    'ExportGanttMermaid': 'Export Gantt Chart (Mermaid)',
    'FindTeamMembers': 'Identify Team Members',
    'EnrichTeamMembersWithContractType': 'Define Contract Types',
    'EnrichTeamMembersWithBackgroundStory': 'Create Team Backgrounds',
    'EnrichTeamMembersWithEnvironmentInfo': 'Define Team Environment',
    'TeamMarkdownDocumentBuilder': 'Build Team Document',
    'ReviewTeam': 'Review Team Structure',
    'CreatePitch': 'Generate Project Pitch',
    'ConvertPitchToMarkdown': 'Format Project Pitch',
    'ExecutiveSummary': 'Generate Executive Summary',
    'ReviewPlan': 'Final Plan Review',
    'ReportGenerator': 'Generate Report',
    'GovernancePhase1AuditTask': 'Governance Audit',
    'GovernancePhase2InternalBodiesTask': 'Design Governance Bodies',
    'GovernancePhase3ImplementationPlanTask': 'Governance Implementation Plan',
    'GovernancePhase4DecisionMatrixTask': 'Decision Escalation Matrix',
    'GovernancePhase5MonitoringTask': 'Progress Monitoring Rules',
    'GovernancePhase6ExtraTask': 'Additional Governance',
    'ConsolidateGovernanceTask': 'Consolidate Governance',
    'DataCollection': 'Define Data Collection',
    'ObtainOutputFiles': 'Obtain Output Files',
    'PipelineEnvironment': 'Setup Pipeline Environment',
    'LLMExecutor': 'Execute LLM Tasks',
    'WBSJSONExporter': 'Export WBS (JSON)',
    'WBSDotExporter': 'Export WBS (DOT)',
    'WBSPNGExporter': 'Export WBS (PNG)',
    'WBSPDFExporter': 'Export WBS (PDF)',
    'BudgetEstimationTask': 'Estimate Budget',
    'CashflowProjectionTask': 'Project Cashflow',
    'FinalReportAssembler': 'Assemble Final Report'
  };

  return nameMap[taskId] || taskId;
};

// Organize tasks into logical phases for the accordion display
export const createLuigiTaskPhases = (): TaskPhase[] => {
  const phases = [
    {
      name: 'Phase 1: Pipeline Setup',
      taskIds: ['StartTimeTask', 'SetupTask']
    },
    {
      name: 'Phase 2: Initial Analysis',
      taskIds: ['RedlineGateTask', 'PremiseAttackTask', 'IdentifyPurposeTask']
    },
    {
      name: 'Phase 3: Strategic Foundation',
      taskIds: [
        'MakeAssumptionsTask', 'DistillAssumptionsTask', 'ReviewAssumptionsTask',
        'IdentifyRisksTask', 'RiskMatrixTask', 'RiskMitigationPlanTask',
        'CurrencyStrategyTask', 'PhysicalLocationsTask'
      ]
    },
    {
      name: 'Phase 4: Strategic Planning',
      taskIds: [
        'StrategicDecisionsMarkdownTask', 'ScenariosMarkdownTask',
        'ExpertFinder', 'ExpertCriticism', 'ExpertOrchestrator'
      ]
    },
    {
      name: 'Phase 5: Work Breakdown Structure',
      taskIds: [
        'CreateWBSLevel1', 'CreateWBSLevel2', 'CreateWBSLevel3',
        'IdentifyWBSTaskDependencies', 'EstimateWBSTaskDurations',
        'WBSPopulate', 'WBSTaskTooltip', 'WBSTask', 'WBSProject'
      ]
    },
    {
      name: 'Phase 6: Scheduling & Exports',
      taskIds: [
        'ProjectSchedulePopulator', 'ProjectSchedule',
        'ExportGanttDHTMLX', 'ExportGanttCSV', 'ExportGanttMermaid'
      ]
    },
    {
      name: 'Phase 7: Team Planning',
      taskIds: [
        'FindTeamMembers', 'EnrichTeamMembersWithContractType',
        'EnrichTeamMembersWithBackgroundStory', 'EnrichTeamMembersWithEnvironmentInfo',
        'TeamMarkdownDocumentBuilder', 'ReviewTeam'
      ]
    },
    {
      name: 'Phase 8: Project Documents',
      taskIds: [
        'CreatePitch', 'ConvertPitchToMarkdown',
        'ExecutiveSummary', 'ReviewPlan', 'ReportGenerator'
      ]
    },
    {
      name: 'Phase 9: Governance Framework',
      taskIds: [
        'GovernancePhase1AuditTask', 'GovernancePhase2InternalBodiesTask',
        'GovernancePhase3ImplementationPlanTask', 'GovernancePhase4DecisionMatrixTask',
        'GovernancePhase5MonitoringTask', 'GovernancePhase6ExtraTask',
        'ConsolidateGovernanceTask'
      ]
    },
    {
      name: 'Phase 10: Data & Environment',
      taskIds: ['DataCollection', 'ObtainOutputFiles', 'PipelineEnvironment', 'LLMExecutor']
    },
    {
      name: 'Phase 11: WBS Exports',
      taskIds: ['WBSJSONExporter', 'WBSDotExporter', 'WBSPNGExporter', 'WBSPDFExporter']
    },
    {
      name: 'Phase 12: Financial Planning',
      taskIds: ['BudgetEstimationTask', 'CashflowProjectionTask']
    },
    {
      name: 'Phase 13: Final Assembly',
      taskIds: ['FinalReportAssembler']
    }
  ];

  return phases.map(phase => ({
    name: phase.name,
    tasks: phase.taskIds.map(taskId => ({
      id: taskId,
      name: getTaskDisplayName(taskId),
      status: 'pending' as const
    })),
    completedTasks: 0,
    totalTasks: phase.taskIds.length
  }));
};