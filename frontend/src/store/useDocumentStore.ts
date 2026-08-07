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

export const useDocumentStore = create<DocumentState>((set, get) => ({
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
      const interval = setInterval(async () => {

        try {

          const updatedDoc =
            await documentsApi.getDocument(newDoc.id);


          console.log(
            "DOCUMENT STATUS:",
            updatedDoc.status
          );


          // Update UI status from backend
          get().updateDocumentStatus(
            newDoc.id,
            updatedDoc.status
          );


          // Stop polling when indexing finishes
          if (updatedDoc.status === "ready") {

            clearInterval(interval);

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
        }


      }, 1000);


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

}));