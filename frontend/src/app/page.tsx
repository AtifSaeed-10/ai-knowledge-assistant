"use client";

import React, { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { useDocumentStore } from "@/store/useDocumentStore";
import { Logo } from "@/components/ui/Logo";
import { getFriendlyDocumentStatus } from "@/components/documents/ProcessingTimeline";

const PREP_STAGES = [
  "Preparing document",
  "Analyzing content",
  "Making searchable",
];

export default function WorkspacePage() {
  const documents = useDocumentStore((state) => state.documents);
  const isLoading = useDocumentStore((state) => state.isLoading);
  const hasInitialized = useDocumentStore((state) => state.hasInitialized);

  useEffect(() => {
    useDocumentStore.getState().initialize();
  }, []);

  const isBooting = !hasInitialized || isLoading;
  const hasDocuments = documents.length > 0;
  const hasReady = documents.some((doc) => doc.status === "ready");
  const processingDocs = documents.filter((doc) => doc.status !== "ready");
  const leadProcessing = processingDocs[0];
  const leadStageLabel = leadProcessing
    ? getFriendlyDocumentStatus(leadProcessing.status)
    : PREP_STAGES[0];
  const leadStageIndex = Math.max(
    0,
    PREP_STAGES.findIndex((label) => label === leadStageLabel)
  );

  return (
    <AppLayout>

      {/* BOOT */}
      {isBooting && (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 animate-in fade-in duration-300">
          <div className="w-48 space-y-2.5">
            <div className="h-3 w-3/5 rounded animate-shimmer" />
            <div className="h-3 w-full rounded animate-shimmer" />
            <div className="h-3 w-4/5 rounded animate-shimmer" />
          </div>
          <p className="text-[13px] text-[#6F7B6B]">Loading workspace…</p>
        </div>
      )}

      {/* EMPTY */}
      {!isBooting && !hasDocuments && (
        <div className="relative min-h-0 flex-1 overflow-y-auto">
          {/* Ambient backdrop — subtle, not flashy */}
          <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
            <div className="absolute left-1/2 top-[28%] h-[28rem] w-[28rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#87AB72]/15 blur-[90px] animate-ambient-drift" />
            <div className="absolute left-[18%] top-[62%] h-56 w-56 rounded-full bg-[#4A5D23]/[0.07] blur-[70px] animate-ambient-drift-slow" />
          </div>

          <div className="relative flex min-h-full items-center justify-center py-8 sm:py-12">
            <div className="w-full max-w-lg text-center">
              <div
                className="mx-auto animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500"
                style={{ animationDelay: "0ms" }}
              >
                <span className="mx-auto flex h-11 w-11 items-center overflow-hidden rounded-xl border border-[#EBEFEA]/80 bg-white/90 px-1.5 shadow-[0_1px_2px_rgba(28,36,31,0.05)] backdrop-blur-sm">
                  <Logo className="w-[130px] shrink-0 [&>svg]:h-auto [&>svg]:w-full" />
                </span>
              </div>

              <div
                className="mt-5 animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500"
                style={{ animationDelay: "60ms" }}
              >
                <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-[#1C241F] sm:text-[30px]">
                  Upload a PDF to begin
                </h1>
                <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-[#6F7B6B]">
                  DocuSage indexes your documents so you can ask questions with cited answers.
                </p>
              </div>

              <div
                className="mt-7 animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500"
                style={{ animationDelay: "120ms" }}
              >
                <div className="rounded-2xl border border-[#EBEFEA]/90 bg-white/90 p-2 shadow-[0_8px_30px_rgba(28,36,31,0.04)] backdrop-blur-sm sm:p-3">
                  <DocumentUploader />
                </div>
                <p className="mt-3 text-[12px] text-[#98A395]">
                  Answers link back to the exact page used
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PROCESSING */}
      {!isBooting && hasDocuments && !hasReady && (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center animate-in fade-in duration-300">
          <div className="w-full max-w-md rounded-2xl border border-[#EBEFEA] bg-white p-7 text-center shadow-[0_1px_2px_rgba(28,36,31,0.04)]">
            <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-[#F6F7F4] text-[#4A5D23]">
              <Loader2 className="h-4 w-4 animate-spin" />
            </span>

            <h2 className="mt-4 text-[16px] font-semibold tracking-[-0.01em] text-[#1C241F]">
              Preparing your knowledge base
            </h2>

            <p className="mt-1.5 text-[13px] leading-relaxed text-[#6F7B6B]">
              {processingDocs.length === 1
                ? leadProcessing?.name
                  ? `Working on “${leadProcessing.name}”`
                  : "Working on your document"
                : `${processingDocs.length} documents in progress`}
            </p>

            <div className="mx-auto mt-5 h-1 w-40 overflow-hidden rounded-full bg-[#EFF1EC]">
              <div className="h-full w-1/2 rounded-full bg-[#87AB72] animate-progress-slide" />
            </div>

            <ol className="mx-auto mt-6 max-w-xs space-y-2 text-left">
              {PREP_STAGES.map((label, index) => {
                const done = index < leadStageIndex || leadStageLabel === "Ready";
                const current = index === leadStageIndex && leadStageLabel !== "Ready";

                return (
                  <li
                    key={label}
                    className={`flex items-center gap-2.5 text-[13px] ${
                      current
                        ? "font-medium text-[#1C241F]"
                        : done
                          ? "text-[#5B6858]"
                          : "text-[#98A395]"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                        current
                          ? "bg-[#4A5D23] animate-pulse"
                          : done
                            ? "bg-[#87AB72]"
                            : "bg-[#D5DBD3]"
                      }`}
                    />
                    {label}
                  </li>
                );
              })}
            </ol>

            <p className="mt-5 text-[12px] text-[#98A395]">
              Per-file progress is in the sidebar
            </p>
          </div>
        </div>
      )}

      {/* READY */}
      {!isBooting && hasDocuments && hasReady && (
        <div className="flex min-h-0 flex-1 flex-col animate-in fade-in duration-300">
          <ChatContainer />
        </div>
      )}

    </AppLayout>
  );
}
