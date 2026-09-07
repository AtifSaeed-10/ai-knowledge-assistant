"use client";

import React from "react";
import { AlertTriangle, Crosshair, Layers, Loader2, PanelRight, PanelRightClose } from "lucide-react";
import { ModeSwitcher } from "./ModeSwitcher";
import { useChatScope } from "@/hooks/useChatScope";
import { useChatStore } from "@/store/useChatStore";
import { usePdfPanelStore } from "@/store/usePdfPanelStore";
import { shouldShowMobileOverlay } from "@/lib/workspace/pdfPanel";
import { cn } from "@/lib/cn";

/**
 * Always-visible answer scope. Sits directly above the composer because
 * "what am I asking?" belongs next to "what am I typing?".
 */
export function ScopeBar() {
  const { mode, scopeLabel, selectedDocument, processingCount, canAsk } = useChatScope();
  const isOpen = usePdfPanelStore((state) => state.isOpen);
  const pinned = usePdfPanelStore((state) => state.pinned);
  const openPanel = usePdfPanelStore((state) => state.open);
  const closePanel = usePdfPanelStore((state) => state.close);
  const activeCitation = useChatStore((state) => state.activeCitation);
  const setActiveCitation = useChatStore((state) => state.setActiveCitation);

  const isFocused = mode === "super_focused";
  const missingSelection = isFocused && !canAsk && !selectedDocument;
  const mobileOverlay = shouldShowMobileOverlay({
    isOpen,
    pinned,
    hasCitation: Boolean(activeCitation),
  });

  const hidePreview = () => {
    setActiveCitation(null);
    closePanel();
  };

  return (
    <div className="mb-2 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
      <ModeSwitcher />

      {missingSelection ? (
        <span className="inline-flex min-w-0 items-center gap-1.5 rounded-md bg-warn-soft px-2 py-1 text-meta text-warn">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">Select a document in the sidebar</span>
        </span>
      ) : (
        <span className="inline-flex min-w-0 items-center gap-1.5 text-meta text-ink-muted">
          {isFocused ? (
            <Crosshair className="h-3.5 w-3.5 shrink-0 text-olive" />
          ) : (
            <Layers className="h-3.5 w-3.5 shrink-0 text-ink-icon" />
          )}
          <span className="truncate" title={scopeLabel}>
            {scopeLabel}
          </span>
        </span>
      )}

      {processingCount > 0 && (
        <span className="inline-flex shrink-0 items-center gap-1.5 text-meta text-ink-subtle">
          <Loader2 className="h-3 w-3 animate-spin" />
          {processingCount} preparing
        </span>
      )}

      <PreviewToggle
        className="ml-auto hidden lg:inline-flex"
        visible={isOpen}
        onShow={() => openPanel({ pinned: true })}
        onHide={hidePreview}
      />
      <PreviewToggle
        className="ml-auto inline-flex lg:hidden"
        visible={mobileOverlay}
        onShow={() => openPanel({ pinned: true })}
        onHide={hidePreview}
      />
    </div>
  );
}

function PreviewToggle({
  visible,
  onShow,
  onHide,
  className,
}: {
  visible: boolean;
  onShow: () => void;
  onHide: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={visible ? onHide : onShow}
      aria-pressed={visible}
      title={
        visible
          ? "Close the PDF and give the chat more room"
          : "Open the PDF beside the chat"
      }
      className={cn(
        "items-center gap-1.5 rounded-lg px-2 py-1 text-meta font-medium text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink",
        className
      )}
    >
      {visible ? (
        <PanelRightClose className="h-3.5 w-3.5 text-olive" />
      ) : (
        <PanelRight className="h-3.5 w-3.5 text-ink-icon" />
      )}
      <span>{visible ? "Hide PDF" : "Show PDF"}</span>
    </button>
  );
}
