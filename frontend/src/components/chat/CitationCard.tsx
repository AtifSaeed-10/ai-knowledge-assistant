import React from "react";
import { Citation } from "@/types";
import { useChatStore } from "@/store/useChatStore";

export const CitationCard = ({
  citation,
  index,
}: {
  citation: Citation;
  index?: number;
}) => {
  const { setActiveCitation } = useChatStore();

  const relScore = citation.relevance
    ? citation.relevance > 1
      ? Math.round(citation.relevance)
      : Math.round(citation.relevance * 100)
    : null;

  return (
    <button
      type="button"
      data-citation-chip="true"
      onClick={() => setActiveCitation(citation)}
      className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-[#D8DED5] bg-[#F6F7F4] px-2 py-1 text-left text-[12px] font-medium text-[#4A5D23] transition-colors hover:border-[#87AB72] hover:bg-white"
      title={
        relScore
          ? `${citation.documentName} · page ${citation.pageNumber} · ${relScore}% match`
          : `${citation.documentName} · page ${citation.pageNumber}`
      }
    >
      {typeof index === "number" && (
        <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded bg-[#4A5D23] text-[10px] font-semibold text-white">
          {index}
        </span>
      )}
      <span className="truncate max-w-[132px]">{citation.documentName}</span>
      <span className="shrink-0 text-[#98A395]">p.{citation.pageNumber}</span>
    </button>
  );
};
