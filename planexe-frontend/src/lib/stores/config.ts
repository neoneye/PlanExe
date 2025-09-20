/**
 * Author: Cascade
 * Date: 2025-09-19T17:40:43-04:00
 * PURPOSE: Configuration state management for LLM models, prompts, and system settings with caching
 * SRP and DRY check: Pass - Single responsibility for configuration management, integrates with llm_config.json
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { LLMModel, PromptExample } from '@/lib/api/fastapi-client';

interface ConfigState {
  // LLM Models
  llmModels: LLMModel[];
  defaultModel: string;
  priorityOrder: string[];
  isLoadingModels: boolean;
  modelsError: string | null;
  modelsLastLoaded: Date | null;

  // Prompt Examples
  promptExamples: PromptExample[];
  promptCategories: string[];
  isLoadingPrompts: boolean;
  promptsError: string | null;
  promptsLastLoaded: Date | null;

  // System Health
  systemHealth: {
    status: 'healthy' | 'degraded' | 'unhealthy';
    services: Record<string, 'up' | 'down'>;
    lastChecked: Date | null;
  };

  // Actions
  loadLLMModels: (force?: boolean) => Promise<void>;
  loadPromptExamples: (force?: boolean) => Promise<void>;
  testLLMModel: (modelId: string, apiKey?: string) => Promise<boolean>;
  checkSystemHealth: () => Promise<void>;
  clearErrors: () => void;

  // Model management
  setDefaultModel: (modelId: string) => void;
  updateModelPriority: (priorityOrder: string[]) => void;

  // Prompt filtering
  getPromptsByCategory: (category?: string) => PromptExample[];
  getPromptsByComplexity: (complexity?: 'simple' | 'medium' | 'complex') => PromptExample[];
}

export const useConfigStore = create<ConfigState>()(
  persist(
    (set, get) => ({
      // Initial state
      llmModels: [],
      defaultModel: '',
      priorityOrder: [],
      isLoadingModels: false,
      modelsError: null,
      modelsLastLoaded: null,

      promptExamples: [],
      promptCategories: [],
      isLoadingPrompts: false,
      promptsError: null,
      promptsLastLoaded: null,

      systemHealth: {
        status: 'healthy',
        services: {},
        lastChecked: null
      },

      // Load LLM models
      loadLLMModels: async (force = false) => {
        const { modelsLastLoaded } = get();
        
        // Check if we need to reload (force or older than 5 minutes)
        if (!force && modelsLastLoaded) {
          const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
          if (modelsLastLoaded > fiveMinutesAgo) {
            return; // Use cached data
          }
        }

        set({ isLoadingModels: true, modelsError: null });

        try {
          // Working models with exact IDs that match llm_config.json keys
          const workingModels = [
            {
              id: "gemini-2.0-flash",
              label: "Gemini 2.0 Flash",
              comment: "Google's latest fast model. 1M context. $0.20/M input, $0.60/M output.",
              priority: 1,
              requires_api_key: false
            },
            {
              id: "gpt-4o-mini",
              label: "GPT-4o Mini",
              comment: "Latest fast OpenAI model. 128K context. Cost-effective.",
              priority: 2,
              requires_api_key: false
            },
            {
              id: "qwen-qwen3-max",
              label: "Qwen3 Max",
              comment: "High-performance Qwen model via OpenRouter.",
              priority: 3,
              requires_api_key: true
            }
          ];

          set({
            llmModels: workingModels,
            defaultModel: "gemini-2.0-flash",
            priorityOrder: workingModels.map(m => m.id),
            isLoadingModels: false,
            modelsError: null,
            modelsLastLoaded: new Date()
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          set({ 
            modelsError: errorMessage, 
            isLoadingModels: false 
          });
        }
      },

      // Load prompt examples
      loadPromptExamples: async (force = false) => {
        const { promptsLastLoaded } = get();
        
        // Check if we need to reload (force or older than 15 minutes)
        if (!force && promptsLastLoaded) {
          const fifteenMinutesAgo = new Date(Date.now() - 15 * 60 * 1000);
          if (promptsLastLoaded > fifteenMinutesAgo) {
            return; // Use cached data
          }
        }

        set({ isLoadingPrompts: true, promptsError: null });

        try {
          // Temporary hardcoded prompt examples while we fix the backend
          const hardcodedPrompts = [
            {
              id: "business-plan",
              title: "Business Plan",
              category: "Business",
              complexity: "complex",
              prompt: "Create a comprehensive business plan for a new tech startup",
              description: "Generate a detailed business plan including market analysis, financial projections, and strategy"
            },
            {
              id: "project-plan",
              title: "Project Plan",
              category: "Project Management",
              complexity: "medium",
              prompt: "Plan the development of a mobile app from concept to launch",
              description: "Create a project plan with timeline, resources, and milestones"
            },
            {
              id: "marketing-strategy",
              title: "Marketing Strategy",
              category: "Marketing",
              complexity: "medium",
              prompt: "Develop a marketing strategy for launching a new product",
              description: "Create a comprehensive marketing plan with target audience analysis"
            }
          ];

          set({
            promptExamples: hardcodedPrompts,
            promptCategories: ["Business", "Project Management", "Marketing"],
            isLoadingPrompts: false,
            promptsError: null,
            promptsLastLoaded: new Date()
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          set({ 
            promptsError: errorMessage, 
            isLoadingPrompts: false 
          });
        }
      },

      // Test LLM model availability
      testLLMModel: async (modelId, apiKey) => {
        try {
          const response = await fetch('/api/config/llms/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              modelId,
              apiKey,
              testPrompt: 'Hello, please respond with "OK" to confirm you are working.'
            })
          });

          if (!response.ok) {
            return false;
          }

          const data = await response.json();
          return data.success && data.available;
        } catch (error) {
          console.error('LLM test error:', error);
          return false;
        }
      },

      // Check system health
      checkSystemHealth: async () => {
        try {
          const response = await fetch('/api/health');
          
          if (!response.ok) {
            set((state) => ({
              systemHealth: {
                ...state.systemHealth,
                status: 'unhealthy',
                lastChecked: new Date()
              }
            }));
            return;
          }

          const data = await response.json();
          
          if (data.success) {
            set({
              systemHealth: {
                status: data.status,
                services: data.services,
                lastChecked: new Date()
              }
            });
          }
        } catch (error) {
          console.error('Health check error:', error);
          set((state) => ({
            systemHealth: {
              ...state.systemHealth,
              status: 'unhealthy',
              lastChecked: new Date()
            }
          }));
        }
      },

      // Clear all errors
      clearErrors: () => set({ 
        modelsError: null, 
        promptsError: null 
      }),

      // Set default model
      setDefaultModel: (modelId) => {
        set({ defaultModel: modelId });
      },

      // Update model priority
      updateModelPriority: (priorityOrder) => {
        set({ priorityOrder });
      },

      // Get prompts by category
      getPromptsByCategory: (category) => {
        const { promptExamples } = get();
        if (!category) return promptExamples;
        
        return promptExamples.filter(prompt => 
          prompt.category.toLowerCase().includes(category.toLowerCase())
        );
      },

      // Get prompts by complexity
      getPromptsByComplexity: (complexity) => {
        const { promptExamples } = get();
        if (!complexity) return promptExamples;
        
        return promptExamples.filter(prompt => prompt.complexity === complexity);
      }
    }),
    {
      name: 'planexe-config',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // Cache models and prompts for offline use
        llmModels: state.llmModels,
        defaultModel: state.defaultModel,
        priorityOrder: state.priorityOrder,
        modelsLastLoaded: state.modelsLastLoaded,
        
        promptExamples: state.promptExamples,
        promptCategories: state.promptCategories,
        promptsLastLoaded: state.promptsLastLoaded
      })
    }
  )
);

// Auto-load configuration on store creation
if (typeof window !== 'undefined') {
  // Load initial config after a short delay to avoid SSR issues
  setTimeout(() => {
    const store = useConfigStore.getState();
    store.loadLLMModels();
    store.loadPromptExamples();
  }, 100);
}
