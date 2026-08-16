import React, { useState, KeyboardEvent, useRef } from "react";
import { ArrowUp, Square } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";

interface ChatInputProps {
  onSend: (content: string) => void;
  isLoading: boolean;
  disabled: boolean;
}

export const ChatInput = ({
  onSend,
  isLoading,
  disabled,
}: ChatInputProps) => {
  const [input, setInput] = useState("");
  const { activeCitation, setActiveCitation, productMode, stopGeneration } = useChatStore();
  const selectedDocumentId = useDocumentStore((state) => state.selectedDocumentId);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const placeholder = disabled
    ? productMode === "super_focused" && !selectedDocumentId
      ? "Select a document for Super Focused mode…"
      : "Waiting for a ready document…"
    : isLoading
      ? "Generating answer…"
      : productMode === "super_focused"
        ? "Ask a question about the selected document…"
        : "Ask about your documents…";

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);

    if (activeCitation && val.length > 0) {
      setActiveCitation(null);
    }

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        160
      )}px`;
    }
  };

  const handleSend = () => {
    if (!input.trim() || isLoading || disabled) return;
    onSend(input.trim());
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = Boolean(input.trim()) && !isLoading && !disabled;

  return (
    <div>
      <div
        className={`flex items-end gap-2 rounded-2xl border bg-white p-1.5 pl-3.5 shadow-[0_1px_2px_rgba(28,36,31,0.04)] transition-shadow ${
          disabled
            ? "border-[#EBEFEA] opacity-70"
            : "border-[#EBEFEA] focus-within:border-[#87AB72] focus-within:shadow-[0_0_0_3px_rgba(135,171,114,0.14)]"
        }`}
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled || isLoading}
          placeholder={placeholder}
          rows={1}
          className="max-h-40 min-h-[42px] flex-1 resize-none bg-transparent py-2.5 text-[14px] leading-relaxed tracking-[-0.01em] text-[#1C241F] outline-none placeholder:text-[#98A395] disabled:cursor-not-allowed"
        />

        {isLoading ? (
          <button
            type="button"
            onClick={stopGeneration}
            aria-label="Stop generation"
            title="Stop generation"
            className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#1C241F] text-white transition-colors hover:bg-[#2A322E]"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
          </button>
        ) : (
        <button
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          className={`mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors ${
            canSend
              ? "bg-[#4A5D23] text-white hover:bg-[#3E4E1D]"
              : "bg-[#F1F3EF] text-[#B0B8AB]"
          } disabled:cursor-not-allowed`}
        >
          <ArrowUp className="h-4 w-4" strokeWidth={2.25} />
        </button>
        )}
      </div>

      {!disabled && (
        <p className="mt-2 px-1 text-[11px] text-[#98A395]">
          Enter to send · Shift+Enter for a new line
        </p>
      )}
    </div>
  );
};
