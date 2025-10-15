/**
 * 
 * Author: Cascade using Claude (following frontend architecture fix plan)
 * Date: 2025-09-19T19:12:34-04:00
 * PURPOSE: Clean direct FastAPI client - NO compatibility layer, uses snake_case throughout to match backend exactly
 * SRP and DRY check: Pass - Single responsibility for FastAPI communication, no field translation complexity
 */

import { getApiBaseUrl } from '@/lib/utils/api-config';

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

export interface PlanFileEntry {
  filename: string;
  content_type: string;
  stage?: string | null;
  size_bytes: number;
  created_at: string;
  description?: string | null;
  task_name?: string | null;
  order?: number | null;
}

export interface PlanFilesResponse {
  plan_id: string;
  files: PlanFileEntry[];
  has_report: boolean;
}

export interface PlanArtefact {
  filename: string;
  content_type: string;
  stage?: string | null;
  size_bytes: number;
  created_at: string;
  description?: string | null;
  task_name?: string | null;
  order?: number | null;
}

export interface PlanArtefactListResponse {
  plan_id: string;
  artefacts: PlanArtefact[];
}

export interface ReportSectionResponse {
  filename: string;
  stage?: string | null;
  content_type: string;
  content: string;
}

export interface MissingSectionResponse {
  filename: string;
  stage?: string | null;
  reason: string;
}

export interface FallbackReportResponse {
  plan_id: string;
  generated_at: string;
  completion_percentage: number;
  sections: ReportSectionResponse[];
  missing_sections: MissingSectionResponse[];
  assembled_html: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  planexe_version: string;
  available_models: number;
}

// WebSocket Client for real-time progress (replaces unreliable SSE)
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Array<(data: any) => void>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private planId: string;
  private baseURL: string;

  constructor(planId: string, baseURL?: string) {
    this.planId = planId;
    this.baseURL = baseURL || '';
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${this.baseURL}/ws/plans/${this.planId}/progress`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          this.reconnectAttempts = 0;
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.emit('message', data);
          } catch (error) {
            // If not JSON, emit as raw message
            this.emit('message', { type: 'raw', message: event.data });
          }
        };

        this.ws.onerror = (error) => {
          this.emit('error', error);
          reject(error);
        };

        this.ws.onclose = (event) => {
          this.emit('close', event);
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
          }
        };

      } catch (error) {
        reject(error);
      }
    });
  }

  private scheduleReconnect() {
    this.reconnectAttempts++;
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000); // Exponential backoff, max 30s

    setTimeout(() => {
      this.connect().catch(() => {
        // Silent fail - let the UI handle reconnection status
      });
    }, this.reconnectDelay);
  }

  on(event: string, callback: (data: any) => void) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  off(event: string, callback: (data: any) => void) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  private emit(event: string, data: any) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => callback(data));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.listeners.clear();
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Simple, Clean FastAPI Client
export class FastAPIClient {
  private baseURL: string;

  constructor(baseURL?: string) {
    const normalized = (baseURL ?? '').trim();
    this.baseURL = normalized.endsWith('/') ? normalized.slice(0, -1) : normalized;
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

  async getPlanArtefacts(plan_id: string): Promise<PlanArtefactListResponse> {
    const response = await fetch(`${this.baseURL}/api/plans/${plan_id}/artefacts`);
    return this.handleResponse<PlanArtefactListResponse>(response);
  }

  async getFallbackReport(plan_id: string): Promise<FallbackReportResponse> {
    const response = await fetch(`${this.baseURL}/api/plans/${plan_id}/fallback-report`);
    return this.handleResponse<FallbackReportResponse>(response);
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

  // WebSocket for Real-time Progress (replaces unreliable SSE)
  streamProgress(plan_id: string): WebSocketClient {
    return new WebSocketClient(plan_id, this.baseURL);
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
const resolvedBaseUrl = getApiBaseUrl();
export const fastApiClient = new FastAPIClient(resolvedBaseUrl);

// Types are already exported above with their interface declarations
