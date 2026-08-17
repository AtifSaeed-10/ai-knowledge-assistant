export type DocumentStatus =
  | 'uploaded'
  | 'extracting'
  | 'chunking'
  | 'embedding'
  | 'indexing'
  | 'ready'
  /** Client-side terminal state: processing failed or stopped responding. */
  | 'failed';

export interface Document {
  id: string;
  name: string;
  size: number;
  status: DocumentStatus;
  uploadedAt: Date;
  totalPages?: number;
  totalChunks?: number;
  /** Populated when status is 'failed'. */
  error?: string;
}
