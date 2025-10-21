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
import { useConfigStore } from '@/lib/stores/config';

interface ConversationModalProps {
  isOpen: boolean;
  request: CreatePlanRequest | null;
  sessionKey: string | null;
  onClose: () => void;
  onFinalize: (result: ConversationFinalizeResult) => Promise<void>;
  isFinalizing: boolean;
}

const MESSAGE_BG: Record<ConversationMessage['role'], string> = {
  user: 'bg-indigo-950/40 border-indigo-800',
  assistant: 'bg-slate-800 border-slate-700',
};

export const ConversationModal: React.FC<ConversationModalProps> = ({
  isOpen,
  request,
  sessionKey,
  onClose,
  onFinalize,
  isFinalizing,
}) => {
  const defaultModelFromStore = useConfigStore((state) => state.defaultModel);
  const initialPrompt = request?.prompt ?? '';
  const fallbackModel = defaultModelFromStore || 'gpt-5-mini-2025-08-07';
  const resolvedModel = request?.llm_model ?? fallbackModel;
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

    console.log('[ConversationModal] Modal opened, attempting to start conversation...');
    console.log('[ConversationModal] Initial prompt:', initialPrompt);
    console.log('[ConversationModal] Model:', resolvedModel);
    console.log('[ConversationModal] Session key:', sessionKey);

    const trimmedPrompt = initialPrompt.trim();
    if (!trimmedPrompt) {
      console.error('[ConversationModal] Empty prompt detected');
      setLocalError('Cannot start conversation without an initial brief.');
      return;
    }

    setHasAttemptedStart(true);
    setLocalError(null);
    console.log('[ConversationModal] Starting conversation with Responses API...');
    startConversation()
      .then(() => {
        console.log('[ConversationModal] Conversation started successfully');
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : 'Failed to start intake conversation.';
        console.error('[ConversationModal] Conversation start failed:', error);
        console.error('[ConversationModal] Error message:', message);
        setLocalError(message);
        setHasAttemptedStart(false);
      });
  }, [hasAttemptedStart, initialPrompt, isOpen, sessionKey, startConversation, resolvedModel]);

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
    console.log('[ConversationModal] Sending user message:', trimmed);
    setLocalError(null);
    try {
      await sendUserMessage(trimmed);
      console.log('[ConversationModal] Message sent successfully');
      setDraftMessage('');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send message.';
      console.error('[ConversationModal] Send message failed:', error);
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
      <DialogContent className="!fixed !inset-0 !top-0 !left-0 !right-0 !bottom-0 !h-screen !w-screen !max-w-none !translate-x-0 !translate-y-0 !transform-none overflow-hidden border-0 bg-slate-950 p-0 shadow-none !m-0">
        <DialogHeader className="shrink-0 px-6 py-4 border-b border-slate-800">
          <DialogTitle className="flex items-center gap-3 text-3xl font-semibold text-slate-100">
            <Sparkles className="h-6 w-6 text-indigo-400" />
            Enrich your plan request
          </DialogTitle>
          <DialogDescription className="max-w-3xl text-base text-slate-400">
            We send your initial brief to the planning agent, who will guide you through the must-have details before Luigi starts.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-0 grid grid-cols-1 gap-6 px-6 py-4 overflow-hidden xl:grid-cols-[1.5fr_1fr]">
          <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-900 shadow-sm">
            <header className="flex items-center justify-between border-b border-slate-800 px-8 py-5">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
                <MessageCircle className="h-4 w-4 text-indigo-400" />
                Conversation timeline
              </div>
              <Badge variant="secondary" className="rounded-full px-3 text-xs uppercase bg-slate-800 text-slate-300">
                Model: {resolvedModel}
              </Badge>
            </header>
            <div className="flex-1 min-h-0 space-y-5 overflow-y-auto px-8 py-6">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={`rounded-lg border px-5 py-4 text-sm leading-relaxed text-slate-200 shadow-sm ${MESSAGE_BG[message.role]}`}
                >
                  <header className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-400">
                    <span>{message.role === 'assistant' ? 'PlanExe Agent' : 'You'}</span>
                    <span>{new Date(message.createdAt).toLocaleTimeString()}</span>
                  </header>
                  <p className="whitespace-pre-wrap">
                    {message.content || (message.streaming ? 'Thinking…' : '')}
                  </p>
                  {message.streaming && (
                    <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Agent drafting response…
                    </div>
                  )}
                </article>
              ))}
            </div>
            <footer className="shrink-0 flex flex-col border-t border-slate-800 bg-slate-900/50 px-8 py-5">
              <div className="flex flex-col gap-3 flex-1">
                <Textarea
                  value={draftMessage}
                  onChange={(event) => setDraftMessage(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Add constraints, dependencies, resources, dates…"
                  className="h-32 text-base resize-none"
                  disabled={isStreaming || isFinalizing}
                />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-slate-400">
                    Press <kbd className="rounded border border-slate-700 bg-slate-800 px-1 text-slate-300">⌘</kbd>
                    +<kbd className="rounded border border-slate-700 bg-slate-800 px-1 text-slate-300">Enter</kbd> to send
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
                <div className="mt-3 flex flex-col gap-3 rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">
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

          <aside className="flex h-full min-h-0 flex-col gap-4 overflow-hidden">
            <Card className="flex flex-col flex-1 min-h-0 border-slate-800 bg-slate-900 overflow-hidden">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                  Answer
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 min-h-0 overflow-y-auto rounded-lg bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
                {textBuffer ? (
                  <p className="whitespace-pre-wrap text-slate-200">{textBuffer}</p>
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

            <Card className="flex flex-col flex-shrink-0 h-[25vh] border-slate-800 bg-slate-900 overflow-hidden">
              <CardHeader className="pb-3 shrink-0">
                <CardTitle className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                  Reasoning summary
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 min-h-0 overflow-y-auto rounded-lg bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
                {reasoningBuffer ? (
                  <pre className="whitespace-pre-wrap text-slate-200">{reasoningBuffer}</pre>
                ) : (
                  <p className="text-slate-500">Reasoning traces will stream here when available.</p>
                )}
              </CardContent>
            </Card>

            <Card className="flex flex-col flex-shrink-0 h-[25vh] border-slate-800 bg-slate-900 overflow-hidden">
              <CardHeader className="pb-3 shrink-0">
                <CardTitle className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                  Data / JSON
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 min-h-0 overflow-y-auto rounded-lg bg-slate-950/40 px-4 py-3 text-xs text-slate-300">
                {jsonChunks.length > 0 ? (
                  <pre className="whitespace-pre-wrap text-slate-200">{JSON.stringify(jsonChunks, null, 2)}</pre>
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
