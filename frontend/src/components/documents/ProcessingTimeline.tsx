import React from 'react';
import { AlertTriangle, CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { DocumentStatus } from '@/types';
import { cn } from '@/lib/cn';

interface ProcessingTimelineProps {
  status: DocumentStatus;
}

const STAGES = [
  {
    id: 'preparing',
    label: 'Preparing document',
    detail: 'Scanned books can take several minutes to read',
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

export const PREP_STAGE_LABELS = STAGES.slice(0, 3).map((stage) => stage.label);

function getStageIndex(status: DocumentStatus): number {
  const index = STAGES.findIndex((stage) => stage.statuses.includes(status));
  return index === -1 ? 0 : index;
}

export function getFriendlyDocumentStatus(status: DocumentStatus): string {
  if (status === 'ready') return 'Ready';
  if (status === 'failed') return 'Processing failed';
  return STAGES[getStageIndex(status)]?.label ?? 'Preparing document';
}

export function ProcessingTimeline({ status }: ProcessingTimelineProps) {
  if (status === 'failed') {
    return (
      <div className="flex items-start gap-2.5 py-1">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" strokeWidth={2} />
        <p className="text-ui leading-relaxed text-ink-muted">
          Processing stopped before this document became searchable.
        </p>
      </div>
    );
  }

  const currentIndex = getStageIndex(status);
  const isReady = status === 'ready';
  const progress = isReady
    ? 100
    : Math.round(((currentIndex + 0.45) / (STAGES.length - 1)) * 100);

  return (
    <div className="space-y-3 py-1">
      <div
        className="h-1 overflow-hidden rounded-full bg-olive-soft"
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Processing progress"
      >
        <div
          className="h-full rounded-full bg-sage transition-[width] duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <ol className="space-y-2.5">
        {STAGES.map((stage, index) => {
          const isCompleted = index < currentIndex || isReady;
          const isCurrent = index === currentIndex && !isReady;

          return (
            <li
              key={stage.id}
              className={cn(
                'flex items-start gap-2.5',
                !isCompleted && !isCurrent && 'opacity-50'
              )}
            >
              <span className="mt-0.5 shrink-0">
                {isCompleted ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-sage" strokeWidth={2} />
                ) : isCurrent ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-olive" strokeWidth={2} />
                ) : (
                  <Circle className="h-3.5 w-3.5 text-line-strong" strokeWidth={2} />
                )}
              </span>

              <span className="min-w-0">
                <span
                  className={cn(
                    'block text-ui tracking-[-0.01em]',
                    isCurrent
                      ? 'font-medium text-ink'
                      : isCompleted
                        ? 'font-medium text-ink-muted'
                        : 'text-ink-subtle'
                  )}
                >
                  {stage.label}
                </span>
                {isCurrent && (
                  <span className="mt-0.5 block text-meta text-ink-muted">{stage.detail}</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
