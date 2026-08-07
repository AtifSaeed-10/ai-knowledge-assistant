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
  "Summarize the key findings",
  "What risks are mentioned?",
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
        <div className="w-full max-w-md animate-in fade-in slide-in-from-bottom-2 duration-500">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#F1F3EF] text-[#4A5D23]">
            <Sparkles className="h-4 w-4" strokeWidth={1.75} />
          </span>

          <h3 className="mt-4 text-[18px] font-semibold tracking-[-0.02em] text-[#1C241F]">
            Ask a question
          </h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-[#6F7B6B]">
            Answers are grounded in your documents and linked to source pages.
          </p>

          {onSelectPrompt && (
            <div className="mt-5 space-y-1.5">
              {SAMPLE_PROMPTS.map((prompt, i) => (
                <button
                  key={prompt}
                  onClick={() => onSelectPrompt(prompt)}
                  className="group flex w-full items-center gap-2.5 rounded-xl border border-transparent bg-white px-3 py-2.5 text-left transition-colors hover:border-[#EBEFEA] hover:bg-[#F6F7F4] animate-in fade-in slide-in-from-bottom-1 fill-mode-both"
                  style={{
                    animationDelay: `${80 + i * 50}ms`,
                    animationDuration: "350ms",
                  }}
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[#F6F7F4] text-[#4A5D23]">
                    {i === 0 ? (
                      <Quote className="h-3.5 w-3.5" strokeWidth={1.75} />
                    ) : (
                      <Search className="h-3.5 w-3.5" strokeWidth={1.75} />
                    )}
                  </span>
                  <span className="min-w-0 flex-1 text-[13px] font-medium text-[#1C241F]">
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
    <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-5 sm:px-6 sm:py-6">
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
