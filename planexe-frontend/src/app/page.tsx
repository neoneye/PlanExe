/**
 * Author: gpt-5-codex
 * Date: 2025-02-15
 * PURPOSE: Immersive landing page that presents a conversation-first planning flow on a single screen.
 *          Introduces a new twilight-inspired visual language, inline model selector, and streamlined
 *          hero copy while maintaining the existing conversation modal workflow for plan creation.
 * SRP and DRY check: Pass - Coordinates plan intake UI, background fetches, and conversation modal state.
 */

'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { SimplifiedPlanInput } from '@/components/planning/SimplifiedPlanInput';
import { ConversationModal } from '@/components/planning/ConversationModal';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useConfigStore } from '@/lib/stores/config';
import { CreatePlanRequest, fastApiClient } from '@/lib/api/fastapi-client';
import { ConversationFinalizeResult } from '@/lib/conversation/useResponsesConversation';

// Prefer backend-provided models; only use these if the API returns none
const FALLBACK_MODEL_OPTIONS = [
  { id: 'gpt-4o-mini-2024-07-18', label: 'gpt-4o-mini' },
  { id: 'gpt-4.1-mini', label: 'gpt-4.1-mini' },
];
const PRIMARY_FALLBACK_MODEL_ID = FALLBACK_MODEL_OPTIONS[0].id;

