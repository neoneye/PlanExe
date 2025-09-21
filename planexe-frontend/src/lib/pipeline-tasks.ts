/**
 * Author: Cascade
 * Date: 2025-09-21T11:41:06-04:00
 * PURPOSE: Provides mappings and groupings for the 61 Luigi pipeline tasks to support a user-friendly progress display.
 * This file decouples the frontend's presentation layer from the backend's technical task names.
 * SRP and DRY check: Pass - This file has a single responsibility: to define and provide data related to pipeline task presentation. It avoids duplicating this information across multiple components.
 */

// Represents the status of an individual task in the pipeline
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed';

// Interface for a single pipeline task's state
export interface PipelineTask {
  id: string; // The technical task name, e.g., 'IdentifyPurposeTask'
  name: string; // The user-friendly name, e.g., 'Identifying Plan Purpose'
  status: TaskStatus;
}

// Interface for a logical grouping of tasks
export interface TaskPhase {
  name: string; // The name of the phase, e.g., 'I. Plan Initiation & Validation'
  tasks: PipelineTask[];
}

// Mapping from technical Luigi task names to user-friendly descriptions
export const taskNameMapping: Record<string, string> = {
  StartTimeTask: 'Pipeline Initiated',
  SetupTask: 'Setting Up Plan Environment',
  RedlineGateTask: 'Performing Safety & Quality Check',
  PremiseAttackTask: 'Challenging Plan Premise',
  IdentifyPurposeTask: 'Identifying Plan Purpose',
  PlanTypeTask: 'Determining Plan Type (Digital/Physical)',
  PotentialLeversTask: 'Identifying Strategic Levers',
  DeduplicateLeversTask: 'Cleaning Up Strategic Levers',
  EnrichLeversTask: 'Adding Detail to Levers',
  FocusOnVitalFewLeversTask: 'Focusing on Vital Levers (80/20 Rule)',
  StrategicDecisionsMarkdownTask: 'Summarizing Strategic Decisions',
  CandidateScenariosTask: 'Generating Strategic Scenarios',
  SelectScenarioTask: 'Selecting Best-Fit Scenario',
  ScenariosMarkdownTask: 'Summarizing Scenarios',
  PhysicalLocationsTask: 'Identifying Physical Locations',
  CurrencyStrategyTask: 'Defining Currency Strategy',
  IdentifyRisksTask: 'Identifying Potential Risks',
  MakeAssumptionsTask: 'Defining Key Assumptions',
  DistillAssumptionsTask: 'Refining Key Assumptions',
  ReviewAssumptionsTask: 'Reviewing & Critiquing Assumptions',
  ConsolidateAssumptionsMarkdownTask: 'Consolidating Assumptions Document',
  PreProjectAssessmentTask: 'Conducting Pre-Project Assessment',
  ProjectPlanTask: 'Generating Initial Project Plan',
  GovernancePhase1AuditTask: 'Developing Governance Audit Plan',
  GovernancePhase2BodiesTask: 'Designing Governance Bodies',
  GovernancePhase3ImplPlanTask: 'Creating Governance Implementation Plan',
  GovernancePhase4DecisionEscalationMatrixTask: 'Building Decision Escalation Matrix',
  GovernancePhase5MonitoringProgressTask: 'Defining Progress Monitoring Rules',
  GovernancePhase6ExtraTask: 'Adding Extra Governance Details',
  ConsolidateGovernanceTask: 'Consolidating Governance Document',
  RelatedResourcesTask: 'Finding Related Resources & Projects',
  FindTeamMembersTask: 'Identifying Required Team Roles',
  EnrichTeamMembersWithContractTypeTask: 'Defining Team Contract Types',
  EnrichTeamMembersWithBackgroundStoryTask: 'Creating Team Role Backgrounds',
  EnrichTeamMembersWithEnvironmentInfoTask: 'Defining Team Environment',
  ReviewTeamTask: 'Reviewing Proposed Team Structure',
  TeamMarkdownTask: 'Consolidating Team Document',
  SWOTAnalysisTask: 'Performing SWOT Analysis',
  ExpertReviewTask: 'Simulating Expert Review & Criticism',
  DataCollectionTask: 'Defining Data Collection Needs',
  IdentifyDocumentsTask: 'Identifying Required Documents',
  FilterDocumentsToFindTask: 'Filtering Documents to Find',
  FilterDocumentsToCreateTask: 'Filtering Documents to Create',
  DraftDocumentsToFindTask: 'Drafting Outlines for Documents to Find',
  DraftDocumentsToCreateTask: 'Drafting Outlines for Documents to Create',
  MarkdownWithDocumentsToCreateAndFindTask: 'Consolidating Document Outlines',
  CreateWBSLevel1Task: 'Creating Work Breakdown Structure (L1)',
  CreateWBSLevel2Task: 'Creating Work Breakdown Structure (L2)',
  WBSProjectLevel1AndLevel2Task: 'Assembling WBS (L1 & L2)',
  CreatePitchTask: 'Generating Project Pitch',
  ConvertPitchToMarkdownTask: 'Formatting Project Pitch',
  IdentifyTaskDependenciesTask: 'Identifying Task Dependencies',
  EstimateTaskDurationsTask: 'Estimating Task Durations',
  CreateWBSLevel3Task: 'Creating Work Breakdown Structure (L3)',
  WBSProjectLevel1AndLevel2AndLevel3Task: 'Assembling Full WBS (L1-L3)',
  CreateScheduleTask: 'Generating Project Schedule & Gantt Charts',
  ReviewPlanTask: 'Performing Final Plan Review',
  ExecutiveSummaryTask: 'Generating Executive Summary',
  QuestionsAndAnswersTask: 'Generating Q&A Section',
  PremortemTask: 'Conducting Project Premortem Analysis',
  ReportTask: 'Assembling Final HTML Report',
  FullPlanPipeline: 'Pipeline Finalization',
};

