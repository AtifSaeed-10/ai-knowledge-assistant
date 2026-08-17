"use client";

import React from "react";
import { AlertTriangle, Crosshair, Layers, Loader2 } from "lucide-react";
import { ModeSwitcher } from "./ModeSwitcher";
import { useChatScope } from "@/hooks/useChatScope";

/**
 * Always-visible answer scope. Sits directly above the composer because
 * "what am I asking?" belongs next to "what am I typing?".
 */
export function ScopeBar() {
  const { mode, scopeLabel, selectedDocument, processingCount, canAsk } = useChatScope();

  const isFocused = mode === "super_focused";
  const missingSelection = isFocused && !canAsk && !selectedDocument;

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
    </div>
  );
}
