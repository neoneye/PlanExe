/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-19
 * PURPOSE: API request/response types for NextJS proxy layer that interfaces with Luigi pipeline
 * SRP and DRY check: Pass - Single responsibility for API type definitions, respects existing pipeline patterns
 */

import {
  SpeedVsDetail,
  PipelineProgress,
  FileListResponse,
  LLMConfig,
  PromptExample,
  PipelineStatus,
  UserSession
} from './pipeline';

// =======================
// PLAN MANAGEMENT API
// =======================

export interface CreatePlanRequest {
  prompt: string;
  llmModel: string;
  speedVsDetail: SpeedVsDetail;
  openrouterApiKey?: string;
  title?: string;
  tags?: string[];
}

export interface CreatePlanResponse {
  success: boolean;
  planId: string;
  runId: string;
  runDir: string;
  status: PipelineStatus;
  message?: string;
  estimatedDuration?: number;
}

export interface GetPlanStatusRequest {
  planId: string;
}

export interface GetPlanStatusResponse {
  success: boolean;
  planId: string;
  status: PipelineStatus;
  progress: PipelineProgress;
  message?: string;
}

export interface StopPlanRequest {
  planId: string;
  reason?: string;
}

export interface StopPlanResponse {
  success: boolean;
  planId: string;
  message: string;
  finalStatus: PipelineStatus;
}

export interface ResumePlanRequest {
  planId: string;
  fromTask?: string;
}

export interface ResumePlanResponse {
  success: boolean;
  planId: string;
  resumedFromTask: string;
  message: string;
}

// =======================
// PROGRESS MONITORING API
// =======================

export interface GetProgressRequest {
  planId: string;
  includeDetails?: boolean;
}

export interface GetProgressResponse {
  success: boolean;
  planId: string;
  progress: PipelineProgress;
  recentTasks: TaskProgressInfo[];
  nextTasks: TaskProgressInfo[];
}

export interface TaskProgressInfo {
  taskId: string;
  taskName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startTime?: string;
  endTime?: string;
  duration?: number;
  progress?: number;
  message?: string;
}

export interface SubscribeProgressRequest {
  planId: string;
  websocketId: string;
}

export interface ProgressUpdateEvent {
  type: 'progress_update';
  planId: string;
  progress: PipelineProgress;
  timestamp: string;
}

export interface TaskStartedEvent {
  type: 'task_started';
  planId: string;
  taskId: string;
  taskName: string;
  timestamp: string;
}

export interface TaskCompletedEvent {
  type: 'task_completed';
  planId: string;
  taskId: string;
  taskName: string;
  duration: number;
  timestamp: string;
}

export interface PipelineErrorEvent {
  type: 'pipeline_error';
  planId: string;
  error: {
    taskName: string;
    errorType: string;
    message: string;
    recoverable: boolean;
  };
  timestamp: string;
}

export interface PipelineCompleteEvent {
  type: 'pipeline_complete';
  planId: string;
  reportUrl: string;
  filesUrl: string;
  duration: number;
  timestamp: string;
}

export type WebSocketEvent =
  | ProgressUpdateEvent
  | TaskStartedEvent
  | TaskCompletedEvent
  | PipelineErrorEvent
  | PipelineCompleteEvent;

// =======================
// FILE MANAGEMENT API
// =======================

export interface GetFilesRequest {
  planId: string;
  phase?: string;
  fileType?: string;
  includeContent?: boolean;
}

export interface GetFilesResponse {
  success: boolean;
  planId: string;
  files: FileListResponse;
}

export interface DownloadFileRequest {
  planId: string;
  filename: string;
  format?: 'original' | 'preview';
}

export interface DownloadFileResponse {
  success: boolean;
  filename: string;
  contentType: string;
  size: number;
  url: string;
}

export interface DownloadZipRequest {
  planId: string;
  includeReports?: boolean;
  includeRawFiles?: boolean;
  phases?: string[];
}

export interface DownloadZipResponse {
  success: boolean;
  filename: string;
  size: number;
  url: string;
  expiresAt: string;
}

export interface PreviewFileRequest {
  planId: string;
  filename: string;
  maxLines?: number;
}

export interface PreviewFileResponse {
  success: boolean;
  filename: string;
  content: string;
  contentType: string;
  isTruncated: boolean;
  totalLines?: number;
}

// =======================
// CONFIGURATION API
// =======================

export interface GetLLMConfigRequest {
  includeUnavailable?: boolean;
}

export interface GetLLMConfigResponse {
  success: boolean;
  models: LLMConfig[];
  defaultModel: string;
  priorityOrder: string[];
}

export interface TestLLMRequest {
  modelId: string;
  apiKey?: string;
  testPrompt?: string;
}

