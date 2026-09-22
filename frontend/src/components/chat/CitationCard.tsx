"use client";

import React from "react";
import { ChevronRight, ExternalLink } from "lucide-react";
import { Citation } from "@/types";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import { citationsMatch } from "@/lib/citations/markers";
import { resolveCitationDocumentName } from "@/lib/citations/documentName";
import {
  evidencePresentationStatus,
  evidenceStatusLabel,
} from "@/lib/citations/evidenceStatus";
import {
  hostnameFromUrl,
  isPreviewWebCitation,
  isWebCitation,
  webSourceBadge,
} from "@/lib/citations/web";
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
  const documents = useDocumentStore((state) => state.documents);

  const isActive = citationsMatch(activeCitation, citation);
  if (isWebCitation(citation)) {
    return <WebCitationCard citation={citation} index={index} />;
  }
  const pageLabel = citation.pageNumber ? `page ${citation.pageNumber}` : "page unknown";
  const preview = (citation.quote || citation.snippet || "").trim();
  const presentation = evidencePresentationStatus(citation);
  const statusLabel =
    presentation === "precise" ? null : evidenceStatusLabel(presentation);

  // The card shows the marker and the quote; the document name is only
  // needed by assistive tech and the hover tooltip.
  const documentName = resolveCitationDocumentName(citation, documents);

  return (
    <button
      type="button"
      data-citation-chip="true"
      onClick={() => setActiveCitation(citation)}
      aria-label={`Open source ${index ?? ""} from ${documentName}, ${pageLabel}`}
      title={`${documentName} · ${pageLabel}`}
      className={cn(
        "group relative min-w-0 w-full overflow-hidden rounded-lg border bg-surface py-1.5 pl-2 pr-6 text-left transition-colors",
        isActive
          ? "border-sage ring-1 ring-sage"
          : "border-line hover:border-sage hover:bg-surface-muted"
      )}
    >
      <div className="flex min-w-0 items-start gap-1.5">
        {typeof index === "number" && (
          <span
            className={cn(
              "mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded text-[10px] font-semibold tabular-nums leading-none",
              isActive ? "bg-olive-dark text-white" : "bg-olive text-white"
            )}
          >
            {index}
          </span>
        )}

        <span className="min-w-0 flex-1">
          <span className="inline-flex max-w-full flex-wrap items-center gap-1">
            <span className="inline-flex rounded bg-surface-sunken px-1 py-px text-label font-medium tabular-nums text-ink-muted">
              {citation.pageNumber ? `p. ${citation.pageNumber}` : "page n/a"}
            </span>

            {statusLabel && (
              <span
                className={cn(
                  "inline-flex rounded px-1 py-px text-label font-medium",
                  presentation === "invalid_quote" || presentation === "missing_metadata"
                    ? "bg-warn-soft text-warn"
                    : "bg-surface-sunken text-ink-muted"
                )}
              >
                {statusLabel}
              </span>
            )}
          </span>

          {preview && (
            <span className="mt-0.5 line-clamp-2 block text-label leading-snug text-ink-muted">
              “{preview}”
            </span>
          )}
        </span>
      </div>

      <ChevronRight
        aria-hidden
        className={cn(
          "absolute right-1.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 transition-colors",
          isActive ? "text-olive" : "text-ink-icon group-hover:text-olive"
        )}
      />
    </button>
  );
};

function WebCitationCard({
  citation,
  index,
}: {
  citation: Citation;
  index?: number;
}) {
  const href = citation.url || "";
  const domain =
    citation.domain || hostnameFromUrl(href) || "web source";
  const title = citation.title || citation.documentName || domain;
  const snippet = (citation.snippet || citation.quote || "").trim();
  const preview = isPreviewWebCitation(citation);
  const label = webSourceBadge(citation);

  const inner = (
    <>
      <div className="flex min-w-0 items-start gap-1.5">
        {typeof index === "number" && (
          <span className="mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded bg-olive text-[10px] font-semibold tabular-nums leading-none text-white">
            {index}
          </span>
        )}
        <span className="min-w-0 flex-1">
          <span className="inline-flex max-w-full flex-wrap items-center gap-1">
            <span className="inline-flex rounded bg-surface-sunken px-1 py-px text-label font-medium text-ink-muted">
              {label}
            </span>
          </span>
          <span className="mt-0.5 line-clamp-2 block text-label font-medium leading-snug text-ink">
            {title}
          </span>
          {snippet && (
            <span className="mt-0.5 line-clamp-1 block text-label leading-snug text-ink-muted">
              {snippet}
            </span>
          )}
        </span>
      </div>
      <ExternalLink
        aria-hidden
        className="absolute right-1.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-icon group-hover:text-olive"
      />
    </>
  );

  const className =
    "group relative min-w-0 w-full overflow-hidden rounded-lg border border-line bg-surface py-1.5 pl-2 pr-6 text-left transition-colors hover:border-sage hover:bg-surface-muted";

  if (!href || preview) {
    return (
      <div className={className} title={preview ? "Preview source — not a live page" : title}>
        {inner}
      </div>
    );
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      data-citation-chip="true"
      aria-label={`Open web source ${index ?? ""}: ${title}`}
      title={`${domain} — opens in a new tab`}
      className={className}
    >
      {inner}
    </a>
  );
}
