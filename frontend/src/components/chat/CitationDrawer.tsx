import React, { useEffect, useRef } from 'react';
import { useChatStore } from '@/store/useChatStore';
import { X, FileText, Fingerprint, Activity } from 'lucide-react';

export const CitationDrawer = () => {
  const { activeCitation, setActiveCitation } = useChatStore();
  const isOpen = !!activeCitation;
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setActiveCitation(null);
    };

    const handleClickOutside = (e: MouseEvent) => {
      // If the click is outside the drawer element
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        // Ensure we aren't clicking a citation chip (which is meant to open the drawer)
        const target = e.target as HTMLElement;
        if (!target.closest('[data-citation-chip="true"]')) {
          setActiveCitation(null);
        }
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, setActiveCitation]);

  const relScore = activeCitation?.relevance 
    ? activeCitation.relevance > 1 ? Math.round(activeCitation.relevance) : Math.round(activeCitation.relevance * 100)
    : null;

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/20 z-40 lg:hidden transition-opacity"
          onClick={() => setActiveCitation(null)}
        />
      )}

      {/* Drawer Panel */}
      <div
        ref={drawerRef}
        className={`fixed top-0 right-0 h-full w-full sm:w-[420px] bg-white shadow-2xl border-l border-gray-200 z-50 transform transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-100 bg-[#F6F7F4]/50">
          <div className="flex items-center gap-2 text-[#4A5D23]">
            <FileText size={18} />
            <h3 className="font-semibold text-sm">Source Document</h3>
          </div>
          <button 
            onClick={() => setActiveCitation(null)}
            className="p-1.5 rounded-md hover:bg-gray-200/50 text-gray-500 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Metadata Details */}
        {activeCitation && (
          <div className="p-6 flex-1 overflow-y-auto">
            <h2 className="text-xl font-bold text-gray-900 mb-6">{activeCitation.documentName}</h2>
            
            <div className="grid grid-cols-2 gap-4 mb-8">
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
                <span className="text-xs text-gray-500 block mb-1 font-medium">Page Number</span>
                <span className="text-lg font-semibold text-gray-800">Page {activeCitation.pageNumber}</span>
              </div>
              
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1 font-medium">
                  <Activity size={12} /> Match Relevance
                </div>
                <span className="text-lg font-semibold text-gray-800">
                  {relScore ? `${relScore}%` : 'N/A'}
                </span>
              </div>
            </div>

            {/* Developer / Chunk ID hidden from main view but available */}
            <div className="flex items-center gap-2 text-xs text-gray-400 bg-gray-50 px-3 py-2 rounded border border-gray-100">
              <Fingerprint size={12} />
              <span className="truncate">Chunk: {activeCitation.chunk_id || activeCitation.id}</span>
            </div>

            {/* PDF Preview Placeholder */}
            <div className="mt-8 border-t border-gray-100 pt-6">
              <h4 className="text-sm font-semibold text-gray-900 mb-3">Document Preview</h4>
              <div className="w-full h-[300px] bg-gray-50 rounded-lg border-2 border-dashed border-gray-200 flex flex-col items-center justify-center text-gray-400 gap-2">
                <FileText size={32} className="opacity-50" />
                <span className="text-sm font-medium">PDF rendering coming soon</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
};