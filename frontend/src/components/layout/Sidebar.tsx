"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, FileText, PanelLeft, PanelLeftClose, Plus, X } from "lucide-react";
import Link from "next/link";
import { Logo, LogoMark } from "@/components/ui/Logo";
import { Dialog } from "@/components/ui/Dialog";
import { DocumentLibrary } from "@/components/documents/DocumentLibrary";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { ConversationList } from "@/components/chat/ConversationList";
import { useDocumentStore } from "@/store/useDocumentStore";
import { cn } from "@/lib/cn";

const WIDTH_KEY = "docusage_sidebar_width";
const COLLAPSED_KEY = "docusage_sidebar_collapsed";
const MIN_WIDTH = 248;
const MAX_WIDTH = 400;
const COLLAPSED_WIDTH = 76;

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  /** Keeps the panel readable while the onboarding tour points at it. */
  forceExpanded?: boolean;
}

export function Sidebar({ isOpen, onClose, forceExpanded = false }: SidebarProps) {
  const documents = useDocumentStore((state) => state.documents);

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [width, setWidth] = useState(300);
  const [isResizing, setIsResizing] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  useEffect(() => {
    try {
      const storedWidth = window.localStorage.getItem(WIDTH_KEY);
      const storedCollapsed = window.localStorage.getItem(COLLAPSED_KEY);
      if (storedWidth) {
        setWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Number(storedWidth) || 300)));
      }
      if (storedCollapsed) setIsCollapsed(storedCollapsed === "true");
    } catch {
      /* storage unavailable — defaults are fine */
    }
  }, []);

  const persist = (key: string, value: string) => {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      /* ignore */
    }
  };

  const toggleCollapsed = () => {
    setIsCollapsed((previous) => {
      persist(COLLAPSED_KEY, String(!previous));
      return !previous;
    });
  };

  const applyWidth = useCallback((next: number) => {
    const clamped = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next));
    setWidth(clamped);
    persist(WIDTH_KEY, String(clamped));
  }, []);

  const startResizing = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const onMouseMove = (event: MouseEvent) => applyWidth(event.clientX);
    const onMouseUp = () => setIsResizing(false);

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing, applyWidth]);

  const readyCount = documents.filter((doc) => doc.status === "ready").length;
  // Collapsing is a desktop affordance; the mobile drawer is always expanded.
  const isCompact = isCollapsed && !isOpen && !forceExpanded;
  const desktopWidth = isCompact ? COLLAPSED_WIDTH : width;

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink/30 lg:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      <aside
        aria-label="Workspace"
        data-tour="documents"
        style={{ width: isOpen ? "min(288px, 86vw)" : desktopWidth }}
        className={cn(
          "fixed left-0 top-0 z-40 flex h-full flex-col border-r border-line bg-surface-muted pt-[env(safe-area-inset-top)] lg:relative lg:visible lg:translate-x-0 lg:pt-0",
          isResizing ? "transition-none" : "transition-[transform,width] duration-200 ease-out",
          isOpen ? "visible translate-x-0" : "invisible -translate-x-full"
        )}
      >
        <div
          className={cn(
            "flex h-14 shrink-0 items-center gap-2 border-b border-line px-3 sm:h-16",
            isCompact ? "justify-center" : "justify-between"
          )}
        >
          {isCompact ? (
            <Link href="/" aria-label="DocuSage home" className="rounded-md">
              <LogoMark className="h-7 w-7" />
            </Link>
          ) : (
            <Link href="/" aria-label="DocuSage home" className="rounded-md">
              <Logo className="h-7 w-auto shrink-0" />
            </Link>
          )}

          {!isCompact && (
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              className="hidden shrink-0 rounded-md p-1.5 text-ink-icon transition-colors hover:bg-surface-sunken hover:text-ink lg:flex"
            >
              <PanelLeftClose size={18} />
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-md p-1.5 text-ink-icon transition-colors hover:bg-surface-sunken hover:text-ink lg:hidden"
            aria-label="Close workspace menu"
          >
            <X size={18} />
          </button>
        </div>

        <div className="shrink-0 space-y-1.5 px-3 py-3">
          {isCompact && (
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label="Expand sidebar"
              title="Expand sidebar"
              className="hidden h-9 w-full items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface-sunken hover:text-olive lg:flex"
            >
              <PanelLeft size={18} />
            </button>
          )}

          <button
            type="button"
            onClick={() => setIsUploadOpen(true)}
            title="Add a PDF"
            className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-olive text-white shadow-card transition-colors hover:bg-olive-dark"
          >
            <Plus size={16} strokeWidth={2.5} />
            {isCompact ? (
              <span className="sr-only">Add a PDF</span>
            ) : (
              <span className="text-ui font-medium tracking-[-0.01em]">New document</span>
            )}
          </button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-[2_1_0%] flex-col border-b border-line">
            <ConversationList isCollapsed={isCompact} onNavigate={onClose} />
          </div>

          <div className="flex min-h-0 flex-[3_1_0%] flex-col">
            <DocumentLibrary isCollapsed={isCompact} />
          </div>
        </div>

        {!isCompact && documents.length > 0 && (
          <div className="shrink-0 border-t border-line px-4 py-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-meta text-ink-muted">
              <span className="inline-flex items-center gap-1.5">
                <FileText size={13} className="text-ink-icon" />
                {documents.length} {documents.length === 1 ? "document" : "documents"}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 size={13} className="text-sage" />
                {readyCount} ready
              </span>
            </div>
          </div>
        )}

        {!isCompact && (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize sidebar"
            aria-valuenow={width}
            aria-valuemin={MIN_WIDTH}
            aria-valuemax={MAX_WIDTH}
            tabIndex={0}
            onMouseDown={startResizing}
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft") {
                event.preventDefault();
                applyWidth(width - 16);
              }
              if (event.key === "ArrowRight") {
                event.preventDefault();
                applyWidth(width + 16);
              }
            }}
            className="group absolute bottom-0 right-0 top-0 z-50 hidden w-1.5 cursor-col-resize lg:block"
          >
            <div className="ml-auto h-full w-px bg-transparent transition-colors group-hover:bg-sage group-focus-visible:bg-olive group-active:bg-olive" />
          </div>
        )}
      </aside>

      <Dialog
        open={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        title="Add documents"
        description="PDFs are extracted, chunked and indexed automatically."
        size="md"
      >
        <DocumentUploader onComplete={() => setIsUploadOpen(false)} />
      </Dialog>
    </>
  );
}
