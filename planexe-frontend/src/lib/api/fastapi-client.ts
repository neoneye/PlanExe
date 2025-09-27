/**
 * 
 * Author: Cascade using Claude (following frontend architecture fix plan)
 * Date: 2025-09-19T19:12:34-04:00
 * PURPOSE: Clean direct FastAPI client - NO compatibility layer, uses snake_case throughout to match backend exactly
 * SRP and DRY check: Pass - Single responsibility for FastAPI communication, no field translation complexity
 */

// FastAPI Backend Types (EXACT match with backend)
export interface CreatePlanRequest {
  prompt: string;
  llm_model?: string;
  speed_vs_detail: 'fast_but_skip_details' | 'balanced_speed_and_detail' | 'all_details_but_slow';
  openrouter_api_key?: string;
}

export interface PlanResponse {
  plan_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  prompt: string;
  progress_percentage: number;
  progress_message: string;
  error_message?: string;
  output_dir?: string;
}

export interface LLMModel {
  id: string;
  label: string;
  comment: string;
  priority: number;
  requires_api_key: boolean;
}

export interface PromptExample {
  uuid: string;
  prompt: string;
  title?: string;
}

export interface PlanFilesResponse {
  plan_id: string;
  files: string[];
  has_report: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  planexe_version: string;
  available_models: number;
}

// Simple, Clean FastAPI Client
export class FastAPIClient {
  private baseURL: string;

  constructor(baseURL?: string) {
    // Railway deployment: FastAPI serves both backend and frontend from same instance
    this.baseURL = baseURL || '';
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(error.error || `HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  }

  // Health Check
  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseURL}/health`);
    return this.handleResponse<HealthResponse>(response);
  }

  // Get available LLM models
  async getModels(): Promise<LLMModel[]> {
    const response = await fetch(`${this.baseURL}/api/models`);
    return this.handleResponse<LLMModel[]>(response);
  }

  // Get example prompts
  async getPrompts(): Promise<PromptExample[]> {
    const response = await fetch(`${this.baseURL}/api/prompts`);
    return this.handleResponse<PromptExample[]>(response);
  }

  // Create new plan
  async createPlan(request: CreatePlanRequest): Promise<PlanResponse> {
    const response = await fetch(`${this.baseURL}/api/plans`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    return this.handleResponse<PlanResponse>(response);
  }

  // Get plan status
  async getPlan(plan_id: string): Promise<PlanResponse> {
    const response = await fetch(`${this.baseURL}/api/plans/${plan_id}`);
    return this.handleResponse<PlanResponse>(response);
  }

  // Get plan files
  async getPlanFiles(plan_id: string): Promise<PlanFilesResponse> {
    const response = await fetch(`${this.baseURL}/api/plans/${plan_id}/files`);
    return this.handleResponse<PlanFilesResponse>(response);
  }

  // Download specific file
  async downloadFile(plan_id: string, filename: string): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/api/plans/${plan_id}/files/${filename}`);
    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.statusText}`);
    }
    return response.blob();
  }

  // Download HTML report
  async downloadReport(plan_id: string): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/api/plans/${plan_id}/report`);
    if (!response.ok) {
      throw new Error(`Failed to download report: ${response.statusText}`);
    }
    return response.blob();
  }

  // Cancel plan
  async cancelPlan(plan_id: string): Promise<{ message: string }> {
    const response = await fetch(`${this.baseURL}/api/plans/${plan_id}`, {
      method: 'DELETE',
    });
    return this.handleResponse<{ message: string }>(response);
  }

  // Get all plans
  async getPlans(): Promise<PlanResponse[]> {
    const response = await fetch(`${this.baseURL}/api/plans`);
    return this.handleResponse<PlanResponse[]>(response);
  }

  // Server-Sent Events for Real-time Progress
  streamProgress(plan_id: string): EventSource {
    return new EventSource(`${this.baseURL}/api/plans/${plan_id}/stream`);
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
export const fastApiClient = new FastAPIClient();

// Types are already exported above with their interface declarations
