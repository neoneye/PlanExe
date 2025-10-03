/**
 * Author: Cascade
 * Date: 2025-09-19T16:59:36-04:00
 * PURPOSE: File management component for browsing and downloading Luigi pipeline outputs with FilenameEnum support
 * SRP and DRY check: Pass - Single responsibility for file operations, respects Luigi pipeline output patterns
 */

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PlanFile, PipelinePhase } from '@/lib/types/pipeline';
import { ReportTaskFallback } from './ReportTaskFallback';
import { formatDistanceToNow } from 'date-fns';

interface FileManagerProps {
  planId: string;
  onFileSelect?: (file: PlanFile) => void;
  className?: string;
}

export const FileManager: React.FC<FileManagerProps> = ({
  planId,
  onFileSelect,
  className = ''
}) => {
  const [files, setFiles] = useState<PlanFile[]>([]);
  const [filteredFiles, setFilteredFiles] = useState<PlanFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPhase, setSelectedPhase] = useState<PipelinePhase | 'all'>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [isDownloadingZip, setIsDownloadingZip] = useState(false);

  // Fetch files
  const fetchFiles = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/plans/${planId}/files`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error?.message || 'Failed to fetch files');
      }

      if (data.success && data.files) {
        setFiles(data.files.files || []);
        setError(null);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [planId, fetchFiles]);

  // Filter files based on search and filters
  useEffect(() => {
    let filtered = files;

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(file =>
        file.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
        file.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        file.taskName.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Phase filter
    if (selectedPhase !== 'all') {
      filtered = filtered.filter(file => file.stage === selectedPhase);
    }

    // Type filter
    if (selectedType !== 'all') {
      filtered = filtered.filter(file => file.type === selectedType);
    }

    setFilteredFiles(filtered);
  }, [files, searchTerm, selectedPhase, selectedType]);

  // Group files by phase
  const filesByPhase = useMemo(() => {
    const grouped: Record<PipelinePhase, PlanFile[]> = {} as Record<PipelinePhase, PlanFile[]>;
    
    filteredFiles.forEach(file => {
      if (!grouped[file.stage]) {
        grouped[file.stage] = [];
      }
      grouped[file.stage].push(file);
    });

    return grouped;
  }, [filteredFiles]);

  // Get file type icon
  const getFileIcon = (type: string) => {
    switch (type) {
      case 'json': return '📄';
      case 'md': return '📝';
      case 'html': return '🌐';
      case 'csv': return '📊';
      case 'txt': return '📋';
      default: return '📁';
    }
  };

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Download single file
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

  // Download all files as ZIP
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

  // Preview file content
  const previewFile = async (file: PlanFile) => {
    if (onFileSelect) {
      onFileSelect(file);
    }
  };

  const phaseDisplayNames: Record<PipelinePhase, string> = {
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
    completion: 'Completion'
  };

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Loading Files...</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded w-full"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-red-600">Error Loading Files</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-red-600 mb-4">{error}</p>
          <Button onClick={fetchFiles} variant="outline">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      <ReportTaskFallback planId={planId} />
      
      {/* Header & Controls */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Generated Files</CardTitle>
              <CardDescription>
                {files.length} files generated • {filteredFiles.length} shown
              </CardDescription>
            </div>
            <div className="flex items-center space-x-2">
              <Button 
                onClick={fetchFiles}
                variant="outline"
                size="sm"
              >
                Refresh
              </Button>
              <Button 
                onClick={downloadZip}
                disabled={files.length === 0 || isDownloadingZip}
                size="sm"
              >
                {isDownloadingZip ? 'Creating ZIP...' : 'Download All'}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-col md:flex-row gap-4 mb-6">
            <div className="flex-1">
              <Input
                placeholder="Search files..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full"
              />
            </div>
            <Select value={selectedPhase} onValueChange={(value) => setSelectedPhase(value as PipelinePhase | 'all')}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Filter by phase" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Phases</SelectItem>
                {Object.entries(phaseDisplayNames).map(([key, name]) => (
                  <SelectItem key={key} value={key}>{name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedType} onValueChange={setSelectedType}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="File type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="json">JSON</SelectItem>
                <SelectItem value="md">Markdown</SelectItem>
                <SelectItem value="html">HTML</SelectItem>
                <SelectItem value="csv">CSV</SelectItem>
                <SelectItem value="txt">Text</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* File Listing */}
      {filteredFiles.length === 0 ? (
        <Card>
          <CardContent className="text-center py-12">
            <div className="text-gray-500">
              {files.length === 0 ? 'No files generated yet' : 'No files match your filters'}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="list" className="w-full">
          <TabsList>
            <TabsTrigger value="list">List View</TabsTrigger>
            <TabsTrigger value="phases">By Phase</TabsTrigger>
          </TabsList>

          <TabsContent value="list" className="space-y-2">
            {filteredFiles.map((file) => (
              <Card key={file.filename} className="cursor-pointer hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3 flex-1">
                      <span className="text-2xl">{getFileIcon(file.type)}</span>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{file.filename}</div>
                        <div className="text-sm text-gray-600 truncate">{file.description}</div>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge variant="outline" className="text-xs">
                            {phaseDisplayNames[file.stage]}
                          </Badge>
                          <Badge variant="secondary" className="text-xs">
                            {file.type.toUpperCase()}
                          </Badge>
                          <span className="text-xs text-gray-500">
                            {formatFileSize(file.size)} • {formatDistanceToNow(new Date(file.lastModified), { addSuffix: true })}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {file.type === 'html' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => previewFile(file)}
                        >
                          Preview
                        </Button>
                      )}
                      <Button
                        size="sm"
                        onClick={() => downloadFile(file)}
                      >
                        Download
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="phases" className="space-y-6">
            {Object.entries(filesByPhase).map(([phase, phaseFiles]) => (
              <Card key={phase}>
                <CardHeader>
                  <CardTitle className="text-lg">{phaseDisplayNames[phase as PipelinePhase]}</CardTitle>
                  <CardDescription>{phaseFiles.length} files</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {phaseFiles.map((file) => (
                    <div key={file.filename} className="flex items-center justify-between p-2 rounded-md hover:bg-gray-50">
                      <div className="flex items-center space-x-3 flex-1">
                        <span>{getFileIcon(file.type)}</span>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{file.filename}</div>
                          <div className="text-sm text-gray-600 flex items-center space-x-2">
                            <Badge variant="secondary" className="text-xs">{file.type}</Badge>
                            <span>{formatFileSize(file.size)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
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
