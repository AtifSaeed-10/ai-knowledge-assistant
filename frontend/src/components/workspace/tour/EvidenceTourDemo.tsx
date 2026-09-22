"use client";

import React from "react";
import { MousePointer2 } from "lucide-react";
import { cn } from "@/lib/cn";

function Line({ className }: { className?: string }) {
  return <span className={cn("block h-1.5 rounded-full bg-line-strong", className)} />;
}

/**
 * Miniature of the real thing: a question, an answer with a citation chip, a
 * click, and the cited line lighting up in the PDF. Purely decorative — the
 * popover copy carries the same meaning for screen readers.
 *
 * The loop is CSS only. Under `prefers-reduced-motion` the global rule in
 * `globals.css` collapses every animation to a single instant pass, which
 * leaves each element on its base styles: the finished frame, highlight shown.
 */
export function EvidenceTourDemo() {
  return (
    <div
      aria-hidden
      className="flex h-40 gap-2.5 overflow-hidden rounded-xl border border-line bg-surface-sunken p-2.5"
    >
      <div className="flex min-w-0 flex-1 flex-col justify-center gap-2 rounded-lg border border-line bg-surface px-3 py-2.5">
        <p className="truncate text-[10px] font-medium leading-none text-ink-subtle">
          Who is the author?
        </p>
        <p className="text-[11px] leading-snug text-ink">
          Jane Harper
          <span className="relative ml-1 inline-flex h-4 min-w-4 animate-tour-chip items-center justify-center rounded bg-olive-soft px-1 align-super text-[10px] font-semibold leading-none text-olive">
            1
            <MousePointer2
              className="absolute -bottom-3 -right-2 h-3.5 w-3.5 animate-tour-pointer fill-ink text-surface opacity-0"
              strokeWidth={1.5}
            />
          </span>
        </p>
        <Line className="w-3/4" />
      </div>

      <div className="relative w-[38%] shrink-0 overflow-hidden rounded-lg border border-line bg-surface">
        <p className="border-b border-line px-2.5 py-1 text-[10px] font-medium text-ink-subtle">
          Page 4
        </p>
        <div className="animate-tour-page space-y-1.5 px-2.5 py-2">
          <Line className="w-full" />
          <Line className="w-5/6" />
          <div className="relative py-0.5">
            {/* Same yellow the PDF viewer paints over a cited region. */}
            <span className="absolute inset-x-0 -inset-y-0.5 origin-left animate-tour-highlight rounded-sm bg-[#FFD54A]/55" />
            <p className="relative text-[9px] font-medium leading-tight text-ink">
              Jane Harper is the author.
            </p>
          </div>
          <Line className="w-2/3" />
          <Line className="w-full" />
          <Line className="w-4/5" />
        </div>
      </div>
    </div>
  );
}
