"use client";

import React from "react";
import { Sparkles } from "lucide-react";
import { Message } from "@/types";
import { SourceList } from "./SourceList";
import { AnswerMarkdown } from "./AnswerMarkdown";
import { MessageActions } from "./MessageActions";
import { useChatStore } from "@/store/useChatStore";

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

export function MessageBubble({
  message,
  isStreaming = false,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const hasContent = Boolean(message.content?.trim());
  const showThinking = !isUser && !hasContent && isStreaming;
  const isLoading = useChatStore((state) => state.isLoading);
  const messages = useChatStore((state) => state.messages);
  const regenerateLast = useChatStore((state) => state.regenerateLast);

  const lastAssistant = [...messages].reverse().find((item) => item.role === "assistant");
  const showRegenerate =
    !isUser &&
    !isStreaming &&
    !isLoading &&
    lastAssistant?.id === message.id &&
    hasContent;

  if (isUser) {
    return (
      <div className="flex justify-end animate-in fade-in slide-in-from-bottom-1 duration-300">
        <div className="max-w-[85%] sm:max-w-[68%]">
          <div className="rounded-2xl rounded-br-md bg-[#4A5D23] px-4 py-2.5 text-[14px] leading-relaxed tracking-[-0.01em] text-white">
            <div className="whitespace-pre-wrap">{message.content}</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-1 duration-300">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#F1F3EF] text-[#4A5D23]">
          <Sparkles className="h-3 w-3" strokeWidth={1.75} />
        </span>
        <span className="text-[12px] font-semibold tracking-[-0.01em] text-[#1C241F]">
          DocuSage
        </span>
        {isStreaming && (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-[#6F7B6B]">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#87AB72] opacity-50" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#4A5D23]" />
            </span>
            {showThinking ? "Searching" : "Writing"}
          </span>
        )}
      </div>

      <div className="pl-8">
        {showThinking ? (
          <div className="space-y-2.5 py-1 animate-in fade-in duration-300">
            <div className="h-3 w-[88%] rounded animate-shimmer" />
            <div className="h-3 w-[72%] rounded animate-shimmer" />
            <div className="h-3 w-[56%] rounded animate-shimmer" />
            <p className="pt-1 text-[12px] text-[#98A395]">
              Retrieving relevant passages…
            </p>
          </div>
        ) : (
          <div className="animate-in fade-in duration-200">
            <AnswerMarkdown content={message.content} />
          </div>
        )}

        {!isUser &&
          message.citations &&
          message.citations.length > 0 &&
          !isStreaming && <SourceList citations={message.citations} />}

        {!isUser && hasContent && !isStreaming && (
          <MessageActions
            content={message.content}
            showRegenerate={showRegenerate}
            onRegenerate={() => void regenerateLast()}
          />
        )}
      </div>
    </div>
  );
}
