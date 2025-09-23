/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-20
 * PURPOSE: Plans Queue UI component - shows all user plans with status, retry/cancel actions, and 3-second polling
 * SRP and DRY check: Pass - Single responsibility of displaying and managing plan queue, reuses existing API client
 */

'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Loader2, RotateCcw, X, ExternalLink } from 'lucide-react'

interface Plan {
  plan_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  prompt: string
  progress_percentage: number
  progress_message: string
  error_message?: string
  output_dir: string
}

interface PlansQueueProps {
  className?: string
  onPlanSelect?: (planId: string) => void
  onPlanRetry?: (planId: string) => void
}

export function PlansQueue({ className, onPlanSelect, onPlanRetry }: PlansQueueProps) {
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [retryingPlanId, setRetryingPlanId] = useState<string | null>(null)

  // Fetch all plans
  const fetchPlans = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/plans')
      if (response.ok) {
        const plansData = await response.json()
        setPlans(plansData.reverse()) // Show newest first
      }
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
      const response = await fetch(`http://localhost:8000/api/plans/${planId}/retry`, {
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

  const getStatusIcon = (status: string, progress: number) => {
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
                      {getStatusIcon(plan.status, plan.progress_percentage)}
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
                  <div className="flex gap-2 ml-4">
                    {(plan.status === 'failed' || plan.status === 'pending') && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => retryPlan(plan.plan_id)}
                        disabled={retryingPlanId === plan.plan_id}
                      >
                        {retryingPlanId === plan.plan_id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <RotateCcw className="h-3 w-3" />
                        )}
                      </Button>
                    )}
                    {onPlanSelect && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onPlanSelect(plan.plan_id)}
                      >
                        <ExternalLink className="h-3 w-3" />
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