"use client";

import React, { useCallback, useRef, useState } from "react";
import { AlertCircle, FileUp, Loader2 } from "lucide-react";
import { useDocumentStore } from "@/store/useDocumentStore";
import { useChatStore } from "@/store/useChatStore";
import { cn } from "@/lib/cn";

const MAX_FILE_BYTES = 50 * 1024 * 1024;

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function rejectionReason(file: File): string | null {
  const isPdf =
    file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

  if (!isPdf) return "Only PDF files can be indexed.";
  if (file.size === 0) return "This file is empty.";
  if (file.size > MAX_FILE_BYTES) {
    return `Too large (${formatBytes(file.size)}). The limit is 50 MB.`;
  }
  return null;
}

interface DocumentUploaderProps {
  /** Fired once every accepted file has been uploaded successfully. */
  onComplete?: () => void;
}

export const DocumentUploader = ({ onComplete }: DocumentUploaderProps = {}) => {
  const uploadDocument = useDocumentStore((state) => state.uploadDocument);
  const setActiveCitation = useChatStore((state) => state.setActiveCitation);

  const [isDragging, setIsDragging] = useState(false);
  const [rejected, setRejected] = useState<{ name: string; reason: string }[]>([]);
  const [pending, setPending] = useState<string[]>([]);

  const inputRef = useRef<HTMLInputElement>(null);
  // Nested elements fire dragleave; count enter/leave pairs instead.
  const dragDepth = useRef(0);

  const processFiles = useCallback(
    async (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;

      const files = Array.from(fileList);
      const accepted: File[] = [];
      const problems: { name: string; reason: string }[] = [];

      files.forEach((file) => {
        const reason = rejectionReason(file);
        if (reason) problems.push({ name: file.name, reason });
        else accepted.push(file);
      });

      setRejected(problems);
      if (accepted.length === 0) return;

      setActiveCitation(null);
      setPending((current) => [...current, ...accepted.map((file) => file.name)]);

      const results = await Promise.all(
        accepted.map(async (file) => {
          const ok = await uploadDocument(file);
          setPending((current) => {
            const index = current.indexOf(file.name);
            if (index === -1) return current;
            return [...current.slice(0, index), ...current.slice(index + 1)];
          });
          return ok;
        })
      );

      if (results.every(Boolean)) onComplete?.();
    },
    [uploadDocument, setActiveCitation, onComplete]
  );

  return (
    <div className="w-full">
      <input
        type="file"
        ref={inputRef}
        onChange={(event) => {
          void processFiles(event.target.files);
          event.target.value = "";
        }}
        accept="application/pdf,.pdf"
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-hidden
      />

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragEnter={(event) => {
          event.preventDefault();
          dragDepth.current += 1;
          setIsDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          event.preventDefault();
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          if (dragDepth.current === 0) setIsDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          dragDepth.current = 0;
          setIsDragging(false);
          void processFiles(event.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center rounded-xl border border-dashed px-6 py-9 text-center transition-colors",
          isDragging
            ? "border-olive bg-olive-soft"
            : "border-line-strong bg-surface hover:border-sage hover:bg-surface-muted"
        )}
      >
        <span
          className={cn(
            "mb-3 flex h-10 w-10 items-center justify-center rounded-full transition-colors",
            isDragging ? "bg-olive text-white" : "bg-olive-soft text-olive"
          )}
        >
          <FileUp size={18} strokeWidth={1.75} />
        </span>

        <span className="text-body font-semibold tracking-[-0.01em] text-ink">
          {isDragging ? "Drop to upload" : "Drop PDFs here, or browse"}
        </span>
        <span className="mt-1 text-meta text-ink-muted">
          PDF only · up to 50 MB each · multiple files supported
        </span>
      </button>

      {pending.length > 0 && (
        <ul className="mt-3 space-y-1.5" aria-live="polite">
          {pending.map((name) => (
            <li
              key={name}
              className="flex items-center gap-2 rounded-lg border border-line bg-surface-muted px-3 py-2 text-meta text-ink-muted"
            >
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-olive" />
              <span className="min-w-0 flex-1 truncate" title={name}>
                Uploading {name}
              </span>
            </li>
          ))}
        </ul>
      )}

      {rejected.length > 0 && (
        <div className="mt-3 rounded-lg border border-danger-line bg-danger-soft px-3 py-2.5" role="alert">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />
            <div className="min-w-0 flex-1">
              <p className="text-meta font-semibold text-danger">
                {rejected.length === 1 ? "1 file was not added" : `${rejected.length} files were not added`}
              </p>
              <ul className="mt-1 space-y-0.5">
                {rejected.map((item) => (
                  <li key={item.name} className="text-meta leading-relaxed text-ink-muted break-anywhere">
                    <span className="font-medium text-ink">{item.name}</span> — {item.reason}
                  </li>
                ))}
              </ul>
            </div>
            <button
              type="button"
              onClick={() => setRejected([])}
              className="shrink-0 rounded-md px-1.5 py-0.5 text-meta font-medium text-ink-muted transition-colors hover:bg-surface hover:text-ink"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
