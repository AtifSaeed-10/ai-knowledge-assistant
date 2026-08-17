"use client";

import React from "react";
import { Loader2 } from "lucide-react";
import { useDocumentStore } from "@/store/useDocumentStore";
import { PREP_STAGE_LABELS, getFriendlyDocumentStatus } from "./ProcessingTimeline";
import { cn } from "@/lib/cn";

/**
 * Shown in the transcript area while a workspace has documents but nothing
 * searchable yet. The workspace itself stays usable behind it.
 */
export function PreparingPanel() {
  const documents = useDocumentStore((state) => state.documents);

  const processing = documents.filter(
    (doc) => doc.status !== "ready" && doc.status !== "failed"
  );
  const failed = documents.filter((doc) => doc.status === "failed");
  const lead = processing[0];

  if (processing.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-5 py-8">
        <div className="w-full max-w-md text-center">
          <h2 className="text-title font-semibold tracking-[-0.01em] text-ink">
            No searchable documents
          </h2>
          <p className="mt-1.5 text-ui leading-relaxed text-ink-muted">
            {failed.length > 0
              ? "Processing did not finish for your documents. Check the sidebar to retry or remove them."
              : "Add a PDF to start asking questions."}
          </p>
        </div>
      </div>
    );
  }

  const leadStageLabel = lead ? getFriendlyDocumentStatus(lead.status) : PREP_STAGE_LABELS[0];
  const leadStageIndex = Math.max(0, PREP_STAGE_LABELS.indexOf(leadStageLabel));

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-5 py-8">
      <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-7 text-center shadow-card">
        <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-olive-soft text-olive">
          <Loader2 className="h-4 w-4 animate-spin" />
        </span>

        <h2 className="mt-4 text-title font-semibold tracking-[-0.01em] text-ink">
          Preparing your knowledge base
        </h2>

        <p className="mt-1.5 text-ui leading-relaxed text-ink-muted break-anywhere">
          {processing.length === 1 && lead?.name
            ? `Working on “${lead.name}”`
            : `${processing.length} documents in progress`}
        </p>

        <div className="mx-auto mt-5 h-1 w-40 overflow-hidden rounded-full bg-olive-soft">
          <div className="h-full w-1/2 animate-progress-slide rounded-full bg-sage" />
        </div>

        <ol className="mx-auto mt-6 max-w-xs space-y-2 text-left">
          {PREP_STAGE_LABELS.map((label, index) => {
            const done = index < leadStageIndex;
            const current = index === leadStageIndex;

            return (
              <li
                key={label}
                className={cn(
                  "flex items-center gap-2.5 text-ui",
                  current
                    ? "font-medium text-ink"
                    : done
                      ? "text-ink-muted"
                      : "text-ink-subtle"
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    current ? "bg-olive" : done ? "bg-sage" : "bg-line-strong"
                  )}
                />
                {label}
              </li>
            );
          })}
        </ol>

        <p className="mt-5 text-meta text-ink-subtle">Per-file progress is in the sidebar</p>
      </div>
    </div>
  );
}
