/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-19
 * PURPOSE: Comprehensive TypeScript interfaces for Luigi pipeline data structures based on 4000-line run_plan_pipeline.py analysis
 * SRP and DRY check: Pass - Single responsibility for pipeline type definitions, respects existing FilenameEnum patterns
 */

// =======================
// CORE PIPELINE TYPES
// =======================

export type SpeedVsDetail = 'ALL_DETAILS_BUT_SLOW' | 'FAST_BUT_SKIP_DETAILS';

export type PipelineStatus = 'created' | 'running' | 'completed' | 'failed' | 'stopped' | 'pending' | 'cancelled';

export type PlanPurpose = 'business' | 'personal' | 'other';

export type PlanType = 'physical' | 'digital';

// =======================
// PIPELINE PROGRESS
// =======================

// Represents the status of an individual task in the pipeline
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed';

// Represents the state of a single task in the UI
export interface TaskState {
  id: string; // The technical task name, e.g., 'IdentifyPurposeTask'
  name: string; // The user-friendly name, e.g., 'Identifying Plan Purpose'
  status: TaskStatus;
}

// Represents a logical grouping of tasks
export interface TaskPhase {
  name: string; // The name of the phase, e.g., 'I. Plan Initiation & Validation'
  tasks: TaskState[];
  completedTasks: number;
  totalTasks: number;
}

// Data structure for the new SSE event from the backend
export interface TaskUpdateEvent {
  task_id: string; // The technical task name from the backend
  status: TaskStatus;
  timestamp: string;
}

// Overall progress state, including all phases and tasks
export interface PipelineProgressState {
  status: PipelineStatus;
  phases: TaskPhase[];
  overallPercentage: number;
  completedTasks: number;
  totalTasks: number;
  error: string | null;
  duration: number;
}

export interface PipelineError {
  taskName: string;
  errorType: string;
  message: string;
  timestamp: Date;
  recoverable: boolean;
}

// =======================
// PIPELINE PHASES
// =======================

export type PipelinePhase =
  | 'setup'
  | 'initial_analysis'
  | 'strategic_planning'
  | 'scenario_planning'
  | 'contextual_analysis'
  | 'assumption_management'
  | 'project_planning'
  | 'governance'
  | 'resource_planning'
  | 'documentation'
  | 'work_breakdown'
  | 'scheduling'
  | 'reporting'
  | 'completion';

export interface PipelinePhaseInfo {
  phase: PipelinePhase;
  displayName: string;
  description: string;
  taskCount: number;
  estimatedDuration: number;
  dependencies: PipelinePhase[];
}

// =======================
// TASK DEFINITIONS
// =======================

export interface LuigiTask {
  taskId: string;
  taskName: string;
  phase: PipelinePhase;
  status: 'pending' | 'running' | 'completed' | 'failed';
  dependencies: string[];
  outputs: TaskOutput[];
  startTime?: Date;
  endTime?: Date;
  duration?: number;
  llmModel?: string;
  errorMessage?: string;
}

export interface TaskOutput {
  filename: string;
  filePath: string;
  fileType: 'json' | 'md' | 'html' | 'csv' | 'txt';
  outputType: 'raw' | 'clean' | 'markdown' | 'html';
  size?: number;
  lastModified?: Date;
}

// =======================
// FILE MANAGEMENT
// =======================

export interface PlanFile {
  filename: string;
  relativePath: string;
  absolutePath: string;
  size: number;
  type: 'json' | 'md' | 'html' | 'csv' | 'txt';
  stage: PipelinePhase;
  taskName: string;
  outputType: 'raw' | 'clean' | 'markdown' | 'html';
  lastModified: Date;
  isRequired: boolean;
  description: string;
}

export interface FileListResponse {
  planId: string;
  files: PlanFile[];
  phases: Record<PipelinePhase, PlanFile[]>;
  zipUrl?: string;
  reportUrl?: string;
  totalSize: number;
  lastUpdated: Date;
}

// =======================
// WBS (WORK BREAKDOWN STRUCTURE)
// =======================

