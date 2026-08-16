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
      className={`group w-full rounded-xl border px-3 py-2.5 text-left transition-all duration-150 ${
        isActive
          ? "border-[#87AB72] bg-white shadow-[0_0_0_3px_rgba(135,171,114,0.14)]"
          : "border-[#EBEFEA] bg-white hover:border-[#D0D7CB] hover:bg-[#FBFBFA]"
      }`}
      title={
        citation.pageNumber
          ? `${citation.documentName} · page ${citation.pageNumber}`
          : citation.documentName
      }
    >
      <div className="flex items-start gap-2.5">
        {typeof index === "number" && (
          <span
            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[11px] font-semibold ${
              isActive
                ? "bg-[#4A5D23] text-white"
                : "bg-[#F1F3EF] text-[#4A5D23]"
            }`}
          >
            {index}
          </span>
        )}

        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12.5px] font-semibold tracking-[-0.01em] text-[#1C241F]">
            {citation.documentName}
          </span>

          <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-[#6F7B6B]">
            <span className="rounded bg-[#F6F7F4] px-1.5 py-0.5 font-medium text-[#5B6858]">
              {citation.pageNumber ? `p. ${citation.pageNumber}` : "page unknown"}
            </span>
            {relScore !== null && <span>{relScore}% match</span>}
          </span>

          {citation.snippet && (
            <span className="mt-1.5 line-clamp-2 block text-[12px] leading-relaxed text-[#6F7B6B]">
              “{citation.snippet}”
            </span>
          )}

          <span className="mt-1.5 block text-[11px] font-medium text-[#4A5D23] opacity-0 transition-opacity group-hover:opacity-100">
          View {citation.pageNumber ? `page ${citation.pageNumber}` : "source"} →
          </span>
        </span>
      </div>
    </button>
  );
};
