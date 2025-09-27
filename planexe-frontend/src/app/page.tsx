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
import { Zap, Brain, Target, Users, FileText, Activity, Sparkles } from 'lucide-react';
import { PlanForm } from '@/components/planning/PlanForm';
import { ProgressMonitor } from '@/components/monitoring/ProgressMonitor';
import { FileManager } from '@/components/files/FileManager';
import { PlansQueue } from '@/components/PlansQueue';
import { PipelineDetails } from '@/components/PipelineDetails';
import { useSessionStore } from '@/lib/stores/session';
import { useConfigStore } from '@/lib/stores/config';
import { CreatePlanRequest, fastApiClient } from '@/lib/api/fastapi-client';

export default function Home() {
  // Session store available but not used in this component
  // const { session, createSession, loadSession } = useSessionStore();
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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <header className="bg-white/90 backdrop-blur-sm border-b border-gray-200 px-6 py-6 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center">
                <Brain className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  PlanExe
                </h1>
                <p className="text-sm text-gray-600 font-medium">AI-Powered Strategic Planning System</p>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {activePlanId && (
              <div className="flex items-center space-x-2">
                <Activity className="h-4 w-4 text-blue-600 animate-pulse" />
                <Badge variant="default" className="bg-blue-600 hover:bg-blue-700 animate-pulse">
                  PLANNING IN PROGRESS
                </Badge>
              </div>
            )}
            <Badge variant="outline" className="text-xs">
              v1.0.0
            </Badge>
          </div>
        </div>
      </header>

      {/* Hero Section - only show when no active plan */}
      {!activePlanId && (
        <section className="relative overflow-hidden">
          <div className="max-w-7xl mx-auto px-6 py-16">
            <div className="text-center space-y-8">
              <div className="space-y-4">
                <h2 className="text-5xl font-bold text-gray-900 leading-tight">
                  Transform Ideas Into
                  <span className="block bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                    Actionable Plans
                  </span>
                </h2>
                <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
                  Our AI-powered Luigi pipeline analyzes your ideas through 61 sophisticated tasks,
                  creating comprehensive strategic plans with detailed analysis, resource planning, and implementation roadmaps.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 max-w-4xl mx-auto">
                <Card className="flex flex-col items-center p-6 bg-white/60 backdrop-blur-sm border border-gray-200 hover:shadow-lg transition-all duration-200">
                  <Target className="h-12 w-12 text-blue-600 mb-4" />
                  <CardTitle className="text-lg mb-2">Strategic Analysis</CardTitle>
                  <p className="text-sm text-gray-600 text-center">Deep analysis of goals, constraints, and success factors</p>
                </Card>
                <Card className="flex flex-col items-center p-6 bg-white/60 backdrop-blur-sm border border-gray-200 hover:shadow-lg transition-all duration-200">
                  <Users className="h-12 w-12 text-purple-600 mb-4" />
                  <CardTitle className="text-lg mb-2">Resource Planning</CardTitle>
                  <p className="text-sm text-gray-600 text-center">Team structure, budgets, and timeline optimization</p>
                </Card>
                <Card className="flex flex-col items-center p-6 bg-white/60 backdrop-blur-sm border border-gray-200 hover:shadow-lg transition-all duration-200">
                  <FileText className="h-12 w-12 text-green-600 mb-4" />
                  <CardTitle className="text-lg mb-2">Implementation</CardTitle>
                  <p className="text-sm text-gray-600 text-center">Step-by-step execution with dependencies and milestones</p>
                </Card>
                <Card className="flex flex-col items-center p-6 bg-white/60 backdrop-blur-sm border border-gray-200 hover:shadow-lg transition-all duration-200">
                  <Sparkles className="h-12 w-12 text-orange-600 mb-4" />
                  <CardTitle className="text-lg mb-2">AI-Powered</CardTitle>
                  <p className="text-sm text-gray-600 text-center">Luigi pipeline with 61 interconnected analysis tasks</p>
                </Card>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Tabs defaultValue="create" className="w-full">
          <TabsList className="grid w-full grid-cols-5 bg-white/80 backdrop-blur-sm p-1 rounded-xl shadow-lg border border-gray-200">
            <TabsTrigger value="create" className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-purple-500 data-[state=active]:text-white flex items-center space-x-2">
              <Zap className="h-4 w-4" />
              <span>Create Plan</span>
            </TabsTrigger>
            <TabsTrigger value="queue" className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-purple-500 data-[state=active]:text-white flex items-center space-x-2">
              <FileText className="h-4 w-4" />
              <span>Plans Queue</span>
            </TabsTrigger>
            <TabsTrigger value="monitor" disabled={!activePlanId} className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-purple-500 data-[state=active]:text-white flex items-center space-x-2">
              <Activity className="h-4 w-4" />
              <span>Monitor Progress</span>
            </TabsTrigger>
            <TabsTrigger value="details" disabled={!activePlanId} className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-purple-500 data-[state=active]:text-white flex items-center space-x-2">
              <Target className="h-4 w-4" />
              <span>Details</span>
            </TabsTrigger>
            <TabsTrigger value="files" disabled={!activePlanId} className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-purple-500 data-[state=active]:text-white flex items-center space-x-2">
              <FileText className="h-4 w-4" />
              <span>View Files</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="create" className="space-y-6">
            {!activePlanId && (
              <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200">
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2 text-2xl">
                    <Brain className="h-6 w-6 text-blue-600" />
                    <span>Create New Strategic Plan</span>
                  </CardTitle>
                  <CardDescription className="text-lg">
                    Describe your project or idea below. Our AI will analyze it through 61 specialized tasks
                    to create a comprehensive strategic plan with detailed analysis, resource planning, and implementation roadmaps.
                  </CardDescription>
                </CardHeader>
              </Card>
            )}

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
