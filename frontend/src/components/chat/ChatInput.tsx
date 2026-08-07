import React, { useState, KeyboardEvent, useRef } from "react";
import { Send } from "lucide-react";
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

  const {
    activeCitation,
    setActiveCitation,
  } = useChatStore();

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLTextAreaElement>
  ) => {
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


  const handleKeyDown = (
    e: KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };


  return (
    <div className="flex items-end gap-2">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={
          disabled
            ? "Upload a document first..."
            : "Ask something about your documents..."
        }
        rows={1}
        className="
          flex-1
          resize-none
          rounded-lg
          border
          border-gray-300
          p-3
          text-sm
          outline-none
          focus:ring-2
          focus:ring-[#4A5D23]
        "
      />

      <button
        onClick={handleSend}
        disabled={!input.trim() || isLoading || disabled}
        className="
          p-2
          mb-1.5
          mr-1.5
          text-white
          bg-[#4A5D23]
          rounded-lg
          hover:bg-[#3d4d1d]
          disabled:opacity-50
          disabled:cursor-not-allowed
          transition-colors
        "
      >
        <Send size={18} />
      </button>
    </div>
  );
};