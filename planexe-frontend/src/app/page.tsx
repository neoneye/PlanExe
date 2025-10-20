/**
 * Author: Claude Code using Sonnet 4.5
 * Date: 2025-10-20
 * PURPOSE: Redesigned landing page with conversation-first UX. Simplifies the user journey from
 *          8 steps to 3 by hiding complexity behind smart defaults and making the excellent
 *          Responses API conversation system immediately accessible. Uses new HeroSection,
 *          SimplifiedPlanInput, and HowItWorksSection components for a cleaner, more inviting experience.
 * SRP and DRY check: Pass - Orchestrates layout and plan creation flow while delegating
 *          presentation to focused components.
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { HeroSection } from '@/components/planning/HeroSection';
import { SimplifiedPlanInput } from '@/components/planning/SimplifiedPlanInput';
import { HowItWorksSection } from '@/components/planning/HowItWorksSection';
import { ConversationModal } from '@/components/planning/ConversationModal';
import { PlansQueue } from '@/components/PlansQueue';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Clock } from 'lucide-react';
import { useConfigStore } from '@/lib/stores/config';
import { CreatePlanRequest, fastApiClient } from '@/lib/api/fastapi-client';
import { ConversationFinalizeResult } from '@/lib/conversation/useResponsesConversation';

const HomePage: React.FC = () => {
  const router = useRouter();
  const { llmModels, loadLLMModels, loadPromptExamples } = useConfigStore();
  const [isCreating, setIsCreating] = useState(false);
  const [isConversationOpen, setIsConversationOpen] = useState(false);
  const [pendingRequest, setPendingRequest] = useState<CreatePlanRequest | null>(null);
  const [conversationSessionKey, setConversationSessionKey] = useState<string | null>(null);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestVersion, setLatestVersion] = useState<string | null>(null);

  useEffect(() => {
    loadLLMModels();
    loadPromptExamples();
  }, [loadLLMModels, loadPromptExamples]);

  useEffect(() => {
    let canceled = false;

    const fetchLatestVersion = async () => {
      try {
        const health = await fastApiClient.getHealth();
        if (canceled) {
          return;
        }

        const nextVersion = health.planexe_version ?? health.version ?? null;
        if (nextVersion) {
          setLatestVersion(nextVersion);
        }
      } catch (err) {
        // Silently fail - version badge will show "..." if fetch fails
        console.warn('Failed to fetch version:', err);
      }
    };

    fetchLatestVersion();

    const refreshInterval = window.setInterval(fetchLatestVersion, 15 * 60 * 1000);

    return () => {
      canceled = true;
      window.clearInterval(refreshInterval);
    };
  }, []);

  const generateConversationSessionKey = () => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return `conversation-${crypto.randomUUID()}`;
    }
    return `conversation-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  };

  const handlePlanSubmit = async (prompt: string) => {
    // Apply smart defaults for simplified UX
    const defaultModel = llmModels && llmModels.length > 0
      ? (llmModels.find((m) => m.priority === 1)?.id || llmModels[0].id)
      : 'gpt-5-mini-2025-08-07';

    const planData: CreatePlanRequest = {
      prompt,
      llm_model: defaultModel,
      speed_vs_detail: 'all_details_but_slow', // Default to comprehensive plan
    };

    setIsCreating(true);
    setError(null);
    setConversationSessionKey(generateConversationSessionKey());
    setPendingRequest(planData);
    setIsConversationOpen(true);
  };

  const resetConversationState = () => {
    setIsConversationOpen(false);
    setPendingRequest(null);
    setConversationSessionKey(null);
    setIsCreating(false);
  };

  const handleConversationClose = () => {
    resetConversationState();
  };

  const handleConversationFinalize = async (
    result: ConversationFinalizeResult,
  ): Promise<void> => {
    if (!pendingRequest) {
      throw new Error('No pending request to finalise.');
    }

    setIsFinalizing(true);
    setError(null);

    try {
      const payload: CreatePlanRequest = {
        ...pendingRequest,
        prompt: result.enrichedPrompt,
      };

      console.log('[PlanExe] Finalising plan with enriched prompt.');
      const plan = await fastApiClient.createPlan(payload);
      console.log('[PlanExe] Plan created successfully:', plan);
      resetConversationState();

      const workspaceUrl = `/recovery?planId=${encodeURIComponent(plan.plan_id)}`;
      window.location.href = workspaceUrl;
    } catch (err) {
      console.error('[PlanExe] Plan creation failed during conversation finalisation:', err);
      const message = err instanceof Error ? err.message : 'Failed to create plan.';
      setError(message);
      throw err instanceof Error ? err : new Error(message);
    } finally {
      setIsFinalizing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Hero Section */}
      <HeroSection version={latestVersion} />

      {/* Main Content */}
      <main className="mx-auto w-full max-w-4xl px-6 pb-20">
        {/* Simplified Plan Input */}
        <section className="mb-16">
          <SimplifiedPlanInput
            onSubmit={handlePlanSubmit}
            isSubmitting={isCreating || isFinalizing}
            autoFocus={true}
          />

          {/* Error display */}
          {error && (
            <Card className="mt-6 border-red-300 bg-red-50 shadow-lg">
              <CardHeader className="py-4">
                <CardTitle className="text-sm font-semibold text-red-700">
                  Plan creation failed
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-red-700">{error}</CardContent>
            </Card>
          )}
        </section>

        {/* How It Works Section */}
        <HowItWorksSection />

        {/* Recent Plans Section */}
        <section className="mt-16">
          <Card className="border-slate-200 bg-white/80 shadow-lg backdrop-blur">
            <CardHeader className="space-y-1 pb-4">
              <CardTitle className="flex items-center gap-2 text-lg text-slate-800">
                <Clock className="h-5 w-5 text-indigo-600" />
                Recent Plans
              </CardTitle>
              <CardDescription className="text-sm text-slate-500">
                Pick up where you left off or review previous planning sessions.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <PlansQueue
                className="w-full"
                onPlanSelect={(planId) =>
                  router.push(`/recovery?planId=${encodeURIComponent(planId)}`)
                }
              />
            </CardContent>
          </Card>
        </section>
      </main>

      {/* Conversation Modal */}
      <ConversationModal
        isOpen={isConversationOpen}
        request={pendingRequest}
        sessionKey={conversationSessionKey}
        onClose={handleConversationClose}
        onFinalize={handleConversationFinalize}
        isFinalizing={isFinalizing}
      />
    </div>
  );
};

export default HomePage;
