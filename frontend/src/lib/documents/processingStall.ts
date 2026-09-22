import type { DocumentStatus } from "@/types";

/** Digital PDFs finish in seconds. A scanned book can take many minutes. */
export const STALL_TIMEOUT_MS = 30 * 60 * 1000;

const PROCESSING_STATUSES = new Set<DocumentStatus>([
  "uploaded",
  "extracting",
  "chunking",
  "embedding",
  "indexing",
]);

export function isProcessingStatus(status: DocumentStatus | string): boolean {
  return PROCESSING_STATUSES.has(status as DocumentStatus);
}

export function activityKey(doc: {
  status?: string | null;
  totalPages?: number | null;
  totalChunks?: number | null;
  indexUpdatedAt?: string | null;
}): string {
  return [
    doc.status || "",
    String(doc.totalPages ?? ""),
    String(doc.totalChunks ?? ""),
    doc.indexUpdatedAt || "",
  ].join("|");
}

export function shouldMarkProcessingStalled(options: {
  lastChangeAt: number;
  now: number;
  serverStatus: DocumentStatus | string;
  stallMs?: number;
}): boolean {
  if (!isProcessingStatus(options.serverStatus)) return false;
  return options.now - options.lastChangeAt > (options.stallMs ?? STALL_TIMEOUT_MS);
}
