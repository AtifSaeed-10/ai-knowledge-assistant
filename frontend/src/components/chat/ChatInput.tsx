import React, { useState, KeyboardEvent, useRef } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";

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

  const { activeCitation, setActiveCitation } = useChatStore();

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;

    setInput(val);

    // Close citation drawer when starting a new question
    if (activeCitation && val.length > 0) {
      setActiveCitation(null);
    }

    // Auto resize textarea
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
        className={`flex items-end gap-2 rounded-xl border bg-[#FBFBFA] p-2 pl-3.5 transition-colors ${
          disabled
            ? "border-[#EBEFEA] opacity-70"
            : "border-[#EBEFEA] focus-within:border-[#87AB72] focus-within:bg-white focus-within:shadow-[0_0_0_3px_rgba(135,171,114,0.12)]"
        }`}
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled || isLoading}
          placeholder={
            disabled
              ? "Upload and wait for a document to become ready…"
              : isLoading
                ? "Waiting for the current answer…"
                : "Ask a question about your documents…"
          }
          rows={1}
          className="max-h-40 min-h-[40px] flex-1 resize-none bg-transparent py-2.5 text-[14px] leading-relaxed tracking-[-0.01em] text-[#1C241F] outline-none placeholder:text-[#98A395] disabled:cursor-not-allowed"
        />

        <button
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          className={`mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors ${
            canSend
              ? "bg-[#4A5D23] text-white hover:bg-[#3E4E1D]"
              : "bg-[#EFF1EC] text-[#98A395]"
          } disabled:cursor-not-allowed`}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowUp className="h-4 w-4" strokeWidth={2.25} />
          )}
        </button>
      </div>

      <p className="mt-2 px-1 text-[11px] text-[#98A395]">
        Enter to send · Shift + Enter for a new line
      </p>
    </div>
  );
};
