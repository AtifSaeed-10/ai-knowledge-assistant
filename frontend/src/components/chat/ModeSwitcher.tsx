"use client";

import React from "react";
import { PRODUCT_MODES, ProductMode } from "@/types/mode";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";

export function ModeSwitcher() {
  const productMode = useChatStore((state) => state.productMode);
  const setProductMode = useChatStore((state) => state.setProductMode);
  const documents = useDocumentStore((state) => state.documents);
  const selectedDocumentId = useDocumentStore((state) => state.selectedDocumentId);
  const selectDocument = useDocumentStore((state) => state.selectDocument);

  const handleSelect = (mode: ProductMode, enabled: boolean) => {
    if (!enabled) return;
    if (mode === "super_focused") {
      const ready = documents.filter((doc) => doc.status === "ready");
      if (!selectedDocumentId && ready.length === 1) {
        selectDocument(ready[0].id);
      }
    }
    setProductMode(mode);
  };

  return (
    <div
      className="inline-flex items-center rounded-lg border border-[#EBEFEA] bg-[#F6F7F4] p-0.5"
      role="radiogroup"
      aria-label="Answer mode"
    >
      {PRODUCT_MODES.map((mode) => {
        const isActive = productMode === mode.id;
        return (
          <button
            key={mode.id}
            type="button"
            role="radio"
            aria-checked={isActive}
            disabled={!mode.enabled}
            title={mode.enabled ? mode.description : mode.description}
            onClick={() => handleSelect(mode.id, mode.enabled)}
            className={`rounded-md px-2 py-1 text-[11px] font-medium tracking-[-0.01em] transition-colors ${
              isActive
                ? "bg-white text-[#1C241F] shadow-sm"
                : mode.enabled
                  ? "text-[#6F7B6B] hover:text-[#1C241F]"
                  : "cursor-not-allowed text-[#C4CBC0]"
            }`}
          >
            {mode.label}
          </button>
        );
      })}
    </div>
  );
}
