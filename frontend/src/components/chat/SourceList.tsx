import React from "react";
import { Citation } from "@/types";
import { CitationCard } from "./CitationCard";

export const SourceList = ({ citations }: { citations?: Citation[] }) => {
  if (!citations || citations.length === 0) return null;

  const topCitations = citations.slice(0, 3);
  const remainingCount = citations.length - 3;

  return (
    <div className="mt-4 border-t border-[#EBEFEA] pt-3.5">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
        Sources
      </p>
      <div className="flex flex-wrap items-center gap-1.5">
        {topCitations.map((cit, index) => (
          <CitationCard key={cit.id} citation={cit} index={index + 1} />
        ))}
        {remainingCount > 0 && (
          <span className="rounded-md border border-[#EBEFEA] bg-[#F6F7F4] px-2 py-1 text-[11px] font-medium text-[#6F7B6B]">
            +{remainingCount} more
          </span>
        )}
      </div>
    </div>
  );
};
