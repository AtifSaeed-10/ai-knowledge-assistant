"use client";

import React from "react";
import { Sparkles } from "lucide-react";
import { Message } from "@/types";
import { SourceList } from "./SourceList";

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong
          key={`${keyPrefix}-b-${index}`}
          className="font-semibold text-[#1C241F]"
        >
          {part.slice(2, -2)}
        </strong>
      );
    }

    return <React.Fragment key={`${keyPrefix}-t-${index}`}>{part}</React.Fragment>;
  });
}

function AnswerContent({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/).filter((block) => block.trim().length > 0);

  if (blocks.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      {blocks.map((block, blockIndex) => {
        const lines = block.split("\n").map((line) => line.trimEnd());
        const isUnordered = lines.every(
          (line) => !line.trim() || /^[-*•]\s+/.test(line.trim())
        );
        const isOrdered = lines.every(
          (line) => !line.trim() || /^\d+\.\s+/.test(line.trim())
        );

        if (isUnordered && lines.some((line) => line.trim())) {
          return (
            <ul
              key={`block-${blockIndex}`}
              className="space-y-1.5 text-[15px] leading-[1.65] text-[#2A322E]"
            >
              {lines
                .filter((line) => line.trim())
                .map((line, lineIndex) => (
                  <li
                    key={`ul-${blockIndex}-${lineIndex}`}
                    className="flex gap-2.5"
                  >
                    <span className="mt-[0.6em] h-1 w-1 shrink-0 rounded-full bg-[#87AB72]" />
                    <span className="min-w-0">
                      {renderInline(
                        line.trim().replace(/^[-*•]\s+/, ""),
                        `ul-${blockIndex}-${lineIndex}`
                      )}
                    </span>
                  </li>
                ))}
            </ul>
          );
        }

        if (isOrdered && lines.some((line) => line.trim())) {
          return (
            <ol
              key={`block-${blockIndex}`}
              className="space-y-1.5 text-[15px] leading-[1.65] text-[#2A322E]"
            >
              {lines
                .filter((line) => line.trim())
                .map((line, lineIndex) => (
                  <li
                    key={`ol-${blockIndex}-${lineIndex}`}
                    className="flex gap-2.5"
                  >
                    <span className="w-4 shrink-0 pt-[0.1em] text-[12px] font-semibold tabular-nums text-[#98A395]">
                      {lineIndex + 1}.
                    </span>
                    <span className="min-w-0">
                      {renderInline(
                        line.trim().replace(/^\d+\.\s+/, ""),
                        `ol-${blockIndex}-${lineIndex}`
                      )}
                    </span>
                  </li>
                ))}
            </ol>
          );
        }

        return (
          <p
            key={`block-${blockIndex}`}
            className="whitespace-pre-wrap text-[15px] leading-[1.65] tracking-[-0.01em] text-[#2A322E]"
          >
            {lines.map((line, lineIndex) => (
              <React.Fragment key={`p-${blockIndex}-${lineIndex}`}>
                {lineIndex > 0 && <br />}
                {renderInline(line, `p-${blockIndex}-${lineIndex}`)}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}

export function MessageBubble({
  message,
  isStreaming = false,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const hasContent = Boolean(message.content?.trim());
  const showThinking = !isUser && !hasContent && isStreaming;

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
            <AnswerContent content={message.content} />
          </div>
        )}

        {!isUser &&
          message.citations &&
          message.citations.length > 0 &&
          !isStreaming && <SourceList citations={message.citations} />}
      </div>
    </div>
  );
}