// Grouping of tasks into logical phases for a better user experience
export const taskPhases: { name: string; tasks: string[] }[] = [
  {
    name: 'Phase 1: Initiation & Validation',
    tasks: [
      'StartTimeTask',
      'SetupTask',
      'RedlineGateTask',
      'PremiseAttackTask',
      'IdentifyPurposeTask',
      'PlanTypeTask',
    ],
  },
  {
    name: 'Phase 2: Strategic Foundation',
    tasks: [
      'PotentialLeversTask',
      'DeduplicateLeversTask',
      'EnrichLeversTask',
      'FocusOnVitalFewLeversTask',
      'StrategicDecisionsMarkdownTask',
      'CandidateScenariosTask',
      'SelectScenarioTask',
      'ScenariosMarkdownTask',
      'PhysicalLocationsTask',
      'CurrencyStrategyTask',
    ],
  },
  {
    name: 'Phase 3: Assumption & Risk Analysis',
    tasks: [
      'IdentifyRisksTask',
      'MakeAssumptionsTask',
      'DistillAssumptionsTask',
      'ReviewAssumptionsTask',
      'ConsolidateAssumptionsMarkdownTask',
      'PreProjectAssessmentTask',
    ],
  },
  {
    name: 'Phase 4: Governance & Team Structure',
    tasks: [
      'ProjectPlanTask',
      'GovernancePhase1AuditTask',
      'GovernancePhase2BodiesTask',
      'GovernancePhase3ImplPlanTask',
      'GovernancePhase4DecisionEscalationMatrixTask',
      'GovernancePhase5MonitoringProgressTask',
      'GovernancePhase6ExtraTask',
      'ConsolidateGovernanceTask',
      'RelatedResourcesTask',
      'FindTeamMembersTask',
      'EnrichTeamMembersWithContractTypeTask',
      'EnrichTeamMembersWithBackgroundStoryTask',
      'EnrichTeamMembersWithEnvironmentInfoTask',
      'ReviewTeamTask',
      'TeamMarkdownTask',
      'SWOTAnalysisTask',
      'ExpertReviewTask',
    ],
  },
  {
    name: 'Phase 5: Work Breakdown & Scheduling',
    tasks: [
      'DataCollectionTask',
      'IdentifyDocumentsTask',
      'FilterDocumentsToFindTask',
      'FilterDocumentsToCreateTask',
      'DraftDocumentsToFindTask',
      'DraftDocumentsToCreateTask',
      'MarkdownWithDocumentsToCreateAndFindTask',
      'CreateWBSLevel1Task',
      'CreateWBSLevel2Task',
      'WBSProjectLevel1AndLevel2Task',
      'CreatePitchTask',
      'ConvertPitchToMarkdownTask',
      'IdentifyTaskDependenciesTask',
      'EstimateTaskDurationsTask',
      'CreateWBSLevel3Task',
      'WBSProjectLevel1AndLevel2AndLevel3Task',
      'CreateScheduleTask',
    ],
  },
  {
    name: 'Phase 6: Final Review & Reporting',
    tasks: [
      'ReviewPlanTask',
      'ExecutiveSummaryTask',
      'QuestionsAndAnswersTask',
      'PremortemTask',
      'ReportTask',
      'FullPlanPipeline',
    ],
  },
];
