import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { useChatStore } from '@/store/useChatStore';
import { Send } from 'lucide-react';

export const ChatInput = () => {
  const [input, setInput] = useState('');
  const { sendMessage, isLoading, activeCitation, setActiveCitation } = useChatStore();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);
    
    // Auto-close drawer the moment the user starts typing a new question
    if (activeCitation && val.length > 0) {
      setActiveCitation(null);
    }

    // Auto-resize textarea logic
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  };

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="p-4 bg-transparent border-t border-gray-100">
      <div className="relative flex items-end w-full max-w-4xl mx-auto border border-gray-200 rounded-xl bg-white shadow-sm focus-within:ring-2 focus-within:ring-[#4A5D23]/20 focus-within:border-[#4A5D23] transition-all">
        <textarea
          ref={textareaRef}
          className="w-full max-h-40 min-h-[44px] p-3 rounded-xl bg-transparent resize-none outline-none text-sm text-gray-800 placeholder-gray-400"
          placeholder="Ask a question about your documents..."
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="p-2 mb-1.5 mr-1.5 text-white bg-[#4A5D23] rounded-lg hover:bg-[#3d4d1d] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
};