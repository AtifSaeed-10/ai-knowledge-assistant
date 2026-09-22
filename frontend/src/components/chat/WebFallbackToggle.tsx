"use client";

import React from "react";
import { Globe } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { cn } from "@/lib/cn";

/**
 * Orthogonal to document scope: PDFs are always first. This only allows a
 * second pass when retrieval finds nothing in the files.
 */
export function WebFallbackToggle() {
  const enabled = useChatStore((state) => state.webFallbackEnabled);
  const setEnabled = useChatStore((state) => state.setWebFallbackEnabled);

  return (
    <button
      type="button"
      data-tour="web-fallback"
      aria-pressed={enabled}
      aria-label={
        enabled
          ? "Web fallback is on. Answers still come from your documents first."
          : "Turn on web fallback. If your documents do not cover a question, look it up."
      }
      title={
        enabled
          ? "On: your PDFs still come first. The web is used only when they don’t cover the question."
          : "Off: answers come only from your documents. Turn on to allow a trusted-site backup."
      }
      onClick={() => setEnabled(!enabled)}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-meta font-medium tracking-[-0.01em] transition-colors sm:px-2 sm:py-1",
        enabled
          ? "bg-olive text-white shadow-card hover:bg-olive-dark"
          : "bg-surface-sunken text-ink-muted hover:text-ink"
      )}
    >
      <Globe className="h-3.5 w-3.5" strokeWidth={2} />
      <span>{enabled ? "Web on" : "Web off"}</span>
    </button>
  );
}
