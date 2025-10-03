'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, Download, RefreshCcw } from 'lucide-react';
import {
  fastApiClient,
  FallbackReportResponse,
  MissingSectionResponse,
  ReportSectionResponse,
} from '@/lib/api/fastapi-client';

interface ReportTaskFallbackProps {
  planId: string;
  className?: string;
}

const downloadStringAsFile = (content: string, filename: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

export const ReportTaskFallback: React.FC<ReportTaskFallbackProps> = ({ planId, className = '' }) => {
  const [report, setReport] = useState<FallbackReportResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    if (!planId) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await fastApiClient.getFallbackReport(planId);
      setReport(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load fallback report.';
      setError(message);
      setReport(null);
    } finally {
      setIsLoading(false);
    }
  }, [planId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const recoveredSectionCount = useMemo(() => {
    if (!report) {
      return 0;
    }
    return report.sections.length;
  }, [report]);

  const missingSectionCount = report?.missing_sections.length ?? 0;

  const handleDownloadHtml = () => {
    if (!report) {
      return;
    }
    downloadStringAsFile(report.assembled_html, `${planId}-fallback-report.html`, 'text/html');
  };

  const handleDownloadMissingJson = () => {
    if (!report) {
      return;
    }
    const payload = JSON.stringify(report.missing_sections, null, 2);
    downloadStringAsFile(payload, `${planId}-missing-sections.json`, 'application/json');
  };

  const renderMissingSections = (missing: MissingSectionResponse[]) => {
    if (missing.length === 0) {
      return <p className="text-sm text-green-600">All expected sections were recovered from the database.</p>;
    }

    return (
      <ul className="space-y-2">
        {missing.map((item) => (
          <li key={item.filename} className="flex items-start justify-between rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm">
            <div className="flex-1 pr-3">
              <div className="font-medium text-yellow-900">{item.stage ?? 'Unknown stage'}</div>
              <div className="text-yellow-800">{item.filename}</div>
              <div className="text-xs text-yellow-700 mt-0.5">{item.reason}</div>
            </div>
            <AlertTriangle className="h-4 w-4 text-yellow-600 mt-1" />
          </li>
        ))}
      </ul>
    );
  };

  const renderSectionList = (sections: ReportSectionResponse[]) => {
    if (sections.length === 0) {
      return <p className="text-sm text-gray-500">No sections recovered yet.</p>;
    }

    return (
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {sections.map((section) => (
          <div key={section.filename} className="rounded-md border border-slate-200 bg-white px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-900 truncate">
                {section.stage ?? section.filename}
              </span>
              <Badge variant="secondary" className="text-xs uppercase">
                {section.content_type}
              </Badge>
            </div>
            <div className="text-xs text-slate-500 truncate mt-1">{section.filename}</div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <Card className={`border-blue-200 bg-gradient-to-r from-blue-50 via-white to-purple-50 ${className}`}>
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center justify-between text-xl">
          <span>Recovered Report Assembly</span>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="text-xs">
              Completion {report ? `${report.completion_percentage.toFixed(2)}%` : '—'}
            </Badge>
            <Badge variant="secondary" className="text-xs">
              {recoveredSectionCount} sections
            </Badge>
          </div>
        </CardTitle>
        <CardDescription>
          Build a fallback report directly from <code className="rounded bg-slate-900 px-1 py-0.5 text-xs text-white">plan_content</code> when Luigi fails to assemble <code className="rounded bg-slate-900 px-1 py-0.5 text-xs text-white">029-report.html</code>.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" size="sm" onClick={loadReport} disabled={isLoading}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </Button>
          <Button variant="default" size="sm" onClick={handleDownloadHtml} disabled={!report || isLoading}>
            <Download className="mr-2 h-4 w-4" />
            Download HTML
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDownloadMissingJson} disabled={!report || missingSectionCount === 0 || isLoading}>
            <Download className="mr-2 h-4 w-4" />
            Missing Sections JSON
          </Button>
          {report?.generated_at && (
            <span className="text-xs text-slate-500">
              Generated at {new Date(report.generated_at).toLocaleString()}
            </span>
          )}
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {!error && !isLoading && report && (
          <>
            <section>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">Missing Sections ({missingSectionCount})</h3>
              {renderMissingSections(report.missing_sections)}
            </section>

            <section>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">Recovered Sections ({recoveredSectionCount})</h3>
              {renderSectionList(report.sections)}
            </section>

            <section className="space-y-2">
              <h3 className="text-sm font-semibold text-slate-700">Preview</h3>
              <div className="rounded-lg border border-slate-200 shadow-inner overflow-hidden bg-white">
                <iframe
                  title="Recovered Plan Report"
                  srcDoc={report.assembled_html}
                  sandbox=""
                  className="h-[480px] w-full border-0"
                />
              </div>
            </section>
          </>
        )}

        {isLoading && (
          <div className="text-sm text-slate-500">Loading fallback report...</div>
        )}
      </CardContent>
    </Card>
  );
};
