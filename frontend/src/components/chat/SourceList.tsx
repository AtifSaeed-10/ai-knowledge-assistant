"use client";

import React, { useState } from "react";
import { Citation } from "@/types";
import { CitationCard } from "./CitationCard";

const PREVIEW_COUNT = 4;

export const SourceList = ({ citations }: { citations?: Citation[] }) => {
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  const visible = expanded ? citations : citations.slice(0, PREVIEW_COUNT);
  const remaining = citations.length - PREVIEW_COUNT;

  return (
    <section className="mt-5" aria-label="Evidence">
      <div className="mb-2.5 flex items-baseline gap-2">
        <h3 className="text-label font-semibold uppercase tracking-[0.09em] text-ink-muted">
          Evidence
        </h3>
        <span className="text-meta text-ink-subtle">
          {citations.length} source{citations.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {visible.map((citation, index) => (
          <CitationCard key={citation.id} citation={citation} index={index + 1} />
        ))}
      </div>

      {remaining > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          className="mt-2.5 rounded px-1 py-0.5 text-meta font-medium text-olive transition-colors hover:text-olive-dark"
        >
          {expanded ? "Show fewer sources" : `Show ${remaining} more source${remaining === 1 ? "" : "s"}`}
        </button>
      )}
    </section>
  );
};
