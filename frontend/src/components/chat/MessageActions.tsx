"use client";

import React, { useState } from "react";
import { Check, Copy, RotateCcw } from "lucide-react";
import { notify } from "@/store/useToastStore";
import { toDisplayCitationText } from "@/lib/citations/markers";

interface MessageActionsProps {
  content: string;
  showRetry?: boolean;
  onRetry?: () => void;
}

const ACTION_CLASS =
  "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-meta font-medium text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink";

export function MessageActions({ content, showRetry, onRetry }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(toDisplayCitationText(content));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      notify.error(
        "Couldn’t copy the answer",
        "Your browser blocked clipboard access. Select the text and copy manually."
      );
    }
  };

  return (
    <div className="mt-3 flex items-center gap-1">
      <button
        type="button"
        onClick={() => void handleCopy()}
        className={ACTION_CLASS}
        title="Copy answer"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-olive" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
        {copied ? "Copied" : "Copy"}
      </button>

      {showRetry && onRetry && (
        <button type="button" onClick={onRetry} className={ACTION_CLASS} title="Regenerate answer">
          <RotateCcw className="h-3.5 w-3.5" />
          Regenerate
        </button>
      )}
    </div>
  );
}
