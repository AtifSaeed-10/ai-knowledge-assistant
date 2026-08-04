import React from 'react';
import { Citation } from '@/types';
import { CitationCard } from './CitationCard';

export const SourceList = ({ citations }: { citations?: Citation[] }) => {
  if (!citations || citations.length === 0) return null;

  const topCitations = citations.slice(0, 3);
  const remainingCount = citations.length - 3;

  return (
    <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-2 items-center">
      <span className="text-xs text-gray-400 font-medium mr-1 uppercase tracking-wider">Sources</span>
      {topCitations.map((cit) => (
        <CitationCard key={cit.id} citation={cit} />
      ))}
      {remainingCount > 0 && (
        <span className="text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded-md border border-gray-100">
          +{remainingCount} more
        </span>
      )}
    </div>
  );
};