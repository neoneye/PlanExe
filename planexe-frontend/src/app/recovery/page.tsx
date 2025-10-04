/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Self-service recovery workspace for assembling plans from database artefacts with live status, report toggle, and file explorer.
 * SRP and DRY check: Pass - Orchestrates workspace UX; delegates artefact rendering to FileManager.
 */
'use client';

import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { FileManager } from '@/components/files/FileManager';
import { PipelineDetails } from '@/components/PipelineDetails';
import {
  fastApiClient,
  PlanArtefact,
  PlanArtefactListResponse,
  PlanResponse,
} from '@/lib/api/fastapi-client';
import { PlanFile } from '@/lib/types/pipeline';
import { ReportTaskFallback } from '@/components/files/ReportTaskFallback';
import { formatDistanceToNow } from 'date-fns';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Home,
  RefreshCcw,
  XCircle,
} from 'lucide-react';

interface StatusDisplay {
  label: string;
  badgeClass: string;
  icon: React.ReactElement;
}

interface StageSummary {
  key: string;
  label: string;
  count: number;
}

const KNOWN_STAGE_ORDER: string[] = [
  'setup',
  'initial_analysis',
  'strategic_planning',
  'scenario_planning',
  'contextual_analysis',
  'assumption_management',
  'project_planning',
  'governance',
  'resource_planning',
  'documentation',
  'work_breakdown',
  'scheduling',
  'reporting',
  'completion',
];

const STAGE_LABELS: Record<string, string> = {
  setup: 'Setup',
  initial_analysis: 'Initial Analysis',
  strategic_planning: 'Strategic Planning',
  scenario_planning: 'Scenario Planning',
  contextual_analysis: 'Contextual Analysis',
  assumption_management: 'Assumption Management',
  project_planning: 'Project Planning',
  governance: 'Governance',
  resource_planning: 'Resource Planning',
  documentation: 'Documentation',
  work_breakdown: 'Work Breakdown',
  scheduling: 'Scheduling',
  reporting: 'Reporting',
  completion: 'Completion',
  unknown: 'Unclassified Stage',
};

const normaliseStageLabel = (stage?: string | null): string => {
  if (!stage) {
    return STAGE_LABELS.unknown;
  }
  return (
    STAGE_LABELS[stage] ??
    stage.replace(/[_-]+/g, ' ').trim().replace(/\b\w/g, (char) => char.toUpperCase())
  );
};

const inferStage = (entry: PlanArtefact): string => entry.stage ?? 'unknown';

const getStatusDisplay = (status: PlanResponse['status']): StatusDisplay => {
  switch (status) {
    case 'completed':
      return {
        label: 'Completed',
        badgeClass: 'border-emerald-200 bg-emerald-50 text-emerald-700',
        icon: <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />,
      };
    case 'running':
      return {
        label: 'Running',
        badgeClass: 'border-blue-200 bg-blue-50 text-blue-700',
        icon: <Activity className="h-4 w-4 text-blue-600" aria-hidden="true" />,
      };
    case 'failed':
      return {
        label: 'Failed',
        badgeClass: 'border-red-200 bg-red-50 text-red-700',
        icon: <XCircle className="h-4 w-4 text-red-600" aria-hidden="true" />,
      };
    case 'cancelled':
      return {
        label: 'Cancelled',
        badgeClass: 'border-slate-200 bg-slate-50 text-slate-700',
        icon: <AlertCircle className="h-4 w-4 text-slate-600" aria-hidden="true" />,
      };
    default:
      return {
        label: 'Pending',
        badgeClass: 'border-amber-200 bg-amber-50 text-amber-700',
        icon: <Clock className="h-4 w-4 text-amber-600" aria-hidden="true" />,
      };
  }
};

