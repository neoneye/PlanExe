/**
 * Author: Cascade
 * Date: 2025-09-19T16:59:36-04:00
 * PURPOSE: API route for LLM configuration management - loads from llm_config.json and provides model availability
 * SRP and DRY check: Pass - Single responsibility for LLM configuration, interfaces with existing llm_config.json
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import {
  GetLLMConfigResponse,
  TestLLMRequest,
  TestLLMResponse,
  APIError
} from '@/lib/types/api';
import { LLMConfig } from '@/lib/types/pipeline';

// Get PlanExe root directory
function getPlanExeRoot(): string {
  return path.resolve(process.cwd(), '..');
}

// Load LLM configuration from llm_config.json
async function loadLLMConfig(): Promise<any> {
  const planExeRoot = getPlanExeRoot();
  const configPath = path.join(planExeRoot, 'llm_config.json');
  
  try {
    const configContent = await fs.readFile(configPath, 'utf-8');
    return JSON.parse(configContent);
  } catch (error) {
    console.error('Failed to load LLM config:', error);
    throw new Error('LLM configuration file not found or invalid');
  }
}

// Transform LLM config to API response format
function transformLLMConfig(config: any): GetLLMConfigResponse {
  const models: LLMConfig[] = [];
  let defaultModel = '';
  const priorityOrder: string[] = [];

  // Parse different LLM providers
  if (config.openrouter_paid_models) {
    config.openrouter_paid_models.forEach((model: any, index: number) => {
      models.push({
        id: `openrouter-paid-${model.model}`,
        name: model.model,
        provider: 'OpenRouter',
        type: 'paid',
        priority: index + 1,
        requiresApiKey: true,
        available: true,
        description: model.comment || '',
        maxTokens: model.max_tokens || 8192,
        costPer1kTokens: model.cost_per_1k_tokens || 0
      });
      
      if (index === 0 && !defaultModel) {
        defaultModel = `openrouter-paid-${model.model}`;
      }
      
      priorityOrder.push(`openrouter-paid-${model.model}`);
    });
  }

  if (config.ollama_models) {
    config.ollama_models.forEach((model: any, index: number) => {
      models.push({
        id: `ollama-${model.model}`,
        name: model.model,
        provider: 'Ollama',
        type: 'local',
        priority: (config.openrouter_paid_models?.length || 0) + index + 1,
        requiresApiKey: false,
        available: true, // TODO: Check actual availability
        description: model.comment || 'Local Ollama model',
        maxTokens: model.max_tokens || 4096,
        costPer1kTokens: 0
      });
      
      priorityOrder.push(`ollama-${model.model}`);
    });
  }

  if (config.lmstudio_models) {
    config.lmstudio_models.forEach((model: any, index: number) => {
      models.push({
        id: `lmstudio-${model.model}`,
        name: model.model,
        provider: 'LM Studio',
        type: 'local',
        priority: (config.openrouter_paid_models?.length || 0) + (config.ollama_models?.length || 0) + index + 1,
        requiresApiKey: false,
        available: true, // TODO: Check actual availability
        description: model.comment || 'Local LM Studio model',
        maxTokens: model.max_tokens || 4096,
        costPer1kTokens: 0
      });
      
      priorityOrder.push(`lmstudio-${model.model}`);
    });
  }

  return {
    success: true,
    models,
    defaultModel,
    priorityOrder
  };
}

// GET /api/config/llms - Get available LLM models
export async function GET(request: NextRequest): Promise<NextResponse> {
  try {
    const config = await loadLLMConfig();
    const response = transformLLMConfig(config);
    
    return NextResponse.json(response);

  } catch (error) {
    console.error('LLM config error:', error);

    const apiError: APIError = {
      success: false,
      error: {
        code: 'CONFIG_ERROR',
        message: error instanceof Error ? error.message : 'Failed to load LLM configuration',
        timestamp: new Date().toISOString(),
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}

// POST /api/config/llms/test - Test LLM model availability
export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const body = await request.json() as TestLLMRequest;
    
    // TODO: Implement actual LLM testing logic
    // For now, return mock response
    const response: TestLLMResponse = {
      success: true,
      modelId: body.modelId,
      available: true,
      responseTime: 1500,
      testResponse: 'OK'
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('LLM test error:', error);

    const apiError: APIError = {
      success: false,
      error: {
        code: 'TEST_ERROR',
        message: error instanceof Error ? error.message : 'Failed to test LLM model',
        timestamp: new Date().toISOString(),
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}
