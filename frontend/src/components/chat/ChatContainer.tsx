"use client";

import React from "react";
import { AlertCircle, RotateCcw } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { useChatScope } from "@/hooks/useChatScope";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ScopeBar } from "./ScopeBar";
import { CitationDrawer } from "./CitationDrawer";
import { PreparingPanel } from "@/components/documents/PreparingPanel";

function TranscriptSkeleton() {
  return (
    <div className="min-h-0 flex-1 space-y-6 overflow-hidden px-4 py-5 sm:px-6" aria-hidden>
      <div className="flex justify-end">
        <div className="skeleton h-9 w-52 rounded-2xl" />
      </div>
      <div className="space-y-2.5">
        <div className="skeleton h-3 w-24" />
        <div className="skeleton h-3 w-[92%]" />
        <div className="skeleton h-3 w-[85%]" />
        <div className="skeleton h-3 w-[60%]" />
      </div>
      <div className="flex justify-end">
        <div className="skeleton h-9 w-40 rounded-2xl" />
      </div>
    </div>
  );
}

export function ChatContainer() {
  const messages = useChatStore((state) => state.messages);
  const isLoading = useChatStore((state) => state.isLoading);
  const isSwitching = useChatStore((state) => state.isSwitching);
  const conversationError = useChatStore((state) => state.conversationError);
  const conversationId = useChatStore((state) => state.conversationId);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const selectConversation = useChatStore((state) => state.selectConversation);

  const { canAsk, blockedReason, readyDocuments, documents } = useChatScope();

  const showPreparing =
    messages.length === 0 && readyDocuments.length === 0 && documents.length > 0;

  const handleSend = (content: string) => {
    void sendMessage(content);
  };

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="flex min-h-0 flex-1 flex-col bg-surface-muted">
        {isSwitching ? (
          <TranscriptSkeleton />
        ) : conversationError ? (
          <div className="flex min-h-0 flex-1 items-center justify-center px-5 py-8">
            <div className="w-full max-w-sm rounded-xl border border-danger-line bg-danger-soft p-5 text-center">
              <AlertCircle className="mx-auto h-5 w-5 text-danger" />
              <h2 className="mt-2 text-ui font-semibold text-danger">
                Couldn’t open this chat
              </h2>
              <p className="mt-1 text-ui leading-relaxed text-ink-muted break-anywhere">
                {conversationError}
              </p>
              <button
                type="button"
                onClick={() => void selectConversation(conversationId)}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-meta font-medium text-ink transition-colors hover:bg-surface-muted"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Try again
              </button>
            </div>
          </div>
        ) : showPreparing ? (
          <PreparingPanel />
        ) : (
          <MessageList
            messages={messages}
            isLoading={isLoading}
            onSelectPrompt={handleSend}
          />
        )}
      </div>

      <div className="shrink-0 border-t border-line bg-surface px-3 py-3 sm:px-4">
        <ScopeBar />
        <ChatInput
          onSend={handleSend}
          isLoading={isLoading}
          canAsk={canAsk}
          blockedReason={blockedReason}
        />
      </div>

      <CitationDrawer />
    </div>
  );
}