export interface WBSTask {
  id: string;
  parentId?: string;
  title: string;
  description: string;
  level: 1 | 2 | 3;
  duration?: number;
  dependencies: string[];
  children: WBSTask[];
  startDate?: Date;
  endDate?: Date;
  status: 'not_started' | 'in_progress' | 'completed';
  assignee?: string;
  estimatedEffort?: number;
  actualEffort?: number;
}

export interface WBSProject {
  projectId: string;
  projectTitle: string;
  rootTask: WBSTask;
  totalDuration: number;
  totalTasks: number;
  phases: WBSPhase[];
  startDate?: Date;
  endDate?: Date;
}

export interface WBSPhase {
  id: string;
  title: string;
  description: string;
  tasks: WBSTask[];
  duration: number;
  dependencies: string[];
}

// =======================
// TEAM & RESOURCES
// =======================

export interface TeamMember {
  id: string;
  name: string;
  role: string;
  contractType: 'full_time' | 'part_time' | 'contractor' | 'consultant';
  skills: string[];
  availability: number; // percentage
  costPerHour?: number;
  backgroundStory?: string;
  environmentInfo?: string;
}

export interface ProjectTeam {
  members: TeamMember[];
  organizationChart: TeamHierarchy;
  totalCost: number;
  totalEffort: number;
  keyRoles: string[];
}

export interface TeamHierarchy {
  lead: TeamMember;
  reports: TeamMember[];
  external: TeamMember[];
}

// =======================
// ANALYSIS & INSIGHTS
// =======================

export interface SWOTAnalysis {
  strengths: SWOTItem[];
  weaknesses: SWOTItem[];
  opportunities: SWOTItem[];
  threats: SWOTItem[];
  strategicInsights: string[];
  recommendations: string[];
}

export interface SWOTItem {
  id: string;
  title: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
  confidence: 'high' | 'medium' | 'low';
  mitigation?: string;
}

export interface RiskAssessment {
  risks: Risk[];
  riskMatrix: RiskMatrix;
  mitigationStrategies: MitigationStrategy[];
  overallRiskLevel: 'low' | 'medium' | 'high' | 'critical';
}

export interface Risk {
  id: string;
  title: string;
  description: string;
  category: string;
  probability: 'low' | 'medium' | 'high';
  impact: 'low' | 'medium' | 'high';
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  mitigation: string;
  contingency: string;
  owner: string;
}

export interface RiskMatrix {
  low: Risk[];
  medium: Risk[];
  high: Risk[];
  critical: Risk[];
}

export interface MitigationStrategy {
  riskId: string;
  strategy: string;
  cost: number;
  timeline: number;
  effectiveness: 'low' | 'medium' | 'high';
}

// =======================
// ASSUMPTIONS & SCENARIOS
// =======================

export interface Assumption {
  id: string;
  title: string;
  description: string;
  category: string;
  confidence: 'low' | 'medium' | 'high';
  impact: 'low' | 'medium' | 'high';
  validation: string;
  dependencies: string[];
}

export interface Scenario {
  id: string;
  title: string;
  description: string;
  characteristics: Record<string, any>;
  assumptions: Assumption[];
  feasibility: number;
  impact: number;
  score: number;
  selected: boolean;
}

// =======================
// GOVERNANCE & COMPLIANCE
// =======================

export interface GovernanceFramework {
  auditResults: GovernanceAudit;
  governanceBodies: GovernanceBody[];
  implementationPlan: ImplementationPlan;
  escalationMatrix: EscalationMatrix;
  monitoringPlan: MonitoringPlan;
  extraConsiderations: string[];
}

export interface GovernanceAudit {
  findings: AuditFinding[];
  recommendations: string[];
  complianceLevel: number;
  riskAreas: string[];
}

export interface AuditFinding {
  area: string;
  issue: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  recommendation: string;
}

export interface GovernanceBody {
  name: string;
  purpose: string;
  members: string[];
  responsibilities: string[];
  meetingFrequency: string;
  reportingLine: string;
}

export interface ImplementationPlan {
  phases: ImplementationPhase[];
  timeline: number;
  resources: string[];
  milestones: Milestone[];
}

export interface ImplementationPhase {
  id: string;
  name: string;
  description: string;
  duration: number;
  dependencies: string[];
  deliverables: string[];
}

