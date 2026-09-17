"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowRight, BookOpen, ListTree, ScrollText } from "lucide-react";
import { Message } from "@/types";
import { MessageBubble } from "./MessageBubble";
import { useChatScope } from "@/hooks/useChatScope";
import {
  citedDocumentIds,
  suggestFollowUps,
} from "@/lib/workspace/followUpSuggestions";

const PIN_THRESHOLD_PX = 96;

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onSelectPrompt: (prompt: string, documentIds?: string[]) => void;
}

const FOCUSED_PROMPTS = [
  { label: "Summarize this document", icon: ScrollText },
  { label: "Walk me through the key events", icon: ListTree },
  { label: "Who are the main people, and what happens to them?", icon: BookOpen },
];

const LIBRARY_PROMPTS = [
  { label: "Summarize the key findings", icon: ScrollText },
  { label: "Walk me through the key events", icon: ListTree },
  { label: "Explain the main ideas in simple terms", icon: BookOpen },
];

const REFUSAL_RE =
  /couldn['’]t find|not enough information|no relevant information|does not give a specific example/i;

export function MessageList({ messages, isLoading, onSelectPrompt }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isPinned, setIsPinned] = useState(true);
  const { mode, selectedDocument, canAsk } = useChatScope();

  const lastMessage = messages[messages.length - 1];
  const streamingLength =
    isLoading && lastMessage?.role === "assistant" ? lastMessage.content.length : 0;

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "auto") => {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTo({ top: element.scrollHeight, behavior });
  }, []);

  const handleScroll = useCallback(() => {
    const element = scrollRef.current;
    if (!element) return;
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
    setIsPinned(distance <= PIN_THRESHOLD_PX);
  }, []);

  // A new turn always scrolls into view; the user is the one who started it.
  useEffect(() => {
    if (messages.length === 0) return;
    setIsPinned(true);
    scrollToBottom("smooth");
  }, [messages.length, scrollToBottom]);

  // While tokens arrive, follow the answer only if the reader stayed at the bottom.
  useEffect(() => {
    if (streamingLength === 0 || !isPinned) return;
    scrollToBottom("auto");
  }, [streamingLength, isPinned, scrollToBottom]);

  const liveStatus = useMemo(() => {
    if (isLoading) return "Reading your documents and writing an answer.";
    if (lastMessage?.role !== "assistant") return "";
    if (lastMessage.status === "error") return "The answer could not be generated.";
    if (lastMessage.status === "stopped") return "Generation stopped.";
    if (lastMessage.content) return "Answer ready.";
    return "";
  }, [isLoading, lastMessage]);

  const prompts = mode === "super_focused" && selectedDocument ? FOCUSED_PROMPTS : LIBRARY_PROMPTS;

  const lastUser = [...messages].reverse().find((item) => item.role === "user");
  const followUps = useMemo(() => {
    if (lastMessage?.role !== "assistant" || !lastMessage.content?.trim()) return [];
    return suggestFollowUps(lastUser?.content || "", lastMessage.content);
  }, [lastMessage, lastUser?.content]);
  const followUpDocumentIds = citedDocumentIds(lastMessage?.citations);

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        aria-busy={isLoading}
        className="scroll-area min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-6 sm:py-5"
      >
        {messages.length === 0 ? (
          <div className="flex h-full min-h-0 items-center justify-center">
            <div className="w-full max-w-md animate-rise-in py-6">
              <h2 className="text-h2 font-semibold tracking-[-0.02em] text-ink">
                Ask this document anything
              </h2>
              <p className="mt-1.5 text-ui leading-relaxed text-ink-muted">
                DocuSage answers only from your files — with a citation back to
                the exact page. Try a summary, a later plot point, or a definition.
              </p>

              <div className="mt-5 space-y-1.5">
                {prompts.map(({ label, icon: Icon }) => (
                  <button
                    key={label}
                    type="button"
                    disabled={!canAsk}
                    onClick={() => onSelectPrompt(label)}
                    className="group flex w-full items-center gap-2.5 rounded-xl border border-transparent bg-surface px-3 py-2.5 text-left shadow-card transition-colors hover:border-line hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:border-transparent disabled:hover:bg-surface"
                  >
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-olive-soft text-olive">
                      <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
                    </span>
                    <span className="min-w-0 flex-1 text-ui font-medium text-ink">{label}</span>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-ink-icon transition-transform group-hover:translate-x-0.5" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((message, index) => (
              <MessageBubble
                key={message.id}
                message={message}
                isStreaming={
                  isLoading && index === messages.length - 1 && message.role === "assistant"
                }
              />
            ))}
            {!isLoading &&
              lastMessage?.role === "assistant" &&
              lastMessage.status === "ok" &&
              Boolean(lastMessage.content?.trim()) &&
              !REFUSAL_RE.test(lastMessage.content) &&
              canAsk &&
              followUps.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {followUps.map((label) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() =>
                        onSelectPrompt(
                          label,
                          followUpDocumentIds.length > 0 ? followUpDocumentIds : undefined
                        )
                      }
                      className="max-w-full rounded-full border border-line bg-surface px-3 py-1.5 text-left text-meta font-medium text-ink-muted transition-colors hover:border-sage hover:bg-olive-soft hover:text-ink"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
          </div>
        )}
      </div>

      {!isPinned && messages.length > 0 && (
        <button
          type="button"
          onClick={() => {
            setIsPinned(true);
            scrollToBottom("smooth");
          }}
          className="absolute bottom-3 left-1/2 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-meta font-medium text-ink shadow-raised transition-colors hover:bg-surface-muted"
        >
          <ArrowDown className="h-3.5 w-3.5" />
          Jump to latest
        </button>
      )}

      <span className="sr-only" aria-live="polite">
        {liveStatus}
      </span>
    </div>
  );
}
