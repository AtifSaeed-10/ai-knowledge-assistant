"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertCircle, ExternalLink, FileText, Minus, Plus, X } from "lucide-react";
import { documentsApi } from "@/lib/api/documents";
import { fetchChunkEvidence } from "@/lib/api/evidence";
import { resolveEvidenceView, type ChunkEvidence } from "@/lib/pdf/coords";
import { pdfFileUrlWithoutHash } from "@/lib/pdf/pdfjs";
import { evidenceStatusDetail, contentTypeDetail } from "@/lib/citations/evidenceStatus";
import { resolveCitationDocumentName } from "@/lib/citations/documentName";
import type { Citation } from "@/types/citation";
import type { Document } from "@/types/document";
import { usePdfPanelStore } from "@/store/usePdfPanelStore";
import { relevancePercent } from "./CitationCard";
import { PdfEvidenceViewer } from "./PdfEvidenceViewer";

const SLOW_LOAD_MS = 6000;
const MIN_ZOOM = 0.75;
const MAX_ZOOM = 2.5;
const ZOOM_STEP = 0.25;

function citationToChunkEvidence(citation: Citation): ChunkEvidence | null {
  if (!citation.chunk_id || !citation.documentId) return null;
  const page = citation.pageNumber && citation.pageNumber >= 1 ? citation.pageNumber : 1;
  return {
    chunk_id: citation.chunk_id,
    document_id: citation.documentId,
    page_start: page,
    page_end: page,
    snippet: citation.snippet || citation.quote || "",
    highlight_available: false,
    regions: [],
    quote: citation.quote ?? null,
    quote_highlight_available: citation.quoteHighlightAvailable === true,
    quote_regions: citation.quoteRegions || [],
    quote_mapping_status: citation.quoteMappingStatus ?? null,
  };
}

function mappingStatusMessage(status: string | null | undefined): string | null {
  if (
    !status ||
    status === "none" ||
    status === "exact" ||
    status === "normalized" ||
    status === "sentence" ||
    status === "semantic_span"
  ) {
    return null;
  }
  if (status === "fallback_chunk") {
    return "Precise highlighting is uncertain for this claim. Showing the cited passage and page instead.";
  }
  if (status === "unresolved") {
    return "Could not locate exact supporting text in the PDF. Showing the cited passage only.";
  }
  if (status === "not_in_chunk") {
    return "The cited quote could not be matched to the retrieved passage.";
  }
  if (status === "no_evidence_data") {
    return "This document was indexed before highlight data was available. Showing the cited page and snippet only.";
  }
  if (status === "no_layout") {
    return "PDF layout data is unavailable for this document.";
  }
  if (status === "not_on_page") {
    return "The quote appears in the passage but could not be located on the PDF page.";
  }
  if (status === "rejected") {
    return "The cited quote was rejected as invalid.";
  }
  return "Exact highlighting is unavailable for this citation.";
}

function isValidPage(page: number | null | undefined): page is number {
  return typeof page === "number" && Number.isFinite(page) && page >= 1;
}

