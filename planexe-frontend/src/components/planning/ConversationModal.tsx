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
import { AlertCircle, Loader2, MessageCircle, RefreshCcw, Send, Sparkles } from 'lucide-react';
import {
  ConversationFinalizeResult,
  ConversationMessage,
  useResponsesConversation,
} from '@/lib/conversation/useResponsesConversation';
import { CreatePlanRequest } from '@/lib/api/fastapi-client';

interface ConversationModalProps {
  isOpen: boolean;
  request: CreatePlanRequest | null;
  sessionKey: string | null;
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
  sessionKey,
  onClose,
  onFinalize,
  isFinalizing,
}) => {
  const initialPrompt = request?.prompt ?? '';
  const resolvedModel = request?.llm_model ?? 'gpt-4o-mini';
  const metadata = useMemo(
    () => ({
      speedVsDetail: request?.speed_vs_detail,
      sessionKey: sessionKey ?? undefined,
    }),
    [request?.speed_vs_detail, sessionKey],
  );

  const {
    messages,
    conversationId,
    currentResponseId,
    startConversation,
    sendUserMessage,
    finalizeConversation,
    resetConversation,
    isStreaming,
    streamFinal,
    streamError,
    textBuffer,
    reasoningBuffer,
    jsonChunks,
    usage,
  } = useResponsesConversation({
    initialPrompt,
    modelKey: resolvedModel,
    metadata,
    sessionKey: sessionKey ?? undefined,
  });

  const tokenUsage = (usage ?? null) as {
    input_tokens?: number;
    output_tokens?: number;
    reasoning_tokens?: number;
  } | null;

  const [draftMessage, setDraftMessage] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [hasAttemptedStart, setHasAttemptedStart] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setDraftMessage('');
      setLocalError(null);
      setHasAttemptedStart(false);
      resetConversation();
    }
  }, [isOpen, resetConversation]);

  useEffect(() => {
    setHasAttemptedStart(false);
  }, [sessionKey]);

  useEffect(() => {
    if (!isOpen || hasAttemptedStart) {
      return;
    }

    const trimmedPrompt = initialPrompt.trim();
    if (!trimmedPrompt) {
      setLocalError('Cannot start conversation without an initial brief.');
      return;
    }

    setHasAttemptedStart(true);
    setLocalError(null);
    startConversation().catch((error) => {
      const message = error instanceof Error ? error.message : 'Failed to start intake conversation.';
      setLocalError(message);
      setHasAttemptedStart(false);
    });
  }, [hasAttemptedStart, initialPrompt, isOpen, sessionKey, startConversation]);

  const handleRetryConversation = () => {
    if (isStreaming) {
      return;
    }
    resetConversation();
    setLocalError(null);
    setHasAttemptedStart(true);
    startConversation().catch((error) => {
      const message = error instanceof Error ? error.message : 'Failed to start intake conversation.';
      setLocalError(message);
      setHasAttemptedStart(false);
    });
  };

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
      <DialogContent className="h-[calc(100vh-1.5rem)] w-[min(1440px,calc(100vw-1.5rem))] max-w-none overflow-hidden rounded-3xl border border-slate-200 bg-slate-50 p-0 shadow-2xl sm:h-[calc(100vh-2rem)] sm:w-[min(1600px,calc(100vw-2rem))]">
        <DialogHeader className="px-10 pt-8 pb-4">
          <DialogTitle className="flex items-center gap-3 text-3xl font-semibold text-slate-900">
            <Sparkles className="h-6 w-6 text-indigo-600" />
            Enrich your plan request
          </DialogTitle>
          <DialogDescription className="max-w-3xl text-base text-slate-600">
            We send your initial brief to the planning agent, who will guide you through the must-have details before Luigi starts.
          </DialogDescription>
        </DialogHeader>

        <div className="grid h-full grid-cols-1 gap-8 px-8 pb-8 md:px-10 md:pb-10 xl:grid-cols-[3fr_1.25fr]">
          <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <header className="flex items-center justify-between border-b border-slate-200 px-8 py-5">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-600">
                <MessageCircle className="h-4 w-4 text-indigo-500" />
                Conversation timeline
              </div>
              <Badge variant="secondary" className="rounded-full px-3 text-xs uppercase">
                Model: {resolvedModel}
              </Badge>
            </header>
            <div className="flex-1 min-h-0 space-y-5 overflow-y-auto px-8 py-6">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={`rounded-xl border px-5 py-4 text-sm leading-relaxed text-slate-800 shadow-sm ${MESSAGE_BG[message.role]}`}
                >
                  <header className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
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
            <footer className="border-t border-slate-200 bg-slate-50 px-8 py-5">
              <div className="space-y-3">
                <Textarea
                  value={draftMessage}
                  onChange={(event) => setDraftMessage(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Add constraints, dependencies, resources, dates…"
                  className="min-h-[140px] text-base"
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
                <div className="mt-3 flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{localError ?? streamError}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRetryConversation}
                      disabled={isStreaming}
                    >
                      <RefreshCcw className="mr-2 h-3 w-3" />
                      Retry intake
                    </Button>
                  </div>
                </div>
              )}
            </footer>
          </section>

          <aside className="flex h-full min-h-0 flex-col gap-5">
            <Card className="flex-1 min-h-0 border-slate-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                  Answer
                </CardTitle>
              </CardHeader>
              <CardContent className="h-full min-h-0 overflow-y-auto rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                {textBuffer ? (
                  <p className="whitespace-pre-wrap text-slate-800">{textBuffer}</p>
                ) : (
                  <p className="text-slate-500">The assistant response will appear here once the stream completes.</p>
                )}
                <div className="mt-4 space-y-1 text-xs text-slate-500">
                  {conversationId && <p>Conversation ID: {conversationId}</p>}
                  {currentResponseId && <p>Response ID: {currentResponseId}</p>}
                  {tokenUsage && (
                    <p>
                      Tokens — input: {String(tokenUsage.input_tokens ?? '–')}, output:{' '}
                      {String(tokenUsage.output_tokens ?? '–')}, reasoning:{' '}
                      {String(tokenUsage.reasoning_tokens ?? '–')}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                  Reasoning summary
                </CardTitle>
              </CardHeader>
              <CardContent className="max-h-48 overflow-y-auto rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                {reasoningBuffer ? (
                  <pre className="whitespace-pre-wrap text-slate-700">{reasoningBuffer}</pre>
                ) : (
                  <p className="text-slate-500">Reasoning traces will stream here when available.</p>
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                  Data / JSON
                </CardTitle>
              </CardHeader>
              <CardContent className="max-h-52 overflow-y-auto rounded-xl bg-slate-50 px-4 py-3 text-xs text-slate-700">
                {jsonChunks.length > 0 ? (
                  <pre className="whitespace-pre-wrap">{JSON.stringify(jsonChunks, null, 2)}</pre>
                ) : (
                  <p className="text-slate-500">No structured deltas received yet.</p>
                )}
              </CardContent>
            </Card>
          </aside>
        </div>
      </DialogContent>
    </Dialog>
  );
};
