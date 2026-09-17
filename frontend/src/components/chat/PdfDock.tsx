"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import { usePdfPanelStore } from "@/store/usePdfPanelStore";
import {
  maxPdfWidthForWorkspace,
  PDF_PANEL_MAX_WIDTH,
  PDF_PANEL_MIN_WIDTH,
  resolvePreviewDocument,
} from "@/lib/workspace/pdfPanel";
import { PdfSourcePanel } from "./PdfSourcePanel";

/**
 * Desktop document pane. Stays mounted while open so a new citation only
 * scrolls and highlights — it does not reload the PDF.
 */
export function PdfDock() {
  const isOpen = usePdfPanelStore((state) => state.isOpen);
  const width = usePdfPanelStore((state) => state.width);
  const setWidth = usePdfPanelStore((state) => state.setWidth);
  const closePanel = usePdfPanelStore((state) => state.close);
  const previewDocumentId = usePdfPanelStore((state) => state.previewDocumentId);
  const setActiveCitation = useChatStore((state) => state.setActiveCitation);
  const activeCitation = useChatStore((state) => state.activeCitation);
  const documents = useDocumentStore((state) => state.documents);
  const selectedDocumentId = useDocumentStore((state) => state.selectedDocumentId);

  const workspaceRef = useRef<HTMLElement | null>(null);
  const [maxAvailable, setMaxAvailable] = useState(PDF_PANEL_MAX_WIDTH);
  const [isResizing, setIsResizing] = useState(false);

  const previewDocument = resolvePreviewDocument({
    documents,
    selectedDocumentId,
    citationDocumentId: activeCitation?.documentId,
    previewDocumentId,
  });

  const close = useCallback(() => {
    setActiveCitation(null);
    closePanel();
  }, [closePanel, setActiveCitation]);

  useEffect(() => {
    const node = workspaceRef.current?.parentElement;
    if (!node) return;

    const measure = () => {
      setMaxAvailable(maxPdfWidthForWorkspace(node.getBoundingClientRect().width));
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [isOpen]);

  useEffect(() => {
    if (width > maxAvailable) setWidth(maxAvailable, maxAvailable);
  }, [maxAvailable, setWidth, width]);

  const startResizing = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = width;
      setIsResizing(true);

      const onMove = (move: MouseEvent) => {
        setWidth(startWidth + (startX - move.clientX), maxAvailable);
      };
      const onUp = () => {
        setIsResizing(false);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };

      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [maxAvailable, setWidth, width]
  );

  if (!isOpen) return null;

  return (
    <aside
      ref={workspaceRef}
      data-pdf-dock="true"
      aria-label="Document preview"
      style={{ width }}
      className="relative hidden min-h-0 shrink-0 lg:flex"
    >
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize document preview"
        aria-valuenow={width}
        aria-valuemin={PDF_PANEL_MIN_WIDTH}
        aria-valuemax={maxAvailable}
        tabIndex={0}
        onMouseDown={startResizing}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") {
            event.preventDefault();
            setWidth(width + 16, maxAvailable);
          }
          if (event.key === "ArrowRight") {
            event.preventDefault();
            setWidth(width - 16, maxAvailable);
          }
        }}
        className="group absolute -left-1.5 bottom-0 top-0 z-20 w-3 cursor-col-resize"
      >
        <div
          className={`mx-auto h-full w-px transition-colors ${
            isResizing ? "bg-olive" : "bg-transparent group-hover:bg-sage group-focus-visible:bg-olive"
          }`}
        />
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-surface-muted/70">
        <PdfSourcePanel
          document={previewDocument}
          citation={activeCitation}
          onClose={close}
        />
      </div>
    </aside>
  );
}
