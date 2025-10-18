/**
 * Author: ChatGPT (gpt-5-codex)
 * Date: 2025-10-30
 * PURPOSE: Full-screen intake modal that opens after the landing form submit,
 *          orchestrates the enrichment conversation, and collects the refined
 *          prompt that seeds the Luigi pipeline.
 * SRP and DRY check: Pass - component focuses on layout/UX for the intake flow
 *          while delegating conversation state to the dedicated hook.
 */

'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, MessageCircle, Send, Sparkles } from 'lucide-react';
import {
  ConversationFinalizeResult,
  ConversationMessage,
  useResponsesConversation,
} from '@/lib/conversation/useResponsesConversation';
import { CreatePlanRequest } from '@/lib/api/fastapi-client';

interface ConversationModalProps {
  isOpen: boolean;
  request: CreatePlanRequest | null;
  onClose: () => void;
  onFinalize: (result: ConversationFinalizeResult) => Promise<void>;
  isFinalizing: boolean;
}

const MESSAGE_BG: Record<ConversationMessage['role'], string> = {
  user: 'bg-indigo-50 border-indigo-200',
  assistant: 'bg-white border-slate-200',
};

export const ConversationModal: React.FC<ConversationModalProps> = ({
  isOpen,
  request,
  onClose,
  onFinalize,
  isFinalizing,
}) => {
  const initialPrompt = request?.prompt ?? '';
  const resolvedModel = request?.llm_model ?? 'gpt-4o-mini';
  const metadata = useMemo(() => ({ speedVsDetail: request?.speed_vs_detail }), [request?.speed_vs_detail]);

  const {
    messages,
    startConversation,
    sendUserMessage,
    finalizeConversation,
    resetConversation,
    isStreaming,
    streamSummary,
    streamError,
    reasoningBuffer,
  } = useResponsesConversation({
    initialPrompt,
    modelKey: resolvedModel,
    metadata,
  });

  const [draftMessage, setDraftMessage] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && initialPrompt.trim()) {
      startConversation().catch((error) => {
        const message = error instanceof Error ? error.message : 'Failed to start intake conversation.';
        setLocalError(message);
      });
    }
  }, [isOpen, initialPrompt, startConversation]);

  useEffect(() => {
    if (!isOpen) {
      setDraftMessage('');
      setLocalError(null);
      resetConversation();
    }
  }, [isOpen, resetConversation]);

  const handleSend = async () => {
    const trimmed = draftMessage.trim();
    if (!trimmed || isStreaming) {
      return;
    }
    setLocalError(null);
    try {
      await sendUserMessage(trimmed);
      setDraftMessage('');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send message.';
      setLocalError(message);
    }
  };

  const handleFinalize = async () => {
    try {
      const result = finalizeConversation();
      await onFinalize(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to finalise plan creation.';
      setLocalError(message);
    }
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      void handleSend();
    }
  };

  const canFinalize = messages.some((message) => message.role === 'assistant');

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open && !isFinalizing) {
          onClose();
        }
      }}
    >
      <DialogContent className="max-h-[90vh] max-w-6xl overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-0 shadow-2xl">
        <DialogHeader className="px-8 pt-6">
          <DialogTitle className="flex items-center gap-3 text-2xl text-slate-900">
            <Sparkles className="h-6 w-6 text-indigo-600" />
            Enrich your plan request
          </DialogTitle>
          <DialogDescription className="text-sm text-slate-600">
            We send your initial brief to the planning agent, who will guide you through the must-have details before Luigi starts.
          </DialogDescription>
        </DialogHeader>

        <div className="grid h-full grid-cols-1 gap-6 px-8 pb-8 lg:grid-cols-[2fr_1fr]">
          <section className="flex h-full flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <header className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
                <MessageCircle className="h-4 w-4 text-indigo-500" />
                Conversation timeline
              </div>
              <Badge variant="secondary" className="text-xs uppercase">
                Model: {resolvedModel}
              </Badge>
            </header>
            <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={`rounded-xl border px-4 py-3 text-sm leading-relaxed text-slate-800 ${MESSAGE_BG[message.role]}`}
                >
                  <header className="mb-1 flex items-center justify-between text-xs uppercase tracking-wide text-slate-500">
                    <span>{message.role === 'assistant' ? 'PlanExe Agent' : 'You'}</span>
                    <span>{new Date(message.createdAt).toLocaleTimeString()}</span>
                  </header>
                  <p className="whitespace-pre-wrap">
                    {message.content || (message.streaming ? 'Thinking…' : '')}
                  </p>
                  {message.streaming && (
                    <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Agent drafting response…
                    </div>
                  )}
                </article>
              ))}
            </div>
            <footer className="border-t border-slate-200 bg-slate-50 px-6 py-4">
              <div className="space-y-3">
                <Textarea
                  value={draftMessage}
                  onChange={(event) => setDraftMessage(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Add constraints, dependencies, resources, dates…"
                  className="min-h-[120px]"
                  disabled={isStreaming || isFinalizing}
                />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-slate-500">
                    Press <kbd className="rounded border border-slate-300 bg-white px-1">⌘</kbd>
                    +<kbd className="rounded border border-slate-300 bg-white px-1">Enter</kbd> to send
                  </p>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" onClick={onClose} disabled={isFinalizing || isStreaming}>
                      Cancel
                    </Button>
                    <Button onClick={handleSend} disabled={isStreaming || !draftMessage.trim()}>
                      <Send className="mr-2 h-4 w-4" />
                      Send update
                    </Button>
                    <Button
                      onClick={handleFinalize}
                      disabled={!canFinalize || isStreaming || isFinalizing}
                    >
                      {isFinalizing ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Creating plan…
                        </>
                      ) : (
                        <>
                          <Sparkles className="mr-2 h-4 w-4" />
                          Finalise & launch
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
              {(localError || streamError) && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {localError ?? streamError}
                </div>
              )}
            </footer>
          </section>

          <aside className="flex h-full flex-col gap-4">
            <Card className="flex-1 border-slate-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-slate-700">Agent notes</CardTitle>
              </CardHeader>
              <CardContent className="h-full overflow-y-auto text-sm text-slate-700">
                {reasoningBuffer ? (
                  <pre className="whitespace-pre-wrap text-slate-700">{reasoningBuffer}</pre>
                ) : (
                  <p className="text-slate-500">Reasoning will appear here while the agent thinks.</p>
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-slate-700">Conversation summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-slate-700">
                {streamSummary?.responseSummary?.analysis ? (
                  <p className="whitespace-pre-wrap">
                    {streamSummary.responseSummary.analysis}
                  </p>
                ) : (
                  <p className="text-slate-500">Complete at least one exchange to view the rolling summary.</p>
                )}
              </CardContent>
            </Card>
          </aside>
        </div>
      </DialogContent>
    </Dialog>
  );
};
