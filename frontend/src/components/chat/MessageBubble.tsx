"use client";

import React from "react";
import { User, Sparkles } from "lucide-react";
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
    <div className="space-y-3.5">
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
              className="space-y-1.5 pl-1 text-[14.5px] leading-[1.7] text-[#2A322E]"
            >
              {lines
                .filter((line) => line.trim())
                .map((line, lineIndex) => (
                  <li
                    key={`ul-${blockIndex}-${lineIndex}`}
                    className="flex gap-2.5"
                  >
                    <span className="mt-[0.55em] h-1 w-1 shrink-0 rounded-full bg-[#87AB72]" />
                    <span className="min-w-0">
                      {renderInline(line.trim().replace(/^[-*•]\s+/, ""), `ul-${blockIndex}-${lineIndex}`)}
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
              className="space-y-1.5 pl-1 text-[14.5px] leading-[1.7] text-[#2A322E]"
            >
              {lines
                .filter((line) => line.trim())
                .map((line, lineIndex) => (
                  <li
                    key={`ol-${blockIndex}-${lineIndex}`}
                    className="flex gap-2.5"
                  >
                    <span className="w-4 shrink-0 text-[13px] font-medium tabular-nums text-[#98A395]">
                      {lineIndex + 1}.
                    </span>
                    <span className="min-w-0">
                      {renderInline(line.trim().replace(/^\d+\.\s+/, ""), `ol-${blockIndex}-${lineIndex}`)}
                    </span>
                  </li>
                ))}
            </ol>
          );
        }

        return (
          <p
            key={`block-${blockIndex}`}
            className="whitespace-pre-wrap text-[14.5px] leading-[1.7] tracking-[-0.01em] text-[#2A322E]"
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
        <div className="flex max-w-[85%] items-start gap-2.5 sm:max-w-[70%]">
          <div className="min-w-0">
            <div className="rounded-2xl rounded-tr-md bg-[#4A5D23] px-4 py-2.5 text-[14px] leading-relaxed tracking-[-0.01em] text-white shadow-sm">
              <div className="whitespace-pre-wrap">{message.content}</div>
            </div>
            {message.timestamp && (
              <p className="mt-1.5 px-1 text-right text-[11px] text-[#98A395]">
                {new Date(message.timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            )}
          </div>
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#1C241F] text-white">
            <User className="h-3.5 w-3.5" />
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 animate-in fade-in slide-in-from-bottom-1 duration-300">
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#EBEFEA] bg-[#F6F7F4] text-[#4A5D23]">
        <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />
      </span>

      <div className="min-w-0 max-w-[92%] flex-1 sm:max-w-[85%]">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[12px] font-semibold tracking-[-0.01em] text-[#1C241F]">
            DocuSage
          </span>
          {isStreaming && (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-[#6F7B6B]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#87AB72] opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#4A5D23]" />
              </span>
              {showThinking ? "Searching documents" : "Writing"}
            </span>
          )}
        </div>

        <div className="rounded-2xl rounded-tl-md border border-[#EBEFEA] bg-white px-4 py-3.5 shadow-[0_1px_2px_rgba(28,36,31,0.03)] sm:px-5 sm:py-4">
          {showThinking ? (
            <div className="space-y-3 py-1 animate-in fade-in duration-300">
              <div className="flex items-center gap-2 text-[13px] text-[#6F7B6B]">
                <span className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#87AB72] [animation-delay:-0.28s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#87AB72] [animation-delay:-0.14s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#87AB72]" />
                </span>
                Retrieving relevant passages…
              </div>
              <div className="space-y-2">
                <div className="h-2.5 w-[92%] animate-pulse rounded bg-[#EFF1EC]" />
                <div className="h-2.5 w-[78%] animate-pulse rounded bg-[#EFF1EC]" />
                <div className="h-2.5 w-[64%] animate-pulse rounded bg-[#EFF1EC]" />
              </div>
            </div>
          ) : (
            <div className="animate-in fade-in duration-200">
              <AnswerContent content={message.content} />
            </div>
          )}

          {!isUser &&
            message.citations &&
            message.citations.length > 0 &&
            !isStreaming && (
              <SourceList citations={message.citations} />
            )}
        </div>

        {message.timestamp && !showThinking && (
          <p className="mt-1.5 px-1 text-[11px] text-[#98A395]">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        )}
      </div>
    </div>
  );
}
