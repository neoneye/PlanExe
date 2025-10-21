/**
 * Author: Claude Code using Sonnet 4.5
 * Date: 2025-10-20
 * PURPOSE: Clear 3-step explanation of how PlanExe works.
 *          Provides non-technical, user-friendly descriptions of the planning process.
 *          Uses icons and visual hierarchy to make the process immediately understandable.
 *          Addresses the problem of redundant, cramped info boxes in the original design.
 * SRP and DRY check: Pass - Single responsibility (process explanation), no duplication.
 */

'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Edit3, MessageCircle, FileCheck } from 'lucide-react';

interface Step {
  icon: React.ReactNode;
  title: string;
  description: string;
  details: string;
}

const steps: Step[] = [
  {
    icon: <Edit3 className="h-6 w-6 text-indigo-600" aria-hidden="true" />,
    title: 'Describe Your Idea',
    description: 'Start with any level of detail',
    details:
      'Type anything from a single sentence to detailed specifications. Our AI understands context and can work with whatever you provide.',
  },
  {
    icon: <MessageCircle className="h-6 w-6 text-blue-600" aria-hidden="true" />,
    title: 'Conversation with AI Agent',
    description: '2-3 clarifying questions',
    details:
      'Our agent asks targeted questions about scope, timeline, constraints, and success metrics to enrich your plan. Quick and conversational.',
  },
  {
    icon: <FileCheck className="h-6 w-6 text-emerald-600" aria-hidden="true" />,
    title: 'Get Your Complete Plan',
    description: '60-task execution pipeline',
    details:
      'Receive a comprehensive strategic plan with Work Breakdown Structure, timeline, dependencies, risk analysis, and detailed reports.',
  },
];

export const HowItWorksSection: React.FC = () => {
  return (
    <section className="py-0">
      <div className="mx-auto max-w-6xl px-6">
        {/* Section header */}
        <div className="mb-4 text-center">
          <h2 className="mb-2 text-2xl font-bold tracking-tight text-slate-900">
            How It Works
          </h2>
          <p className="mx-auto max-w-2xl text-sm text-slate-600">
            From idea to execution plan in three simple steps
          </p>
        </div>

        {/* Steps grid */}
        <div className="grid gap-4 md:grid-cols-3">
          {steps.map((step, index) => (
            <Card
              key={step.title}
              className="group relative overflow-hidden border border-slate-200 bg-white shadow-sm transition-all hover:border-indigo-300 hover:shadow-md"
            >
              {/* Step number badge */}
              <div className="absolute right-3 top-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-600 transition-colors group-hover:bg-indigo-100 group-hover:text-indigo-700">
                  {index + 1}
                </div>
              </div>

              <CardHeader className="space-y-2 pb-2">
                {/* Icon */}
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 shadow-inner transition-transform group-hover:scale-110">
                  {step.icon}
                </div>

                {/* Title and description */}
                <div>
                  <CardTitle className="mb-1 text-base font-bold text-slate-900">
                    {step.title}
                  </CardTitle>
                  <CardDescription className="text-xs font-medium text-indigo-600">
                    {step.description}
                  </CardDescription>
                </div>
              </CardHeader>

              <CardContent className="pb-3">
                <p className="text-xs leading-relaxed text-slate-600">{step.details}</p>
              </CardContent>

              {/* Decorative gradient border on hover */}
              <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-indigo-600 to-blue-600 opacity-0 transition-opacity group-hover:opacity-100" />
            </Card>
          ))}
        </div>

        {/* Additional context */}
        <div className="mt-4 rounded-xl border border-slate-200 bg-white/50 p-3 text-center shadow-sm backdrop-blur">
          <p className="text-xs text-slate-600">
            <strong className="font-semibold text-slate-900">Powered by OpenAI GPT-5</strong> with
            Responses API for real-time reasoning and strategic analysis. Your plan is generated
            using a 61-task Luigi pipeline with multi-stage analysis, scenario planning, and
            comprehensive documentation.
          </p>
        </div>
      </div>
    </section>
  );
};
