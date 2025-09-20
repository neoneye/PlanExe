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
import { useSessionStore } from '@/lib/stores/session';
import { useConfigStore } from '@/lib/stores/config';
import { usePlanningStore } from '@/lib/stores/planning';

export default function Home() {
  const { session, createSession, loadSession } = useSessionStore();
  const { llmModels, promptExamples, loadLLMModels, loadPromptExamples } = useConfigStore();
  const { activePlan, createPlan, clearPlan, isCreating } = usePlanningStore();

  // Initialize stores
  useEffect(() => {
    const init = async () => {
      // Skip session management for now - focus on core functionality

      // Load configuration
      await loadLLMModels();
      await loadPromptExamples();
    };

    init();
  }, []);

  const handlePlanSubmit = async (planData: any) => {
    await createPlan(planData);
  };

  const handlePlanComplete = () => {
    // Plan completed - could show success message
    console.log('Plan completed successfully!');
  };

  const handlePlanError = (error: string) => {
    console.error('Plan error:', error);
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
            {session && (
              <div className="text-sm text-gray-600">
                Session: {session.sessionId.substring(0, 8)}...
              </div>
            )}
            {activePlan && (
              <Badge variant={activePlan.status === 'running' ? 'default' : 'secondary'}>
                {activePlan.status.toUpperCase()}
              </Badge>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Tabs defaultValue="create" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="create">Create Plan</TabsTrigger>
            <TabsTrigger value="monitor" disabled={!activePlan}>
              Monitor Progress
            </TabsTrigger>
            <TabsTrigger value="files" disabled={!activePlan}>
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

            {/* Plan Creation Form */}
            <PlanForm
              onSubmit={handlePlanSubmit}
              isSubmitting={isCreating}
              llmModels={llmModels}
              promptExamples={promptExamples}
            />

            {/* Recent Plans */}
            {session?.planHistory && session.planHistory.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Recent Plans</CardTitle>
                  <CardDescription>Your planning history</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {session.planHistory.slice(0, 5).map((plan) => (
                      <div key={plan.planId} className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
                        <div>
                          <div className="font-medium">{plan.title}</div>
                          <div className="text-sm text-gray-600">{plan.promptPreview}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            Created {plan.createdAt.toLocaleDateString()} • {plan.fileCount} files
                          </div>
                        </div>
                        <Badge variant={plan.status === 'completed' ? 'default' : 'secondary'}>
                          {plan.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="monitor" className="space-y-6">
            {activePlan ? (
              <ProgressMonitor
                planId={activePlan.planId}
                onComplete={handlePlanComplete}
                onError={handlePlanError}
                onStop={clearPlan}
              />
            ) : (
              <Card>
                <CardContent className="text-center py-12">
                  <p className="text-gray-500">No active plan to monitor</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="files" className="space-y-6">
            {activePlan ? (
              <FileManager
                planId={activePlan.planId}
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
