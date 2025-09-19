/**
 * Author: Cascade
 * Date: 2025-09-19T17:40:43-04:00
 * PURPOSE: Planning state management for plan creation, progress tracking, and Luigi pipeline integration
 * SRP and DRY check: Pass - Single responsibility for planning workflow state, integrates with Luigi pipeline
 */

import { create } from 'zustand';
import { CreatePlanRequest, CreatePlanResponse } from '@/lib/types/api';
import { PipelineProgress, PipelineStatus } from '@/lib/types/pipeline';
import { useSessionStore } from './session';

interface ActivePlan {
  planId: string;
  runId: string;
  runDir: string;
  status: PipelineStatus;
  progress: PipelineProgress | null;
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
      const response = await fetch('/api/plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error?.message || 'Failed to create plan');
      }

      const data: CreatePlanResponse = await response.json();

      if (data.success) {
        const activePlan: ActivePlan = {
          planId: data.planId,
          runId: data.runId,
          runDir: data.runDir,
          status: data.status,
          progress: null,
          startTime: new Date(),
          lastUpdated: new Date()
        };

        set({ 
          activePlan,
          isCreating: false,
          error: null
        });

        // Add to session history
        const sessionStore = useSessionStore.getState();
        sessionStore.setCurrentPlan(data.planId);
        sessionStore.addToHistory({
          planId: data.planId,
          title: request.title || 'Untitled Plan',
          status: data.status,
          createdAt: new Date(),
          fileCount: 0,
          promptPreview: request.prompt.substring(0, 100) + (request.prompt.length > 100 ? '...' : '')
        });

        // Start progress monitoring
        get().startProgressMonitoring(data.planId);
      } else {
        throw new Error('Plan creation failed');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      set({ error: errorMessage, isCreating: false });
    }
  },

  // Stop plan execution
  stopPlan: async (reason) => {
    const { activePlan } = get();
    if (!activePlan) return;

    try {
      const response = await fetch(`/api/plans/${activePlan.planId}/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || 'User requested stop' })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error?.message || 'Failed to stop plan');
      }

      const data = await response.json();
      
      if (data.success) {
        set((state) => ({
          activePlan: state.activePlan ? {
            ...state.activePlan,
            status: data.finalStatus,
            lastUpdated: new Date()
          } : null
        }));

        // Update session history
        const sessionStore = useSessionStore.getState();
        sessionStore.updatePlanInHistory(activePlan.planId, {
          status: data.finalStatus,
          completedAt: new Date()
        });

        // Stop monitoring
        get().stopProgressMonitoring();
      }
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
      const response = await fetch(`/api/plans/${planId}/progress`);
      
      if (!response.ok) {
        // Don't throw error for progress fetch failures - just log
        console.error('Progress fetch failed:', response.statusText);
        return;
      }

      const data = await response.json();
      
      if (data.success) {
        set((state) => ({
          activePlan: state.activePlan ? {
            ...state.activePlan,
            progress: data.progress,
            status: data.progress.status,
            lastUpdated: new Date()
          } : null
        }));

        // Update session history with file count and status
        const sessionStore = useSessionStore.getState();
        sessionStore.updatePlanInHistory(planId, {
          status: data.progress.status,
          fileCount: data.progress.filesCompleted,
          ...(data.progress.status === 'completed' && {
            completedAt: new Date(),
            duration: data.progress.duration
          })
        });

        // If completed, stop monitoring
        if (['completed', 'failed', 'stopped'].includes(data.progress.status)) {
          get().stopProgressMonitoring();
        }
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
