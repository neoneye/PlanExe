/**
 * Author: Codex using GPT-5
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Plans queue with recovery workspace shortcut; keeps polling/retry behaviour intact.
 * SRP and DRY check: Pass - Focused on queue management, reusing central API client without duplication.
 */

'use client'

import Link from 'next/link'
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Loader2, RotateCcw, Monitor } from 'lucide-react'
import { fastApiClient, PlanResponse } from '@/lib/api/fastapi-client'

// Use the PlanResponse type from fastapi-client instead of local interface

interface PlansQueueProps {
  className?: string
  onPlanSelect?: (planId: string) => void
  onPlanRetry?: (planId: string) => void
}

export function PlansQueue({ className, onPlanSelect, onPlanRetry }: PlansQueueProps) {
  const [plans, setPlans] = useState<PlanResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [retryingPlanId, setRetryingPlanId] = useState<string | null>(null)

  // Fetch all plans
  const fetchPlans = async () => {
    try {
      const plansData = await fastApiClient.getPlans()
      const sortedPlans = [...plansData].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      setPlans(sortedPlans)
    } catch (error) {
      console.error('Failed to fetch plans:', error)
    } finally {
      setLoading(false)
    }
  }

  // Retry a plan
  const retryPlan = async (planId: string) => {
    setRetryingPlanId(planId)
    try {
      const response = await fetch(`/api/plans/${planId}/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      if (response.ok) {
        const newPlan = await response.json();
        // Refresh plans to show updated status
        await fetchPlans();
        if (onPlanRetry) {
          // Pass the NEW planId to the handler
          onPlanRetry(newPlan.plan_id);
        }
      } else {
        console.error('Failed to retry plan')
      }
    } catch (error) {
      console.error('Error retrying plan:', error)
    } finally {
      setRetryingPlanId(null)
    }
  }

  // 3-second polling
  useEffect(() => {
    fetchPlans()
    const interval = setInterval(fetchPlans, 3000)
    return () => clearInterval(interval)
  }, [])

  const getStatusBadge = (status: string) => {
    const variants = {
      pending: 'secondary',
      running: 'default',
      completed: 'success',
      failed: 'destructive'
    } as const

    return (
      <Badge variant={variants[status as keyof typeof variants] || 'secondary'}>
        {status.toUpperCase()}
      </Badge>
    )
  }

  const getStatusIcon = (status: string) => {
    if (status === 'running') {
      return <Loader2 className="h-4 w-4 animate-spin" />
    }
    return null
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const truncatePrompt = (prompt: string, maxLength = 80) => {
    return prompt.length > maxLength ? prompt.substring(0, maxLength) + '...' : prompt
  }

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Plans Queue</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            Loading plans...
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          Plans Queue
          <Badge variant="outline">{plans.length} total</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {plans.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">No plans found</p>
          ) : (
            plans.map((plan) => (
              <div
                key={plan.plan_id}
                className="border rounded-lg p-4 space-y-2 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      {getStatusIcon(plan.status)}
                      {getStatusBadge(plan.status)}
                      <span className="text-sm text-muted-foreground">
                        {formatDate(plan.created_at)}
                      </span>
                    </div>
                    <p className="text-sm font-mono text-muted-foreground mb-1">
                      {plan.plan_id}
                    </p>
                    <p className="text-sm mb-2">
                      {truncatePrompt(plan.prompt)}
                    </p>
                    {plan.status === 'running' && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span>{plan.progress_message}</span>
                          <span>{plan.progress_percentage}%</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className="bg-primary h-2 rounded-full transition-all duration-300"
                            style={{ width: `${plan.progress_percentage}%` }}
                          />
                        </div>
                      </div>
                    )}
                    {plan.error_message && (
                      <div className="bg-destructive/10 border border-destructive/20 rounded p-2">
                        <p className="text-xs text-destructive">{plan.error_message}</p>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 ml-4">
                    <Button
                      asChild
                      size="sm"
                      variant="secondary"
                      aria-label="Open plan in workspace"
                    >
                      <Link
                        href={`/recovery?planId=${encodeURIComponent(plan.plan_id)}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open Workspace
                      </Link>
                    </Button>
                    {onPlanSelect && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onPlanSelect(plan.plan_id)}
                        aria-label="View in dashboard"
                      >
                        <Monitor className="h-3 w-3" />
                      </Button>
                    )}
                    {(plan.status === 'failed' || plan.status === 'pending') && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => retryPlan(plan.plan_id)}
                        disabled={retryingPlanId === plan.plan_id}
                        aria-label="Retry plan"
                      >
                        {retryingPlanId === plan.plan_id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <RotateCcw className="h-3 w-3" />
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}