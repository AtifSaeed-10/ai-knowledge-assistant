import { create } from 'zustand';
import { Document, DocumentStatus } from '@/types';
import { documentsApi } from '@/lib/api/documents';

interface DocumentState {
  documents: Document[];
  isLoading: boolean;
  hasInitialized: boolean;
  initialize: () => Promise<void>;
  uploadDocument: (file: File) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  updateDocumentStatus: (id: string, status: DocumentStatus) => void;
}

const pollIntervals = new Map<string, ReturnType<typeof setInterval>>();

export const useDocumentStore = create<DocumentState>((set, get) => {
  const startStatusPolling = (documentId: string) => {
    if (pollIntervals.has(documentId)) {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updatedDoc = await documentsApi.getDocument(documentId);

        console.log(
          "DOCUMENT STATUS:",
          updatedDoc.status
        );

        get().updateDocumentStatus(
          documentId,
          updatedDoc.status
        );

        if (updatedDoc.status === "ready") {
          clearInterval(interval);
          pollIntervals.delete(documentId);

          console.log(
            "DOCUMENT READY"
          );
        }
      } catch (error) {
        console.error(
          "STATUS POLLING FAILED:",
          error
        );

        clearInterval(interval);
        pollIntervals.delete(documentId);
      }
    }, 1000);

    pollIntervals.set(documentId, interval);
  };

  return {
  documents: [],
  isLoading: false,
  hasInitialized: false,

  initialize: async () => {
    const { hasInitialized, isLoading } = get();
    if (hasInitialized || isLoading) return;

    set({ isLoading: true });

    try {
      const docs = await documentsApi.getDocuments();
      set({ documents: docs });

      docs.forEach((doc) => {
        if (doc.status !== "ready") {
          startStatusPolling(doc.id);
        }
      });
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      set({ isLoading: false, hasInitialized: true });
    }
  },

  uploadDocument: async (file: File) => {
    try {
      // 1. Upload file to FastAPI
      const newDoc = await documentsApi.uploadDocument(file);

      console.log("NEW DOCUMENT FROM API:", newDoc);


      // 2. Add document immediately to UI
      set((state) => ({
        documents: [
          newDoc,
          ...state.documents
        ],
      }));

      console.log("DOCUMENT ADDED TO STORE");


      // 3. Poll backend for real processing status
      startStatusPolling(newDoc.id);


    } catch (error) {

      console.error(
        'Failed to upload document:',
        error
      );

    }
  },


  deleteDocument: async (id: string) => {

    try {

      // 1. Delete from backend
      await documentsApi.deleteDocument(id);


      // 2. Remove from UI
      set((state) => ({
        documents:
          state.documents.filter(
            (doc) => doc.id !== id
          ),
      }));


    } catch (error) {

      console.error(
        'Failed to delete document:',
        error
      );

    }

  },


  updateDocumentStatus: (
    id: string,
    status: DocumentStatus
  ) => {

    set((state) => ({

      documents:

        state.documents.map((doc) =>

          doc.id === id

            ? {
                ...doc,
                status
              }

            : doc

        ),

    }));

  },

};
});