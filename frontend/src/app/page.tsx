"use client";

import React, { useEffect } from "react";
import { AlertCircle, RotateCcw } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { WorkspaceStage } from "@/components/layout/WorkspaceStage";
import { useDocumentStore } from "@/store/useDocumentStore";
import { LogoMark } from "@/components/ui/Logo";

export default function WorkspacePage() {
  const documents = useDocumentStore((state) => state.documents);
  const hasInitialized = useDocumentStore((state) => state.hasInitialized);
  const loadError = useDocumentStore((state) => state.loadError);
  const initialize = useDocumentStore((state) => state.initialize);
  const reload = useDocumentStore((state) => state.reload);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  const isBooting = !hasInitialized;
  const hasDocuments = documents.length > 0;

  return (
    <AppLayout>
      {isBooting && (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4">
          <div className="w-48 space-y-2.5" aria-hidden>
            <div className="skeleton h-3 w-3/5" />
            <div className="skeleton h-3 w-full" />
            <div className="skeleton h-3 w-4/5" />
          </div>
          <p className="text-ui text-ink-muted" role="status">
            Loading workspace…
          </p>
        </div>
      )}

      {!isBooting && !hasDocuments && (
        <div className="scroll-area min-h-0 flex-1 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center py-8">
            <div className="w-full max-w-lg text-center">
              <LogoMark className="mx-auto h-10 w-auto" />

              <h1 className="mt-5 text-display font-semibold tracking-[-0.02em] text-ink">
                Upload a PDF to begin
              </h1>
              <p className="mx-auto mt-2 max-w-md text-body leading-relaxed text-ink-muted">
                DocuSage indexes your documents so you can ask questions and get answers with
                citations.
              </p>

              {loadError && (
                <div
                  role="alert"
                  className="mx-auto mt-5 flex max-w-md items-start gap-2 rounded-xl border border-danger-line bg-danger-soft px-3.5 py-3 text-left"
                >
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
                  <div className="min-w-0 flex-1">
                    <p className="text-ui font-semibold text-danger">
                      Couldn’t load your workspace
                    </p>
                    <p className="mt-0.5 text-meta leading-relaxed text-ink-muted break-anywhere">
                      {loadError}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void reload()}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-surface px-2 py-1 text-meta font-medium text-ink ring-1 ring-line transition-colors hover:bg-surface-muted"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Retry
                  </button>
                </div>
              )}

              <div className="mt-7 rounded-2xl border border-line bg-surface p-2 shadow-card sm:p-3">
                <DocumentUploader />
              </div>

              <p className="mt-3 text-meta text-ink-subtle">
                Every answer links back to the exact page it came from
              </p>
            </div>
          </div>
        </div>
      )}

      {!isBooting && hasDocuments && <WorkspaceStage />}
    </AppLayout>
  );
}
