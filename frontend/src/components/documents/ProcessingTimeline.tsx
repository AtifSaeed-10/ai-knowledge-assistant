import React from 'react';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { DocumentStatus } from '@/types';

interface ProcessingTimelineProps {
  status: DocumentStatus;
}

const STEPS = [
  { id: 'uploaded', label: 'Uploaded' },
  { id: 'extracting', label: 'Extracting text' },
  { id: 'chunking', label: 'Splitting chunks' },
  { id: 'embedding', label: 'Creating embeddings' },
  { id: 'indexing', label: 'Building search index' },
  { id: 'ready', label: 'Ready' }
];

export function ProcessingTimeline({ status }: ProcessingTimelineProps) {
  const currentStepIndex = STEPS.findIndex(s => s.id === status);
  const safeIndex = currentStepIndex === -1 ? 0 : currentStepIndex;

  return (
    <div className="py-2 space-y-3">
      {STEPS.map((step, index) => {
        const isCompleted = index < safeIndex || status === 'ready';
        const isCurrent = index === safeIndex && status !== 'ready';
        const isPending = index > safeIndex && status !== 'ready';

        return (
          <div key={step.id} className="flex items-center gap-3">
            {isCompleted && <CheckCircle2 className="w-4 h-4 text-green-500" />}
            {isCurrent && <Loader2 className="w-4 h-4 text-[#4A5D23] animate-spin" />}
            {isPending && <Circle className="w-4 h-4 text-gray-300" />}
            
            <span className={`text-sm ${
              isCurrent ? 'text-gray-900 font-medium' : 
              isCompleted ? 'text-gray-600' : 'text-gray-400'
            }`}>
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}