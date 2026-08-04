import { Document, DocumentStatus } from '@/types';
import { API_CONFIG, delay } from './client';

export const documentsApi = {

  /**
   * Upload document
   * POST /upload
   */
  async uploadDocument(file: File): Promise<Document> {

    if (API_CONFIG.useMock) {

      await delay(400);

      return {
        id: `doc-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        name: file.name,
        size: file.size,
        status: 'uploaded' as DocumentStatus,
        uploadedAt: new Date(),
      };

    }


    const formData = new FormData();

    formData.append(
      'file',
      file
    );


    const response = await fetch(
      `${API_CONFIG.baseUrl}/upload`,
      {
        method: 'POST',
        body: formData,
      }
    );


    if (!response.ok) {

      throw new Error(
        `Failed to upload document: ${response.statusText}`
      );

    }


    const data = await response.json();


    console.log(
      "UPLOAD RESPONSE:",
      data
    );


    return {

      id: data.document_id,

      name: file.name,

      size: file.size,

      status: data.status as DocumentStatus,

      uploadedAt: new Date(),

    };

  },


  /**
   * Fetch all documents
   * GET /documents
   */
  async getDocuments(): Promise<Document[]> {

    if (API_CONFIG.useMock) {

      return [];

    }


    const response = await fetch(
      `${API_CONFIG.baseUrl}/documents`
    );


    if (!response.ok) {

      throw new Error(
        `Failed to fetch documents: ${response.statusText}`
      );

    }


    const data = await response.json();


    return data.map(
      (doc: any) => ({

        id: doc.document_id,

        name: doc.filename,

        size: 0,

        status: doc.status as DocumentStatus,

        uploadedAt: new Date(
          doc.upload_time
        ),

      })
    );

  },


  /**
   * Fetch single document with status
   * GET /documents/{document_id}
   */
  async getDocument(id: string): Promise<Document> {

    if (API_CONFIG.useMock) {

      await delay(100);

      return {

        id,

        name: "Mock Document",

        size: 0,

        status: "ready" as DocumentStatus,

        uploadedAt: new Date(),

      };

    }


    const response = await fetch(
      `${API_CONFIG.baseUrl}/documents/${id}`
    );


    if (!response.ok) {

      throw new Error(
        `Failed to fetch document: ${response.statusText}`
      );

    }


    const data = await response.json();


    console.log(
      "DOCUMENT STATUS RESPONSE:",
      data
    );


    return {

      id: data.document_id,

      name: data.filename,

      size: 0,

      status: data.status as DocumentStatus,

      uploadedAt: new Date(
        data.upload_time
      ),

    };

  },


  /**
   * Delete document
   * DELETE /documents/{document_id}
   */
  async deleteDocument(
    id: string
  ): Promise<{ success: boolean; id: string }> {


    if (API_CONFIG.useMock) {

      await delay(300);

      return {
        success: true,
        id
      };

    }


    const response = await fetch(
      `${API_CONFIG.baseUrl}/documents/${id}`,
      {
        method: 'DELETE',
      }
    );


    if (!response.ok) {

      throw new Error(
        `Failed to delete document: ${response.statusText}`
      );

    }


    return {
      success: true,
      id
    };

  },

};