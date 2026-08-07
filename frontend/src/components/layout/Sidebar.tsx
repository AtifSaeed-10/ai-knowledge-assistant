"use client";
import React, { useState, useEffect, useCallback } from 'react';
import { X, PanelLeftClose, PanelLeft, Plus, FileText, CheckCircle2 } from 'lucide-react';
import { Logo } from '@/components/ui/Logo';
import { DocumentLibrary } from '@/components/documents/DocumentLibrary';
import { DocumentUploader } from '@/components/documents/DocumentUploader';
import { useDocumentStore } from '@/store/useDocumentStore';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const documents = useDocumentStore((state) => state.documents);

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [width, setWidth] = useState(300);
  const [isResizing, setIsResizing] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  // Restore states
  useEffect(() => {
    const storedWidth = sessionStorage.getItem('docusage_sidebar_width');
    const storedCollapsed = sessionStorage.getItem('docusage_sidebar_collapsed');
    if (storedWidth) setWidth(Number(storedWidth));
    if (storedCollapsed) setIsCollapsed(storedCollapsed === 'true');
  }, []);

  const handleCollapseToggle = () => {
    const newState = !isCollapsed;
    setIsCollapsed(newState);
    sessionStorage.setItem('docusage_sidebar_collapsed', String(newState));
  };

  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      let newWidth = e.clientX;
      if (newWidth < 240) newWidth = 240;
      if (newWidth > 380) newWidth = 380;

      setWidth(newWidth);
      sessionStorage.setItem('docusage_sidebar_width', String(newWidth));

      if (isCollapsed && newWidth > 240) {
        setIsCollapsed(false);
        sessionStorage.setItem('docusage_sidebar_collapsed', 'false');
      }
    };
    const handleMouseUp = () => setIsResizing(false);

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, isCollapsed]);

  // Close upload modal dynamically when upload begins
  const prevDocsLength = React.useRef(documents.length);
  useEffect(() => {
    if (isUploadModalOpen && documents.length > prevDocsLength.current) {
      setIsUploadModalOpen(false);
    }
    prevDocsLength.current = documents.length;
  }, [documents.length, isUploadModalOpen]);

  const currentWidth = isCollapsed ? 80 : width;
  const readyCount = documents.filter((doc) => doc.status === 'ready').length;

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-[#1C241F]/25 backdrop-blur-[2px] lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        style={{ width: isOpen ? 280 : currentWidth }} // Mobile is fixed, desktop is dynamic
        className={`fixed left-0 top-0 z-40 flex h-full flex-col border-r border-[#EBEFEA] bg-[#FBFBFA] transition-all duration-300 ease-out lg:relative ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        } ${isResizing ? 'cursor-col-resize select-none transition-none' : ''}`}
      >
        {/* Brand header */}
        <div
          className={`flex h-16 shrink-0 items-center gap-2 border-b border-[#EBEFEA] px-3 ${
            isCollapsed ? 'justify-center' : 'justify-between'
          }`}
        >
          {isCollapsed ? (
            <span
              className="flex h-8 w-8 items-center overflow-hidden"
              aria-label="DocuSage"
            >
              <Logo className="w-[128px] shrink-0 [&>svg]:h-auto [&>svg]:w-full" />
            </span>
          ) : (
            <Logo className="w-[126px] shrink-0 pl-1 [&>svg]:h-auto [&>svg]:w-full" />
          )}

          {!isCollapsed && (
            <button
              onClick={handleCollapseToggle}
              className="hidden shrink-0 rounded-md p-1.5 text-[#98A395] transition-colors hover:bg-[#EFF1EC] hover:text-[#4A5D23] lg:flex"
              title="Collapse sidebar"
            >
              <PanelLeftClose size={18} />
            </button>
          )}

          <button
            onClick={onClose}
            className="shrink-0 rounded-md p-1.5 text-[#98A395] transition-colors hover:bg-[#EFF1EC] hover:text-[#1C241F] lg:hidden"
            aria-label="Close sidebar"
          >
            <X size={18} />
          </button>
        </div>

        {/* Primary action */}
        <div className="shrink-0 space-y-1.5 px-3 py-3">
          {isCollapsed && (
            <button
              onClick={handleCollapseToggle}
              className="hidden h-9 w-full items-center justify-center rounded-lg text-[#6F7B6B] transition-colors hover:bg-[#EFF1EC] hover:text-[#4A5D23] lg:flex"
              title="Expand sidebar"
            >
              <PanelLeft size={18} />
            </button>
          )}

          <button
            onClick={() => setIsUploadModalOpen(true)}
            title="Upload PDF"
            className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-[#4A5D23] text-white shadow-sm transition-colors hover:bg-[#3E4E1D]"
          >
            <Plus size={16} strokeWidth={2.5} />
            {!isCollapsed && (
              <span className="text-[13px] font-medium tracking-[-0.01em]">
                New document
              </span>
            )}
          </button>
        </div>

        {/* Document library */}
        <div className="flex-1 overflow-y-auto pb-4">
          <DocumentLibrary isCollapsed={isCollapsed} />
        </div>

        {/* Workspace summary */}
        {!isCollapsed && documents.length > 0 && (
          <div className="shrink-0 border-t border-[#EBEFEA] px-4 py-3.5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
              Workspace
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#5B6858]">
              <span className="inline-flex items-center gap-1.5">
                <FileText size={13} className="text-[#98A395]" />
                {documents.length} {documents.length === 1 ? 'document' : 'documents'}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 size={13} className="text-[#87AB72]" />
                {readyCount} ready
              </span>
            </div>
          </div>
        )}

        {/* Resizer Edge Handler */}
        {!isCollapsed && (
          <div
            onMouseDown={startResizing}
            className="group absolute bottom-0 right-0 top-0 z-50 hidden w-1.5 cursor-col-resize lg:block"
          >
            <div className="ml-auto h-full w-px bg-transparent transition-colors group-hover:bg-[#87AB72] group-active:bg-[#4A5D23]" />
          </div>
        )}
      </aside>

      {/* Upload Modal Overlay */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#1C241F]/40 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative flex w-full max-w-xl flex-col overflow-hidden rounded-xl border border-[#EBEFEA] bg-white shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex items-start justify-between gap-4 border-b border-[#EBEFEA] px-5 py-4">
              <div>
                <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-[#1C241F]">
                  Upload documents
                </h2>
                <p className="mt-0.5 text-xs text-[#6F7B6B]">
                  PDFs are extracted, chunked and indexed automatically.
                </p>
              </div>
              <button
                onClick={() => setIsUploadModalOpen(false)}
                className="shrink-0 rounded-md p-1.5 text-[#98A395] transition-colors hover:bg-[#F1F3EF] hover:text-[#1C241F]"
                aria-label="Close upload dialog"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-5">
              <DocumentUploader />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