export function PdfSourcePanel({
  document,
  citation,
  onClose,
  closeButtonRef,
}: {
  document: Document | null;
  citation: Citation | null;
  onClose: () => void;
  closeButtonRef?: React.Ref<HTMLButtonElement>;
}) {
  const [isFrameLoading, setIsFrameLoading] = useState(true);
  const [isSlow, setIsSlow] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [evidence, setEvidence] = useState<ChunkEvidence | null>(null);
  const [evidenceReady, setEvidenceReady] = useState(false);
  const navFocusPage = usePdfPanelStore((state) => state.focusPage);
  const navToken = usePdfPanelStore((state) => state.navToken);
  const setPageCount = usePdfPanelStore((state) => state.setPageCount);
  const setVisiblePage = usePdfPanelStore((state) => state.setVisiblePage);

  const documentId = document?.id || citation?.documentId || null;
  const view = resolveEvidenceView({
    citationPage: citation?.pageNumber ?? null,
    evidence,
    citationSnippet: citation?.snippet ?? null,
    citationQuote: citation?.quote ?? null,
  });
  const pageValid = isValidPage(view.page);
  const pdfUrl = documentId
    ? documentsApi.fileUrl(documentId, citation && pageValid ? view.page : null)
    : null;
  const viewerUrl = pdfUrl ? pdfFileUrlWithoutHash(pdfUrl) : null;
  const snippet = view.snippet || citation?.quote || citation?.snippet || "";
  const showSnippetFallback = Boolean(citation) && evidenceReady && !view.canHighlight;
  const mappingMessage =
    contentTypeDetail(citation?.contentType) ||
    evidenceStatusDetail(citation ?? {}) ||
    mappingStatusMessage(citation?.quoteMappingStatus) ||
    mappingStatusMessage(evidence?.quote_mapping_status ?? null);

  useEffect(() => {
    setIsFrameLoading(true);
    setIsSlow(false);
    setLoadFailed(false);
    setZoom(1);
    setPageCount(null);
  }, [documentId, setPageCount]);

  useEffect(() => {
    setEvidence(null);
    setEvidenceReady(!citation?.chunk_id);
  }, [citation?.id, citation?.pageNumber, citation?.chunk_id, citation?.quote, documentId]);

  useEffect(() => {
    if (!documentId || !citation?.chunk_id) {
      setEvidenceReady(true);
      return;
    }

    const preResolved = citationToChunkEvidence(citation);
    if (
      preResolved &&
      (preResolved.quote_highlight_available === true ||
        Boolean(preResolved.quote_mapping_status && preResolved.quote_mapping_status !== "none"))
    ) {
      setEvidence(preResolved);
      setEvidenceReady(true);
      return;
    }

    const controller = new AbortController();

    void fetchChunkEvidence(documentId, citation.chunk_id, {
      quote: citation.quote,
      claim: citation.claimContext,
      signal: controller.signal,
    })
      .then((row) => {
        if (controller.signal.aborted) return;
        setEvidence(row);
        setEvidenceReady(true);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setEvidence(null);
        setEvidenceReady(true);
      });

    return () => controller.abort();
  }, [
    citation?.chunk_id,
    citation?.claimContext,
    citation?.documentId,
    citation?.pageNumber,
    citation?.quote,
    citation?.quoteHighlightAvailable,
    citation?.quoteMappingStatus,
    citation?.quoteRegions,
    citation?.snippet,
    documentId,
  ]);

  useEffect(() => {
    if (!isFrameLoading) return;
    const timer = window.setTimeout(() => setIsSlow(true), SLOW_LOAD_MS);
    return () => window.clearTimeout(timer);
  }, [isFrameLoading, documentId]);

  const handleReady = useCallback(() => {
    setIsFrameLoading(false);
    setLoadFailed(false);
  }, []);

  const handleError = useCallback(() => {
    setIsFrameLoading(false);
    setLoadFailed(true);
  }, []);

  const title =
    document?.name ||
    (citation ? resolveCitationDocumentName(citation, [], "Document") : "Document");
  const score = citation ? relevancePercent(citation.relevance) : null;
  const previewPage =
    citation && pageValid
      ? view.page
      : navFocusPage && navFocusPage >= 1
        ? navFocusPage
        : 1;
  const pageLabel = citation
    ? pageValid
      ? `Page ${view.page}`
      : "Page unavailable"
    : navFocusPage && navFocusPage >= 1
      ? `Page ${navFocusPage}`
      : document?.totalPages
        ? `${document.totalPages} pages`
        : "Preview";
  const preparing = Boolean(document && document.status !== "ready" && document.status !== "failed");

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface">
      <div className="flex shrink-0 items-start justify-between gap-3 border-b border-line px-4 py-3 sm:px-5 sm:py-3.5">
        <div className="min-w-0">
          <p className="text-label font-semibold uppercase tracking-[0.09em] text-ink-muted">
            {citation ? "Source document" : "Document"}
          </p>
          <h2 className="truncate text-body font-semibold tracking-[-0.01em] text-ink">
            {title}
          </h2>
        </div>
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          className="shrink-0 rounded-lg p-1.5 text-ink-icon transition-colors hover:bg-surface-sunken hover:text-ink"
          aria-label="Close PDF"
          title="Close PDF and give the chat more room"
        >
          <X size={18} />
        </button>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-line px-4 py-2.5 sm:px-5">
        <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-sunken px-2.5 py-1.5 text-meta font-medium text-ink-muted">
          <FileText className="h-3.5 w-3.5" />
          {pageLabel}
        </span>

        {preparing && (
          <span className="inline-flex items-center rounded-lg bg-olive-soft px-2.5 py-1.5 text-meta font-medium text-olive">
            Preparing…
          </span>
        )}

        {score !== null && (
          <span className="inline-flex items-center rounded-lg bg-surface-sunken px-2.5 py-1.5 text-meta font-medium tabular-nums text-ink-muted">
            {score}% relevance
          </span>
        )}

        {viewerUrl && (
          <div className="inline-flex items-center rounded-lg bg-surface-sunken">
            <button
              type="button"
              onClick={() => setZoom((value) => Math.max(MIN_ZOOM, value - ZOOM_STEP))}
              disabled={zoom <= MIN_ZOOM}
              className="rounded-lg p-1.5 text-ink-icon transition-colors hover:text-ink disabled:opacity-40"
              aria-label="Zoom out"
            >
              <Minus className="h-3.5 w-3.5" />
            </button>
            <span className="min-w-10 px-0.5 text-center text-meta tabular-nums text-ink-muted">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              onClick={() => setZoom((value) => Math.min(MAX_ZOOM, value + ZOOM_STEP))}
              disabled={zoom >= MAX_ZOOM}
              className="rounded-lg p-1.5 text-ink-icon transition-colors hover:text-ink disabled:opacity-40"
              aria-label="Zoom in"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {pdfUrl && (
          <a
            href={pdfUrl}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-meta font-medium text-olive transition-colors hover:bg-olive-soft"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Open in new tab
          </a>
        )}
      </div>

      {showSnippetFallback && (
        <div className="shrink-0 border-b border-warn-line bg-warn-soft px-4 py-3 sm:px-5">
          <p className="text-meta font-medium text-warn">Highlight unavailable</p>
          {mappingMessage ? (
            <p className="mt-1 text-ui leading-relaxed text-ink-muted">{mappingMessage}</p>
          ) : null}
          {snippet ? (
            <p className="mt-1 text-ui leading-relaxed text-ink-muted">“{snippet}”</p>
          ) : (
            <p className="mt-1 text-ui leading-relaxed text-ink-muted">
              This source has no stored highlight. Showing the cited page.
            </p>
          )}
        </div>
      )}

      <div className="relative min-h-0 flex-1 bg-paper">
        {viewerUrl ? (
          <>
            <PdfEvidenceViewer
              fileUrl={viewerUrl}
              focusPage={previewPage}
              focusNonce={navToken}
              evidence={evidence}
              scale={zoom}
              onReady={handleReady}
              onError={handleError}
              onPageCount={setPageCount}
              onVisiblePage={setVisiblePage}
            />

            {isFrameLoading && (
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3 bg-paper px-8 text-center">
                <div className="w-full max-w-xs space-y-2.5">
                  <div className="skeleton h-3 w-3/5" />
                  <div className="skeleton h-3 w-full" />
                  <div className="skeleton h-3 w-4/5" />
                </div>
                <p className="text-meta text-ink-muted">
                  {isSlow
                    ? "Still loading this page. You can open the PDF in a new tab instead."
                    : "Loading page…"}
                </p>
              </div>
            )}

            {loadFailed && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-paper px-8 text-center">
                <AlertCircle className="h-5 w-5 text-ink-icon" />
                <p className="max-w-sm text-ui leading-relaxed text-ink-muted">
                  The PDF preview could not be loaded. Open it in a new tab instead.
                </p>
              </div>
            )}
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-8 text-center">
            <AlertCircle className="h-5 w-5 text-ink-icon" />
            <p className="max-w-sm text-ui leading-relaxed text-ink-muted">
              This document cannot be opened in the preview.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
