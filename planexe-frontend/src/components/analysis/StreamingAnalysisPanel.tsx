/**
 * Author: ChatGPT gpt-5-codex
 * Date: 2025-10-27T00:00:00Z
 * PURPOSE: High-level panel that wires streaming hooks into reusable UI blocks for
 *          analysis modals, providing status controls and aggregated reasoning buffers.
 * SRP and DRY check: Pass - encapsulates modal presentation, delegates streaming
 *          orchestration to hooks.
 */

import { useCallback, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, CheckCircle2, Loader2, Play, StopCircle } from 'lucide-react';
import { StreamingMessageBox } from '@/components/analysis/StreamingMessageBox';
import {
  useAnalysisResults,
  AnalysisStreamHandlers,
  AnalysisStreamCompletePayload,
} from '@/lib/streaming/analysis-streaming';

interface StreamingAnalysisPanelProps {
  taskId: string;
  modelKey: string;
  prompt: string;
  context?: string;
  systemPrompt?: string;
  stage?: string;
  metadata?: Record<string, unknown>;
  heading?: string;
  description?: string;
  onPersist?: (payload: AnalysisStreamCompletePayload) => void | Promise<void>;
}

const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  idle: { label: 'Idle', className: 'border-slate-200 bg-slate-100 text-slate-700' },
  connecting: { label: 'Connecting', className: 'border-amber-200 bg-amber-100 text-amber-800' },
  running: { label: 'Streaming', className: 'border-sky-200 bg-sky-100 text-sky-800' },
  completed: { label: 'Completed', className: 'border-emerald-200 bg-emerald-100 text-emerald-800' },
  error: { label: 'Error', className: 'border-red-200 bg-red-100 text-red-800' },
};

export const StreamingAnalysisPanel = ({
  taskId,
  modelKey,
  prompt,
  context,
  systemPrompt,
  stage,
  metadata,
  heading = 'Streaming Analysis',
  description = 'Execute reasoning-rich analysis runs with live deltas.',
  onPersist,
}: StreamingAnalysisPanelProps) => {
  const { state, supportsStreaming, startAnalysis, cancelAnalysis } = useAnalysisResults({
    taskId,
    modelKey,
    systemPrompt,
    stage,
    metadata,
    onPersist,
  });

  const [actionError, setActionError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  const statusMeta = useMemo(() => STATUS_STYLES[state.status] ?? STATUS_STYLES.idle, [state.status]);

  const handleStart = useCallback(async () => {
    if (!supportsStreaming || state.status === 'running' || state.status === 'connecting') {
      return;
    }
    setActionError(null);
    setIsStarting(true);
    const handlers: AnalysisStreamHandlers = {
      onError: (payload) => {
        if (typeof payload.error === 'string') {
          setActionError(payload.error);
        } else {
          setActionError('Streaming error encountered.');
        }
      },
    };
    try {
      await startAnalysis({ prompt, context }, handlers);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to start streaming analysis.';
      setActionError(message);
    } finally {
      setIsStarting(false);
    }
  }, [supportsStreaming, state.status, startAnalysis, prompt, context, metadata]);

  const handleCancel = useCallback(() => {
    cancelAnalysis(true);
  }, [cancelAnalysis]);

  const tokenUsage = state.summary?.responseSummary.tokenUsage as Record<string, unknown> | undefined;

  return (
    <Card className="border-slate-200">
      <CardHeader className="gap-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="text-lg text-slate-800">{heading}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
          <Badge variant="outline" className={statusMeta.className}>
            {statusMeta.label}
          </Badge>
        </div>
        {!supportsStreaming ? (
          <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
            <AlertCircle className="h-4 w-4" />
            <span>Streaming is disabled for this environment.</span>
          </div>
        ) : null}
        {actionError ? (
          <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-800">
            <AlertCircle className="h-4 w-4" />
            <span>{actionError}</span>
          </div>
        ) : null}
        {state.error && state.error !== actionError ? (
          <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-800">
            <AlertCircle className="h-4 w-4" />
            <span>{state.error}</span>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            onClick={handleStart}
            disabled={!supportsStreaming || isStarting || state.status === 'running' || state.status === 'connecting'}
          >
            {isStarting || state.status === 'connecting' ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            Start analysis
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleCancel}
            disabled={state.status !== 'running'}
          >
            <StopCircle className="mr-2 h-4 w-4" />
            Cancel
          </Button>
          {state.summary ? (
            <Badge variant="outline" className="flex items-center gap-1 border-emerald-200 bg-emerald-50 text-emerald-700">
              <CheckCircle2 className="h-3 w-3" />
              Saved
            </Badge>
          ) : null}
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <StreamingMessageBox variant="text" title="Live response">
            {state.textBuffer || 'Awaiting tokens…'}
          </StreamingMessageBox>
          <StreamingMessageBox variant="reasoning" title="Reasoning">
            {state.reasoningBuffer || 'No reasoning received yet.'}
          </StreamingMessageBox>
          <StreamingMessageBox
            variant="json"
            title="Structured deltas"
            footer={
              state.jsonChunks.length > 0
                ? `${state.jsonChunks.length} chunk${state.jsonChunks.length === 1 ? '' : 's'} captured`
                : 'Waiting for structured output…'
            }
          >
            {state.jsonChunks.length > 0 ? state.jsonChunks[state.jsonChunks.length - 1] : '—'}
          </StreamingMessageBox>
        </div>

        {state.summary ? (
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
            <div className="font-semibold text-slate-800">Final summary</div>
            <div className="mt-1 space-y-1">
              {state.summary.responseSummary.analysis ? (
                <p>
                  <span className="font-semibold">Analysis:</span> {state.summary.responseSummary.analysis}
                </p>
              ) : null}
              {state.summary.responseSummary.reasoning ? (
                <p>
                  <span className="font-semibold">Reasoning:</span> {state.summary.responseSummary.reasoning}
                </p>
              ) : null}
              {tokenUsage ? (
                <p>
                  <span className="font-semibold">Token usage:</span> {JSON.stringify(tokenUsage)}
                </p>
              ) : null}
              {state.summary.responseSummary.responseId ? (
                <p>
                  <span className="font-semibold">Response ID:</span> {state.summary.responseSummary.responseId}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};
