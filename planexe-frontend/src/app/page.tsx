/**
 * Author: ChatGPT (gpt-5-codex)
 * Date: 2025-10-23
 * PURPOSE: Landing screen for PlanExe that orchestrates plan creation, surfaces system health, and now syncs the release badge with the CHANGELOG on GitHub.
 * SRP and DRY check: Pass - this file owns only landing-page layout/orchestration while delegating form logic, queues, and data fetching helpers to shared components.
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Brain, LayoutGrid, Rocket, Sparkles } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { PlanForm } from '@/components/planning/PlanForm';
import { ConversationModal } from '@/components/planning/ConversationModal';
import { PlansQueue } from '@/components/PlansQueue';
import { useConfigStore } from '@/lib/stores/config';
import { CreatePlanRequest, fastApiClient } from '@/lib/api/fastapi-client';
import { ConversationFinalizeResult } from '@/lib/conversation/useResponsesConversation';

const CHANGELOG_URL = 'https://github.com/PlanExe/PlanExe/blob/main/CHANGELOG.md';

const HomePage: React.FC = () => {
  const router = useRouter();
  const { llmModels, promptExamples, modelsError, isLoadingModels, loadLLMModels, loadPromptExamples } = useConfigStore();
  const [isCreating, setIsCreating] = useState(false);
  const [isConversationOpen, setIsConversationOpen] = useState(false);
  const [pendingRequest, setPendingRequest] = useState<CreatePlanRequest | null>(null);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [versionError, setVersionError] = useState<string | null>(null);

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
          setVersionError(null);
        } else {
          setVersionError('Health endpoint did not include a version string.');
        }
      } catch (err) {
        if (!canceled) {
          const message = err instanceof Error ? err.message : 'Unknown error fetching PlanExe version.';
          setVersionError(message);
        }
      }
    };

    fetchLatestVersion();

    const refreshInterval = window.setInterval(fetchLatestVersion, 15 * 60 * 1000);

    return () => {
      canceled = true;
      window.clearInterval(refreshInterval);
    };
  }, []);

  const handlePlanSubmit = async (planData: CreatePlanRequest) => {
    setIsCreating(true);
    setError(null);
    setPendingRequest(planData);
    setIsConversationOpen(true);
  };

  const resetConversationState = () => {
    setIsConversationOpen(false);
    setPendingRequest(null);
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

  const modelSummary = (() => {
    if (isLoadingModels) {
      return 'Loading models…';
    }
    if (modelsError) {
      return 'Model load issue';
    }
    if (!llmModels || llmModels.length === 0) {
      return 'No models available';
    }
    return `${llmModels.length} models ready`;
  })();

  const promptSummary = promptExamples && promptExamples.length > 0
    ? `${promptExamples.length} curated prompts`
    : 'Add your own context';

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-sky-600">
              <Brain className="h-5 w-5 text-white" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-2xl font-semibold text-slate-900">PlanExe</h1>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Strategic Planning Control Center</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <a
              href={CHANGELOG_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline text-indigo-600 hover:text-indigo-500"
            >
              Workspace build changelog
            </a>
            <Badge
              variant="outline"
              className="border-slate-200 font-semibold uppercase tracking-wide"
              title={versionError ?? undefined}
            >
              v{latestVersion ?? '…'}
            </Badge>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Main Action Section - Form and Queue */}
        <section className="grid gap-6 lg:grid-cols-2">
          <Card className="border-slate-200">
            <CardHeader className="space-y-1 pb-4">
              <CardTitle className="flex items-center gap-2 text-lg text-slate-800">
                <Sparkles className="h-5 w-5 text-indigo-600" />
                Launch a new plan
              </CardTitle>
              <CardDescription className="text-sm text-slate-500">
                Provide context, pick the model, and we&apos;ll orchestrate the full 60-task pipeline for you.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <PlanForm
                onSubmit={handlePlanSubmit}
                isSubmitting={isCreating || isFinalizing}
                llmModels={llmModels}
                promptExamples={promptExamples}
                modelsError={modelsError}
                isLoadingModels={isLoadingModels}
                loadLLMModels={loadLLMModels}
              />
              {error && (
                <Card className="mt-4 border-red-300 bg-red-50">
                  <CardHeader className="py-3">
                    <CardTitle className="text-sm font-semibold text-red-700">Plan creation failed</CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm text-red-700">{error}</CardContent>
                </Card>
              )}
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card className="border-slate-200">
              <CardHeader className="space-y-1 pb-3">
                <CardTitle className="flex items-center gap-2 text-base text-slate-700">
                  <Rocket className="h-4 w-4 text-indigo-600" />
                  Recent activity
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Pick up where you left off or audit a teammate&apos;s run.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <PlansQueue
                  className="w-full"
                  onPlanSelect={(planId) => router.push(`/recovery?planId=${encodeURIComponent(planId)}`)}
                />
              </CardContent>
            </Card>

            <Card className="border-slate-200">
              <CardHeader className="space-y-1 pb-4">
                <CardTitle className="text-lg text-slate-800">Workspace primer</CardTitle>
                <CardDescription className="text-sm text-slate-500">
                  Orient yourself before the pipeline begins streaming updates.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-0 text-sm text-slate-600">
                <div>
                  <h3 className="font-medium text-slate-700">Timeline &amp; status</h3>
                  <p className="text-xs text-slate-500">Monitor each stage&apos;s completion and retry failed nodes without leaving the run.</p>
                </div>
                <div>
                  <h3 className="font-medium text-slate-700">Reports &amp; artefacts</h3>
                  <p className="text-xs text-slate-500">Download canonical reports, inspect fallback drafts, and review generated files in one place.</p>
                </div>
                <div>
                  <h3 className="font-medium text-slate-700">Live reasoning</h3>
                  <p className="text-xs text-slate-500">Use the console stream to understand decisions and catch blockers early.</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Info Cards Section */}
        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card className="border-slate-200">
            <CardHeader className="space-y-1 pb-3">
              <CardTitle className="flex items-center gap-2 text-base text-slate-700">
                <Sparkles className="h-4 w-4 text-indigo-600" />
                Plan pipeline
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Kick off a plan and jump directly to workspace monitoring when ready.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0 text-sm text-slate-600">
              <p className="font-medium text-slate-700">{modelSummary}</p>
              <p className="mt-1 text-xs text-slate-500">Health updates auto-refresh as models load.</p>
            </CardContent>
          </Card>

          <Card className="border-slate-200">
            <CardHeader className="space-y-1 pb-3">
              <CardTitle className="flex items-center gap-2 text-base text-slate-700">
                <LayoutGrid className="h-4 w-4 text-indigo-600" />
                Prompt library
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Use a curated starting point or craft a focused brief of your own.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0 text-sm text-slate-600">
              <p className="font-medium text-slate-700">{promptSummary}</p>
              <p className="mt-1 text-xs text-slate-500">Switch to Examples to drop in one instantly.</p>
            </CardContent>
          </Card>

          <Card className="border-slate-200">
            <CardHeader className="space-y-1 pb-3">
              <CardTitle className="flex items-center gap-2 text-base text-slate-700">
                <Brain className="h-4 w-4 text-indigo-600" />
                System status
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Live status of models and pipeline infrastructure.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0 text-sm text-slate-600">
              <p className="font-medium text-slate-700">
                {isLoadingModels ? 'Initializing...' : 'All systems operational'}
              </p>
              <p className="mt-1 text-xs text-slate-500">Ready to process your strategic plans.</p>
            </CardContent>
          </Card>
        </section>
      </main>

      <ConversationModal
        isOpen={isConversationOpen}
        request={pendingRequest}
        onClose={handleConversationClose}
        onFinalize={handleConversationFinalize}
        isFinalizing={isFinalizing}
      />
    </div>
  );
};

export default HomePage;
