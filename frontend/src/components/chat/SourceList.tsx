"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Citation } from "@/types";
import { CitationCard } from "./CitationCard";

export const SourceList = ({ citations }: { citations?: Citation[] }) => {
  const [open, setOpen] = useState(false);

  if (!citations || citations.length === 0) return null;

  const count = citations.length;

  return (
    <section className="mt-3" aria-label="Sources">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-meta font-medium text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        Sources
        <span className="tabular-nums text-ink-subtle">{count}</span>
      </button>

      {open && (
        <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
          {citations.map((citation, index) => (
            <CitationCard
              key={citation.id}
              citation={citation}
              index={citation.displayNumber ?? index + 1}
            />
          ))}
        </div>
      )}
    </section>
  );
};