const HomePage: React.FC = () => {
  const { llmModels, loadLLMModels, loadPromptExamples } = useConfigStore();
  const [isCreating, setIsCreating] = useState(false);
  const [isConversationOpen, setIsConversationOpen] = useState(false);
  const [pendingRequest, setPendingRequest] = useState<CreatePlanRequest | null>(null);
  const [conversationSessionKey, setConversationSessionKey] = useState<string | null>(null);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>(FALLBACK_MODEL_OPTIONS[0].id);

  const availableModels = useMemo(() => {
    const deduped = new Map<string, { id: string; label: string }>();

    for (const option of FALLBACK_MODEL_OPTIONS) {
      deduped.set(option.id, option);
    }

    if (llmModels && llmModels.length > 0) {
      const sorted = [...llmModels].sort((a, b) => a.priority - b.priority);
      for (const model of sorted) {
        const label = model.label?.trim().length ? model.label : model.id;
        deduped.set(model.id, { id: model.id, label });
      }
    }

    return Array.from(deduped.values());
  }, [llmModels]);

  useEffect(() => {
    if (availableModels.length === 0) return;

    const hasSelection = availableModels.some((option) => option.id === selectedModel);
    if (!hasSelection) {
      // Prefer API-provided first-priority model when available
      const apiPreferred = llmModels && llmModels.length > 0
        ? [...llmModels].sort((a, b) => a.priority - b.priority)[0]?.id
        : undefined;
      const preferred =
        (apiPreferred && availableModels.find((o) => o.id === apiPreferred)) ||
        availableModels.find((option) => option.id === PRIMARY_FALLBACK_MODEL_ID) ||
        availableModels[0];

      if (preferred) setSelectedModel(preferred.id);
    }
  }, [availableModels, selectedModel, llmModels]);

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
    const fallbackModel = availableModels.find((option) => option.id === PRIMARY_FALLBACK_MODEL_ID)?.id;
    const modelForRequest = selectedModel || fallbackModel || availableModels[0]?.id || FALLBACK_MODEL_OPTIONS[0].id;
    const planData: CreatePlanRequest = {
      prompt,
      llm_model: modelForRequest,
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
        enriched_intake: result.enrichedIntake ?? undefined,
      };

      console.log('[PlanExe] Finalising plan with enriched prompt.');
      if (result.enrichedIntake) {
        console.log('[PlanExe] Enriched intake data available:', result.enrichedIntake);
      }
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
    <div className="relative min-h-screen overflow-hidden bg-[#030712] text-slate-100">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute -left-40 top-[-10%] h-[420px] w-[420px] rounded-full
          bg-[radial-gradient(circle_at_center,_rgba(168,85,247,0.35),_rgba(3,7,18,0.05))] blur-3xl"
        />
        <div
          className="absolute bottom-[-20%] right-[-10%] h-[500px] w-[500px] rounded-full
          bg-[radial-gradient(circle_at_center,_rgba(34,211,238,0.3),_rgba(3,7,18,0.05))] blur-3xl"
        />
        <div
          className="absolute left-1/2 top-1/2 h-[280px] w-[280px] -translate-x-1/2 -translate-y-1/2 rounded-full
          bg-[conic-gradient(from_120deg,_rgba(14,165,233,0.2),_rgba(236,72,153,0.15),_rgba(14,165,233,0.05))] blur-2xl"
        />
      </div>

      <main className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 py-16">
        <div className="w-full max-w-6xl">
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,_1.2fr)_minmax(0,_1fr)]">
            <section className="space-y-6 text-balance">
              <div className="inline-flex items-center gap-3 text-xs uppercase tracking-[0.3em] text-cyan-200/70">
                <span className="h-px w-10 bg-cyan-200/60" aria-hidden="true" />
                PlanExe Conversations
              </div>
              <div className="space-y-4">
                <h1 className="text-4xl font-semibold leading-tight text-white md:text-5xl">
                  Launch thoughtful execution plans in one continuous dialogue.
                </h1>
                <p className="max-w-xl text-base text-slate-300 md:text-lg">
                  Share the idea you are shaping and our copilot will guide a short back-and-forth, capture the
                  important context, and hand back a plan ready to move.
                </p>
              </div>

              <dl className="grid gap-4 text-sm text-slate-300 sm:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-lg shadow-cyan-500/10 backdrop-blur">
                  <dt className="text-xs uppercase tracking-[0.2em] text-cyan-200/80">Dialogue First</dt>
                  <dd className="mt-2 text-base font-medium text-white">Stay in the flow, no extra screens.</dd>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-lg shadow-fuchsia-500/10 backdrop-blur">
                  <dt className="text-xs uppercase tracking-[0.2em] text-fuchsia-200/80">Adaptive Insight</dt>
                  <dd className="mt-2 text-base font-medium text-white">Clarifying questions tailor every brief.</dd>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-lg shadow-emerald-500/10 backdrop-blur">
                  <dt className="text-xs uppercase tracking-[0.2em] text-emerald-200/80">Ready to Execute</dt>
                  <dd className="mt-2 text-base font-medium text-white">Structured plans export directly to your workspace.</dd>
                </div>
              </dl>
            </section>

            <section>
              <Card className="border-white/10 bg-white/10 shadow-2xl shadow-cyan-500/10 backdrop-blur">
                <CardHeader className="space-y-3 pb-2">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <CardTitle className="text-lg font-semibold text-white">Start a new plan</CardTitle>
                      <CardDescription className="text-xs text-slate-300">
                        Choose a model, describe your idea, and the conversation modal opens instantly.
                      </CardDescription>
                    </div>
                    <div className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs font-medium text-slate-200">
                      {latestVersion ? `v${latestVersion}` : '…'}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-300">
                    <Label htmlFor="model-select" className="text-[11px] uppercase tracking-[0.2em] text-slate-200">
                      Model
                    </Label>
                    <Select
                      value={selectedModel}
                      onValueChange={(value) => setSelectedModel(value)}
                    >
                      <SelectTrigger id="model-select" size="sm" className="w-[160px] border-white/20 bg-white/10 text-slate-100">
                        <SelectValue placeholder="Select model" />
                      </SelectTrigger>
                      <SelectContent className="border-white/10 bg-[#0b1220]/90 text-slate-100">
                        {availableModels.map((model) => (
                          <SelectItem key={model.id} value={model.id} className="text-slate-100">
                            {model.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <SimplifiedPlanInput
                    onSubmit={handlePlanSubmit}
                    isSubmitting={isCreating || isFinalizing}
                    autoFocus={true}
                  />

                  {error && (
                    <div className="rounded-xl border border-rose-400/40 bg-rose-500/10 p-3 text-sm text-rose-100">
                      {error}
                    </div>
                  )}
                </CardContent>
              </Card>
            </section>
          </div>
        </div>
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
