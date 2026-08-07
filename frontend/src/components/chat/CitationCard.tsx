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
  const { setActiveCitation, activeCitation } = useChatStore();

  const isActive = activeCitation?.id === citation.id;

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
      className={`group inline-flex max-w-full items-start gap-2 rounded-lg border px-2.5 py-2 text-left transition-all duration-150 sm:max-w-[280px] ${
        isActive
          ? "border-[#87AB72] bg-white shadow-[0_0_0_3px_rgba(135,171,114,0.15)]"
          : "border-[#EBEFEA] bg-[#F6F7F4] hover:border-[#D8DED5] hover:bg-white"
      }`}
      title={
        relScore
          ? `${citation.documentName} · page ${citation.pageNumber} · ${relScore}% match`
          : `${citation.documentName} · page ${citation.pageNumber}`
      }
    >
      {typeof index === "number" && (
        <span
          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[11px] font-semibold ${
            isActive
              ? "bg-[#4A5D23] text-white"
              : "bg-white text-[#4A5D23] ring-1 ring-[#D8DED5]"
          }`}
        >
          {index}
        </span>
      )}

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12px] font-semibold tracking-[-0.01em] text-[#1C241F]">
          {citation.documentName}
        </span>
        <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-[#6F7B6B]">
          <span>Page {citation.pageNumber}</span>
          {relScore !== null && (
            <>
              <span className="text-[#D5DBD3]">·</span>
              <span>{relScore}% match</span>
            </>
          )}
        </span>
        {citation.snippet && (
          <span className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-[#98A395]">
            {citation.snippet}
          </span>
        )}
      </span>
    </button>
  );
};
