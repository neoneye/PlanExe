/**
 * Author: Cascade
 * Date: 2025-09-19T17:40:43-04:00
 * PURPOSE: Planning state management for plan creation, progress tracking, and Luigi pipeline integration
 * SRP and DRY check: Pass - Single responsibility for planning workflow state, integrates with Luigi pipeline
 */

import { create } from 'zustand';
import { CreatePlanRequest, PlanResponse } from '@/lib/api/fastapi-client';
import { fastApiClient as apiClient } from '@/lib/api/fastapi-client';
import { PipelineProgressState, PipelineStatus } from '@/lib/types/pipeline';
import { useSessionStore } from './session';

interface ActivePlan {
  planId: string;
  runId: string;
  runDir: string;
  status: PipelineStatus;
  progress: PipelineProgressState | null;
  startTime: Date;
  lastUpdated: Date;
}

interface PlanningState {
  // Current plan
  activePlan: ActivePlan | null;
  isCreating: boolean;
  isMonitoring: boolean;
  error: string | null;

  // Progress polling
  progressInterval: NodeJS.Timeout | null;

  // Actions
  createPlan: (request: CreatePlanRequest) => Promise<void>;
  stopPlan: (reason?: string) => Promise<void>;
  resumePlan: (fromTask?: string) => Promise<void>;
  clearPlan: () => void;
  
  // Progress monitoring
  startProgressMonitoring: (planId: string) => void;
  stopProgressMonitoring: () => void;
  fetchProgress: (planId: string) => Promise<void>;
  
  // Error handling
  clearError: () => void;
}

export const usePlanningStore = create<PlanningState>((set, get) => ({
  // Initial state
  activePlan: null,
  isCreating: false,
  isMonitoring: false,
  error: null,
  progressInterval: null,

  // Create new plan
  createPlan: async (request) => {
    set({ isCreating: true, error: null });

    try {
      // Use new API client - returns PlanResponse directly
      const data: PlanResponse = await apiClient.createPlan(request);

      // API returns data directly, no success wrapper
      const activePlan: ActivePlan = {
        planId: data.plan_id,  // Use snake_case from API
        runId: data.plan_id,    // Use plan_id as runId
        runDir: data.output_dir || '',  // Use output_dir from API
        status: data.status as PipelineStatus,
        progress: null,
        startTime: new Date(data.created_at),
        lastUpdated: new Date()
      };

      set({
        activePlan,
        isCreating: false,
        error: null
      });

      // Add to session history
      const sessionStore = useSessionStore.getState();
      sessionStore.setCurrentPlan(data.plan_id);
      sessionStore.addToHistory({
        planId: data.plan_id,
        title: 'Untitled Plan',  // Title not in request anymore
        status: data.status as PipelineStatus,
        createdAt: new Date(data.created_at),
        fileCount: 0,
        promptPreview: request.prompt.substring(0, 100) + (request.prompt.length > 100 ? '...' : '')
      });

      // Start progress monitoring
      get().startProgressMonitoring(data.plan_id);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      set({ error: errorMessage, isCreating: false });
    }
  },

  // Stop plan execution
  stopPlan: async (_reason) => {
    const { activePlan } = get();
    if (!activePlan) return;

    try {
      const response = await fetch(`/api/plans/${activePlan.planId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error?.message || 'Failed to stop plan');
      }

      const _data = await response.json();

      // API returns message directly
      set((state) => ({
        activePlan: state.activePlan ? {
          ...state.activePlan,
          status: 'cancelled' as PipelineStatus,
          lastUpdated: new Date()
        } : null
      }));

      // Update session history
      const sessionStore = useSessionStore.getState();
      sessionStore.updatePlanInHistory(activePlan.planId, {
        status: 'cancelled' as PipelineStatus,
        completedAt: new Date()
      });

      // Stop monitoring
      get().stopProgressMonitoring();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      set({ error: errorMessage });
    }
  },

  // Resume stopped plan
  resumePlan: async (fromTask) => {
    const { activePlan } = get();
    if (!activePlan) return;

    try {
      // Note: Resume endpoint not implemented in backend yet
      const response = await fetch(`/api/plans/${activePlan.planId}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fromTask })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error?.message || 'Failed to resume plan');
      }

      const data = await response.json();
      
      if (data.success) {
        set((state) => ({
          activePlan: state.activePlan ? {
            ...state.activePlan,
            status: 'running',
            lastUpdated: new Date()
          } : null
        }));

        // Update session history
        const sessionStore = useSessionStore.getState();
        sessionStore.updatePlanInHistory(activePlan.planId, {
          status: 'running'
        });

        // Restart monitoring
        get().startProgressMonitoring(activePlan.planId);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      set({ error: errorMessage });
    }
  },

  // Clear current plan
  clearPlan: () => {
    get().stopProgressMonitoring();
    
    const sessionStore = useSessionStore.getState();
    sessionStore.setCurrentPlan(null);
    
    set({ 
      activePlan: null, 
      error: null 
    });
  },

  // Start progress monitoring
  startProgressMonitoring: (planId) => {
    const { progressInterval } = get();
    
    // Clear existing interval
    if (progressInterval) {
      clearInterval(progressInterval);
    }

    set({ isMonitoring: true });

    // Initial fetch
    get().fetchProgress(planId);

    // Set up polling interval (every 3 seconds)
    const interval = setInterval(() => {
      const { activePlan } = get();
      if (activePlan && ['running', 'created'].includes(activePlan.status)) {
        get().fetchProgress(planId);
      } else {
        // Stop monitoring if plan is no longer active
        get().stopProgressMonitoring();
      }
    }, 3000);

    set({ progressInterval: interval });
  },

  // Stop progress monitoring
  stopProgressMonitoring: () => {
    const { progressInterval } = get();
    
    if (progressInterval) {
      clearInterval(progressInterval);
    }

    set({ 
      progressInterval: null,
      isMonitoring: false 
    });
  },

  // Fetch current progress
  fetchProgress: async (planId) => {
    try {
      const response = await fetch(`/api/plans/${planId}`);
      
      if (!response.ok) {
        // Don't throw error for progress fetch failures - just log
        console.error('Progress fetch failed:', response.statusText);
        return;
      }

      const data: PlanResponse = await response.json();

      // API returns PlanResponse directly - create simplified progress state
      const progress: PipelineProgressState = {
        status: data.status as PipelineStatus,
        phases: [], // Will be populated by SSE updates
        overallPercentage: data.progress_percentage,
        completedTasks: Math.floor(data.progress_percentage / 2), // Approximate
        totalTasks: 61, // Luigi pipeline has 61 tasks
        error: data.error_message || null,
        duration: 0, // Will be calculated from startTime
      };

      set((state) => ({
        activePlan: state.activePlan ? {
          ...state.activePlan,
          progress: progress,
          status: data.status as PipelineStatus,
          lastUpdated: new Date()
        } : null
      }));

      // Update session history with status
      const sessionStore = useSessionStore.getState();
      sessionStore.updatePlanInHistory(planId, {
        status: data.status as PipelineStatus,
        fileCount: 0, // Will be updated when files are available
        ...(data.status === 'completed' && {
          completedAt: new Date()
        })
      });

      // If completed, stop monitoring
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        get().stopProgressMonitoring();
      }
    } catch (error) {
      console.error('Progress fetch error:', error);
      // Don't update error state for progress fetch failures
    }
  },

  // Clear error
  clearError: () => set({ error: null })
}));

// Cleanup on window unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    const { stopProgressMonitoring } = usePlanningStore.getState();
    stopProgressMonitoring();
  });
}
