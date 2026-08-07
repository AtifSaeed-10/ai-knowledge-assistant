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
    <div className="mt-5 animate-in fade-in slide-in-from-bottom-1 duration-300">
      <div className="mb-2.5 flex items-baseline gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
          Evidence
        </p>
        <span className="text-[11px] text-[#C4CBC0]">
          {citations.length} source{citations.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {visible.map((cit, index) => (
          <CitationCard key={cit.id} citation={cit} index={index + 1} />
        ))}
      </div>

      {!expanded && remaining > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-2.5 text-[12px] font-medium text-[#4A5D23] transition-colors hover:text-[#3E4E1D]"
        >
          Show {remaining} more
        </button>
      )}

      {expanded && citations.length > 3 && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="mt-2.5 text-[12px] font-medium text-[#6F7B6B] transition-colors hover:text-[#1C241F]"
        >
          Show less
        </button>
      )}
    </div>
  );
};
