/**
 * Author: gpt-5-codex
 * Date: 2025-02-15
 * PURPOSE: Aurora-themed intake surface for the landing page conversation flow. Presents a single
 *          textarea with keyboard shortcut hints and an animated gradient call-to-action that aligns
 *          with the refreshed twilight UI while keeping behaviour unchanged for the parent page.
 * SRP and DRY check: Pass - Solely manages user prompt entry and submission interactions.
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
  placeholder = `Describe what you are building, improving, or investigating...

Examples:
• Reposition our flagship product for creative teams
• Plan a pop-up experience for our next launch
• Map the hiring plan for opening a new studio`,
  buttonText = 'Open the conversation',
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
            className="min-h-[140px] resize-none rounded-2xl border border-white/20 bg-[#0b1220]/80 p-5 text-base leading-relaxed
            text-slate-100 placeholder:text-slate-400 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/30 disabled:cursor-not-allowed
            disabled:opacity-50"
            aria-label="Describe your business idea"
          />

          {/* Character count indicator */}
          <div className="absolute bottom-4 right-4 text-xs text-slate-400">
            {charCount} characters
            {charCount > 0 && charCount < minChars && (
              <span className="ml-2 text-amber-300">
                ({minChars - charCount} more needed)
              </span>
            )}
          </div>
        </div>

        {/* Submit Button and Keyboard Shortcut Hint */}
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
          <div className="flex items-center gap-1.5 text-xs text-slate-300">
            <kbd
              className="rounded border border-white/10 bg-white/10 px-1.5 py-0.5 font-mono text-[10px] text-slate-100 shadow-sm"
            >
              ⌘
            </kbd>
            <span>+</span>
            <kbd
              className="rounded border border-white/10 bg-white/10 px-1.5 py-0.5 font-mono text-[10px] text-slate-100 shadow-sm"
            >
              Enter
            </kbd>
            <span className="hidden sm:inline">to submit</span>
          </div>

          <Button
            type="submit"
            disabled={!isValid || isSubmitting}
            size="default"
            className="group relative min-w-[200px] overflow-hidden rounded-full bg-gradient-to-r from-cyan-400 via-blue-500 to-fuchsia-500
            px-6 py-2 text-base font-semibold text-slate-900 shadow-lg shadow-cyan-500/30 transition-all hover:from-cyan-300 hover:via-blue-400
            hover:to-fuchsia-400 focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Opening conversation...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4 text-slate-900" />
                {buttonText}
                <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
              </>
            )}
          </Button>
        </div>

        {/* Helpful hint below button */}
        {!isSubmitting && (
          <div className="text-center text-xs text-slate-300">
            {!isValid && prompt.length > 0 ? (
              <p className="text-amber-300">
                Please provide at least {minChars} characters to help our AI understand your idea.
              </p>
            ) : (
              <p>
                Expect a few clarifying questions—then your tailored execution plan arrives moments later.
              </p>
            )}
          </div>
        )}
      </div>
    </form>
  );
};
