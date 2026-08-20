"use client";

import React from "react";
import { Citation } from "@/types";
import { useChatStore } from "@/store/useChatStore";
import { cn } from "@/lib/cn";
import { displayNumberFromEvidenceId } from "@/lib/citations/markers";

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
  const number =
    citation?.displayNumber ?? displayNumberFromEvidenceId(evidenceId);

  if (!citation || number === null) return null;

  const pageLabel = citation.pageNumber
    ? `page ${citation.pageNumber}`
    : "page unknown";
  const cleanedQuote = quote?.trim() || null;

  return (
    <button
      type="button"
      data-citation-chip="true"
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        setActiveCitation({
          ...citation,
          quote: cleanedQuote,
          id: cleanedQuote ? `${citation.id}::${cleanedQuote}` : citation.id,
        });
      }}
      aria-label={`Open source ${number}: ${citation.documentName}, ${pageLabel}`}
      title={`${citation.documentName} · ${pageLabel}`}
      className={cn(
        "relative -top-px mx-0.5 inline-flex h-4 min-w-4 items-center justify-center",
        "rounded px-1 align-super text-[10px] font-semibold tabular-nums leading-none",
        "bg-olive-soft text-olive transition-colors hover:bg-olive hover:text-white"
      )}
    >
      {number}
    </button>
  );
}
