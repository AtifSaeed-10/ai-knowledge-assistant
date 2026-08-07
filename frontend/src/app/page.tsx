"use client";

import React, { useEffect } from "react";
import { Loader2, Quote, ScanText, Search } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { useDocumentStore } from "@/store/useDocumentStore";
import { Logo } from "@/components/ui/Logo";

const CAPABILITIES = [
  {
    icon: ScanText,
    title: "Automatic indexing",
    description: "Text extraction, chunking and embeddings run the moment you upload.",
  },
  {
    icon: Search,
    title: "Semantic retrieval",
    description: "Ask in plain language and search across everything in your workspace.",
  },
  {
    icon: Quote,
    title: "Traceable answers",
    description: "Every response links back to the source document and page.",
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

  return (
    <AppLayout>

      {/* BOOT: loading existing documents */}
      {isBooting && (
        <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-[#4A5D23]" />
          <p className="text-sm text-[#6F7B6B]">Loading your workspace</p>
        </div>
      )}

      {/* STATE 1: EMPTY */}
      {!isBooting && !hasDocuments && (
        <div className="flex h-full min-h-[60vh] items-center justify-center py-6">
          <div className="w-full max-w-xl">

            <div
              className="animate-in fade-in slide-in-from-bottom-2 fill-mode-backwards duration-500"
              style={{ animationDelay: "0ms" }}
            >
              <span className="flex h-12 w-12 items-center overflow-hidden rounded-xl border border-[#EBEFEA] bg-white px-2 shadow-[0_1px_2px_rgba(28,36,31,0.05)]">
                <Logo className="w-[140px] shrink-0 [&>svg]:h-auto [&>svg]:w-full" />
              </span>
            </div>

            <div
              className="mt-6 animate-in fade-in slide-in-from-bottom-2 fill-mode-backwards duration-500"
              style={{ animationDelay: "80ms" }}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#98A395]">
                Get started
              </p>
              <h1 className="mt-3 text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-[#1C241F] sm:text-[32px]">
                Turn your PDFs into an answerable knowledge base
              </h1>
              <p className="mt-3 text-[15px] leading-relaxed text-[#6F7B6B]">
                Upload a document and DocuSage indexes it for retrieval, then answers your
                questions with citations back to the exact page.
              </p>
            </div>

            <div
              className="mt-7 animate-in fade-in slide-in-from-bottom-2 fill-mode-backwards duration-500"
              style={{ animationDelay: "160ms" }}
            >
              <div className="rounded-xl border border-[#EBEFEA] bg-white p-2 shadow-[0_1px_2px_rgba(28,36,31,0.04)] sm:p-3">
                <DocumentUploader />
              </div>
            </div>

            <dl
              className="mt-8 grid gap-6 border-t border-[#EBEFEA] pt-7 sm:grid-cols-3 animate-in fade-in slide-in-from-bottom-2 fill-mode-backwards duration-500"
              style={{ animationDelay: "240ms" }}
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
      )}

      {/* STATE 2: PROCESSING */}
      {!isBooting && hasDocuments && !hasReady && (
        <div className="flex h-full min-h-[60vh] items-center justify-center">
          <div className="w-full max-w-md rounded-xl border border-[#EBEFEA] bg-white p-8 text-center shadow-[0_1px_2px_rgba(28,36,31,0.04)] animate-in fade-in duration-500">
            <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-[#EBEFEA] bg-[#F6F7F4]">
              <Loader2 className="h-4 w-4 animate-spin text-[#4A5D23]" />
            </span>

            <h2 className="mt-4 text-base font-semibold tracking-[-0.01em] text-[#1C241F]">
              Processing your documents
            </h2>

            <p className="mt-1.5 text-sm leading-relaxed text-[#6F7B6B]">
              Extraction and indexing are running. Per-file progress is shown in the sidebar.
            </p>
          </div>
        </div>
      )}

      {/* STATE 3: READY */}
      {!isBooting && hasDocuments && hasReady && (
        <div
          className="
            h-full
            w-full
            animate-in
            fade-in
            duration-300
          "
        >
          <ChatContainer />
        </div>
      )}

    </AppLayout>
  );
}