export interface TestLLMResponse {
  success: boolean;
  modelId: string;
  available: boolean;
  responseTime?: number;
  errorMessage?: string;
  testResponse?: string;
}

export interface GetPromptExamplesRequest {
  category?: string;
  complexity?: 'simple' | 'medium' | 'complex';
  limit?: number;
}

export interface GetPromptExamplesResponse {
  success: boolean;
  examples: PromptExample[];
  categories: string[];
  totalCount: number;
}

export interface UpdateConfigRequest {
  defaultModel?: string;
  priorityOrder?: string[];
  enableFeatures?: string[];
  disableFeatures?: string[];
}

export interface UpdateConfigResponse {
  success: boolean;
  message: string;
  updatedConfig: Record<string, any>;
}

// =======================
// SESSION MANAGEMENT API
// =======================

export interface CreateSessionRequest {
  deviceId?: string;
  preferences?: Record<string, any>;
}

export interface CreateSessionResponse {
  success: boolean;
  sessionId: string;
  session: UserSession;
  expiresAt: string;
}

export interface GetSessionRequest {
  sessionId: string;
}

export interface GetSessionResponse {
  success: boolean;
  session: UserSession;
  isValid: boolean;
}

export interface UpdateSessionRequest {
  sessionId: string;
  currentPlanId?: string;
  settings?: Record<string, any>;
  preferences?: Record<string, any>;
}

export interface UpdateSessionResponse {
  success: boolean;
  session: UserSession;
  message?: string;
}

export interface EndSessionRequest {
  sessionId: string;
}

export interface EndSessionResponse {
  success: boolean;
  message: string;
}

// =======================
// PLAN HISTORY API
// =======================

export interface GetPlanHistoryRequest {
  sessionId: string;
  limit?: number;
  offset?: number;
  status?: PipelineStatus;
  dateFrom?: string;
  dateTo?: string;
}

export interface GetPlanHistoryResponse {
  success: boolean;
  plans: Array<{
    planId: string;
    title: string;
    status: PipelineStatus;
    createdAt: string;
    completedAt?: string;
    duration?: number;
    fileCount: number;
    promptPreview: string;
    hasReport: boolean;
    hasFiles: boolean;
  }>;
  totalCount: number;
  hasMore: boolean;
}

export interface DeletePlanRequest {
  planId: string;
  sessionId: string;
  confirmDelete: boolean;
}

export interface DeletePlanResponse {
  success: boolean;
  planId: string;
  message: string;
  filesDeleted: number;
}

// =======================
// HEALTH & MONITORING API
// =======================

export interface HealthCheckRequest {
  includeDetails?: boolean;
}

export interface HealthCheckResponse {
  success: boolean;
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  services: {
    database: 'up' | 'down';
    fileSystem: 'up' | 'down';
    llmModels: Record<string, 'up' | 'down'>;
    luigiScheduler: 'up' | 'down';
  };
  metrics?: {
    activePlans: number;
    totalPlans: number;
    avgPlanDuration: number;
    errorRate: number;
  };
}

export interface GetMetricsRequest {
  timeframe?: '1h' | '24h' | '7d' | '30d';
  includeDetailed?: boolean;
}

export interface GetMetricsResponse {
  success: boolean;
  timeframe: string;
  metrics: {
    plansCreated: number;
    plansCompleted: number;
    plansFailed: number;
    avgDuration: number;
    totalLLMCalls: number;
    errorRate: number;
  };
  trends?: {
    plansOverTime: Array<{ date: string; count: number }>;
    durationOverTime: Array<{ date: string; avgDuration: number }>;
    errorRateOverTime: Array<{ date: string; errorRate: number }>;
  };
}

// =======================
// ERROR RESPONSES
// =======================

export interface APIError {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
    timestamp: string;
    requestId?: string;
  };
}

export interface ValidationError extends APIError {
  error: APIError['error'] & {
    code: 'VALIDATION_ERROR';
    fieldErrors: Record<string, string[]>;
  };
}

export interface AuthenticationError extends APIError {
  error: APIError['error'] & {
    code: 'AUTHENTICATION_ERROR';
    redirectUrl?: string;
  };
}

export interface RateLimitError extends APIError {
  error: APIError['error'] & {
    code: 'RATE_LIMIT_ERROR';
    resetTime: string;
    remainingRequests: number;
  };
}

export interface PipelineError extends APIError {
  error: APIError['error'] & {
    code: 'PIPELINE_ERROR';
    taskName?: string;
    phase?: string;
    retryable: boolean;
  };
}

// =======================
// TYPE UNIONS & HELPERS
// =======================

export type APIResponse<T = any> = T | APIError;

