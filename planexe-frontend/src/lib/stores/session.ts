/**
 * Author: Cascade
 * Date: 2025-09-19T17:40:43-04:00
 * PURPOSE: Session state management with localStorage persistence for user sessions and preferences
 * SRP and DRY check: Pass - Single responsibility for session state, integrates with API session routes
 */

import React from 'react';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { UserSession, PlanHistoryItem } from '@/lib/types/pipeline';

interface SessionState {
  // Session data
  session: UserSession | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  createSession: (preferences?: Record<string, any>) => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  updateSession: (updates: Partial<UserSession>) => Promise<void>;
  endSession: () => Promise<void>;
  clearError: () => void;

  // Plan history
  addToHistory: (plan: PlanHistoryItem) => void;
  updatePlanInHistory: (planId: string, updates: Partial<PlanHistoryItem>) => void;
  removePlanFromHistory: (planId: string) => void;

  // Current plan tracking
  setCurrentPlan: (planId: string | null) => void;

  // Settings management
  updateSettings: (settings: Partial<UserSession['settings']>) => void;
  updatePreferences: (preferences: Partial<UserSession['preferences']>) => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      // Initial state
      session: null,
      isLoading: false,
      error: null,

      // Create new session
      createSession: async (preferences) => {
        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch('/api/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              deviceId: generateDeviceId(),
              preferences: preferences || {}
            })
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error?.message || 'Failed to create session');
          }

          const data = await response.json();
          
          if (data.success) {
            set({ 
              session: data.session, 
              isLoading: false,
              error: null
            });
          } else {
            throw new Error('Session creation failed');
          }
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          set({ error: errorMessage, isLoading: false });
        }
      },

      // Load existing session
      loadSession: async (sessionId) => {
        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch(`/api/session?sessionId=${sessionId}`);
          
          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error?.message || 'Failed to load session');
          }

          const data = await response.json();
          
          if (data.success && data.session) {
            set({ 
              session: data.session, 
              isLoading: false,
              error: null
            });
          } else {
            throw new Error('Session not found or expired');
          }
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          set({ error: errorMessage, isLoading: false });
          
          // If session load fails, create a new session
          await get().createSession();
        }
      },

      // Update session
      updateSession: async (updates) => {
        const { session } = get();
        if (!session) return;

        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch('/api/session', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              sessionId: session.sessionId,
              ...updates
            })
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error?.message || 'Failed to update session');
          }

          const data = await response.json();
          
          if (data.success) {
            set({ 
              session: data.session, 
              isLoading: false,
              error: null
            });
          }
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          set({ error: errorMessage, isLoading: false });
        }
      },

      // End session
      endSession: async () => {
        const { session } = get();
        if (!session) return;

        try {
          await fetch(`/api/session?sessionId=${session.sessionId}`, {
            method: 'DELETE'
          });
        } catch (error) {
          console.error('Failed to end session:', error);
        }

        set({ session: null, error: null });
      },

      // Clear error
      clearError: () => set({ error: null }),

      // Plan history management
      addToHistory: (plan) => {
        const { session } = get();
        if (!session) return;

        const updatedHistory = [plan, ...session.planHistory.slice(0, 49)]; // Keep last 50
        const updatedSession = {
          ...session,
          planHistory: updatedHistory
        };

        set({ session: updatedSession });
        
        // Update on server
        get().updateSession({ planHistory: updatedHistory });
      },

      updatePlanInHistory: (planId, updates) => {
        const { session } = get();
        if (!session) return;

        const updatedHistory = session.planHistory.map(plan =>
          plan.planId === planId ? { ...plan, ...updates } : plan
        );

        const updatedSession = {
          ...session,
          planHistory: updatedHistory
        };

        set({ session: updatedSession });
        get().updateSession({ planHistory: updatedHistory });
      },

      removePlanFromHistory: (planId) => {
        const { session } = get();
        if (!session) return;

        const updatedHistory = session.planHistory.filter(plan => plan.planId !== planId);
        const updatedSession = {
          ...session,
          planHistory: updatedHistory
        };

        set({ session: updatedSession });
        get().updateSession({ planHistory: updatedHistory });
      },

      // Current plan tracking
      setCurrentPlan: (planId) => {
        get().updateSession({ currentPlanId: planId || undefined });
      },

      // Settings management
      updateSettings: (settings) => {
        const { session } = get();
        if (!session) return;

        const updatedSettings = { ...session.settings, ...settings };
        get().updateSession({ settings: updatedSettings });
      },

      updatePreferences: (preferences) => {
        const { session } = get();
        if (!session) return;

        const updatedPreferences = { ...session.preferences, ...preferences };
        get().updateSession({ preferences: updatedPreferences });
      }
    }),
    {
      name: 'planexe-session',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        session: state.session ? {
          ...state.session,
          // Don't persist sensitive data
          currentPlanId: state.session.currentPlanId,
          planHistory: state.session.planHistory,
          settings: state.session.settings,
          preferences: state.session.preferences
        } : null
      })
    }
  )
);

// Helper function to generate device ID
function generateDeviceId(): string {
  const stored = localStorage.getItem('planexe-device-id');
  if (stored) return stored;
  
  const deviceId = `device_${Date.now()}_${Math.random().toString(36).substring(2)}`;
  localStorage.setItem('planexe-device-id', deviceId);
  return deviceId;
}

// Session initialization hook
export function useSessionInit() {
  const { session, createSession, loadSession } = useSessionStore();

  React.useEffect(() => {
    const initSession = async () => {
      if (session?.sessionId) {
        // Try to load existing session
        await loadSession(session.sessionId);
      } else {
        // Create new session
        await createSession();
      }
    };

    initSession();
  }, []);

  return session;
}
