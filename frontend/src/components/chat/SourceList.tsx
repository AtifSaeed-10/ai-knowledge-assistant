"use client";

import React, { useState } from "react";
import { Citation } from "@/types";
import { CitationCard } from "./CitationCard";

export const SourceList = ({ citations }: { citations?: Citation[] }) => {
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  const visible = expanded ? citations : citations.slice(0, 3);
  const remaining = citations.length - 3;

  return (
    <div className="mt-4 border-t border-[#EBEFEA] pt-3.5 animate-in fade-in slide-in-from-bottom-1 duration-300">
      <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
        Sources
        <span className="ml-1.5 font-medium normal-case tracking-normal text-[#C4CBC0]">
          {citations.length}
        </span>
      </p>

      <div className="flex flex-col gap-1.5 sm:flex-row sm:flex-wrap sm:items-stretch">
        {visible.map((cit, index) => (
          <CitationCard key={cit.id} citation={cit} index={index + 1} />
        ))}
      </div>

      {!expanded && remaining > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-2 rounded-lg px-1 py-1 text-[12px] font-medium text-[#4A5D23] transition-colors hover:text-[#3E4E1D]"
        >
          Show {remaining} more source{remaining === 1 ? "" : "s"}
        </button>
      )}

      {expanded && citations.length > 3 && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="mt-2 rounded-lg px-1 py-1 text-[12px] font-medium text-[#6F7B6B] transition-colors hover:text-[#1C241F]"
        >
          Show less
        </button>
      )}
    </div>
  );
};