export interface EscalationMatrix {
  levels: EscalationLevel[];
  procedures: string[];
  timeframes: Record<string, number>;
}

export interface EscalationLevel {
  level: number;
  authority: string;
  responsibilities: string[];
  timeframe: number;
}

export interface MonitoringPlan {
  metrics: PerformanceMetric[];
  reportingSchedule: string;
  reviewProcesses: string[];
  continuousImprovement: string[];
}

export interface PerformanceMetric {
  name: string;
  description: string;
  target: number;
  frequency: string;
  owner: string;
}

export interface Milestone {
  id: string;
  name: string;
  description: string;
  targetDate: Date;
  dependencies: string[];
  criteria: string[];
}

// =======================
// REPORTING & OUTPUTS
// =======================

export interface ExecutiveSummary {
  projectTitle: string;
  objective: string;
  scope: string;
  duration: number;
  budget: number;
  keyMetrics: Record<string, any>;
  risks: string[];
  recommendations: string[];
  nextSteps: string[];
}

export interface ProjectPitch {
  title: string;
  elevator: string;
  problem: string;
  solution: string;
  benefits: string[];
  investment: number;
  timeline: number;
  team: string[];
  risks: string[];
  callToAction: string;
}

export interface QuestionsAndAnswers {
  questions: QuestionAnswer[];
  categories: Record<string, QuestionAnswer[]>;
  keyInsights: string[];
}

export interface QuestionAnswer {
  id: string;
  question: string;
  answer: string;
  category: string;
  importance: 'high' | 'medium' | 'low';
  source: string;
}

export interface PremortemAnalysis {
  potentialFailures: FailureScenario[];
  preventiveMeasures: PreventiveMeasure[];
  contingencyPlans: ContingencyPlan[];
  overallReadiness: number;
}

export interface FailureScenario {
  id: string;
  scenario: string;
  probability: 'low' | 'medium' | 'high';
  impact: 'low' | 'medium' | 'high';
  earlyWarnings: string[];
  prevention: string[];
}

export interface PreventiveMeasure {
  id: string;
  measure: string;
  cost: number;
  effectiveness: number;
  timeline: number;
}

export interface ContingencyPlan {
  scenarioId: string;
  plan: string;
  triggers: string[];
  resources: string[];
  timeline: number;
}

// =======================
// CONFIGURATION & SETTINGS
// =======================

export interface LLMConfig {
  id: string;
  name: string;
  provider: string;
  type: 'paid' | 'local';
  priority: number;
  requiresApiKey: boolean;
  available: boolean;
  description?: string;
  maxTokens?: number;
  costPer1kTokens?: number;
}

export interface PromptExample {
  uuid: string;
  title?: string;
  prompt: string;
}

export interface PipelineConfig {
  speedVsDetail: SpeedVsDetail;
  llmModels: string[];
  enableCsvExport: boolean;
  maxConcurrentTasks: number;
  timeoutMinutes: number;
  retryAttempts: number;
}

// =======================
// SESSION & PERSISTENCE
// =======================

export interface UserSession {
  sessionId: string;
  currentPlanId?: string;
  planHistory: PlanHistoryItem[];
  settings: UserSettings;
  preferences: UserPreferences;
  lastActivity: Date;
}

export interface PlanHistoryItem {
  planId: string;
  title: string;
  status: PipelineStatus;
  createdAt: Date;
  completedAt?: Date;
  duration?: number;
  fileCount: number;
  promptPreview: string;
}

export interface UserSettings {
  defaultSpeedVsDetail: SpeedVsDetail;
  preferredLLMModel: string;
  openrouterApiKey?: string;
  notificationPreferences: NotificationSettings;
  uiPreferences: UIPreferences;
}

export interface NotificationSettings {
  emailNotifications: boolean;
  progressUpdates: boolean;
  completionAlerts: boolean;
  errorAlerts: boolean;
}

export interface UIPreferences {
  theme: 'light' | 'dark' | 'auto';
  compactMode: boolean;
  showAdvancedOptions: boolean;
  defaultView: 'overview' | 'detailed';
}

export interface UserPreferences {
  autoSave: boolean;
  confirmBeforeStop: boolean;
  showTooltips: boolean;
  enableKeyboardShortcuts: boolean;
}