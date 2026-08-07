export interface Citation {
  id: string;
  documentName: string;
  pageNumber: number;
  snippet?: string;
  relevance?: number | null;
  chunk_id?: string | null;
  documentId?: string;
}
