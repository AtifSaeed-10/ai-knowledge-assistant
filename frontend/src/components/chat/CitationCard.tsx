"use client";

import React from "react";
import { ChevronRight } from "lucide-react";
import { Citation } from "@/types";
import { useChatStore } from "@/store/useChatStore";
import { citationsMatch } from "@/lib/citations/markers";
import {
  evidencePresentationStatus,
  evidenceStatusLabel,
} from "@/lib/citations/evidenceStatus";
import { cn } from "@/lib/cn";

export function relevancePercent(relevance?: number | null): number | null {
  if (relevance === null || relevance === undefined) return null;
  const value = relevance > 1 ? Math.round(relevance) : Math.round(relevance * 100);
  if (!Number.isFinite(value) || value <= 0) return null;
  return Math.min(100, value);
}

export const CitationCard = ({
  citation,
  index,
}: {
  citation: Citation;
  index?: number;
}) => {
  const setActiveCitation = useChatStore((state) => state.setActiveCitation);
  const activeCitation = useChatStore((state) => state.activeCitation);

  const isActive = citationsMatch(activeCitation, citation);
  const pageLabel = citation.pageNumber ? `page ${citation.pageNumber}` : "page unknown";
  const preview = (citation.quote || citation.snippet || "").trim();
  const presentation = evidencePresentationStatus(citation);
  const statusLabel =
    presentation === "precise" ? null : evidenceStatusLabel(presentation);

  return (
    <button
      type="button"
      data-citation-chip="true"
      onClick={() => setActiveCitation(citation)}
      aria-label={`Open ${citation.documentName}, ${pageLabel}`}
      title={`${citation.documentName} · ${pageLabel}`}
      className={cn(
        "group relative w-full rounded-xl border bg-surface py-2.5 pl-3 pr-7 text-left transition-colors",
        isActive
          ? "border-sage ring-1 ring-sage"
          : "border-line hover:border-line-strong hover:bg-surface-muted"
      )}
    >
      <div className="flex items-start gap-2.5">
        {typeof index === "number" && (
          <span
            className={cn(
              "mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-label font-semibold tabular-nums",
              isActive ? "bg-olive text-white" : "bg-olive-soft text-olive"
            )}
          >
            {index}
          </span>
        )}

        <span className="min-w-0 flex-1">
          <span className="block truncate text-ui font-semibold tracking-[-0.01em] text-ink">
            {citation.documentName}
          </span>

          <span className="mt-1 inline-flex rounded bg-surface-sunken px-1.5 py-0.5 text-meta font-medium tabular-nums text-ink-muted">
            {citation.pageNumber ? `p. ${citation.pageNumber}` : "page n/a"}
          </span>

          {statusLabel && (
            <span
              className={cn(
                "mt-1 inline-flex rounded px-1.5 py-0.5 text-meta font-medium",
                presentation === "invalid_quote" || presentation === "missing_metadata"
                  ? "bg-amber-50 text-amber-800"
                  : "bg-surface-sunken text-ink-muted"
              )}
            >
              {statusLabel}
            </span>
          )}

          {preview && (
            <span className="mt-1.5 line-clamp-2 block text-meta leading-relaxed text-ink-muted">
              “{preview}”
            </span>
          )}
        </span>
      </div>

      <ChevronRight
        aria-hidden
        className={cn(
          "absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 transition-colors",
          isActive ? "text-olive" : "text-ink-icon group-hover:text-olive"
        )}
      />
    </button>
  );
};
