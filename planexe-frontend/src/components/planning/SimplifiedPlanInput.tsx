/**
 * Author: Claude Code using Sonnet 4.5
 * Date: 2025-10-20
 * PURPOSE: Simplified plan creation input that hides all complexity behind smart defaults.
 *          Provides a single textarea and prominent "Start Planning" button.
 *          All configuration (model, speed, tags) is hidden from the user.
 *          This component makes PlanExe accessible to everyone by removing cognitive load
 *          and letting the conversation modal handle enrichment.
 * SRP and DRY check: Pass - Single responsibility (simplified input), reuses existing API types.
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ArrowRight, Loader2, Sparkles } from 'lucide-react';

interface SimplifiedPlanInputProps {
  onSubmit: (prompt: string) => void;
  isSubmitting?: boolean;
  placeholder?: string;
  buttonText?: string;
  autoFocus?: boolean;
  defaultModel?: string;
}

export const SimplifiedPlanInput: React.FC<SimplifiedPlanInputProps> = ({
  onSubmit,
  isSubmitting = false,
  placeholder = 'Describe your business idea, project, or goal...\n\nExamples:\n• Launch a subscription box service for eco-friendly products\n• Build a mobile app for connecting local service providers\n• Restructure our sales team to focus on enterprise clients',
  buttonText = 'Start Planning',
  autoFocus = true,
}) => {
  const [prompt, setPrompt] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (autoFocus && textareaRef.current) {
      // Small delay to ensure component is mounted
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 100);
    }
  }, [autoFocus]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed || isSubmitting) {
      return;
    }
    onSubmit(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Cmd/Ctrl + Enter to submit
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const charCount = prompt.length;
  const minChars = 10;
  const isValid = charCount >= minChars;

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="space-y-4">
        {/* Main Textarea */}
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isSubmitting}
            className="min-h-[180px] resize-none rounded-2xl border-2 border-slate-300 bg-white p-6 text-lg leading-relaxed text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/20 disabled:cursor-not-allowed disabled:opacity-50 sm:min-h-[200px]"
            aria-label="Describe your business idea"
          />

          {/* Character count indicator */}
          <div className="absolute bottom-4 right-4 text-sm text-slate-400">
            {charCount} characters
            {charCount > 0 && charCount < minChars && (
              <span className="ml-2 text-amber-600">
                ({minChars - charCount} more needed)
              </span>
            )}
          </div>
        </div>

        {/* Submit Button and Keyboard Shortcut Hint */}
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <kbd className="rounded border border-slate-300 bg-white px-2 py-1 font-mono text-xs shadow-sm">
              ⌘
            </kbd>
            <span>+</span>
            <kbd className="rounded border border-slate-300 bg-white px-2 py-1 font-mono text-xs shadow-sm">
              Enter
            </kbd>
            <span className="hidden sm:inline">to submit</span>
          </div>

          <Button
            type="submit"
            disabled={!isValid || isSubmitting}
            size="lg"
            className="group relative min-w-[200px] overflow-hidden rounded-full bg-gradient-to-r from-indigo-600 to-blue-600 px-8 py-6 text-lg font-semibold text-white shadow-lg transition-all hover:from-indigo-700 hover:to-blue-700 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Opening conversation...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-5 w-5" />
                {buttonText}
                <ArrowRight className="ml-2 h-5 w-5 transition-transform group-hover:translate-x-1" />
              </>
            )}
          </Button>
        </div>

        {/* Helpful hint below button */}
        {!isSubmitting && (
          <div className="text-center text-sm text-slate-500">
            {!isValid && prompt.length > 0 ? (
              <p className="text-amber-600">
                Please provide at least {minChars} characters to help our AI understand your idea.
              </p>
            ) : (
              <p>
                Our AI agent will ask you 2-3 clarifying questions, then generate your complete plan.
              </p>
            )}
          </div>
        )}
      </div>
    </form>
  );
};
