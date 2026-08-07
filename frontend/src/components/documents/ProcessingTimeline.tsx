import React from 'react';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { DocumentStatus } from '@/types';

interface ProcessingTimelineProps {
  status: DocumentStatus;
}

/**
 * Maps raw backend pipeline statuses onto user-facing stages.
 * Backend values are never shown in the UI.
 */
const STAGES = [
  {
    id: 'preparing',
    label: 'Preparing document',
    statuses: ['uploaded', 'extracting'] as DocumentStatus[],
  },
  {
    id: 'analyzing',
    label: 'Analyzing content',
    statuses: ['chunking', 'embedding'] as DocumentStatus[],
  },
  {
    id: 'searchable',
    label: 'Making searchable',
    statuses: ['indexing'] as DocumentStatus[],
  },
  {
    id: 'ready',
    label: 'Ready',
    statuses: ['ready'] as DocumentStatus[],
  },
];

function getStageIndex(status: DocumentStatus): number {
  const index = STAGES.findIndex((stage) => stage.statuses.includes(status));
  return index === -1 ? 0 : index;
}

/** Shared helper for list rows / badges outside this component. */
export function getFriendlyDocumentStatus(status: DocumentStatus): string {
  if (status === 'ready') return 'Ready';
  return STAGES[getStageIndex(status)]?.label ?? 'Preparing document';
}

export function ProcessingTimeline({ status }: ProcessingTimelineProps) {
  const currentIndex = getStageIndex(status);
  const isReady = status === 'ready';

  return (
    <div className="space-y-2.5 py-1">
      {STAGES.map((stage, index) => {
        const isCompleted = index < currentIndex || isReady;
        const isCurrent = index === currentIndex && !isReady;
        const isPending = index > currentIndex && !isReady;

        return (
          <div
            key={stage.id}
            className={`flex items-center gap-2.5 transition-opacity duration-300 ${
              isPending ? 'opacity-45' : 'opacity-100'
            }`}
          >
            {isCompleted && (
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[#87AB72]" strokeWidth={2} />
            )}
            {isCurrent && (
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-[#4A5D23]" strokeWidth={2} />
            )}
            {isPending && (
              <Circle className="h-3.5 w-3.5 shrink-0 text-[#D5DBD3]" strokeWidth={2} />
            )}

            <span
              className={`text-[13px] tracking-[-0.01em] ${
                isCurrent
                  ? 'font-medium text-[#1C241F]'
                  : isCompleted
                    ? 'font-medium text-[#5B6858]'
                    : 'text-[#98A395]'
              }`}
            >
              {stage.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