export type APIRequest =
  | CreatePlanRequest
  | GetPlanStatusRequest
  | StopPlanRequest
  | ResumePlanRequest
  | GetProgressRequest
  | GetFilesRequest
  | DownloadFileRequest
  | DownloadZipRequest
  | PreviewFileRequest
  | GetLLMConfigRequest
  | TestLLMRequest
  | GetPromptExamplesRequest
  | UpdateConfigRequest
  | CreateSessionRequest
  | GetSessionRequest
  | UpdateSessionRequest
  | EndSessionRequest
  | GetPlanHistoryRequest
  | DeletePlanRequest
  | HealthCheckRequest
  | GetMetricsRequest;

export interface APIEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  description: string;
  requestType?: string;
  responseType: string;
  requiresAuth?: boolean;
  rateLimit?: number;
}

export const API_ENDPOINTS: Record<string, APIEndpoint> = {
  // Plan Management
  CREATE_PLAN: {
    method: 'POST',
    path: '/api/plans',
    description: 'Create a new plan and start pipeline execution',
    requestType: 'CreatePlanRequest',
    responseType: 'CreatePlanResponse',
  },
  GET_PLAN_STATUS: {
    method: 'GET',
    path: '/api/plans/{planId}',
    description: 'Get current plan status and basic information',
    responseType: 'GetPlanStatusResponse',
  },
  STOP_PLAN: {
    method: 'POST',
    path: '/api/plans/{planId}/stop',
    description: 'Stop a running plan execution',
    requestType: 'StopPlanRequest',
    responseType: 'StopPlanResponse',
  },
  RESUME_PLAN: {
    method: 'POST',
    path: '/api/plans/{planId}/resume',
    description: 'Resume a stopped or failed plan',
    requestType: 'ResumePlanRequest',
    responseType: 'ResumePlanResponse',
  },

  // Progress Monitoring
  GET_PROGRESS: {
    method: 'GET',
    path: '/api/plans/{planId}/progress',
    description: 'Get detailed progress information',
    responseType: 'GetProgressResponse',
  },

  // File Management
  GET_FILES: {
    method: 'GET',
    path: '/api/plans/{planId}/files',
    description: 'List all files generated by the plan',
    responseType: 'GetFilesResponse',
  },
  DOWNLOAD_FILE: {
    method: 'GET',
    path: '/api/plans/{planId}/files/{filename}',
    description: 'Download a specific file',
    responseType: 'DownloadFileResponse',
  },
  DOWNLOAD_ZIP: {
    method: 'GET',
    path: '/api/plans/{planId}/download',
    description: 'Download all files as ZIP archive',
    responseType: 'DownloadZipResponse',
  },
  PREVIEW_FILE: {
    method: 'GET',
    path: '/api/plans/{planId}/files/{filename}/preview',
    description: 'Preview file content',
    responseType: 'PreviewFileResponse',
  },

  // Configuration
  GET_LLM_CONFIG: {
    method: 'GET',
    path: '/api/config/llms',
    description: 'Get available LLM models configuration',
    responseType: 'GetLLMConfigResponse',
  },
  TEST_LLM: {
    method: 'POST',
    path: '/api/config/llms/{modelId}/test',
    description: 'Test LLM model availability',
    requestType: 'TestLLMRequest',
    responseType: 'TestLLMResponse',
  },
  GET_PROMPT_EXAMPLES: {
    method: 'GET',
    path: '/api/config/prompts',
    description: 'Get prompt examples from catalog',
    responseType: 'GetPromptExamplesResponse',
  },

  // Session Management
  CREATE_SESSION: {
    method: 'POST',
    path: '/api/session',
    description: 'Create a new user session',
    requestType: 'CreateSessionRequest',
    responseType: 'CreateSessionResponse',
  },
  GET_SESSION: {
    method: 'GET',
    path: '/api/session/{sessionId}',
    description: 'Get session information',
    responseType: 'GetSessionResponse',
  },
  UPDATE_SESSION: {
    method: 'PUT',
    path: '/api/session/{sessionId}',
    description: 'Update session settings',
    requestType: 'UpdateSessionRequest',
    responseType: 'UpdateSessionResponse',
  },

  // Plan History
  GET_PLAN_HISTORY: {
    method: 'GET',
    path: '/api/session/{sessionId}/plans',
    description: 'Get user plan history',
    responseType: 'GetPlanHistoryResponse',
  },
  DELETE_PLAN: {
    method: 'DELETE',
    path: '/api/plans/{planId}',
    description: 'Delete a plan and its files',
    requestType: 'DeletePlanRequest',
    responseType: 'DeletePlanResponse',
  },

  // Health & Monitoring
  HEALTH_CHECK: {
    method: 'GET',
    path: '/api/health',
    description: 'System health check',
    responseType: 'HealthCheckResponse',
  },
  GET_METRICS: {
    method: 'GET',
    path: '/api/metrics',
    description: 'Get system metrics and usage statistics',
    responseType: 'GetMetricsResponse',
  },
} as const;