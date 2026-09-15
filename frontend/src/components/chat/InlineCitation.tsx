"use client";

import React from "react";
import { Citation } from "@/types";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import { cn } from "@/lib/cn";
import { resolveCitationDocumentName } from "@/lib/citations/documentName";
import { displayNumberFromEvidenceId, openCitationPayload } from "@/lib/citations/markers";

export function InlineCitation({
  evidenceId,
  quote,
  citations,
}: {
  evidenceId: string;
  quote?: string | null;
  citations?: Citation[];
}) {
  const setActiveCitation = useChatStore((state) => state.setActiveCitation);
  const documents = useDocumentStore((state) => state.documents);
  const citation = citations?.find(
    (item) => item.evidenceId?.toUpperCase() === evidenceId.toUpperCase()
  );
  const number = displayNumberFromEvidenceId(evidenceId);
  if (number === null) return null;

  const pageLabel = citation?.pageNumber
    ? `page ${citation.pageNumber}`
    : "page unknown";
  const documentName = citation
    ? resolveCitationDocumentName(citation, documents)
    : "Source";
  const degraded = !citation;
  const cleanedQuote = quote?.trim() || citation?.quote?.trim() || null;

  return (
    <button
      type="button"
      data-citation-chip="true"
      data-citation-degraded={degraded ? "true" : undefined}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!citation) return;
        setActiveCitation(openCitationPayload(citation, cleanedQuote));
      }}
      aria-label={`Open source ${number}: ${documentName}, ${pageLabel}`}
      title={`${documentName} · ${pageLabel}`}
      className={cn(
        "relative -top-px mx-0.5 inline-flex h-[1.125rem] min-w-[1.125rem] items-center justify-center",
        "rounded px-1 align-super text-[11px] font-semibold tabular-nums leading-none",
        // Widens the thumb target without changing how the line wraps.
        "after:absolute after:-inset-1 after:content-['']",
        degraded
          ? "bg-surface-sunken text-ink-subtle ring-1 ring-line-strong"
          : "bg-olive text-white transition-colors hover:bg-olive-dark"
      )}
    >
      {number}
    </button>
  );
}
