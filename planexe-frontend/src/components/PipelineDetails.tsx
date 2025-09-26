/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-20
 * PURPOSE: Pipeline Details UI component - shows real-time Luigi pipeline stage execution, logs, and generated files
 * SRP and DRY check: Pass - Single responsibility of displaying pipeline execution details with 3-second polling
 */

'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Loader2, CheckCircle, XCircle, Clock, FileText, Activity, Terminal } from 'lucide-react'

interface PipelineStage {
  event_name: string
  task_name: string
  timestamp: string
  task_id?: string
  status?: string
}

interface GeneratedFile {
  filename: string
  size_bytes: number
  modified_at: number
}

interface PipelineDetails {
  plan_id: string
  run_directory: string
  pipeline_stages: PipelineStage[]
  pipeline_log: string
  generated_files: GeneratedFile[]
  total_files: number
}

interface PipelineDetailsProps {
  planId: string
  className?: string
}

export function PipelineDetails({ planId, className }: PipelineDetailsProps) {
  const [details, setDetails] = useState<PipelineDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch pipeline details
  const fetchDetails = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/plans/${planId}/details`)
      if (response.ok) {
        const detailsData = await response.json()
        setDetails(detailsData)
        setError(null)
      } else {
        setError(`Failed to fetch details: ${response.status}`)
      }
    } catch (err) {
      setError(`Network error: ${err}`)
    } finally {
      setLoading(false)
    }
  }

  // 3-second polling
  useEffect(() => {
    fetchDetails()
    const interval = setInterval(fetchDetails, 3000)
    return () => clearInterval(interval)
  }, [planId, fetchDetails])

  const getStageIcon = (eventName: string) => {
    switch (eventName) {
      case 'PROCESSING':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      case 'SUCCESS':
      case 'DONE':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'FAILURE':
      case 'ERROR':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'START':
        return <Clock className="h-4 w-4 text-yellow-500" />
      default:
        return <Activity className="h-4 w-4 text-gray-500" />
    }
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatTaskName = (taskName: string) => {
    // Convert camelCase/PascalCase to readable format
    return taskName
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, str => str.toUpperCase())
      .trim()
  }

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            Pipeline Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            Loading pipeline details...
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            Pipeline Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-red-500 text-center p-8">{error}</div>
        </CardContent>
      </Card>
    )
  }

  if (!details) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            Pipeline Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center p-8">No details available</div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Terminal className="h-5 w-5" />
          Pipeline Details
        </CardTitle>
        <div className="flex gap-2">
          <Badge variant="outline">{details.pipeline_stages.length} stages</Badge>
          <Badge variant="outline">{details.total_files} files</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="stages" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="stages">Stages</TabsTrigger>
            <TabsTrigger value="logs">Logs</TabsTrigger>
            <TabsTrigger value="files">Files</TabsTrigger>
          </TabsList>

          <TabsContent value="stages" className="space-y-4">
            <div className="space-y-2">
              {details.pipeline_stages.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No pipeline stages recorded yet
                </p>
              ) : (
                details.pipeline_stages.map((stage, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted/50"
                  >
                    {getStageIcon(stage.event_name)}
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">
                          {formatTaskName(stage.task_name)}
                        </span>
                        <Badge
                          variant={
                            stage.event_name === 'SUCCESS' ? 'default' :
                            stage.event_name === 'FAILURE' ? 'destructive' :
                            stage.event_name === 'PROCESSING' ? 'secondary' :
                            'outline'
                          }
                        >
                          {stage.event_name}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {formatTimestamp(stage.timestamp)}
                        {stage.task_id && (
                          <span className="ml-2 font-mono text-xs">
                            {stage.task_id}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </TabsContent>

          <TabsContent value="logs" className="space-y-4">
            <div className="bg-black text-green-400 p-4 rounded-lg font-mono text-sm max-h-96 overflow-y-auto">
              {details.pipeline_log ? (
                <pre className="whitespace-pre-wrap">{details.pipeline_log}</pre>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  No logs available yet
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="files" className="space-y-4">
            <div className="space-y-2">
              {details.generated_files.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No files generated yet
                </p>
              ) : (
                details.generated_files
                  .sort((a, b) => b.modified_at - a.modified_at)
                  .map((file, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50"
                    >
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-blue-500" />
                        <span className="font-mono text-sm">{file.filename}</span>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {formatFileSize(file.size_bytes)}
                      </div>
                    </div>
                  ))
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}