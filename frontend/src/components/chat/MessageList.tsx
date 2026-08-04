"use client";

import React, { useRef, useEffect } from 'react';
import { Message } from '@/types';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';
import { Sparkles, FileText, ArrowRight } from 'lucide-react';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onSelectPrompt?: (prompt: string) => void;
}

const SAMPLE_PROMPTS = [
  'Summarize the key findings in my documents',
  'What are the main risks or warnings mentioned?',
  'List all dates and deadlines from the text',
];

export function MessageList({ messages, isLoading, onSelectPrompt }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-center">
        <div className="w-12 h-12 bg-[#4A5D23]/10 text-[#4A5D23] rounded-2xl flex items-center justify-center mb-4">
          <Sparkles className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-gray-900 mb-1">
          Ask DocuSage Anything
        </h3>
        <p className="text-sm text-gray-500 max-w-sm mb-6">
          Query your uploaded documents with precise semantic search and cited answers.
        </p>

        {onSelectPrompt && (
          <div className="w-full max-w-md space-y-2">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block text-left">
              Suggested Prompts
            </span>
            {SAMPLE_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => onSelectPrompt(prompt)}
                className="w-full text-left p-3 rounded-xl bg-white border border-gray-200/80 hover:border-[#4A5D23] hover:bg-[#F6F7F4] text-xs text-gray-700 flex items-center justify-between transition-all group"
              >
                <div className="flex items-center gap-2">
                  <FileText className="w-3.5 h-3.5 text-[#4A5D23]" />
                  <span>{prompt}</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-gray-400 group-hover:text-[#4A5D23] group-hover:translate-x-0.5 transition-all" />
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {isLoading && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}