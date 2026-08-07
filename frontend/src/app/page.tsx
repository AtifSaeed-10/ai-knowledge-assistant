"use client";

import React, { useEffect } from "react";
import { FileUp, Loader2, Quote, ScanText, Search } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { useDocumentStore } from "@/store/useDocumentStore";
import { Logo } from "@/components/ui/Logo";

const CAPABILITIES = [
  {
    icon: ScanText,
    title: "Automatic indexing",
    description: "Text is prepared for search as soon as you upload.",
  },
  {
    icon: Search,
    title: "Semantic retrieval",
    description: "Ask in plain language across your whole workspace.",
  },
  {
    icon: Quote,
    title: "Traceable answers",
    description: "Every reply links back to the source page used.",
  },
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
  const processingCount = documents.filter((doc) => doc.status !== "ready").length;

  return (
    <AppLayout>

      {/* BOOT */}
      {isBooting && (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 animate-in fade-in duration-300">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-[#EBEFEA] bg-white shadow-[0_1px_2px_rgba(28,36,31,0.04)]">
            <Loader2 className="h-5 w-5 animate-spin text-[#4A5D23]" />
          </div>
          <div className="text-center">
            <p className="text-[14px] font-medium tracking-[-0.01em] text-[#1C241F]">
              Loading workspace
            </p>
            <p className="mt-1 text-[13px] text-[#6F7B6B]">
              Checking for existing documents…
            </p>
          </div>
        </div>
      )}

      {/* EMPTY */}
      {!isBooting && !hasDocuments && (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center py-6 sm:py-10">
            <div className="w-full max-w-xl">
              <div
                className="animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500"
                style={{ animationDelay: "0ms" }}
              >
                <span className="flex h-12 w-12 items-center overflow-hidden rounded-xl border border-[#EBEFEA] bg-white px-2 shadow-[0_1px_2px_rgba(28,36,31,0.05)]">
                  <Logo className="w-[140px] shrink-0 [&>svg]:h-auto [&>svg]:w-full" />
                </span>
              </div>

              <div
                className="mt-6 animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500"
                style={{ animationDelay: "70ms" }}
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#98A395]">
                  Get started
                </p>
                <h1 className="mt-3 text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-[#1C241F] sm:text-[32px]">
                  Turn your PDFs into an answerable knowledge base
                </h1>
                <p className="mt-3 text-[15px] leading-relaxed text-[#6F7B6B]">
                  Upload a document to index it for search. Then ask questions and get
                  answers with citations back to the exact page.
                </p>
              </div>

              <div
                className="mt-7 animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500"
                style={{ animationDelay: "140ms" }}
              >
                <div className="rounded-xl border border-[#EBEFEA] bg-white p-2 shadow-[0_1px_2px_rgba(28,36,31,0.04)] sm:p-3">
                  <div className="mb-2.5 flex items-center gap-2 px-1 pt-1">
                    <FileUp className="h-3.5 w-3.5 text-[#4A5D23]" strokeWidth={1.75} />
                    <p className="text-[12px] font-medium text-[#5B6858]">
                      Step 1 · Add your first PDF
                    </p>
                  </div>
                  <DocumentUploader />
                </div>
              </div>

              <dl
                className="mt-8 grid gap-5 border-t border-[#EBEFEA] pt-7 sm:grid-cols-3 animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-500"
                style={{ animationDelay: "210ms" }}
              >
                {CAPABILITIES.map(({ icon: Icon, title, description }) => (
                  <div key={title}>
                    <Icon className="h-4 w-4 text-[#4A5D23]" strokeWidth={1.75} />
                    <dt className="mt-2.5 text-[13px] font-semibold tracking-[-0.01em] text-[#1C241F]">
                      {title}
                    </dt>
                    <dd className="mt-1 text-[13px] leading-relaxed text-[#6F7B6B]">
                      {description}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </div>
      )}

      {/* PROCESSING */}
      {!isBooting && hasDocuments && !hasReady && (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center animate-in fade-in duration-400">
          <div className="w-full max-w-md rounded-xl border border-[#EBEFEA] bg-white p-8 text-center shadow-[0_1px_2px_rgba(28,36,31,0.04)]">
            <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full border border-[#EBEFEA] bg-[#F6F7F4]">
              <Loader2 className="h-4 w-4 animate-spin text-[#4A5D23]" />
            </span>

            <h2 className="mt-4 text-[16px] font-semibold tracking-[-0.01em] text-[#1C241F]">
              Preparing your knowledge base
            </h2>

            <p className="mt-1.5 text-[14px] leading-relaxed text-[#6F7B6B]">
              {processingCount === 1
                ? "One document is being prepared for search."
                : `${processingCount} documents are being prepared for search.`}
              {" "}
              Progress is shown in the sidebar.
            </p>

            <div className="mx-auto mt-5 h-1 w-32 overflow-hidden rounded-full bg-[#EFF1EC]">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-[#87AB72]" />
            </div>
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
