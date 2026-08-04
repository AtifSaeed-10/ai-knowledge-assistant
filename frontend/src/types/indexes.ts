export interface Citation {
  id: string; // mapped from chunk_id
  documentName: string; // mapped from filename
  pageNumber: number; // mapped from page
  snippet?: string;
  relevance?: number;
  chunk_id?: string;
}