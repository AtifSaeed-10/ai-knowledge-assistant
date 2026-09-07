import { create } from 'zustand';
import { Document, DocumentStatus } from '@/types';
import { documentsApi } from '@/lib/api/documents';
import { QuotaExceededError, toUserMessage } from '@/lib/api/client';
import { useAuthStore } from './useAuthStore';
import { usePdfPanelStore } from './usePdfPanelStore';
import { notify } from './useToastStore';

/** Poll cadence, and the point at which a silent backend is treated as a failure. */
const POLL_INTERVAL_MS = 1500;
const SLOW_POLL_AFTER_MS = 30_000;
const SLOW_POLL_INTERVAL_MS = 4000;
const STALL_TIMEOUT_MS = 120_000;
const MAX_CONSECUTIVE_ERRORS = 4;

interface PollRecord {
  timer: ReturnType<typeof setTimeout> | null;
  startedAt: number;
  lastChangeAt: number;
  lastStatus: DocumentStatus;
  errorCount: number;
}

interface DocumentState {
  documents: Document[];
  isLoading: boolean;
  hasInitialized: boolean;
  loadError: string | null;
  selectedDocumentId: string | null;
  initialize: () => Promise<void>;
  reload: () => Promise<void>;
  beginIdentitySwitch: () => void;
  uploadDocument: (file: File) => Promise<boolean>;
  deleteDocument: (id: string) => Promise<boolean>;
  retryProcessing: (id: string) => void;
  selectDocument: (id: string | null) => void;
}

