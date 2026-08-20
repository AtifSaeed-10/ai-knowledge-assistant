"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AlertCircle, ExternalLink, FileText, Minus, Plus, X } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { documentsApi } from "@/lib/api/documents";
import { fetchChunkEvidence } from "@/lib/api/evidence";
import { resolveEvidenceView, type ChunkEvidence } from "@/lib/pdf/coords";
import { pdfFileUrlWithoutHash } from "@/lib/pdf/pdfjs";
import { relevancePercent } from "./CitationCard";
import { PdfEvidenceViewer } from "./PdfEvidenceViewer";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

const SLOW_LOAD_MS = 6000;
const MIN_ZOOM = 0.75;
const MAX_ZOOM = 2.5;
const ZOOM_STEP = 0.25;

function isValidPage(page: number | null | undefined): page is number {
  return typeof page === "number" && Number.isFinite(page) && page >= 1;
}

export const CitationDrawer = () => {
  const activeCitation = useChatStore((state) => state.activeCitation);
  const setActiveCitation = useChatStore((state) => state.setActiveCitation);

  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const [mounted, setMounted] = useState(false);
  const [isFrameLoading, setIsFrameLoading] = useState(true);
  const [isSlow, setIsSlow] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [evidence, setEvidence] = useState<ChunkEvidence | null>(null);
  const [evidenceReady, setEvidenceReady] = useState(false);

  const isOpen = Boolean(activeCitation);
  const close = useCallback(() => setActiveCitation(null), [setActiveCitation]);

  useEffect(() => setMounted(true), []);

  const documentId = activeCitation?.documentId || null;
  const view = resolveEvidenceView({
    citationPage: activeCitation?.pageNumber ?? null,
    evidence,
    citationSnippet: activeCitation?.snippet ?? null,
    citationQuote: activeCitation?.quote ?? null,
  });
  const pageValid = isValidPage(view.page);
  const pdfUrl = documentId
    ? documentsApi.fileUrl(documentId, pageValid ? view.page : null)
    : null;
  const viewerUrl = pdfUrl ? pdfFileUrlWithoutHash(pdfUrl) : null;
  const snippet = view.snippet || activeCitation?.quote || activeCitation?.snippet || "";
  const showSnippetFallback = evidenceReady && !view.canHighlight;

  useEffect(() => {
    setIsFrameLoading(true);
    setIsSlow(false);
    setLoadFailed(false);
    setZoom(1);
    setEvidence(null);
    setEvidenceReady(false);
  }, [activeCitation?.id, activeCitation?.pageNumber, activeCitation?.chunk_id, activeCitation?.quote]);

  useEffect(() => {
    if (!documentId || !activeCitation?.chunk_id) {
      setEvidenceReady(true);
      return;
    }
    const controller = new AbortController();

    void fetchChunkEvidence(documentId, activeCitation.chunk_id, {
      quote: activeCitation.quote,
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
  }, [activeCitation?.chunk_id, activeCitation?.quote, documentId]);

  useEffect(() => {
    if (!isOpen || !isFrameLoading) return;
    const timer = window.setTimeout(() => setIsSlow(true), SLOW_LOAD_MS);
    return () => window.clearTimeout(timer);
  }, [isOpen, isFrameLoading, activeCitation?.id]);

  useEffect(() => {
    if (!isOpen) return;

    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 0);

    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = overflow;
      returnFocusRef.current?.focus?.();
    };
  }, [isOpen]);

  const handleReady = useCallback(() => {
    setIsFrameLoading(false);
    setLoadFailed(false);
  }, []);

  const handleError = useCallback(() => {
    setIsFrameLoading(false);
    setLoadFailed(true);
  }, []);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      close();
      return;
    }

    if (event.key !== "Tab" || !panelRef.current) return;

    const focusable = Array.from(
      panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)
    ).filter((element) => element.offsetParent !== null);

    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!mounted || !isOpen || !activeCitation) return null;

  const score = relevancePercent(activeCitation.relevance);
  const pageLabel = pageValid ? `Page ${view.page}` : "Page unavailable";

  return createPortal(
    <div className="fixed inset-0 z-[110]" onKeyDown={handleKeyDown}>
      <div className="absolute inset-0 animate-fade-in bg-ink/30" onClick={close} aria-hidden />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Source: ${activeCitation.documentName}`}
        className="absolute right-0 top-0 flex h-full w-full animate-slide-in-right flex-col border-l border-line bg-surface shadow-overlay sm:w-[min(760px,92vw)]"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            <p className="text-label font-semibold uppercase tracking-[0.09em] text-ink-muted">
              Source document
            </p>
            <h2 className="truncate text-body font-semibold tracking-[-0.01em] text-ink">
              {activeCitation.documentName}
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={close}
            className="shrink-0 rounded-lg p-1.5 text-ink-icon transition-colors hover:bg-surface-sunken hover:text-ink"
            aria-label="Close source panel"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-line px-5 py-3">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-sunken px-2.5 py-1.5 text-meta font-medium text-ink-muted">
            <FileText className="h-3.5 w-3.5" />
            {pageLabel}
          </span>

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
          <div className="shrink-0 border-b border-warn-line bg-warn-soft px-5 py-3">
            <p className="text-meta font-medium text-warn">Highlight unavailable</p>
            {snippet ? (
              <p className="mt-1 text-ui leading-relaxed text-ink-muted">
                “{snippet}”
              </p>
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
                key={`${documentId}-${activeCitation.chunk_id || "none"}-${activeCitation.quote || ""}`}
                fileUrl={viewerUrl}
                focusPage={view.page}
                evidence={evidence}
                scale={zoom}
                onReady={handleReady}
                onError={handleError}
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
                This citation has no document reference, so the original PDF cannot be opened.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};
