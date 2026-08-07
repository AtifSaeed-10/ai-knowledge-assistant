"use client";

import React, { useRef, useEffect } from "react";
import { Message } from "@/types";
import { MessageBubble } from "./MessageBubble";
import { ArrowRight, Quote, Search, Sparkles } from "lucide-react";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onSelectPrompt?: (prompt: string) => void;
}

const SAMPLE_PROMPTS = [
  "Summarize the key findings in my documents",
  "What risks or warnings are mentioned?",
  "List important dates and deadlines",
];

export function MessageList({
  messages,
  isLoading,
  onSelectPrompt,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center overflow-y-auto px-5 py-8 sm:px-8">
        <div className="w-full max-w-lg animate-in fade-in slide-in-from-bottom-2 duration-500">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#EBEFEA] bg-white text-[#4A5D23] shadow-[0_1px_2px_rgba(28,36,31,0.04)]">
            <Sparkles className="h-5 w-5" strokeWidth={1.75} />
          </span>

          <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#98A395]">
            Ready to research
          </p>
          <h3 className="mt-2 text-[20px] font-semibold leading-tight tracking-[-0.02em] text-[#1C241F] sm:text-[22px]">
            Ask anything grounded in your documents
          </h3>
          <p className="mt-2 text-[14px] leading-relaxed text-[#6F7B6B]">
            Answers are retrieved from your indexed PDFs and linked back to the
            source pages used.
          </p>

          {onSelectPrompt && (
            <div className="mt-6 space-y-2">
              <p className="px-0.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
                Try asking
              </p>
              {SAMPLE_PROMPTS.map((prompt, i) => (
                <button
                  key={prompt}
                  onClick={() => onSelectPrompt(prompt)}
                  className="group flex w-full items-center gap-3 rounded-xl border border-[#EBEFEA] bg-white px-3.5 py-3 text-left transition-all duration-150 hover:border-[#D8DED5] hover:bg-[#F6F7F4] animate-in fade-in slide-in-from-bottom-1 fill-mode-both"
                  style={{
                    animationDelay: `${120 + i * 60}ms`,
                    animationDuration: "400ms",
                  }}
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#F6F7F4] text-[#4A5D23]">
                    {prompt.startsWith("Summarize") ? (
                      <Quote className="h-3.5 w-3.5" strokeWidth={1.75} />
                    ) : (
                      <Search className="h-3.5 w-3.5" strokeWidth={1.75} />
                    )}
                  </span>
                  <span className="min-w-0 flex-1 text-[13px] font-medium tracking-[-0.01em] text-[#1C241F]">
                    {prompt}
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-[#C4CBC0] transition-all group-hover:translate-x-0.5 group-hover:text-[#4A5D23]" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  const lastMessage = messages[messages.length - 1];
  const isStreamingAssistant =
    isLoading && lastMessage?.role === "assistant";

  return (
    <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:space-y-6 sm:px-6 sm:py-6">
      {messages.map((message, index) => {
        const isLastAssistant =
          isStreamingAssistant &&
          index === messages.length - 1 &&
          message.role === "assistant";

        return (
          <MessageBubble
            key={message.id}
            message={message}
            isStreaming={isLastAssistant}
          />
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