const StageTimeline: React.FC<{ stages: StageSummary[] }> = ({ stages }) => (
  <Card className="h-fit">
    <CardHeader>
      <CardTitle className="text-lg">Stage Progress</CardTitle>
      <CardDescription>
        Stages are marked as soon as artefacts land in plan_content.
      </CardDescription>
    </CardHeader>
    <CardContent className="space-y-2">
      {stages.map((stage) => {
        const isComplete = stage.count > 0;
        return (
          <div
            key={stage.key}
            className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2"
          >
            <div className="flex items-center gap-3">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  isComplete ? 'bg-emerald-500' : 'bg-slate-300'
                }`}
                aria-hidden="true"
              />
              <span className="text-sm font-medium text-slate-700">{stage.label}</span>
            </div>
            <span className="text-xs text-slate-500">
              {stage.count} artefact{stage.count === 1 ? '' : 's'}
            </span>
          </div>
        );
      })}
    </CardContent>
  </Card>
);

const ReportPanel: React.FC<{
  planId: string;
  canonicalHtml: string | null;
  canonicalError: string | null;
  fallbackPlanId: string;
  onRefresh: () => void;
  isRefreshing: boolean;
}> = ({ planId, canonicalHtml, canonicalError, fallbackPlanId, onRefresh, isRefreshing }) => {
  const canonicalAvailable = Boolean(canonicalHtml);
  const [activeTab, setActiveTab] = useState<'canonical' | 'fallback'>(
    canonicalAvailable ? 'canonical' : 'fallback'
  );

  useEffect(() => {
    if (!canonicalAvailable) {
      setActiveTab('fallback');
    }
  }, [canonicalAvailable]);

  return (
    <Card>
      <CardHeader className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle className="text-lg">Plan Report</CardTitle>
          <CardDescription>
            Select between canonical output and database-assembled fallback.
          </CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={isRefreshing}>
          {isRefreshing ? 'Refreshing...' : 'Refresh Reports'}
        </Button>
      </CardHeader>
      <CardContent>
        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as 'canonical' | 'fallback')}
        >
          <TabsList>
            <TabsTrigger value="canonical" disabled={!canonicalAvailable}>
              Canonical Report
            </TabsTrigger>
            <TabsTrigger value="fallback">Fallback Report</TabsTrigger>
          </TabsList>
          <TabsContent value="canonical" className="mt-4">
            {canonicalHtml ? (
              <div className="rounded-lg border border-slate-200 shadow-inner overflow-hidden">
                <iframe
                  title={`${planId}-canonical-report`}
                  srcDoc={canonicalHtml}
                  sandbox=""
                  className="h-[520px] w-full border-0"
                />
              </div>
            ) : (
              <Card className="border-amber-200 bg-amber-50">
                <CardContent className="py-6 text-sm text-amber-700">
                  {canonicalError ?? 'Canonical report is not yet available for this plan.'}
                </CardContent>
              </Card>
            )}
          </TabsContent>
          <TabsContent value="fallback" className="mt-4">
            <Card className="border-slate-200">
              <CardContent className="p-0">
                <ReportTaskFallback planId={fallbackPlanId} className="border-0" />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};

const WorkspaceContent: React.FC = () => {
  const searchParams = useSearchParams();
  const planIdFromQuery = searchParams.get('planId')?.trim() ?? '';
  const planId = useMemo(() => planIdFromQuery.replace(/\s+/g, ''), [planIdFromQuery]);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [artefacts, setArtefacts] = useState<PlanFile[]>([]);
  const [artefactError, setArtefactError] = useState<string | null>(null);
  const [artefactLoading, setArtefactLoading] = useState(false);
  const [artefactLastUpdated, setArtefactLastUpdated] = useState<Date | null>(null);
  const [canonicalHtml, setCanonicalHtml] = useState<string | null>(null);
  const [canonicalError, setCanonicalError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  const loadPlan = useCallback(async () => {
    if (!planId) {
      setPlan(null);
      return;
    }
    setPlanLoading(true);
    setPlanError(null);
    try {
      const response = await fastApiClient.getPlan(planId);
      setPlan(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load plan metadata.';
      setPlanError(message);
      setPlan(null);
    } finally {
      setPlanLoading(false);
    }
  }, [planId]);

  const fetchArtefacts = useCallback(async () => {
    if (!planId) {
      setArtefacts([]);
      return;
    }
    setArtefactLoading(true);
    setArtefactError(null);
    try {
      const response: PlanArtefactListResponse = await fastApiClient.getPlanArtefacts(
        planId
      );
      const mapped: PlanFile[] = response.artefacts.map((entry) => ({
        filename: entry.filename,
        stage: entry.stage ?? 'unknown',
        contentType: entry.content_type,
        sizeBytes: entry.size_bytes ?? 0,
        createdAt: entry.created_at,
        description: entry.description ?? entry.filename,
        taskName: entry.task_name ?? entry.stage ?? entry.filename,
        order: entry.order ?? Number.MAX_SAFE_INTEGER,
      }));
      mapped.sort((a, b) => {
        const orderDiff = (a.order ?? 9999) - (b.order ?? 9999);
        if (orderDiff !== 0) {
          return orderDiff;
        }
        return a.filename.localeCompare(b.filename);
      });
      setArtefacts(mapped);
      setArtefactLastUpdated(new Date());
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load artefacts.';
      setArtefactError(message);
      setArtefacts([]);
    } finally {
      setArtefactLoading(false);
    }
  }, [planId]);

  const fetchReports = useCallback(async () => {
    if (!planId) {
      setCanonicalHtml(null);
      setCanonicalError(null);
      return;
    }
    setReportLoading(true);
    setCanonicalError(null);
    try {
      const blob = await fastApiClient.downloadReport(planId);
      const text = await blob.text();
      setCanonicalHtml(text);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Canonical report unavailable.';
      setCanonicalHtml(null);
      setCanonicalError(message);
    } finally {
      setReportLoading(false);
    }
  }, [planId]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  useEffect(() => {
    fetchArtefacts();
    if (!planId) {
      return () => undefined;
    }
    const interval = window.setInterval(fetchArtefacts, 5000);
    return () => window.clearInterval(interval);
  }, [planId, fetchArtefacts]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const stageSummary: StageSummary[] = useMemo(() => {
    const counts = new Map<string, number>();
    artefacts.forEach((file) => {
      const stageKey = inferStage({
        filename: file.filename,
        content_type: file.contentType,
        stage: file.stage,
        size_bytes: file.sizeBytes,
        created_at: file.createdAt,
        description: file.description ?? null,
        task_name: file.taskName ?? null,
        order: file.order ?? null,
      });
      counts.set(stageKey, (counts.get(stageKey) ?? 0) + 1);
    });

    const orderedStages = KNOWN_STAGE_ORDER.filter((stage) => counts.has(stage));
    const extraStages = Array.from(counts.keys())
      .filter((stage) => !KNOWN_STAGE_ORDER.includes(stage) && stage !== 'unknown')
      .sort();
    const includeUnknown = counts.has('unknown');

    const combined = [...orderedStages, ...extraStages, ...(includeUnknown ? ['unknown'] : [])];

    return combined.map((stage) => ({
      key: stage,
      label: normaliseStageLabel(stage),
      count: counts.get(stage) ?? 0,
    }));
  }, [artefacts]);

  if (!planId) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
        <header className="border-b border-slate-200 bg-white/90 backdrop-blur px-6 py-4">
          <div className="mx-auto flex max-w-6xl items-center justify-between">
            <h1 className="text-2xl font-semibold text-slate-800">Plan Recovery Workspace</h1>
            <Button asChild variant="outline" size="sm">
              <Link href="/">
                <Home className="mr-2 h-4 w-4" aria-hidden="true" />
                Back to Dashboard
              </Link>
            </Button>
          </div>
        </header>
        <main className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
          <Card className="border-amber-200 bg-amber-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-amber-800">
                <AlertCircle className="h-5 w-5" aria-hidden="true" />
                Missing planId
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-amber-900">
              Provide a plan identifier in the query string, for example{' '}
              <span className="font-mono">/recovery?planId=PlanExe_1234abcd</span>.
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  const statusDisplay = plan ? getStatusDisplay(plan.status) : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-800">Plan Recovery Workspace</h1>
            <p className="text-sm text-slate-500">
              Inspect reports, artefacts, and progress driven directly by plan_content.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/">
                <Home className="mr-2 h-4 w-4" aria-hidden="true" />
                Back to Dashboard
              </Link>
            </Button>
            <Button variant="default" size="sm" onClick={loadPlan} disabled={planLoading}>
              {planLoading ? 'Refreshing...' : 'Refresh Plan'}
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
        <Card>
          <CardHeader className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <span className="font-mono text-base">{planId}</span>
                {statusDisplay && (
                  <Badge className={`${statusDisplay.badgeClass} flex items-center gap-1`}>
                    {statusDisplay.icon}
                    {statusDisplay.label}
                  </Badge>
                )}
              </CardTitle>
              {plan?.prompt && (
                <CardDescription className="mt-1 max-w-3xl text-sm text-slate-600">{plan.prompt}</CardDescription>
              )}
            </div>
            <div className="flex flex-col items-end text-sm text-slate-500">
              {plan ? (
                <>
                  <span>Progress: {plan.progress_percentage}%</span>
                  {plan.progress_message && <span className="mt-1 text-xs text-slate-400">{plan.progress_message}</span>}
                  <span className="mt-1 text-xs">Created {new Date(plan.created_at).toLocaleString()}</span>
                </>
              ) : planError ? (
                <span className="text-xs text-red-600">{planError}</span>
              ) : null}
            </div>
          </CardHeader>
        </Card>
        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
          <StageTimeline stages={stageSummary} />
          <div className="space-y-6">
            <ReportPanel
              planId={planId}
              canonicalHtml={canonicalHtml}
              canonicalError={canonicalError}
              fallbackPlanId={planId}
              onRefresh={() => {
                fetchReports();
                fetchArtefacts();
              }}
              isRefreshing={reportLoading || artefactLoading}
            />
            <FileManager
              planId={planId}
              artefacts={artefacts}
              isLoading={artefactLoading}
              error={artefactError}
              lastUpdated={artefactLastUpdated}
              onRefresh={fetchArtefacts}
            />
            <PipelineDetails planId={planId} />
          </div>
        </div>
      </main>
    </div>
  );
};

const RecoveryPageWrapper: React.FC = () => (
  <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-600">Loading plan workspace...</div>}>
    <WorkspaceContent />
  </Suspense>
);

export default RecoveryPageWrapper;