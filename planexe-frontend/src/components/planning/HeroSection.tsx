/**
 * Author: Claude Code using Sonnet 4.5
 * Date: 2025-10-20
 * PURPOSE: Hero section for the PlanExe landing page that clearly communicates the value proposition.
 *          Provides an inviting, visually appealing introduction to the planning system.
 *          Uses gradient backgrounds and clear typography hierarchy to guide users.
 * SRP and DRY check: Pass - Single responsibility (hero presentation), no duplication.
 */

'use client';

import React from 'react';
import { Brain, Zap } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface HeroSectionProps {
  version?: string | null;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ version }) => {
  return (
    <section className="relative overflow-hidden py-6 sm:py-8">
      {/* Background decorative elements */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute right-0 top-0 h-64 w-64 rounded-full bg-indigo-200/30 blur-3xl" />
        <div className="absolute bottom-0 left-0 h-96 w-96 rounded-full bg-blue-200/30 blur-3xl" />
      </div>

      <div className="mx-auto max-w-6xl px-6">
        {/* Logo and version badge */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-blue-600 shadow-lg">
              <Brain className="h-6 w-6 text-white" aria-hidden="true" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-xl font-bold text-slate-900">PlanExe</h1>
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                Strategic Planning Engine
              </p>
            </div>
          </div>

          {version && (
            <Badge
              variant="outline"
              className="border-indigo-200 bg-white/80 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-indigo-700 backdrop-blur"
            >
              v{version}
            </Badge>
          )}
        </div>

        {/* Main headline */}
        <div className="space-y-3 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Turn Your Idea Into an{' '}
            <span className="bg-gradient-to-r from-indigo-600 to-blue-600 bg-clip-text text-transparent">
              Execution Plan
            </span>
          </h2>

          <p className="mx-auto max-w-2xl text-base text-slate-600 sm:text-lg">
            Describe your business idea. Our AI agent will guide you through a conversation, then
            generate a complete 60-task strategic plan.
          </p>

          {/* Value propositions */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
            <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-medium text-slate-700 shadow-sm backdrop-blur">
              <Zap className="h-3.5 w-3.5 text-indigo-600" aria-hidden="true" />
              <span>AI-Powered</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-medium text-slate-700 shadow-sm backdrop-blur">
              <span>📊</span>
              <span>60-Task Pipeline</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-medium text-slate-700 shadow-sm backdrop-blur">
              <span>⚡</span>
              <span>45-90 Minutes</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
