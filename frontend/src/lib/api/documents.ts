import { Document, DocumentEvidenceSummary, DocumentStatus } from '@/types';
import { API_CONFIG, apiFetch, apiJson, delay } from './client';

interface ApiDocument {
  document_id: string;
  filename: string;
  upload_time: string;
  status: DocumentStatus;
  total_pages?: number;
  total_chunks?: number;
  index_error?: string | null;
  index_updated_at?: string | null;
}

interface UploadApiResponse {
  document_id: string;
  status: DocumentStatus;
}

function mapApiDocumentToDocument(doc: ApiDocument): Document {
  return {
    id: doc.document_id,
    name: doc.filename,
    size: 0,
    status: doc.status,
    uploadedAt: new Date(doc.upload_time),
    totalPages: doc.total_pages,
    totalChunks: doc.total_chunks,
    indexUpdatedAt: doc.index_updated_at || undefined,
    error:
      doc.status === 'failed' && doc.index_error
        ? doc.index_error
        : undefined,
  };
}

export const documentsApi = {
  /** POST /upload */
  async uploadDocument(file: File): Promise<Document> {
    if (API_CONFIG.useMock) {
      await delay(400);
      return {
        id: `doc-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        name: file.name,
        size: file.size,
        status: 'uploaded',
        uploadedAt: new Date(),
      };
    }

    const formData = new FormData();
    formData.append('file', file);

    const data = await apiJson<UploadApiResponse>('/upload', {
      method: 'POST',
      body: formData,
      errorMessage: 'Upload failed. Please try again',
    });

    return {
      id: data.document_id,
      name: file.name,
      size: file.size,
      status: data.status,
      uploadedAt: new Date(),
    };
  },

  /** GET /documents */
  async getDocuments(): Promise<Document[]> {
    if (API_CONFIG.useMock) {
      return [];
    }

    const data = await apiJson<ApiDocument[]>('/documents', {
      errorMessage: 'Could not load your documents',
    });
    return data.map(mapApiDocumentToDocument);
  },

  /** GET /documents/{document_id} */
  async getDocument(id: string): Promise<Document> {
    if (API_CONFIG.useMock) {
      await delay(100);
      return {
        id,
        name: 'Mock Document',
        size: 0,
        status: 'ready',
        uploadedAt: new Date(),
      };
    }

    const data = await apiJson<ApiDocument>(
      `/documents/${encodeURIComponent(id)}`,
      { errorMessage: 'Could not read processing status' }
    );
    return mapApiDocumentToDocument(data);
  },

  /** DELETE /documents/{document_id} */
  async deleteDocument(id: string): Promise<{ success: boolean; id: string }> {
    if (API_CONFIG.useMock) {
      await delay(300);
      return { success: true, id };
    }

    await apiFetch(`/documents/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      errorMessage: 'Could not delete the document',
    });

    return { success: true, id };
  },

  /**
   * Original PDF for page-accurate preview.
   * GET /documents/{document_id}/file
   */
  fileUrl(documentId: string, page?: number | null): string {
    const base = `${API_CONFIG.baseUrl}/documents/${encodeURIComponent(documentId)}/file`;

    if (typeof page === 'number' && Number.isFinite(page) && page >= 1) {
      return `${base}#page=${Math.floor(page)}`;
    }

    return base;
  },

  /** GET /documents/{document_id}/evidence-summary */
  async getEvidenceSummary(documentId: string): Promise<DocumentEvidenceSummary> {
    if (API_CONFIG.useMock) {
      return {
        document_id: documentId,
        chunk_evidence_count: 0,
        highlighted_chunk_count: 0,
        has_evidence_data: false,
        highlight_ratio: 0,
      };
    }

    return apiJson<DocumentEvidenceSummary>(
      `/documents/${encodeURIComponent(documentId)}/evidence-summary`,
      { errorMessage: 'Could not load highlight data' }
    );
  },
};
