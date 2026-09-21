"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Citation } from "@/types";
import { CitationCard } from "./CitationCard";
import { isPreviewWebCitation, isWebCitation } from "@/lib/citations/web";

export const SourceList = ({ citations }: { citations?: Citation[] }) => {
  const [open, setOpen] = useState(true);

  if (!citations || citations.length === 0) return null;

  const count = citations.length;
  const webOnly = citations.every(isWebCitation);
  const preview = citations.some(isPreviewWebCitation);
  const label = webOnly
    ? preview
      ? "Preview sources"
      : "Web sources"
    : "Sources";

  return (
    <section className="mt-3" aria-label={label}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-1.5 text-meta font-medium text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink sm:py-1"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        {label}
        <span className="tabular-nums text-ink-subtle">{count}</span>
      </button>

      {open && (
        <div className="mt-1.5 grid min-w-0 grid-cols-1 gap-1.5 sm:grid-cols-2">
          {citations.map((citation, index) => (
            <CitationCard
              key={citation.id || `${citation.evidenceId}-${index}`}
              citation={citation}
              index={citation.displayNumber ?? index + 1}
            />
          ))}
        </div>
      )}
    </section>
  );
};
