/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: ASCII-safe artefact browser driven by plan_content metadata supplied via the workspace.
 * SRP and DRY check: Pass - Presentational component for artefact exploration; delegates data fetching to parent.
 */

'use client';

import React, { useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatDistanceToNow } from 'date-fns';
import { PlanFile } from '@/lib/types/pipeline';
import { FileCode2, FileJson, FileSpreadsheet, FileText, FileType } from 'lucide-react';

interface FileManagerProps {
  planId: string;
  artefacts: PlanFile[];
  isLoading: boolean;
  error?: string | null;
  lastUpdated?: Date | null;
  onRefresh?: () => void;
  onPreview?: (file: PlanFile) => void;
  className?: string;
}

const KNOWN_PHASE_ORDER: string[] = [
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

const PHASE_LABELS: Record<string, string> = {
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

const getPhaseLabel = (phase?: string | null): string => {
  // Guard against null, undefined, empty string, or non-string values
  if (!phase || typeof phase !== 'string' || phase.trim() === '') {
    return PHASE_LABELS.unknown;
  }
  const trimmed = phase.trim();
  return PHASE_LABELS[trimmed] ?? trimmed.replace(/[_-]+/g, ' ').trim().replace(/\b\w/g, (char) => char.toUpperCase());
};

const getFileIcon = (type: string): React.ReactElement => {
  const iconClass = 'h-5 w-5 text-blue-500';
  switch (type) {
    case 'json':
      return <FileJson className={iconClass} aria-hidden="true" />;
    case 'md':
      return <FileText className={iconClass} aria-hidden="true" />;
    case 'html':
      return <FileCode2 className={iconClass} aria-hidden="true" />;
    case 'csv':
      return <FileSpreadsheet className={iconClass} aria-hidden="true" />;
    case 'txt':
      return <FileText className={iconClass} aria-hidden="true" />;
    default:
      return <FileType className={iconClass} aria-hidden="true" />;
  }
};

const formatFileSize = (bytes: number): string => {
  if (!bytes) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB'];
  const exponent = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, exponent);
  return `${value.toFixed(1)} ${units[exponent]}`;
};

export const FileManager: React.FC<FileManagerProps> = ({
  planId,
  artefacts,
  isLoading,
  error,
  lastUpdated,
  onRefresh,
  onPreview,
  className = '',
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStage, setSelectedStage] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [isDownloadingZip, setIsDownloadingZip] = useState(false);

  const stageOptions = useMemo(() => {
    const stages = new Set<string>();
    artefacts.forEach((file) => {
      stages.add(file.stage ?? 'unknown');
    });
    const ordered = KNOWN_PHASE_ORDER.filter((stage) => stages.has(stage));
    const extras = Array.from(stages)
      .filter((stage) => !KNOWN_PHASE_ORDER.includes(stage) && stage !== 'unknown')
      .sort();
    const includeUnknown = stages.has('unknown');
    return [...ordered, ...extras, ...(includeUnknown ? ['unknown'] : [])];
  }, [artefacts]);

  const typeOptions = useMemo(() => {
    const types = new Set<string>();
    artefacts.forEach((file) => types.add(file.contentType));
    return Array.from(types).sort();
  }, [artefacts]);

  const filteredFiles = useMemo(() => {
    return artefacts.filter((file) => {
      const matchesSearch = searchTerm
        ? file.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
          (file.description?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false) ||
          (file.taskName?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false)
        : true;

      const matchesStage = selectedStage === 'all' ? true : (file.stage ?? 'unknown') === selectedStage;
      const matchesType = selectedType === 'all' ? true : file.contentType === selectedType;

      return matchesSearch && matchesStage && matchesType;
    });
  }, [artefacts, searchTerm, selectedStage, selectedType]);

  const filesByStage = useMemo(() => {
    const grouped: Record<string, PlanFile[]> = {};
    filteredFiles.forEach((file) => {
      const key = file.stage ?? 'unknown';
      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key].push(file);
    });
    return grouped;
  }, [filteredFiles]);

  const lastUpdatedLabel = lastUpdated
    ? formatDistanceToNow(lastUpdated, { addSuffix: true })
    : 'never';

  const downloadFile = async (file: PlanFile) => {
    try {
      const response = await fetch(`/api/plans/${planId}/files/${file.filename}`);
      if (!response.ok) {
        throw new Error('Failed to download file');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const downloadZip = async () => {
    try {
      setIsDownloadingZip(true);
      const response = await fetch(`/api/plans/${planId}/download`);
      if (!response.ok) {
        throw new Error('Failed to create ZIP archive');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `plan-${planId}-files.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('ZIP download failed:', err);
    } finally {
      setIsDownloadingZip(false);
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      <Card className="border-blue-200 bg-blue-50/50">
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Plan Artefacts</CardTitle>
              <CardDescription>
                Database-backed outputs captured during pipeline execution. Last updated {lastUpdatedLabel}.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={onRefresh} disabled={isLoading}>
                Refresh
              </Button>
              <Button variant="ghost" size="sm" onClick={downloadZip} disabled={isDownloadingZip || isLoading}>
                {isDownloadingZip ? 'Preparing...' : 'Download ZIP'}
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Input
              placeholder="Search by filename, description, or task"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              className="max-w-sm"
            />
            <Select value={selectedStage} onValueChange={setSelectedStage}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Filter by stage" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Stages</SelectItem>
                {stageOptions.map((stage) => (
                  <SelectItem key={stage} value={stage}>
                    {getPhaseLabel(stage)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedType} onValueChange={setSelectedType}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="File type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {typeOptions.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
      </Card>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="py-4 text-sm text-red-700">{error}</CardContent>
        </Card>
      )}

      {isLoading && artefacts.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-slate-500">
            Loading artefacts from the database...
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && filteredFiles.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-slate-500">
            {artefacts.length === 0
              ? 'No artefacts recorded yet. The pipeline may still be running or has not produced any outputs.'
              : 'No artefacts match your filters.'}
          </CardContent>
        </Card>
      )}

      {filteredFiles.length > 0 && (
        <Tabs defaultValue="list" className="w-full">
          <TabsList>
            <TabsTrigger value="list">List View</TabsTrigger>
            <TabsTrigger value="stages">By Stage</TabsTrigger>
          </TabsList>

          <TabsContent value="list" className="space-y-2">
            {filteredFiles.map((file) => (
              <Card key={file.filename} className="cursor-pointer transition-shadow hover:shadow-md">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3 flex-1">
                      {getFileIcon(file.contentType)}
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{file.filename}</div>
                        <div className="text-sm text-gray-600 truncate">{file.description}</div>
                        <div className="flex items-center space-x-2 mt-1 text-xs text-gray-500">
                          <Badge variant="outline" className="text-xs">
                            {getPhaseLabel(file.stage)}
                          </Badge>
                          <Badge variant="secondary" className="text-xs">
                            {file.contentType.toUpperCase()}
                          </Badge>
                          <span>{formatFileSize(file.sizeBytes)}</span>
                          <span>Stored {formatDistanceToNow(new Date(file.createdAt), { addSuffix: true })}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Button size="sm" variant="outline" onClick={() => onPreview?.(file)}>
                        Preview
                      </Button>
                      <Button size="sm" onClick={() => downloadFile(file)}>
                        Download
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="stages" className="space-y-6">
            {Object.entries(filesByStage).map(([stageKey, stageFiles]) => (
              <Card key={stageKey}>
                <CardHeader>
                  <CardTitle className="text-lg">{getPhaseLabel(stageKey)}</CardTitle>
                  <CardDescription>{stageFiles.length} artefact{stageFiles.length === 1 ? '' : 's'}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {stageFiles.map((file) => (
                    <div key={file.filename} className="flex items-center justify-between p-2 rounded-md hover:bg-gray-50">
                      <div className="flex items-center space-x-3 flex-1">
                        {getFileIcon(file.contentType)}
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{file.filename}</div>
                          <div className="text-sm text-gray-600 truncate">{file.description}</div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2 text-xs text-gray-500">
                        <span>{file.contentType.toUpperCase()}</span>
                        <span>{formatFileSize(file.sizeBytes)}</span>
                        <Button size="sm" variant="outline" onClick={() => downloadFile(file)}>
                          Download
                        </Button>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ))}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
};