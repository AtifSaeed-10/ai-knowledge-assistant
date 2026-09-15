"use client";

import React, { KeyboardEvent, useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { isSocialMessage, isWorkspaceCommand } from "@/lib/workspace/chatCommand";
import { cn } from "@/lib/cn";

const MAX_HEIGHT = 180;

interface ChatInputProps {
  onSend: (content: string) => void;
  isLoading: boolean;
  /** False when there is nothing to search yet. */
  canAsk: boolean;
  blockedReason: string | null;
}

export function ChatInput({ onSend, isLoading, canAsk, blockedReason }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const stopGeneration = useChatStore((state) => state.stopGeneration);
  const focusToken = useChatStore((state) => state.composerFocusToken);

  useEffect(() => {
    if (focusToken > 0) textareaRef.current?.focus();
  }, [focusToken]);

  const resize = () => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, MAX_HEIGHT)}px`;
  };

  const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value);
    resize();
  };

  const commandReady = isWorkspaceCommand(input);
  const socialReady = isSocialMessage(input);
  const canSendText = canAsk || commandReady || socialReady;

  const handleSend = () => {
    const value = input.trim();
    if (!value || isLoading || !canSendText) return;

    onSend(value);
    setInput("");

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.focus();
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const placeholder = !canAsk
    ? blockedReason || "Waiting for a ready document…"
    : isLoading
      ? "Type your next question while this one answers…"
      : "Ask a question about your documents…";

  const readyToSend = Boolean(input.trim()) && !isLoading && canSendText;

  return (
    <div>
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl bg-surface-sunken p-1.5 pl-3.5 transition-colors",
          canSendText
            ? "focus-within:bg-surface"
            : "opacity-80"
        )}
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          aria-label="Ask a question about your documents"
          className="min-h-[42px] flex-1 resize-none bg-transparent py-2.5 text-body leading-relaxed tracking-[-0.01em] text-ink outline-none placeholder:text-ink-subtle disabled:cursor-not-allowed"
          style={{ maxHeight: MAX_HEIGHT }}
        />

        {isLoading ? (
          <button
            type="button"
            onClick={stopGeneration}
            aria-label="Stop generating"
            title="Stop generating"
            className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-ink text-paper transition-colors hover:bg-ink-soft sm:h-9 sm:w-9"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSend}
            disabled={!readyToSend}
            aria-label="Send question"
            title="Send question"
            className={cn(
              "mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors sm:h-9 sm:w-9",
              readyToSend
                ? "bg-olive text-white hover:bg-olive-dark"
                : "bg-surface-sunken text-ink-icon"
            )}
          >
            <ArrowUp className="h-4 w-4" strokeWidth={2.25} />
          </button>
        )}
      </div>

      <p className="mt-1.5 hidden px-1 text-meta text-ink-subtle sm:block">
        {commandReady
          ? "This will move the PDF — it will not search the document."
          : canAsk || socialReady
            ? "Enter to send · Shift + Enter for a new line"
            : blockedReason || "Waiting for a ready document"}
      </p>
    </div>
  );
}
