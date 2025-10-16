/**
 * Author: ChatGPT (gpt-5-codex)
 * Date: 2025-10-15
 * PURPOSE: Landing screen for PlanExe that orchestrates plan creation, surfaces system health, and links into the recovery workspace.
 * SRP and DRY check: Pass - this file owns only landing-page layout/orchestration while delegating form logic and queues to shared components.
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Brain, LayoutGrid, Rocket, Sparkles } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { PlanForm } from '@/components/planning/PlanForm';
import { PlansQueue } from '@/components/PlansQueue';
import { useConfigStore } from '@/lib/stores/config';
import { CreatePlanRequest, fastApiClient } from '@/lib/api/fastapi-client';

const HomePage: React.FC = () => {
  const router = useRouter();
  const { llmModels, promptExamples, modelsError, isLoadingModels, loadLLMModels, loadPromptExamples } = useConfigStore();
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadLLMModels();
    loadPromptExamples();
  }, [loadLLMModels, loadPromptExamples]);

  const handlePlanSubmit = async (planData: CreatePlanRequest) => {
    setIsCreating(true);
    setError(null);
    try {
      console.log('[PlanExe] Creating plan with data:', planData);
      const plan = await fastApiClient.createPlan(planData);
      console.log('[PlanExe] Plan created successfully:', plan);
      console.log('[PlanExe] Navigating to workspace with plan_id:', plan.plan_id);
      
      // Navigate to workspace (recovery route) - use window.location for guaranteed navigation
      const workspaceUrl = `/recovery?planId=${encodeURIComponent(plan.plan_id)}`;
      console.log('[PlanExe] Workspace URL:', workspaceUrl);
      
      // Use window.location to ensure navigation happens
      // Next.js router.push() can sometimes be prevented by form submission
      window.location.href = workspaceUrl;
    } catch (err) {
      console.error('[PlanExe] Plan creation failed:', err);
      const message = err instanceof Error ? err.message : 'Failed to create plan.';
      setError(message);
    } finally {
      setIsCreating(false);
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
            <span className="hidden sm:inline">Workspace build</span>
            <Badge variant="outline" className="border-slate-200 font-semibold uppercase tracking-wide">v1.0.0</Badge>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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

          <Card className="border-slate-200 sm:col-span-2 lg:col-span-1">
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
        </section>

        <section className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
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
                isSubmitting={isCreating}
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
        </section>
      </main>
    </div>
  );
};

export default HomePage;