export const useDocumentStore = create<DocumentState>((set, get) => {
  const polls = new Map<string, PollRecord>();
  let loadGeneration = 0;

  const stopPolling = (documentId: string) => {
    const record = polls.get(documentId);
    if (record?.timer) clearTimeout(record.timer);
    polls.delete(documentId);
  };

  const patchDocument = (id: string, patch: Partial<Document>) => {
    set((state) => ({
      documents: state.documents.map((doc) =>
        doc.id === id ? { ...doc, ...patch } : doc
      ),
    }));
  };

  const markFailed = (id: string, error: string) => {
    stopPolling(id);
    const doc = get().documents.find((item) => item.id === id);
    if (!doc || doc.status === 'failed') return;

    patchDocument(id, { status: 'failed', error });
    notify.error(`Could not process “${doc.name}”`, error, `doc-failed-${id}`);
  };

  const startPolling = (documentId: string) => {
    if (polls.has(documentId)) return;

    const current = get().documents.find((doc) => doc.id === documentId);
    const now = Date.now();

    const record: PollRecord = {
      timer: null,
      startedAt: now,
      lastChangeAt: now,
      lastStatus: current?.status ?? 'uploaded',
      errorCount: 0,
    };
    polls.set(documentId, record);

    const tick = async () => {
      if (!polls.has(documentId)) return;

      try {
        const updated = await documentsApi.getDocument(documentId);
        if (!polls.has(documentId)) return;

        record.errorCount = 0;

        if (updated.status !== record.lastStatus) {
          record.lastStatus = updated.status;
          record.lastChangeAt = Date.now();
        }

        patchDocument(documentId, {
          status: updated.status,
          totalPages: updated.totalPages,
          totalChunks: updated.totalChunks,
          error: updated.status === 'failed' ? updated.error : undefined,
        });

        if (updated.status === 'ready') {
          stopPolling(documentId);
          return;
        }

        if (updated.status === 'failed') {
          markFailed(
            documentId,
            updated.error || 'Processing failed on the server.'
          );
          return;
        }

        if (Date.now() - record.lastChangeAt > STALL_TIMEOUT_MS) {
          markFailed(
            documentId,
            'Processing stopped responding. The file may be scanned, empty or password protected.'
          );
          return;
        }
      } catch (error) {
        if (!polls.has(documentId)) return;

        record.errorCount += 1;
        if (record.errorCount >= MAX_CONSECUTIVE_ERRORS) {
          markFailed(documentId, toUserMessage(error, 'Lost contact with the server.'));
          return;
        }
      }

      const elapsed = Date.now() - record.startedAt;
      const interval =
        elapsed > SLOW_POLL_AFTER_MS ? SLOW_POLL_INTERVAL_MS : POLL_INTERVAL_MS;
      record.timer = setTimeout(() => void tick(), interval);
    };

    record.timer = setTimeout(() => void tick(), POLL_INTERVAL_MS);
  };

  const resumePollingForProcessing = (documents: Document[]) => {
    documents.forEach((doc) => {
      if (doc.status !== 'ready' && doc.status !== 'failed') {
        startPolling(doc.id);
      }
    });
  };

  const loadDocuments = async () => {
    const generation = ++loadGeneration;
    set({ isLoading: true });

    try {
      const docs = await documentsApi.getDocuments();
      if (generation !== loadGeneration) return;

      const selectedDocumentId = get().selectedDocumentId;
      const selectedStillOwned =
        selectedDocumentId && docs.some((doc) => doc.id === selectedDocumentId);

      set({
        documents: docs,
        loadError: null,
        selectedDocumentId: selectedStillOwned ? selectedDocumentId : null,
      });
      resumePollingForProcessing(docs);
    } catch (error) {
      if (generation !== loadGeneration) return;
      const message = toUserMessage(error, 'Could not load your documents.');
      set({ loadError: message });
    } finally {
      if (generation === loadGeneration) {
        set({ isLoading: false, hasInitialized: true });
      }
    }
  };

  return {
    documents: [],
    isLoading: false,
    hasInitialized: false,
    loadError: null,
    selectedDocumentId: null,

    selectDocument: (id) => set({ selectedDocumentId: id }),

    initialize: async () => {
      const { hasInitialized, isLoading } = get();
      if (hasInitialized || isLoading) return;
      await loadDocuments();
    },

    reload: async () => {
      await loadDocuments();
    },

    beginIdentitySwitch: () => {
      loadGeneration += 1;
      Array.from(polls.keys()).forEach(stopPolling);
      set({
        documents: [],
        selectedDocumentId: null,
        loadError: null,
        hasInitialized: false,
        isLoading: true,
      });
    },

    uploadDocument: async (file: File) => {
      try {
        const newDoc = await documentsApi.uploadDocument(file);

        set((state) => ({ documents: [newDoc, ...state.documents] }));
        startPolling(newDoc.id);
        usePdfPanelStore.getState().open({ documentId: newDoc.id });
        void useAuthStore.getState().refreshUsage();

        return true;
      } catch (error) {
        // A spent allowance already opened the signup modal; a toast on top
        // of it would just repeat the same sentence.
        if (error instanceof QuotaExceededError) return false;

        notify.error(
          `Upload failed for “${file.name}”`,
          toUserMessage(error, 'The file could not be uploaded.')
        );
        return false;
      }
    },

    deleteDocument: async (id: string) => {
      const doc = get().documents.find((item) => item.id === id);

      try {
        await documentsApi.deleteDocument(id);
        stopPolling(id);

        set((state) => ({
          documents: state.documents.filter((item) => item.id !== id),
          selectedDocumentId:
            state.selectedDocumentId === id ? null : state.selectedDocumentId,
        }));
        // Deleting frees an upload slot.
        void useAuthStore.getState().refreshUsage();

        return true;
      } catch (error) {
        notify.error(
          doc ? `Could not delete “${doc.name}”` : 'Could not delete document',
          toUserMessage(error, 'The document is still in your workspace.')
        );
        return false;
      }
    },

    /** Clears the failed state and resumes watching the server. */
    retryProcessing: (id: string) => {
      const doc = get().documents.find((item) => item.id === id);
      if (!doc) return;

      stopPolling(id);
      patchDocument(id, { status: 'uploaded', error: undefined });
      startPolling(id);
    },
  };
});
