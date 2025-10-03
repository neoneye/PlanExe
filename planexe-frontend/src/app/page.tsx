/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Minimal entry page that collects a prompt and routes users directly to the Workspace for plan assembly.
 * SRP and DRY check: Pass - Focused on initial UX; delegates monitoring/recovery to the Workspace route.
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Brain, Sparkles } from 'lucide-react';
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
      const plan = await fastApiClient.createPlan(planData);
      router.push(`/recovery?planId=${encodeURIComponent(plan.plan_id)}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create plan.';
      setError(message);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <header className="bg-white/90 backdrop-blur-sm border-b border-gray-200 px-6 py-6 sticky top-0 z-40">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
              <Brain className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                PlanExe
              </h1>
              <p className="text-sm text-gray-600 font-medium">AI-powered strategic planning workspace</p>
            </div>
          </div>
          <Badge variant="outline" className="text-xs">v1.0.0</Badge>
        </div>
      </header>

      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
        <section className="flex flex-col gap-6">
          <Card className="border-blue-200 bg-blue-50/70">
            <CardHeader className="space-y-2">
              <CardTitle className="flex items-center gap-2 text-2xl text-blue-900">
                <Sparkles className="h-5 w-5 text-blue-600" />
                Describe your plan idea
              </CardTitle>
              <CardDescription className="text-base text-blue-800">
                Submit a prompt and jump straight into the Workspace to watch the pipeline populate artefacts in real time.
              </CardDescription>
            </CardHeader>
            <CardContent>
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
                  <CardHeader>
                    <CardTitle className="text-red-700 text-sm">Plan creation failed</CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm text-red-700">{error}</CardContent>
                </Card>
              )}
            </CardContent>
          </Card>
        </section>

        <section>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Plans</CardTitle>
              <CardDescription>
                Open any plan in the Workspace to inspect artefacts, fallback reports, and stage progress — even if it is pending or failed.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PlansQueue
                className="w-full"
                onPlanSelect={(planId) => router.push(`/recovery?planId=${encodeURIComponent(planId)}`)}
              />
            </CardContent>
          </Card>
        </section>
      </main>
    </div>
  );
};

export default HomePage;