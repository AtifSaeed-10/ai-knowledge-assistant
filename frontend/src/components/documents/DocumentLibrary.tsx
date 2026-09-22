"use client";

import React, { useEffect, useId, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  Crosshair,
  FileText,
  Loader2,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useDocumentStore } from "@/store/useDocumentStore";
import { useChatStore } from "@/store/useChatStore";
import { usePdfPanelStore } from "@/store/usePdfPanelStore";
import { Document, DocumentEvidenceSummary } from "@/types";
import { documentsApi } from "@/lib/api/documents";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { ProcessingTimeline, getFriendlyDocumentStatus } from "./ProcessingTimeline";
import { cn } from "@/lib/cn";

interface DocumentLibraryProps {
  isCollapsed?: boolean;
}

function formatRelativeTime(input: Date): string {
  const value = input instanceof Date ? input : new Date(input);
  const minutes = Math.floor((Date.now() - value.getTime()) / 60000);

  if (Number.isNaN(minutes) || minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return value.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function highlightAvailabilityLabel(summary: DocumentEvidenceSummary): string | null {
  if (!summary.has_evidence_data) {
    return "PDF highlight data is unavailable for this document. Citations still work, but page regions may be limited.";
  }
  const ratio = summary.highlight_ratio;
  if (ratio >= 0.95) return null;
  const pct = Math.round(ratio * 100);
  if (pct === 0) {
    return "This PDF has no mappable text regions. Citations show snippets only.";
  }
  return `PDF highlights available for ${pct}% of indexed passages.`;
}

function DocumentEvidenceNote({ documentId }: { documentId: string }) {
  const [summary, setSummary] = useState<DocumentEvidenceSummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    void documentsApi
      .getEvidenceSummary(documentId)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  const label = summary ? highlightAvailabilityLabel(summary) : null;
  if (!label) return null;

  return (
    <p className="mt-2.5 border-t border-line pt-2 text-meta leading-relaxed text-ink-muted">
      {label}
    </p>
  );
}

export function DocumentLibrary({ isCollapsed = false }: DocumentLibraryProps) {
  const documents = useDocumentStore((state) => state.documents);
  const deleteDocument = useDocumentStore((state) => state.deleteDocument);
  const retryProcessing = useDocumentStore((state) => state.retryProcessing);
  const selectedDocumentId = useDocumentStore((state) => state.selectedDocumentId);
  const selectDocument = useDocumentStore((state) => state.selectDocument);
  const loadError = useDocumentStore((state) => state.loadError);
  const reload = useDocumentStore((state) => state.reload);
  const productMode = useChatStore((state) => state.productMode);
  const setActiveCitation = useChatStore((state) => state.setActiveCitation);
  const previewOpen = usePdfPanelStore((state) => state.isOpen);
  const openPreview = usePdfPanelStore((state) => state.open);

  const chooseDocument = (id: string | null) => {
    selectDocument(id);
    if (id && previewOpen) {
      setActiveCitation(null);
      openPreview({ documentId: id });
    }
  };

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Document | null>(null);
  const detailsId = useId();

  const header = !isCollapsed && (
    <div className="flex shrink-0 items-center justify-between gap-2 px-5 pb-1.5 pt-3">
      <h2 className="text-label font-semibold uppercase tracking-[0.09em] text-ink-muted">
        Documents
      </h2>
      {documents.length > 0 && (
        <span className="rounded-md bg-olive-soft px-1.5 py-0.5 text-label font-medium tabular-nums text-ink-muted">
          {documents.length}
        </span>
      )}
    </div>
  );

  if (documents.length === 0) {
    if (isCollapsed) return null;

    return (
      <section className="flex min-h-0 flex-col" aria-label="Documents">
        {header}
        <div className="px-5 py-3">
          {loadError ? (
            <div className="rounded-lg border border-danger-line bg-danger-soft p-3">
              <p className="text-meta font-medium text-danger">Couldn’t load documents</p>
              <p className="mt-1 text-meta leading-relaxed text-ink-muted break-anywhere">
                {loadError}
              </p>
              <button
                type="button"
                onClick={() => void reload()}
                className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-surface px-2 py-1 text-meta font-medium text-ink ring-1 ring-line transition-colors hover:bg-surface-muted"
              >
                <RotateCcw className="h-3 w-3" />
                Try again
              </button>
            </div>
          ) : (
            <p className="text-meta leading-relaxed text-ink-muted">
              No documents yet. Use <span className="font-medium text-ink">New document</span> to
              add your first PDF.
            </p>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="flex min-h-0 flex-col" aria-label="Documents">
      {header}

      <div className={cn("scroll-area min-h-0 flex-1 overflow-y-auto pb-3", isCollapsed ? "px-2" : "px-3")}>
        <ul className="space-y-0.5">
          {documents.map((doc) => {
            const isExpanded = expandedId === doc.id;
            const isSelected = selectedDocumentId === doc.id;
            const isReady = doc.status === "ready";
            const isFailed = doc.status === "failed";
            const rowDetailsId = `${detailsId}-${doc.id}`;

            if (isCollapsed) {
              return (
                <li key={doc.id}>
                  <button
                    type="button"
                    onClick={() => chooseDocument(doc.id)}
                    aria-pressed={isSelected}
                    title={`${doc.name} — ${getFriendlyDocumentStatus(doc.status)}`}
                    className={cn(
                      "relative flex h-11 w-full items-center justify-center rounded-lg transition-colors",
                      isSelected ? "bg-surface ring-1 ring-sage" : "hover:bg-surface-sunken"
                    )}
                  >
                    <span className="sr-only">{doc.name}</span>
                    {isFailed ? (
                      <AlertTriangle className="h-4 w-4 text-danger" strokeWidth={1.75} />
                    ) : isReady ? (
                      <FileText className="h-4 w-4 text-olive" strokeWidth={1.75} />
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin text-olive" strokeWidth={1.75} />
                    )}
                  </button>
                </li>
              );
            }

            return (
              <li key={doc.id} className="group relative">
                <button
                  type="button"
                  onClick={() => chooseDocument(isSelected ? null : doc.id)}
                  aria-pressed={isSelected}
                  title={doc.name}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-lg py-2 pl-2 pr-[4.25rem] text-left transition-colors",
                    isSelected
                      ? "bg-surface ring-1 ring-sage"
                      : isExpanded
                        ? "bg-olive-soft"
                        : "hover:bg-surface-sunken"
                  )}
                >
                  <span
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border bg-surface",
                      isFailed ? "border-danger-line text-danger" : "border-line text-olive"
                    )}
                  >
                    {isFailed ? (
                      <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.75} />
                    ) : isReady ? (
                      <FileText className="h-3.5 w-3.5" strokeWidth={1.75} />
                    ) : (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} />
                    )}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span
                      className={cn(
                        "block truncate text-ui font-medium tracking-[-0.01em]",
                        isReady || isFailed ? "text-ink" : "text-ink-muted"
                      )}
                    >
                      {doc.name}
                    </span>

                    <span className="mt-0.5 flex items-center gap-1.5 text-meta text-ink-subtle">
                      <span
                        className={cn(
                          "truncate",
                          isFailed ? "text-danger" : isReady ? "text-ink-muted" : "text-warn"
                        )}
                      >
                        {isFailed ? "Processing failed" : getFriendlyDocumentStatus(doc.status)}
                      </span>

                      {isReady && doc.totalPages ? (
                        <>
                          <span aria-hidden className="text-line-strong">
                            ·
                          </span>
                          <span className="shrink-0 tabular-nums">{doc.totalPages}p</span>
                        </>
                      ) : null}

                      {isSelected && (
                        <>
                          <span aria-hidden className="text-line-strong">
                            ·
                          </span>
                          <span className="inline-flex shrink-0 items-center gap-0.5 font-medium text-olive">
                            <Crosshair className="h-3 w-3" />
                            {productMode === "super_focused" ? "Focused" : "Selected"}
                          </span>
                        </>
                      )}

                      {!isSelected && (
                        <>
                          <span aria-hidden className="text-line-strong">
                            ·
                          </span>
                          <span className="shrink-0">{formatRelativeTime(doc.uploadedAt)}</span>
                        </>
                      )}
                    </span>
                  </span>
                </button>

                <div className="pointer-events-none absolute right-1.5 top-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100">
                  <button
                    type="button"
                    onClick={() => setExpandedId(isExpanded ? null : doc.id)}
                    aria-expanded={isExpanded}
                    aria-controls={rowDetailsId}
                    className="rounded-md p-1.5 text-ink-icon transition-colors hover:bg-surface hover:text-ink"
                    title={isExpanded ? "Hide details" : "Show details"}
                    aria-label={`${isExpanded ? "Hide" : "Show"} details for ${doc.name}`}
                  >
                    <ChevronDown
                      className={cn("h-3.5 w-3.5 transition-transform", isExpanded && "rotate-180")}
                    />
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingDelete(doc)}
                    className="rounded-md p-1.5 text-ink-icon transition-colors hover:bg-danger-soft hover:text-danger"
                    title="Delete document"
                    aria-label={`Delete ${doc.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>

                {isFailed && (
                  <div className="mx-2 mb-1.5 mt-1 rounded-lg border border-danger-line bg-danger-soft px-3 py-2.5">
                    <p className="text-meta leading-relaxed text-ink-muted break-anywhere">
                      {doc.error || "Processing did not finish."}
                    </p>
                    <div className="mt-2 flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => retryProcessing(doc.id)}
                        className="inline-flex items-center gap-1.5 rounded-md bg-surface px-2 py-1 text-meta font-medium text-ink ring-1 ring-line transition-colors hover:bg-surface-muted"
                      >
                        <RotateCcw className="h-3 w-3" />
                        Check again
                      </button>
                      <button
                        type="button"
                        onClick={() => setPendingDelete(doc)}
                        className="rounded-md px-2 py-1 text-meta font-medium text-danger transition-colors hover:bg-surface"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                )}

                {isExpanded && (
                  <div
                    id={rowDetailsId}
                    className="mx-2 mb-1.5 mt-1 animate-fade-in rounded-lg border border-line bg-surface px-3 py-2.5"
                  >
                    <p className="mb-2 text-label font-semibold uppercase tracking-[0.09em] text-ink-muted">
                      Progress
                    </p>
                    <ProcessingTimeline status={doc.status} />
                    {doc.totalChunks ? (
                      <p className="mt-2.5 border-t border-line pt-2 text-meta text-ink-muted">
                        {doc.totalPages ? `${doc.totalPages} pages · ` : ""}
                        {doc.totalChunks} indexed passages
                      </p>
                    ) : null}
                    {isReady ? <DocumentEvidenceNote documentId={doc.id} /> : null}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete document"
        confirmLabel="Delete document"
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          const target = pendingDelete;
          setPendingDelete(null);
          if (target) void deleteDocument(target.id);
        }}
      >
        <p>
          <span className="font-medium text-ink">“{pendingDelete?.name}”</span> will be removed from
          your workspace and will no longer be searchable. This cannot be undone.
        </p>
      </ConfirmDialog>
    </section>
  );
}
