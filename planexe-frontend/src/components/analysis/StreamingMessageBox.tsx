/**
 * Author: ChatGPT gpt-5-codex
 * Date: 2025-10-27T00:00:00Z
 * PURPOSE: Reusable message box for streaming modal deltas with variant-specific styling.
 * SRP and DRY check: Pass - focused on rendering presentation, avoids duplicating Tailwind
 *          styles across streaming panels.
 */

import { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export type StreamingMessageVariant = 'text' | 'reasoning' | 'json';

interface StreamingMessageBoxProps {
  title: string;
  variant: StreamingMessageVariant;
  children: ReactNode;
  footer?: ReactNode;
}

const VARIANT_STYLES: Record<StreamingMessageVariant, { container: string; badge: string; label: string }> = {
  text: {
    container: 'border-sky-200 bg-sky-50/80 text-sky-900',
    badge: 'border-sky-200 bg-sky-100 text-sky-800',
    label: 'Text',
  },
  reasoning: {
    container: 'border-amber-200 bg-amber-50/80 text-amber-900',
    badge: 'border-amber-200 bg-amber-100 text-amber-800',
    label: 'Reasoning',
  },
  json: {
    container: 'border-emerald-200 bg-emerald-50/80 text-emerald-900',
    badge: 'border-emerald-200 bg-emerald-100 text-emerald-800',
    label: 'JSON',
  },
};

export const StreamingMessageBox = ({ title, variant, children, footer }: StreamingMessageBoxProps) => {
  const styles = VARIANT_STYLES[variant];
  return (
    <div
      className={cn(
        'rounded-lg border p-3 text-sm shadow-sm transition-colors',
        'backdrop-blur-sm',
        styles.container,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-semibold tracking-wide">{title}</span>
        <Badge variant="outline" className={cn('text-xs uppercase', styles.badge)}>
          {styles.label}
        </Badge>
      </div>
      <div className="whitespace-pre-wrap break-words text-xs leading-relaxed text-slate-800">
        {children}
      </div>
      {footer ? <div className="mt-2 text-[11px] text-slate-600">{footer}</div> : null}
    </div>
  );
};
