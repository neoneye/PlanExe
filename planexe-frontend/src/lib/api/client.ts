/**
 * Author: Cascade  
 * Date: 2025-09-19T19:02:57-04:00
 * PURPOSE: Clean API client with compatibility layer - connects to FastAPI backend with field translation
 * SRP and DRY check: Pass - Single responsibility for API communication, handles legacy field names internally
 */

// FastAPI Backend Types (exact match)
export interface FastAPICreatePlanRequest {
  prompt: string;
  llm_model?: string;
  speed_vs_detail: 'FAST_BUT_BASIC' | 'BALANCED_SPEED_AND_DETAIL' | 'ALL_DETAILS_BUT_SLOW';
  openrouter_api_key?: string;
}

export interface FastAPIPlanResponse {
  plan_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  prompt: string;
  progress_percentage: number;
  progress_message: string;
  error_message?: string;
  output_dir?: string;
}

export interface FastAPILLMModel {
  id: string;
  label: string;
  comment: string;
  priority: number;
  requires_api_key: boolean;
}

export interface FastAPIPromptExample {
  uuid: string;
  prompt: string;
  title?: string;
}

export interface FastAPIPlanFilesResponse {
  plan_id: string;
  files: string[];
  has_report: boolean;
}

// Frontend Types (existing - for compatibility)
export interface CreatePlanRequest {
  prompt: string;
  llmModel?: string;
  speedVsDetail: 'FAST_BUT_SKIP_DETAILS' | 'ALL_DETAILS_BUT_SLOW';
  openrouterApiKey?: string;
  title?: string;
}

export interface PlanResponse {
  planId: string;
  status: string;
  createdAt: string;
  prompt: string;
  progressPercentage: number;
  progressMessage: string;
  errorMessage?: string;
  outputDir?: string;
}

export interface LLMModel {
  id: string;
  label: string;
  comment: string;
  priority: number;
  requiresApiKey: boolean;
}

export interface PromptExample {
  uuid: string;
  prompt: string;
  title?: string;
}

export interface PlanFilesResponse {
  planId: string;
  files: string[];
  hasReport: boolean;
}

// API Client with Compatibility Layer
export class PlanExeAPIClient {
  private baseURL: string;

  constructor(baseURL = 'http://localhost:8000') {
    this.baseURL = baseURL;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(error.error || `HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  }

  // Field Translation Helpers
  private translateToFastAPI(request: CreatePlanRequest): FastAPICreatePlanRequest {
    return {
      prompt: request.prompt,
      llm_model: request.llmModel,
      speed_vs_detail: request.speedVsDetail === 'FAST_BUT_SKIP_DETAILS' 
        ? 'FAST_BUT_BASIC' 
        : 'ALL_DETAILS_BUT_SLOW',
      openrouter_api_key: request.openrouterApiKey,
    };
  }

  private translateFromFastAPI(response: FastAPIPlanResponse): PlanResponse {
    return {
      planId: response.plan_id,
      status: response.status,
      createdAt: response.created_at,
      prompt: response.prompt,
      progressPercentage: response.progress_percentage,
      progressMessage: response.progress_message,
      errorMessage: response.error_message,
      outputDir: response.output_dir,
    };
  }

  private translateModelFromFastAPI(model: FastAPILLMModel): LLMModel {
    return {
      id: model.id,
      label: model.label,
      comment: model.comment,
      priority: model.priority,
      requiresApiKey: model.requires_api_key,
    };
  }

  private translateFilesFromFastAPI(response: FastAPIPlanFilesResponse): PlanFilesResponse {
    return {
      planId: response.plan_id,
      files: response.files,
      hasReport: response.has_report,
    };
  }

  // API Methods
  async getModels(): Promise<LLMModel[]> {
    const response = await fetch(`${this.baseURL}/api/models`);
    const models = await this.handleResponse<FastAPILLMModel[]>(response);
    return models.map(model => this.translateModelFromFastAPI(model));
  }

  async getPrompts(): Promise<PromptExample[]> {
    const response = await fetch(`${this.baseURL}/api/prompts`);
    return this.handleResponse<PromptExample[]>(response); // No translation needed
  }

  async createPlan(request: CreatePlanRequest): Promise<PlanResponse> {
    const fastApiRequest = this.translateToFastAPI(request);
    const response = await fetch(`${this.baseURL}/api/plans`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(fastApiRequest),
    });
    const plan = await this.handleResponse<FastAPIPlanResponse>(response);
    return this.translateFromFastAPI(plan);
  }

  async getPlan(planId: string): Promise<PlanResponse> {
    const response = await fetch(`${this.baseURL}/api/plans/${planId}`);
    const plan = await this.handleResponse<FastAPIPlanResponse>(response);
    return this.translateFromFastAPI(plan);
  }

  async getPlanFiles(planId: string): Promise<PlanFilesResponse> {
    const response = await fetch(`${this.baseURL}/api/plans/${planId}/files`);
    const files = await this.handleResponse<FastAPIPlanFilesResponse>(response);
    return this.translateFilesFromFastAPI(files);
  }

  async downloadFile(planId: string, filename: string): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/api/plans/${planId}/files/${filename}`);
    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.statusText}`);
    }
    return response.blob();
  }

  // Server-Sent Events for Real-time Progress
  streamProgress(planId: string, onProgress: (data: PlanResponse) => void): EventSource {
    const eventSource = new EventSource(`${this.baseURL}/api/plans/${planId}/stream`);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const translatedData = this.translateFromFastAPI(data);
        onProgress(translatedData);
      } catch (error) {
        console.error('Error parsing SSE data:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
    };

    return eventSource;
  }

  // Health Check
  async getHealth(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${this.baseURL}/health`);
    return this.handleResponse<{ status: string; version: string }>(response);
  }

  // Utility: Download blob as file
  downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

// Default client instance
export const apiClient = new PlanExeAPIClient();

// Export types for convenience
export type {
  CreatePlanRequest,
  PlanResponse,
  LLMModel,
  PromptExample,
  PlanFilesResponse,
};
