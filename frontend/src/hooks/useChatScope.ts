"use client";

import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import type { Document } from "@/types";
import type { ProductMode } from "@/types/mode";

export interface ChatScope {
  mode: ProductMode;
  documents: Document[];
  readyDocuments: Document[];
  processingCount: number;
  failedCount: number;
  selectedDocument: Document | null;
  /** True when a question can actually be answered right now. */
  canAsk: boolean;
  /** Why asking is blocked, in plain language. Null when ready. */
  blockedReason: string | null;
  /** Short, always-visible description of what will be searched. */
  scopeLabel: string;
}

/**
 * Single source of truth for "what will this question search?".
 * The composer and the scope bar both read it so they can never disagree.
 */
export function useChatScope(): ChatScope {
  const mode = useChatStore((state) => state.productMode);
  const documents = useDocumentStore((state) => state.documents);
  const selectedDocumentId = useDocumentStore((state) => state.selectedDocumentId);

  const readyDocuments = documents.filter((doc) => doc.status === "ready");
  const processingCount = documents.filter(
    (doc) => doc.status !== "ready" && doc.status !== "failed"
  ).length;
  const failedCount = documents.filter((doc) => doc.status === "failed").length;

  const selectedDocument =
    documents.find((doc) => doc.id === selectedDocumentId) || null;
  const selectedIsReady = selectedDocument?.status === "ready";

  const focusedReady = mode === "super_focused" ? selectedIsReady : true;
  const canAsk = readyDocuments.length > 0 && focusedReady;

  let blockedReason: string | null = null;
  if (readyDocuments.length === 0) {
    blockedReason =
      processingCount > 0
        ? "Your documents are still being prepared."
        : "Add a PDF to start asking questions.";
  } else if (!focusedReady) {
    blockedReason = "Pick a ready document in the sidebar, or search all documents.";
  }

  const scopeLabel =
    mode === "super_focused"
      ? selectedIsReady
        ? selectedDocument!.name
        : "No document selected"
      : `All documents (${readyDocuments.length})`;

  return {
    mode,
    documents,
    readyDocuments,
    processingCount,
    failedCount,
    selectedDocument,
    canAsk,
    blockedReason,
    scopeLabel,
  };
}
