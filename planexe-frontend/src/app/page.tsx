/**
 * Author: Cascade
 * Date: 2025-09-19T17:40:43-04:00
 * PURPOSE: Main PlanExe application page that integrates all components and provides the complete planning interface
 * SRP and DRY check: Pass - Single responsibility for main app layout, orchestrates UI components and state
 */

'use client';

import React, { useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { PlanForm } from '@/components/planning/PlanForm';
import { ProgressMonitor } from '@/components/monitoring/ProgressMonitor';
import { FileManager } from '@/components/files/FileManager';
import { PlansQueue } from '@/components/PlansQueue';
import { PipelineDetails } from '@/components/PipelineDetails';
import { useSessionStore } from '@/lib/stores/session';
import { useConfigStore } from '@/lib/stores/config';
import { CreatePlanRequest, fastApiClient } from '@/lib/api/fastapi-client';

export default function Home() {
  const { session, createSession, loadSession } = useSessionStore();
  const { llmModels, promptExamples, loadLLMModels, loadPromptExamples } = useConfigStore();
  
  // Simple, local state management instead of the complex planning store
  const [activePlanId, setActivePlanId] = React.useState<string | null>(null);
  const [isCreating, setIsCreating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Initialize config store
  useEffect(() => {
    const init = async () => {
      await loadLLMModels();
      await loadPromptExamples();
    };
    init();
  }, [loadLLMModels, loadPromptExamples]);

  const handlePlanSubmit = async (planData: CreatePlanRequest) => {
    setIsCreating(true);
    setError(null);
    try {
      const newPlan = await fastApiClient.createPlan(planData);
      setActivePlanId(newPlan.plan_id);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create plan.';
      setError(errorMessage);
      console.error('Plan creation error:', errorMessage);
    } finally {
      setIsCreating(false);
    }
  };

  const handlePlanComplete = () => {
    console.log('Plan completed successfully!');
    // Switch to the "details" tab so the user can see outputs instead of hiding the UI
    const detailsTab = document.querySelector('[data-radix-value="details"]') as HTMLElement | null;
    detailsTab?.click();
    // Do NOT clear activePlanId automatically; let the user decide what to do next.
  };

  const handlePlanError = (error: string) => {
    setError(error);
    console.error('Plan error:', error);
  };

  const handleStop = () => {
    console.log('Plan stopped by user.');
    setActivePlanId(null); // Return to the form
  };

  const handlePlanRetry = (planId: string) => {
    setActivePlanId(planId);
    // Use a timeout to ensure the tab is enabled before clicking
    setTimeout(() => {
      const monitorTab = document.querySelector('[data-radix-value="monitor"]') as HTMLElement | null;
      monitorTab?.click();
    }, 100);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">PlanExe</h1>
            <p className="text-sm text-gray-600">AI-Powered Strategic Planning System</p>
          </div>
          <div className="flex items-center space-x-4">
            {activePlanId && (
              <Badge variant={'default'}>
                PLANNING
              </Badge>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Tabs defaultValue="create" className="w-full">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="create">Create Plan</TabsTrigger>
            <TabsTrigger value="queue">Plans Queue</TabsTrigger>
            <TabsTrigger value="monitor" disabled={!activePlanId}>
              Monitor Progress
            </TabsTrigger>
            <TabsTrigger value="details" disabled={!activePlanId}>
              Details
            </TabsTrigger>
            <TabsTrigger value="files" disabled={!activePlanId}>
              View Files
            </TabsTrigger>
          </TabsList>

          <TabsContent value="create" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Create New Strategic Plan</CardTitle>
                <CardDescription>
                  Use AI to generate comprehensive strategic plans with detailed analysis, 
                  resource planning, and implementation roadmaps.
                </CardDescription>
              </CardHeader>
            </Card>

            {/* Show Progress Monitor if plan is active, otherwise show form */}
            {activePlanId ? (
              <ProgressMonitor
                planId={activePlanId}
                onComplete={handlePlanComplete}
                onError={handlePlanError}
                onStop={handleStop}
              />
            ) : (
              /* Plan Creation Form */
              <PlanForm
                onSubmit={handlePlanSubmit}
                isSubmitting={isCreating}
                llmModels={llmModels}
                promptExamples={promptExamples}
              />
            )}

            {/* Display error if any */}
            {error && (
                <Card className="border-red-500">
                    <CardHeader>
                        <CardTitle className="text-red-600">An Error Occurred</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-red-600">{error}</p>
                        <button onClick={() => setError(null)} className="mt-4 text-sm text-blue-500">Dismiss</button>
                    </CardContent>
                </Card>
            )}

          </TabsContent>

          <TabsContent value="queue" className="space-y-6">
            <PlansQueue
              className="w-full"
              onPlanSelect={(planId) => {
                setActivePlanId(planId);
              }}
              onPlanRetry={handlePlanRetry}
            />
          </TabsContent>

          <TabsContent value="monitor" className="space-y-6">
            {activePlanId ? (
              <ProgressMonitor
                planId={activePlanId}
                onComplete={handlePlanComplete}
                onError={handlePlanError}
                onStop={handleStop}
              />
            ) : (
              <Card>
                <CardContent className="text-center py-12">
                  <p className="text-gray-500">No active plan to monitor</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="details" className="space-y-6">
            {activePlanId ? (
              <PipelineDetails
                planId={activePlanId}
                className="w-full"
              />
            ) : (
              <Card>
                <CardContent className="text-center py-12">
                  <p className="text-muted-foreground">No active plan selected</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="files" className="space-y-6">
            {activePlanId ? (
              <FileManager
                planId={activePlanId}
              />
            ) : (
              <Card>
                <CardContent className="text-center py-12">
                  <p className="text-gray-500">No active plan files to view</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
