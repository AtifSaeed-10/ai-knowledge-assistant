"use client";

import React from 'react';
import { Logo } from '@/components/ui/Logo';

export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 my-4 animate-in fade-in duration-300">
      <div className="w-8 h-8 rounded-full bg-[#4A5D23] text-white flex items-center justify-center shrink-0 shadow-sm">
        <Logo className="w-5 h-5 text-white" />
      </div>

      <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm flex items-center gap-1.5">
        <span className="text-xs text-gray-400 font-medium mr-1">DocuSage is thinking</span>
        <div className="w-1.5 h-1.5 bg-[#4A5D23] rounded-full animate-bounce [animation-delay:-0.32s]" />
        <div className="w-1.5 h-1.5 bg-[#4A5D23] rounded-full animate-bounce [animation-delay:-0.16s]" />
        <div className="w-1.5 h-1.5 bg-[#4A5D23] rounded-full animate-bounce" />
      </div>
    </div>
  );
}