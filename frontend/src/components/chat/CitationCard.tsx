import React from 'react';
import { Citation } from '@/types';
import { useChatStore } from '@/store/useChatStore';
import { FileText } from 'lucide-react';

export const CitationCard = ({ citation }: { citation: Citation }) => {
  const { setActiveCitation } = useChatStore();
  
  const relScore = citation.relevance 
    ? citation.relevance > 1 ? Math.round(citation.relevance) : Math.round(citation.relevance * 100)
    : null;

  return (
    <button
      data-citation-chip="true"
      onClick={() => setActiveCitation(citation)}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-[#F6F7F4] text-[#4A5D23] rounded-md hover:bg-[#e9ece4] transition-colors border border-[#d3dbc9]"
      title={citation.documentName}
    >
      <FileText size={12} className="opacity-70" />
      <span className="truncate max-w-[140px]">{citation.documentName}</span>
      <span className="opacity-50">•</span>
      <span>Pg {citation.pageNumber}</span>
      {relScore && (
        <>
          <span className="opacity-50">•</span>
          <span>{relScore}% match</span>
        </>
      )}
    </button>
  );
};