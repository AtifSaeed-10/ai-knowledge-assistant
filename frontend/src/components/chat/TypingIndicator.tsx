"use client";

import React from "react";
import { Sparkles } from "lucide-react";

export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 animate-in fade-in duration-300">
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#EBEFEA] bg-[#F6F7F4] text-[#4A5D23]">
        <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />
      </span>

      <div className="rounded-2xl rounded-tl-md border border-[#EBEFEA] bg-white px-4 py-3 shadow-[0_1px_2px_rgba(28,36,31,0.03)]">
        <div className="flex items-center gap-2 text-[13px] text-[#6F7B6B]">
          <span className="flex gap-1">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#87AB72] [animation-delay:-0.28s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#87AB72] [animation-delay:-0.14s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#87AB72]" />
          </span>
          Searching your documents…
        </div>
      </div>
    </div>
  );
}
