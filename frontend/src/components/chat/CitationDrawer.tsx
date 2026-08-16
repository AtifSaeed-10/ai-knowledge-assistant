import React, { useEffect, useRef, useState } from "react";
import { useChatStore } from "@/store/useChatStore";
import { documentsApi } from "@/lib/api/documents";
import { X, FileText, AlertCircle } from "lucide-react";

function isValidPage(page: number | null | undefined): page is number {
  return typeof page === "number" && Number.isFinite(page) && page >= 1;
}

export const CitationDrawer = () => {
  const { activeCitation, setActiveCitation } = useChatStore();
  const isOpen = !!activeCitation;
  const drawerRef = useRef<HTMLDivElement>(null);
  const [iframeFailed, setIframeFailed] = useState(false);

  useEffect(() => {
    setIframeFailed(false);
  }, [activeCitation?.id, activeCitation?.pageNumber]);

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

  const documentId = activeCitation?.documentId || null;
  const pageValid = isValidPage(activeCitation?.pageNumber ?? null);
  const pdfUrl = documentId
    ? documentsApi.fileUrl(
        documentId,
        pageValid ? activeCitation?.pageNumber : null
      )
    : null;

  const relScore = activeCitation?.relevance
    ? activeCitation.relevance > 1
      ? Math.round(activeCitation.relevance)
      : Math.round(activeCitation.relevance * 100)
    : null;

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#1C241F]/25 backdrop-blur-[2px] animate-in fade-in duration-200"
          onClick={() => setActiveCitation(null)}
        />
      )}

      <div
        ref={drawerRef}
        className={`fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-[#EBEFEA] bg-white shadow-2xl transition-transform duration-300 ease-out sm:w-[min(720px,92vw)] ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-[#EBEFEA] px-5 py-3.5">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
              Source document
            </p>
            <h3 className="truncate text-[13px] font-semibold tracking-[-0.01em] text-[#1C241F]">
              {activeCitation?.documentName || "Citation"}
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
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-wrap items-center gap-2 border-b border-[#EBEFEA] px-5 py-3">
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-[#F6F7F4] px-2.5 py-1.5 text-[12px] font-medium text-[#5B6858]">
                <FileText className="h-3.5 w-3.5" />
                {pageValid
                  ? `p. ${activeCitation.pageNumber}`
                  : "Page unavailable"}
              </span>
              {relScore !== null && (
                <span className="inline-flex items-center rounded-lg bg-[#F6F7F4] px-2.5 py-1.5 text-[12px] font-medium text-[#5B6858]">
                  {relScore}% relevance
                </span>
              )}
              {pdfUrl && (
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-auto text-[12px] font-medium text-[#4A5D23] hover:text-[#3E4E1D]"
                >
                  Open in new tab
                </a>
              )}
            </div>

            <div className="min-h-0 flex-1 bg-[#F6F7F4]">
              {pdfUrl && !iframeFailed ? (
                <iframe
                  key={`${documentId}-${pageValid ? activeCitation.pageNumber : "none"}`}
                  title={`${activeCitation.documentName} page preview`}
                  src={pdfUrl}
                  className="h-full w-full border-0 bg-white"
                  onError={() => setIframeFailed(true)}
                />
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-2 px-8 text-center">
                  <AlertCircle className="h-5 w-5 text-[#98A395]" />
                  <p className="text-[13px] leading-relaxed text-[#6F7B6B]">
                    {documentId
                      ? "The PDF preview could not be loaded. Use Open in new tab if the file is available."
                      : "This citation does not include a document id, so the original PDF cannot be opened."}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
};
