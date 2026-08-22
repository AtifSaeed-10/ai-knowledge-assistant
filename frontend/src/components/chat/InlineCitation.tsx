"use client";

import React from "react";
import { Citation } from "@/types";
import { useChatStore } from "@/store/useChatStore";
import { cn } from "@/lib/cn";
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
  const citation = citations?.find(
    (item) => item.evidenceId?.toUpperCase() === evidenceId.toUpperCase()
  );
  const number = displayNumberFromEvidenceId(evidenceId);
  if (number === null) return null;

  const pageLabel = citation?.pageNumber
    ? `page ${citation.pageNumber}`
    : "page unknown";
  const documentName = citation?.documentName ?? "Source";
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
        "relative -top-px mx-0.5 inline-flex h-4 min-w-4 items-center justify-center",
        "rounded px-1 align-super text-[10px] font-semibold tabular-nums leading-none",
        degraded
          ? "bg-stone-200 text-stone-600"
          : "bg-olive-soft text-olive transition-colors hover:bg-olive hover:text-white"
      )}
    >
      {number}
    </button>
  );
}
