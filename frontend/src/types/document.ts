export type DocumentStatus =
  | 'uploaded'
  | 'extracting'
  | 'chunking'
  | 'embedding'
  | 'indexing'
  | 'ready'
  /** Client-side terminal state: processing failed or stopped responding. */
  | 'failed';

export interface DocumentEvidenceSummary {
  document_id: string;
  chunk_evidence_count: number;
  highlighted_chunk_count: number;
  has_evidence_data: boolean;
  highlight_ratio: number;
}

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
  evidenceSummary?: DocumentEvidenceSummary;
}
