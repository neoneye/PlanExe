/**
 * Author: Claude Code using Haiku 4.5
 * Date: 2025-10-21
 * PURPOSE: Display enriched plan intake data with edit capability before finalizing plan creation.
 *          Shows the 10 key variables extracted from the Responses API structured output in a
 *          structured review UI. Allows users to verify and modify extracted data before submission.
 * SRP and DRY check: Pass - Single responsibility of displaying and editing intake data.
 */

'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  CheckCircle2,
  Edit2,
  MapPin,
  DollarSign,
  Calendar,
  Users,
  Target,
  Shield,
} from 'lucide-react';
import { EnrichedPlanIntake } from '@/lib/api/fastapi-client';

interface EnrichedIntakeReviewProps {
  intake: EnrichedPlanIntake;
  onConfirm: (editedIntake: EnrichedPlanIntake) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export const EnrichedIntakeReview: React.FC<EnrichedIntakeReviewProps> = ({
  intake,
  onConfirm,
  onCancel,
  isSubmitting,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedIntake, setEditedIntake] = useState<EnrichedPlanIntake>(intake);

  const handleConfirm = () => {
    onConfirm(editedIntake);
  };

  const scaleLabels: Record<string, string> = {
    personal: 'Personal',
    local: 'Local',
    regional: 'Regional',
    national: 'National',
    global: 'Global',
  };

  const riskLabels: Record<string, string> = {
    conservative: 'Conservative',
    moderate: 'Moderate',
    aggressive: 'Aggressive',
    experimental: 'Experimental',
  };

  return (
    <div className="space-y-6 pb-6">
      {/* Header */}
      <Card className="bg-gradient-to-r from-indigo-950/40 to-slate-900 border-indigo-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl text-slate-100">
            <CheckCircle2 className="h-5 w-5 text-green-400" />
            Plan Variables Captured
          </CardTitle>
          <CardDescription className="text-slate-300">
            Review the information extracted from your conversation. You can edit any field before
            creating the plan.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className="bg-green-950/30 text-green-400 border-green-800"
              >
                Confidence: {editedIntake.confidence_score}/10
              </Badge>
              <Badge variant="outline" className="bg-slate-800 text-slate-300">
                {editedIntake.scale ? scaleLabels[editedIntake.scale] : 'Unknown Scale'}
              </Badge>
              <Badge variant="outline" className="bg-slate-800 text-slate-300">
                {editedIntake.risk_tolerance
                  ? riskLabels[editedIntake.risk_tolerance]
                  : 'Unknown Risk'}
              </Badge>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsEditing(!isEditing)}
              className="gap-2"
            >
              <Edit2 className="h-4 w-4" />
              {isEditing ? 'Done Editing' : 'Edit Fields'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Project Identity */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-lg text-slate-100">Project Identity</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-slate-300">Project Title</Label>
            {isEditing ? (
              <Input
                value={editedIntake.project_title}
                onChange={(e) =>
                  setEditedIntake({ ...editedIntake, project_title: e.target.value })
                }
                className="mt-1"
              />
            ) : (
              <p className="mt-1 text-base text-slate-100 font-medium">
                {editedIntake.project_title}
              </p>
            )}
          </div>
          <div>
            <Label className="text-slate-300">Objective</Label>
            {isEditing ? (
              <Textarea
                value={editedIntake.refined_objective}
                onChange={(e) =>
                  setEditedIntake({ ...editedIntake, refined_objective: e.target.value })
                }
                className="mt-1"
                rows={3}
              />
            ) : (
              <p className="mt-1 text-sm text-slate-200">{editedIntake.refined_objective}</p>
            )}
          </div>
          <div>
            <Label className="text-slate-300">Domain / Industry</Label>
            <p className="mt-1 text-sm text-slate-200">{editedIntake.domain}</p>
          </div>
        </CardContent>
      </Card>

      {/* Resources Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Budget */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-slate-100">
              <DollarSign className="h-4 w-4 text-green-400" />
              Budget & Funding
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>
              <Label className="text-xs text-slate-400">Estimated Total</Label>
              <p className="text-sm text-slate-200">
                {editedIntake.budget.estimated_total || 'Not specified'}
              </p>
            </div>
            <div>
              <Label className="text-xs text-slate-400">Funding Sources</Label>
              <p className="text-sm text-slate-200">
                {editedIntake.budget.funding_sources?.join(', ') || 'Not specified'}
              </p>
            </div>
            <div>
              <Label className="text-xs text-slate-400">Currency</Label>
              <p className="text-sm text-slate-200">
                {editedIntake.budget.currency || 'Not specified'}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Timeline */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-slate-100">
              <Calendar className="h-4 w-4 text-blue-400" />
              Timeline
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>
              <Label className="text-xs text-slate-400">Target Completion</Label>
              <p className="text-sm text-slate-200">
                {editedIntake.timeline.target_completion || 'Not specified'}
              </p>
            </div>
            <div>
              <Label className="text-xs text-slate-400">Key Milestones</Label>
              <p className="text-sm text-slate-200">
                {editedIntake.timeline.key_milestones?.join(', ') || 'None specified'}
              </p>
            </div>
            <div>
              <Label className="text-xs text-slate-400">Urgency</Label>
              <p className="text-sm text-slate-200">
                {editedIntake.timeline.urgency || 'Not specified'}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Geography */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-slate-100">
              <MapPin className="h-4 w-4 text-purple-400" />
              Geographic Scope
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>
              <Label className="text-xs text-slate-400">Type</Label>
              <p className="text-sm text-slate-200">
                {editedIntake.geography.is_digital_only
                  ? 'Digital Only'
                  : 'Physical Locations Required'}
              </p>
            </div>
            {!editedIntake.geography.is_digital_only && (
              <div>
                <Label className="text-xs text-slate-400">Locations</Label>
                <p className="text-sm text-slate-200">
                  {editedIntake.geography.physical_locations?.join(', ') || 'Not specified'}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Team */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-slate-100">
              <Users className="h-4 w-4 text-orange-400" />
              Team & Resources
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>
              <Label className="text-xs text-slate-400">Team Size</Label>
              <p className="text-sm text-slate-200">{editedIntake.team_size || 'Not specified'}</p>
            </div>
            <div>
              <Label className="text-xs text-slate-400">Existing Resources</Label>
              <p className="text-sm text-slate-200">
                {editedIntake.existing_resources?.join(', ') || 'None specified'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Constraints & Success */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-slate-100">
            <Target className="h-4 w-4 text-yellow-400" />
            Constraints & Success Criteria
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-slate-300">Hard Constraints</Label>
            <ul className="mt-1 list-disc list-inside text-sm text-slate-200 space-y-1">
              {editedIntake.hard_constraints && editedIntake.hard_constraints.length > 0 ? (
                editedIntake.hard_constraints.map((c, i) => <li key={i}>{c}</li>)
              ) : (
                <li className="text-slate-400">None specified</li>
              )}
            </ul>
          </div>
          <div>
            <Label className="text-slate-300">Success Criteria</Label>
            <ul className="mt-1 list-disc list-inside text-sm text-slate-200 space-y-1">
              {editedIntake.success_criteria && editedIntake.success_criteria.length > 0 ? (
                editedIntake.success_criteria.map((c, i) => <li key={i}>{c}</li>)
              ) : (
                <li className="text-slate-400">None specified</li>
              )}
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Governance */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-slate-100">
            <Shield className="h-4 w-4 text-red-400" />
            Governance & Stakeholders
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-slate-300">Key Stakeholders</Label>
            <p className="mt-1 text-sm text-slate-200">
              {editedIntake.key_stakeholders?.join(', ') || 'None specified'}
            </p>
          </div>
          <div>
            <Label className="text-slate-300">Regulatory Context</Label>
            <p className="mt-1 text-sm text-slate-200">
              {editedIntake.regulatory_context || 'None specified'}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
        <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          disabled={isSubmitting}
          className="gap-2 bg-indigo-600 hover:bg-indigo-700"
        >
          <CheckCircle2 className="h-4 w-4" />
          {isSubmitting ? 'Creating Plan...' : 'Confirm & Create Plan'}
        </Button>
      </div>
    </div>
  );
};
