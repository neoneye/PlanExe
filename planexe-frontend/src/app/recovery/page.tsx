/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Self-service recovery workspace that surfaces fallback report assembly, file browser, and pipeline details for any plan via query string.
 * SRP and DRY check: Pass - Dedicated page for recovery workflows; reuses existing shared components without duplicating logic.
 */
'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ReportTaskFallback } from '@/components/files/ReportTaskFallback';
import { FileManager } from '@/components/files/FileManager';
import { PipelineDetails } from '@/components/PipelineDetails';
import { fastApiClient, PlanResponse } from '@/lib/api/fastapi-client';
import { Activity, AlertCircle, CheckCircle2, Clock, Home, RefreshCcw, XCircle } from 'lucide-react';

interface StatusConfig {
  label: string;
  icon: JSX.Element;
  className: string;
}

const getStatusConfig = (status: PlanResponse['status']): StatusConfig => {
  switch (status) {
    case 'completed':
      return {
        label: 'Completed',
        icon: <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />,
        className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      };
    case 'running':
      return {
        label: 'Running',
        icon: <Activity className="h-4 w-4 text-blue-600" aria-hidden="true" />,
        className: 'border-blue-200 bg-blue-50 text-blue-700',
      };
    case 'failed':
      return {
        label: 'Failed',
        icon: <XCircle className="h-4 w-4 text-red-600" aria-hidden="true" />,
        className: 'border-red-200 bg-red-50 text-red-700',
      };
    case 'cancelled':
      return {
        label: 'Cancelled',
        icon: <AlertCircle className="h-4 w-4 text-slate-600" aria-hidden="true" />,
        className: 'border-slate-200 bg-slate-50 text-slate-700',
      };
    default:
      return {
        label: 'Pending',
        icon: <Clock className="h-4 w-4 text-amber-600" aria-hidden="true" />,
        className: 'border-amber-200 bg-amber-50 text-amber-700',
      };
  }
};

const RecoveryPage = () => {
  const searchParams = useSearchParams();
  const planIdFromQuery = searchParams.get('planId')?.trim() ?? '';
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sanitizedPlanId = useMemo(() => planIdFromQuery.replace(/\s+/g, ''), [planIdFromQuery]);

  const loadPlan = useCallback(async () => {
    if (!sanitizedPlanId) {
      setPlan(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await fastApiClient.getPlan(sanitizedPlanId);
      setPlan(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load plan details.';
      setError(message);
      setPlan(null);
    } finally {
      setIsLoading(false);
    }
  }, [sanitizedPlanId]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  const statusMeta = plan ? getStatusConfig(plan.status) : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-800">Plan Recovery Workspace</h1>
            <p className="text-sm text-slate-500">
              Inspect fallback reports, generated files, and pipeline activity for any plan ID.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/">
                <Home className="mr-2 h-4 w-4" aria-hidden="true" />
                Back to Dashboard
              </Link>
            </Button>
            {sanitizedPlanId && (
              <Button variant="default" size="sm" onClick={loadPlan} disabled={isLoading}>
                <RefreshCcw className="mr-2 h-4 w-4" aria-hidden="true" />
                {isLoading ? 'Refreshing...' : 'Refresh Plan'}
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
        {!sanitizedPlanId && (
          <Card className="border-amber-200 bg-amber-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-amber-800">
                <AlertCircle className="h-5 w-5" aria-hidden="true" />
                Missing planId
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-amber-900">
              Provide a plan identifier in the query string, for example
              <span className="ml-1 font-mono">/recovery?planId=PlanExe_1234abcd</span>.
            </CardContent>
          </Card>
        )}

        {sanitizedPlanId && (
          <Card>
            <CardHeader className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <span className="font-mono text-base">{sanitizedPlanId}</span>
                  {statusMeta && (
                    <Badge className={`${statusMeta.className} flex items-center gap-1`}>
                      {statusMeta.icon}
                      {statusMeta.label}
                    </Badge>
                  )}
                </CardTitle>
                {plan?.prompt && (
                  <CardDescription className="mt-1 max-w-3xl text-sm text-slate-600">
                    {plan.prompt}
                  </CardDescription>
                )}
              </div>
              <div className="flex flex-col items-end text-sm text-slate-500">
                {plan && (
                  <>
                    <span>Progress: {plan.progress_percentage}%</span>
                    {plan.progress_message && (
                      <span className="mt-1 text-xs text-slate-400">{plan.progress_message}</span>
                    )}
                    <span className="mt-1 text-xs">
                      Created {new Date(plan.created_at).toLocaleString()}
                    </span>
                  </>
                )}
              </div>
            </CardHeader>
            {error && (
              <CardContent>
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              </CardContent>
            )}
          </Card>
        )}

        {sanitizedPlanId && !error && (
          <div className="grid grid-cols-1 gap-6">
            <ReportTaskFallback planId={sanitizedPlanId} />
            <FileManager planId={sanitizedPlanId} />
            <PipelineDetails planId={sanitizedPlanId} />
          </div>
        )}
      </main>
    </div>
  );
};

export default RecoveryPage;