"use client";

import React, { useState } from 'react';
import { FileText, Trash2, ChevronDown, Loader2, Focus } from 'lucide-react';
import { useDocumentStore } from '@/store/useDocumentStore';
import { useChatStore } from '@/store/useChatStore';
import { Document, DocumentStatus } from '@/types';
import { ProcessingTimeline, getFriendlyDocumentStatus } from './ProcessingTimeline';

interface DocumentLibraryProps {
  isCollapsed?: boolean;
}

function formatRelativeTime(date: Date): string {
  const value = date instanceof Date ? date : new Date(date);
  const diffMs = Date.now() - value.getTime();
  const minutes = Math.floor(diffMs / 60000);

  if (Number.isNaN(minutes) || minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return value.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

function StatusDot({ status }: { status: DocumentStatus }) {
  const isReady = status === 'ready';

  return (
    <span
      className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
        isReady
          ? 'bg-[#87AB72]'
          : 'bg-[#C4A35A] animate-pulse'
      }`}
      aria-hidden
    />
  );
}

export function DocumentLibrary({ isCollapsed = false }: DocumentLibraryProps) {
  const documents = useDocumentStore((state) => state.documents);
  const deleteDocument = useDocumentStore((state) => state.deleteDocument);
  const selectedDocumentId = useDocumentStore((state) => state.selectedDocumentId);
  const selectDocument = useDocumentStore((state) => state.selectDocument);
  const productMode = useChatStore((state) => state.productMode);

  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);
  const [docToDelete, setDocToDelete] = useState<Document | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedDoc(expandedDoc === id ? null : id);
  };

  const confirmDelete = () => {
    if (docToDelete) {
      deleteDocument(docToDelete.id);
      setDocToDelete(null);
    }
  };

  if (documents.length === 0) {
    if (isCollapsed) return null;

    return (
      <div className="px-4 pt-1">
        <p className="mb-3 px-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
          Documents
        </p>
        <div className="rounded-lg px-3 py-5 text-center">
          <p className="text-[13px] font-medium tracking-[-0.01em] text-[#5B6858]">
            No documents yet
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-[#98A395]">
            Use New document to add your first PDF.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={isCollapsed ? 'px-2' : 'px-3'}>
      {!isCollapsed && (
        <div className="mb-2 flex items-center justify-between px-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
            Documents
          </span>
          <span className="rounded-md bg-[#EFF1EC] px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-[#5B6858]">
            {documents.length}
          </span>
        </div>
      )}

      <ul className="space-y-0.5">
        {documents.map((doc) => {
          const isExpanded = expandedDoc === doc.id;
          const isSelected = selectedDocumentId === doc.id;
          const isReady = doc.status === 'ready';
          const friendlyStatus = getFriendlyDocumentStatus(doc.status);

          return (
            <li
              key={doc.id}
              className="group animate-in fade-in slide-in-from-left-1 duration-300"
            >
              <div
                className={`flex items-center rounded-lg transition-colors duration-150 ${
                  isCollapsed
                    ? 'justify-center p-2'
                    : 'justify-between gap-1 px-2 py-2'
                } ${
                  isSelected
                    ? 'bg-white ring-1 ring-[#87AB72]'
                    : isExpanded
                      ? 'bg-[#EFF1EC]'
                      : 'hover:bg-[#F1F3EF]'
                }`}
              >
                <div
                  className={`flex min-w-0 items-center gap-2.5 cursor-pointer ${
                    isCollapsed ? 'justify-center' : 'flex-1'
                  }`}
                  onClick={() => {
                    if (isCollapsed) {
                      selectDocument(doc.id);
                      return;
                    }
                    selectDocument(doc.id);
                  }}
                  title={
                    isReady
                      ? `Use ${doc.name} as the focused document`
                      : doc.name
                  }
                >
                  <div
                    className={`relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                      isReady
                        ? 'border-[#EBEFEA] bg-white text-[#4A5D23]'
                        : 'border-[#EBEFEA] bg-white text-[#98A395]'
                    }`}
                  >
                    {isReady ? (
                      <FileText className="h-3.5 w-3.5" strokeWidth={1.75} />
                    ) : (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-[#4A5D23]" strokeWidth={1.75} />
                    )}
                    {isCollapsed && (
                      <span className="absolute -right-0.5 -top-0.5 flex h-2.5 w-2.5 items-center justify-center rounded-full border-2 border-[#FBFBFA] bg-[#FBFBFA]">
                        <StatusDot status={doc.status} />
                      </span>
                    )}
                  </div>

                  {!isCollapsed && (
                    <div className="min-w-0 flex-1">
                      <h4
                        className={`truncate text-[13px] font-medium tracking-[-0.01em] ${
                          isReady ? 'text-[#1C241F]' : 'text-[#5B6858]'
                        }`}
                      >
                        {doc.name}
                      </h4>
                      <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-[#98A395]">
                        <StatusDot status={doc.status} />
                        <span className={isReady ? 'text-[#5B6858]' : 'text-[#8A7350]'}>
                          {friendlyStatus}
                        </span>
                        {isSelected && (
                          <>
                            <span className="text-[#D5DBD3]">·</span>
                            <span className="inline-flex items-center gap-0.5 font-medium text-[#4A5D23]">
                              <Focus className="h-3 w-3" />
                              {productMode === 'super_focused' ? 'Focused' : 'Selected'}
                            </span>
                          </>
                        )}
                        <span className="text-[#D5DBD3]">·</span>
                        <span>{formatRelativeTime(doc.uploadedAt)}</span>
                      </div>
                    </div>
                  )}
                </div>

                {!isCollapsed && (
                  <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity duration-150 group-hover:opacity-100 focus-within:opacity-100">
                    <button
                      onClick={() => toggleExpand(doc.id)}
                      className="rounded-md p-1.5 text-[#98A395] transition-colors hover:bg-white hover:text-[#1C241F]"
                      aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
                      title={isExpanded ? 'Collapse' : 'Details'}
                    >
                      <ChevronDown
                        className={`h-3.5 w-3.5 transition-transform duration-200 ${
                          isExpanded ? 'rotate-180' : ''
                        }`}
                      />
                    </button>
                    <button
                      onClick={() => setDocToDelete(doc)}
                      className="rounded-md p-1.5 text-[#98A395] transition-colors hover:bg-red-50 hover:text-red-600"
                      title="Delete document"
                      aria-label={`Delete ${doc.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>

              {!isCollapsed && isExpanded && (
                <div className="mx-2 mb-1.5 overflow-hidden rounded-lg border border-[#EBEFEA] bg-white px-3 py-2.5 animate-in fade-in slide-in-from-top-1 duration-200">
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
                    Progress
                  </p>
                  <ProcessingTimeline status={doc.status} />
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {/* Delete Confirmation Dialog */}
      {docToDelete && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-[#1C241F]/40 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-sm rounded-xl border border-[#EBEFEA] bg-white p-5 shadow-2xl animate-in zoom-in-95 duration-200">
            <h3 className="text-[15px] font-semibold tracking-[-0.01em] text-[#1C241F]">
              Delete document
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[#6F7B6B]">
              Remove{' '}
              <span className="font-medium text-[#1C241F]">
                &quot;{docToDelete.name}&quot;
              </span>
              {' '}from your workspace? It will no longer be searchable, and this cannot be undone.
            </p>
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={() => setDocToDelete(null)}
                className="rounded-lg px-3.5 py-2 text-[13px] font-medium text-[#5B6858] transition-colors hover:bg-[#F1F3EF]"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="rounded-lg bg-red-600 px-3.5 py-2 text-[13px] font-medium text-white shadow-sm transition-colors hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
