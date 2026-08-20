export interface EvidenceRegion {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  coord_space: string;
}

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
  quotes?: string[];
  quoteMappingStatus?: string | null;
  quoteHighlightAvailable?: boolean;
  quoteRegions?: EvidenceRegion[];
}
