"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import { usePdfPanelStore } from "@/store/usePdfPanelStore";
import {
  resolvePreviewDocument,
  shouldShowMobileOverlay,
} from "@/lib/workspace/pdfPanel";
import { PdfSourcePanel } from "./PdfSourcePanel";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Phone overlay. Desktop uses the docked pane instead, so this portal is
 * hidden from `lg` and up even when a citation is active.
 */
export const CitationDrawer = () => {
  const activeCitation = useChatStore((state) => state.activeCitation);
  const setActiveCitation = useChatStore((state) => state.setActiveCitation);
  const isOpen = usePdfPanelStore((state) => state.isOpen);
  const pinned = usePdfPanelStore((state) => state.pinned);
  const closePanel = usePdfPanelStore((state) => state.close);
  const previewDocumentId = usePdfPanelStore((state) => state.previewDocumentId);
  const documents = useDocumentStore((state) => state.documents);
  const selectedDocumentId = useDocumentStore((state) => state.selectedDocumentId);

  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const [mounted, setMounted] = useState(false);

  const showOverlay = shouldShowMobileOverlay({
    isOpen,
    pinned,
    hasCitation: Boolean(activeCitation),
  });

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

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!showOverlay) return;

    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 0);

    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = overflow;
      returnFocusRef.current?.focus?.();
    };
  }, [showOverlay]);

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

  if (!mounted || !showOverlay || !previewDocument) return null;

  return createPortal(
    <div className="fixed inset-0 z-[110] lg:hidden" onKeyDown={handleKeyDown}>
      <div className="absolute inset-0 animate-fade-in bg-ink/30" onClick={close} aria-hidden />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Source: ${previewDocument.name}`}
        className="absolute right-0 top-0 flex h-full w-full animate-slide-in-right flex-col border-l border-line bg-surface pt-[env(safe-area-inset-top)] shadow-overlay sm:w-[min(760px,92vw)]"
      >
        <PdfSourcePanel
          document={previewDocument}
          citation={activeCitation}
          onClose={close}
          closeButtonRef={closeButtonRef}
        />
      </div>
    </div>,
    document.body
  );
};
