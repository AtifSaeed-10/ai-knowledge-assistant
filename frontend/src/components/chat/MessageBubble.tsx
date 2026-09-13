"use client";

import React from "react";
import { AlertCircle, CircleSlash, RotateCcw } from "lucide-react";
import { Message } from "@/types";
import { SourceList } from "./SourceList";
import { AnswerMarkdown } from "./AnswerMarkdown";
import { MessageActions } from "./MessageActions";
import { useChatStore } from "@/store/useChatStore";
import { withAnswerQuotes, usedCitationsWithFallback } from "@/lib/citations/markers";

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
  const isLoading = useChatStore((state) => state.isLoading);
  const messages = useChatStore((state) => state.messages);
  const retryLastAnswer = useChatStore((state) => state.retryLastAnswer);

  const hasContent = Boolean(message.content?.trim());
  const isSearching = !hasContent && isStreaming;
  const citations = withAnswerQuotes(message.citations, message.content);
  const citedSources = usedCitationsWithFallback(message.citations, message.content);

  const chooseDocumentScope = useChatStore((state) => state.chooseDocumentScope);
  const lastAssistant = [...messages].reverse().find((item) => item.role === "assistant");
  const isLastAssistant = lastAssistant?.id === message.id;
  const canRetry = isLastAssistant && !isStreaming && !isLoading && !message.scopeChoices?.length;
  const scopeChoices = message.scopeChoices || [];

  if (message.role === "user") {
    return (
      <div className="flex animate-rise-in justify-end">
        <div className="max-w-[92%] rounded-2xl rounded-br-md bg-olive px-3.5 py-2.5 text-body leading-relaxed tracking-[-0.01em] text-white sm:max-w-[70%] sm:px-4">
          <p className="whitespace-pre-wrap break-anywhere">{message.content}</p>
        </div>
      </div>
    );
  }

  if (message.status === "error") {
    return (
      <div className="animate-rise-in">
        <div className="rounded-xl border border-danger-line bg-danger-soft p-4">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
            <div className="min-w-0 flex-1">
              <p className="text-ui font-semibold text-danger">Answer not generated</p>
              <p className="mt-1 text-ui leading-relaxed text-ink-muted break-anywhere">
                {message.content}
              </p>

              {canRetry && (
                <button
                  type="button"
                  onClick={() => void retryLastAnswer()}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-meta font-medium text-ink transition-colors hover:bg-surface-muted"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Try again
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-rise-in">
      <div className="mb-2 flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="text-label font-semibold uppercase tracking-[0.09em] text-ink-muted">
          DocuSage
        </span>

        {isStreaming && (
          <span className="inline-flex items-center gap-1.5 text-meta font-medium text-ink-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-sage" aria-hidden />
            {isSearching ? "Searching your documents" : "Writing"}
          </span>
        )}

        {message.status === "stopped" && (
          <span className="inline-flex items-center gap-1 text-meta font-medium text-ink-subtle">
            <CircleSlash className="h-3 w-3" />
            Stopped
          </span>
        )}
      </div>

      {isSearching ? (
        <div className="space-y-2.5 py-1">
          <div className="skeleton h-3 w-[88%]" />
          <div className="skeleton h-3 w-[72%]" />
          <div className="skeleton h-3 w-[56%]" />
        </div>
      ) : (
        <AnswerMarkdown content={message.content} citations={citations} />
      )}

      {scopeChoices.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {scopeChoices.map((choice) => (
            <button
              key={choice.id}
              type="button"
              disabled={isLoading}
              onClick={() => void chooseDocumentScope(choice.id)}
              className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-meta font-medium text-ink transition-colors hover:border-sage hover:bg-olive-soft disabled:cursor-not-allowed disabled:opacity-60"
            >
              {choice.name}
            </button>
          ))}
        </div>
      )}

      {message.status === "stopped" && (
        <p className="mt-2 text-meta text-ink-subtle">
          Generation was stopped, so this answer is incomplete.
        </p>
      )}

      {!isStreaming && citedSources.length > 0 && <SourceList citations={citedSources} />}

      {!isStreaming && hasContent && scopeChoices.length === 0 && (
        <MessageActions
          content={message.content}
          showRetry={canRetry}
          onRetry={() => void retryLastAnswer()}
        />
      )}
    </div>
  );
}
