import React from 'react';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { DocumentStatus } from '@/types';

interface ProcessingTimelineProps {
  status: DocumentStatus;
}

const STAGES = [
  {
    id: 'preparing',
    label: 'Preparing document',
    detail: 'Opening and extracting text',
    statuses: ['uploaded', 'extracting'] as DocumentStatus[],
  },
  {
    id: 'analyzing',
    label: 'Analyzing content',
    detail: 'Understanding structure and meaning',
    statuses: ['chunking', 'embedding'] as DocumentStatus[],
  },
  {
    id: 'searchable',
    label: 'Making searchable',
    detail: 'Building retrieval index',
    statuses: ['indexing'] as DocumentStatus[],
  },
  {
    id: 'ready',
    label: 'Ready',
    detail: 'Available for research',
    statuses: ['ready'] as DocumentStatus[],
  },
];

function getStageIndex(status: DocumentStatus): number {
  const index = STAGES.findIndex((stage) => stage.statuses.includes(status));
  return index === -1 ? 0 : index;
}

export function getFriendlyDocumentStatus(status: DocumentStatus): string {
  if (status === 'ready') return 'Ready';
  return STAGES[getStageIndex(status)]?.label ?? 'Preparing document';
}

export function ProcessingTimeline({ status }: ProcessingTimelineProps) {
  const currentIndex = getStageIndex(status);
  const isReady = status === 'ready';
  const progress = isReady
    ? 100
    : Math.round(((currentIndex + 0.45) / (STAGES.length - 1)) * 100);

  return (
    <div className="space-y-3 py-1">
      <div className="h-1 overflow-hidden rounded-full bg-[#EFF1EC]">
        <div
          className="h-full rounded-full bg-[#87AB72] transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="space-y-2.5">
        {STAGES.map((stage, index) => {
          const isCompleted = index < currentIndex || isReady;
          const isCurrent = index === currentIndex && !isReady;
          const isPending = index > currentIndex && !isReady;

          return (
            <div
              key={stage.id}
              className={`flex items-start gap-2.5 transition-opacity duration-300 ${
                isPending ? 'opacity-40' : 'opacity-100'
              }`}
            >
              <span className="mt-0.5 shrink-0">
                {isCompleted && (
                  <CheckCircle2 className="h-3.5 w-3.5 text-[#87AB72]" strokeWidth={2} />
                )}
                {isCurrent && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#4A5D23]" strokeWidth={2} />
                )}
                {isPending && (
                  <Circle className="h-3.5 w-3.5 text-[#D5DBD3]" strokeWidth={2} />
                )}
              </span>

              <span className="min-w-0">
                <span
                  className={`block text-[13px] tracking-[-0.01em] ${
                    isCurrent
                      ? 'font-medium text-[#1C241F]'
                      : isCompleted
                        ? 'font-medium text-[#5B6858]'
                        : 'text-[#98A395]'
                  }`}
                >
                  {stage.label}
                </span>
                {isCurrent && (
                  <span className="mt-0.5 block text-[11px] text-[#6F7B6B]">
                    {stage.detail}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
