export type DocumentStatus =
  | 'uploaded'
  | 'extracting'
  | 'chunking'
  | 'embedding'
  | 'indexing'
  | 'ready';

export interface Document {
  id: string;
  name: string;
  size: number;
  status: DocumentStatus;
  uploadedAt: Date;
  totalPages?: number;
  totalChunks?: number;
}
