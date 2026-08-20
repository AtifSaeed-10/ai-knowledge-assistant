export interface Citation {
  id: string;
  documentName: string;
  pageNumber: number | null;
  snippet?: string;
  relevance?: number | null;
  chunk_id?: string | null;
  documentId?: string | null;
  evidenceId?: string | null;
  displayNumber?: number | null;
  quote?: string | null;
}
