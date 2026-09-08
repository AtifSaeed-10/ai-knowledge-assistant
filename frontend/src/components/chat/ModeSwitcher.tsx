"use client";

import React, { useRef } from "react";
import { PRODUCT_MODES, ProductMode } from "@/types/mode";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import { cn } from "@/lib/cn";

/**
 * Radio group with roving tabindex: one tab stop, arrow keys move between modes.
 */
export function ModeSwitcher() {
  const productMode = useChatStore((state) => state.productMode);
  const setProductMode = useChatStore((state) => state.setProductMode);
  const documents = useDocumentStore((state) => state.documents);
  const selectedDocumentId = useDocumentStore((state) => state.selectedDocumentId);
  const selectDocument = useDocumentStore((state) => state.selectDocument);

  const buttonsRef = useRef<(HTMLButtonElement | null)[]>([]);

  const applyMode = (mode: ProductMode) => {
    if (mode === "super_focused") {
      const ready = documents.filter((doc) => doc.status === "ready");
      const selectedIsReady = ready.some((doc) => doc.id === selectedDocumentId);

      // Choosing single-document mode with one obvious candidate should just work.
      if (!selectedIsReady && ready.length === 1) {
        selectDocument(ready[0].id);
      }
    }
    setProductMode(mode);
  };

  const onKeyDown = (event: React.KeyboardEvent, index: number) => {
    const keys = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"];
    if (!keys.includes(event.key)) return;

    event.preventDefault();
    const forward = event.key === "ArrowRight" || event.key === "ArrowDown";
    const next = (index + (forward ? 1 : -1) + PRODUCT_MODES.length) % PRODUCT_MODES.length;

    applyMode(PRODUCT_MODES[next].id);
    buttonsRef.current[next]?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label="Which documents to search"
      data-tour="scope"
      className="inline-flex shrink-0 items-center rounded-lg border border-line bg-surface-sunken p-0.5"
    >
      {PRODUCT_MODES.map((mode, index) => {
        const isActive = productMode === mode.id;

        return (
          <button
            key={mode.id}
            ref={(element) => {
              buttonsRef.current[index] = element;
            }}
            type="button"
            role="radio"
            aria-checked={isActive}
            tabIndex={isActive ? 0 : -1}
            title={mode.description}
            onClick={() => applyMode(mode.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "rounded-md px-2 py-1 text-meta font-medium tracking-[-0.01em] transition-colors",
              isActive
                ? "bg-surface text-ink shadow-card"
                : "text-ink-muted hover:text-ink"
            )}
          >
            {mode.label}
          </button>
        );
      })}
    </div>
  );
}
