"use client";

import React, { useState } from "react";
import { Check, Copy, RotateCcw } from "lucide-react";

export function MessageActions({
  content,
  showRegenerate,
  onRegenerate,
}: {
  content: string;
  showRegenerate?: boolean;
  onRegenerate?: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch (error) {
      console.error("Copy failed:", error);
    }
  };

  return (
    <div className="mt-3 flex items-center gap-1">
      <button
        type="button"
        onClick={() => void handleCopy()}
        className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium text-[#6F7B6B] transition-colors hover:bg-[#F1F3EF] hover:text-[#1C241F]"
        title="Copy answer"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? "Copied" : "Copy"}
      </button>
      {showRegenerate && onRegenerate && (
        <button
          type="button"
          onClick={onRegenerate}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium text-[#6F7B6B] transition-colors hover:bg-[#F1F3EF] hover:text-[#1C241F]"
          title="Regenerate response"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Regenerate
        </button>
      )}
    </div>
  );
}
