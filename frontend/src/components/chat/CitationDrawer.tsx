import React, { useEffect, useRef } from "react";
import { useChatStore } from "@/store/useChatStore";
import { X, FileText, Quote } from "lucide-react";

export const CitationDrawer = () => {
  const { activeCitation, setActiveCitation } = useChatStore();
  const isOpen = !!activeCitation;
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setActiveCitation(null);
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        const target = e.target as HTMLElement;
        if (!target.closest('[data-citation-chip="true"]')) {
          setActiveCitation(null);
        }
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, setActiveCitation]);

  const relScore = activeCitation?.relevance
    ? activeCitation.relevance > 1
      ? Math.round(activeCitation.relevance)
      : Math.round(activeCitation.relevance * 100)
    : null;

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#1C241F]/20 backdrop-blur-[1px] transition-opacity animate-in fade-in duration-200 lg:hidden"
          onClick={() => setActiveCitation(null)}
        />
      )}

      <div
        ref={drawerRef}
        className={`fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-[#EBEFEA] bg-white shadow-2xl transition-transform duration-300 ease-out sm:w-[400px] ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-[#EBEFEA] px-5 py-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
              Source
            </p>
            <h3 className="mt-0.5 text-[14px] font-semibold tracking-[-0.01em] text-[#1C241F]">
              Cited passage
            </h3>
          </div>
          <button
            onClick={() => setActiveCitation(null)}
            className="rounded-lg p-1.5 text-[#98A395] transition-colors hover:bg-[#F1F3EF] hover:text-[#1C241F]"
            aria-label="Close source panel"
          >
            <X size={18} />
          </button>
        </div>

        {activeCitation && (
          <div
            key={activeCitation.id}
            className="flex-1 overflow-y-auto px-5 py-5 animate-in fade-in slide-in-from-right-2 duration-300"
          >
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#EBEFEA] bg-[#F6F7F4] text-[#4A5D23]">
                <FileText className="h-4 w-4" strokeWidth={1.75} />
              </span>
              <div className="min-w-0">
                <h2 className="text-[16px] font-semibold leading-snug tracking-[-0.01em] text-[#1C241F]">
                  {activeCitation.documentName}
                </h2>
                <p className="mt-1 text-[13px] text-[#6F7B6B]">
                  Page {activeCitation.pageNumber}
                  {relScore !== null ? ` · ${relScore}% match` : ""}
                </p>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-2.5">
              <div className="rounded-xl border border-[#EBEFEA] bg-[#FBFBFA] px-3.5 py-3">
                <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-[#98A395]">
                  Page
                </p>
                <p className="mt-1 text-[18px] font-semibold tabular-nums tracking-[-0.02em] text-[#1C241F]">
                  {activeCitation.pageNumber}
                </p>
              </div>
              <div className="rounded-xl border border-[#EBEFEA] bg-[#FBFBFA] px-3.5 py-3">
                <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-[#98A395]">
                  Relevance
                </p>
                <p className="mt-1 text-[18px] font-semibold tabular-nums tracking-[-0.02em] text-[#1C241F]">
                  {relScore !== null ? `${relScore}%` : "—"}
                </p>
              </div>
            </div>

            {activeCitation.snippet ? (
              <div className="mt-6">
                <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
                  <Quote className="h-3 w-3" />
                  Excerpt
                </div>
                <blockquote className="rounded-xl border border-[#EBEFEA] bg-[#F6F7F4] px-4 py-3.5 text-[14px] leading-relaxed text-[#2A322E]">
                  {activeCitation.snippet}
                </blockquote>
              </div>
            ) : (
              <div className="mt-6 rounded-xl border border-[#EBEFEA] bg-[#FBFBFA] px-4 py-4">
                <p className="text-[13px] leading-relaxed text-[#6F7B6B]">
                  This answer cited page {activeCitation.pageNumber} of{" "}
                  <span className="font-medium text-[#1C241F]">
                    {activeCitation.documentName}
                  </span>
                  . Open that page in the original PDF to review the full context.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
};
