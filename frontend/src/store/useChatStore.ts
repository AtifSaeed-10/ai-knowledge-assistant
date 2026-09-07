import { create } from 'zustand';
import { Message, Citation } from '@/types';
import { ProductMode } from '@/types/mode';
import { ConversationSummary } from '@/types/conversation';
import { chatApi, mapSourceToCitation } from '@/lib/api/chat';
import { conversationsApi } from '@/lib/api/conversations';
import { toUserMessage } from '@/lib/api/client';
import { ensureGuestSession } from '@/lib/guestSession';
import { useAuthStore } from './useAuthStore';
import { useDocumentStore } from './useDocumentStore';
import { usePdfPanelStore } from './usePdfPanelStore';
import { notify } from './useToastStore';
import { shouldFollowAnswerCitation } from '@/lib/workspace/pdfPanel';
import { classifyChatCommand } from '@/lib/workspace/chatCommand';
import { runWorkspaceCommand } from '@/lib/workspace/applyChatCommand';

const ACTIVE_CONVERSATION_PREFIX = 'docusage_active_conversation';
const MODE_KEY = 'docusage_product_mode';

function readStored(key: string): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string | null) {
  if (typeof window === 'undefined') return;
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) — non-fatal */
  }
}

function workspaceConversationKey(): string {
  const userId = useAuthStore.getState().user?.id;
  if (userId) return `${ACTIVE_CONVERSATION_PREFIX}:user:${userId}`;
  return `${ACTIVE_CONVERSATION_PREFIX}:guest:${ensureGuestSession()}`;
}

function readActiveConversation(): string | null {
  const scoped = readStored(workspaceConversationKey());
  if (scoped) return scoped;
  if (!useAuthStore.getState().user) {
    return readStored(ACTIVE_CONVERSATION_PREFIX);
  }
  return null;
}

function writeActiveConversation(id: string | null) {
  writeStored(workspaceConversationKey(), id);
  if (useAuthStore.getState().user) {
    writeStored(ACTIVE_CONVERSATION_PREFIX, null);
  }
}

function resolveRetrievalDocumentIds(mode: ProductMode): string[] {
  const { documents, selectedDocumentId } = useDocumentStore.getState();
  const readyDocuments = documents.filter((doc) => doc.status === 'ready');

  if (mode === 'super_focused') {
    if (selectedDocumentId && readyDocuments.some((doc) => doc.id === selectedDocumentId)) {
      return [selectedDocumentId];
    }
    return [];
  }

  return readyDocuments.map((doc) => doc.id);
}

function mapStoredMessages(
  raw: Array<{
    id?: number | string;
    role: string;
    content: string;
    citations?: unknown;
    created_at?: string;
  }>
): Message[] {
  return raw.map((item, index) => {
    const citations = Array.isArray(item.citations)
      ? (item.citations as Parameters<typeof mapSourceToCitation>[0][]).map(mapSourceToCitation)
      : [];

    return {
      id: String(item.id ?? `msg-${index}`),
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: item.content,
      timestamp: item.created_at ? new Date(item.created_at) : new Date(),
      citations: citations as Citation[],
      status: 'ok' as const,
    };
  });
}

interface ChatState {
  /** Empty string means "unsaved draft" — nothing is created until the first send. */
  conversationId: string;
  conversations: ConversationSummary[];
  messages: Message[];
  isLoading: boolean;
  isHydrating: boolean;
  hasHydrated: boolean;
  isSwitching: boolean;
  conversationError: string | null;
  productMode: ProductMode;
  activeCitation: Citation | null;
  composerFocusToken: number;

  setActiveCitation: (citation: Citation | null) => void;
  setProductMode: (mode: ProductMode) => void;
  requestComposerFocus: () => void;

  initializeConversations: () => Promise<void>;
  reloadConversations: () => Promise<void>;
  beginIdentitySwitch: () => void;
  refreshConversations: () => Promise<void>;
  startNewConversation: () => void;
  selectConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;

  sendMessage: (content: string) => Promise<void>;
  stopGeneration: () => void;
  retryLastAnswer: () => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => {
  let abortController: AbortController | null = null;
  let stoppedByUser = false;
  let hydrateGeneration = 0;

  const abortInFlight = () => {
    if (abortController) {
      stoppedByUser = false;
      abortController.abort();
      abortController = null;
    }
  };

  const patchMessage = (id: string, patch: Partial<Message>) => {
    set((state) => ({
      messages: state.messages.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg)),
    }));
  };

  const streamAssistant = async ({
    content,
    assistantId,
    conversationId,
    regenerate,
  }: {
    content: string;
    assistantId: string;
    conversationId: string;
    regenerate: boolean;
  }) => {
    abortController?.abort();
    abortController = new AbortController();
    stoppedByUser = false;

    const signal = abortController.signal;

    try {
      const mode = get().productMode;
      const documentIds = resolveRetrievalDocumentIds(mode);

      if (documentIds.length === 0) {
        throw new Error(
          mode === 'super_focused'
            ? 'Choose a ready document before asking in single-document mode.'
            : 'No documents are ready yet. Upload a PDF or wait for processing to finish.'
        );
      }

      await chatApi.streamMessage(
        content,
        documentIds,
        conversationId,
        (token) => {
          set((state) => ({
            messages: state.messages.map((msg) =>
              msg.id === assistantId ? { ...msg, content: msg.content + token } : msg
            ),
          }));
        },
        (citations) => {
          patchMessage(assistantId, { citations });
          if (
            shouldFollowAnswerCitation({
              isOpen: usePdfPanelStore.getState().isOpen,
              citationCount: citations.length,
            })
          ) {
            const target =
              citations.find((item) => item.documentId) || citations[0];
            if (target) get().setActiveCitation(target);
          }
        },
        mode,
        signal,
        regenerate,
        // The server corrected the streamed draft; show the saved answer instead.
        (finalAnswer) => patchMessage(assistantId, { content: finalAnswer })
      );

      patchMessage(assistantId, { status: 'ok' });
      void get().refreshConversations();
      void useAuthStore.getState().refreshUsage();
    } catch (error) {
      const aborted =
        signal.aborted ||
        (error instanceof DOMException && error.name === 'AbortError') ||
        (error instanceof Error && error.name === 'AbortError');

      if (aborted) {
        const partial = get().messages.find((msg) => msg.id === assistantId);

        // Stopping should never feel like a crash: keep whatever was written.
        if (stoppedByUser && partial?.content.trim()) {
          patchMessage(assistantId, { status: 'stopped' });
        } else {
          set((state) => ({
            messages: state.messages.filter((msg) => msg.id !== assistantId),
          }));
        }

        stoppedByUser = false;
        return;
      }

      patchMessage(assistantId, {
        status: 'error',
        content: toUserMessage(error, 'The answer could not be generated.'),
        citations: [],
      });
    } finally {
      abortController = null;
      set({ isLoading: false });
    }
  };

  const hydrateConversations = async () => {
    const generation = ++hydrateGeneration;
    set({ isHydrating: true });

    const storedMode = readStored(MODE_KEY);
    if (storedMode === 'normal' || storedMode === 'super_focused') {
      set({ productMode: storedMode });
    }

    try {
      const conversations = await conversationsApi.list();
      if (generation !== hydrateGeneration) return;

      const storedId = readActiveConversation();
      const activeId =
        (storedId && conversations.some((item) => item.conversation_id === storedId)
          ? storedId
          : conversations[0]?.conversation_id) || '';

      if (!activeId) {
        writeActiveConversation(null);
        set({ conversations, conversationId: '', messages: [], conversationError: null });
        return;
      }

      const detail = await conversationsApi.get(activeId);
      if (generation !== hydrateGeneration) return;

      writeActiveConversation(activeId);
      set({
        conversations,
        conversationId: activeId,
        messages: mapStoredMessages(detail.messages || []),
        conversationError: null,
      });
    } catch (error) {
      if (generation !== hydrateGeneration) return;
      set({
        conversationError: toUserMessage(error, 'Could not load your conversations.'),
      });
    } finally {
      if (generation === hydrateGeneration) {
        set({ isHydrating: false, hasHydrated: true });
      }
    }
  };

  return {
    conversationId: '',
    conversations: [],
    messages: [],
    isLoading: false,
    isHydrating: false,
    hasHydrated: false,
    isSwitching: false,
    conversationError: null,
    productMode: 'normal',
    activeCitation: null,
    composerFocusToken: 0,

    setActiveCitation: (citation) => {
      set({ activeCitation: citation });
      if (citation) usePdfPanelStore.getState().open();
    },

    setProductMode: (mode) => {
      writeStored(MODE_KEY, mode);
      set({ productMode: mode });
    },

    requestComposerFocus: () =>
      set((state) => ({ composerFocusToken: state.composerFocusToken + 1 })),

    refreshConversations: async () => {
      try {
        const conversations = await conversationsApi.list();
        set({ conversations });
      } catch {
        /* the list is non-critical; the visible conversation still works */
      }
    },

    initializeConversations: async () => {
      if (get().isHydrating || get().hasHydrated) return;
      await hydrateConversations();
    },

    reloadConversations: async () => {
      await hydrateConversations();
    },

    beginIdentitySwitch: () => {
      abortInFlight();
      hydrateGeneration += 1;
      set({
        conversations: [],
        conversationId: '',
        messages: [],
        activeCitation: null,
        conversationError: null,
        isHydrating: true,
        hasHydrated: false,
        isLoading: false,
        isSwitching: false,
      });
    },

    /** New chat is a local draft: no empty conversations are ever persisted. */
    startNewConversation: () => {
      const { conversationId, messages, isLoading } = get();

      if (!conversationId && messages.length === 0 && !isLoading) {
        get().requestComposerFocus();
        return;
      }

      abortInFlight();
      writeActiveConversation(null);
      set((state) => ({
        conversationId: '',
        messages: [],
        activeCitation: null,
        conversationError: null,
        isLoading: false,
        isSwitching: false,
        composerFocusToken: state.composerFocusToken + 1,
      }));
    },

    selectConversation: async (id: string) => {
      if (!id || (id === get().conversationId && !get().conversationError)) return;

      abortInFlight();
      writeActiveConversation(id);

      // Clear immediately so the previous transcript can never be mistaken for this one.
      set({
        conversationId: id,
        messages: [],
        activeCitation: null,
        conversationError: null,
        isLoading: false,
        isSwitching: true,
      });

      try {
        const detail = await conversationsApi.get(id);
        if (get().conversationId !== id) return;

        set({ messages: mapStoredMessages(detail.messages || []) });
      } catch (error) {
        if (get().conversationId !== id) return;
        set({
          conversationError: toUserMessage(error, 'Could not open this conversation.'),
        });
      } finally {
        if (get().conversationId === id) set({ isSwitching: false });
      }
    },

    renameConversation: async (id: string, title: string) => {
      const previous = get().conversations;

      set((state) => ({
        conversations: state.conversations.map((item) =>
          item.conversation_id === id ? { ...item, title } : item
        ),
      }));

      try {
        const updated = await conversationsApi.rename(id, title);
        set((state) => ({
          conversations: state.conversations.map((item) =>
            item.conversation_id === id ? { ...item, title: updated.title } : item
          ),
        }));
      } catch (error) {
        set({ conversations: previous });
        notify.error('Rename failed', toUserMessage(error, 'The title was not changed.'));
      }
    },

    deleteConversation: async (id: string) => {
      try {
        await conversationsApi.remove(id);
      } catch (error) {
        notify.error(
          'Could not delete conversation',
          toUserMessage(error, 'It is still in your history.')
        );
        return;
      }

      const remaining = get().conversations.filter((item) => item.conversation_id !== id);
      set({ conversations: remaining });

      if (get().conversationId !== id) return;

      if (remaining.length > 0) {
        await get().selectConversation(remaining[0].conversation_id);
      } else {
        writeActiveConversation(null);
        set({ conversationId: '', messages: [], activeCitation: null });
      }
    },

    sendMessage: async (raw: string) => {
      const content = raw.trim();
      if (!content || get().isLoading) return;

      const command = classifyChatCommand(content);
      if (command.kind !== 'question') {
        const documents = useDocumentStore.getState().documents;
        const selectedDocumentId = useDocumentStore.getState().selectedDocumentId;
        const panel = usePdfPanelStore.getState();
        const reply = await runWorkspaceCommand(command, {
          documents,
          selectedDocumentId,
          previewDocumentId: panel.previewDocumentId,
          citationDocumentId: get().activeCitation?.documentId,
          visiblePage: panel.visiblePage,
          pageCount: panel.pageCount,
          openPanel: (options) => usePdfPanelStore.getState().open(options),
          closePanel: () => {
            get().setActiveCitation(null);
            usePdfPanelStore.getState().close();
          },
          requestPage: (page) => {
            get().setActiveCitation(null);
            usePdfPanelStore.getState().requestPage(page);
          },
        });
        const stamp = Date.now();
        set((state) => ({
          messages: [
            ...state.messages,
            {
              id: `user-${stamp}-nav`,
              role: 'user',
              content,
              timestamp: new Date(),
              status: 'ok',
            },
            {
              id: `assistant-${stamp}-nav`,
              role: 'assistant',
              content: reply,
              timestamp: new Date(),
              citations: [],
              status: 'ok',
            },
          ],
          isLoading: false,
        }));
        return;
      }

      const assistantId = `assistant-${Date.now()}`;

      set((state) => ({
        activeCitation: null,
        isLoading: true,
        messages: [
          ...state.messages,
          {
            id: `user-${Date.now()}`,
            role: 'user',
            content,
            timestamp: new Date(),
            status: 'ok',
          },
          {
            id: assistantId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            citations: [],
          },
        ],
      }));

      let conversationId = get().conversationId;

      if (!conversationId) {
        try {
          const created = await conversationsApi.create();
          conversationId = created.conversation_id;
          writeActiveConversation(conversationId);
          set((state) => ({
            conversationId: created.conversation_id,
            conversations: [created, ...state.conversations],
          }));
        } catch (error) {
          patchMessage(assistantId, {
            status: 'error',
            content: toUserMessage(error, 'Could not start this conversation.'),
          });
          set({ isLoading: false });
          return;
        }
      }

      await streamAssistant({
        content,
        assistantId,
        conversationId,
        regenerate: false,
      });
    },

    stopGeneration: () => {
      if (!abortController) return;
      stoppedByUser = true;
      abortController.abort();
    },

    retryLastAnswer: async () => {
      const { messages, isLoading, conversationId } = get();
      if (isLoading || messages.length === 0) return;

      let lastAssistantIndex = -1;
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        if (messages[i].role === 'assistant') {
          lastAssistantIndex = i;
          break;
        }
      }
      if (lastAssistantIndex <= 0) return;

      const question = messages[lastAssistantIndex - 1];
      if (!question || question.role !== 'user') return;

      const assistantId = `assistant-${Date.now()}`;

      set({
        activeCitation: null,
        isLoading: true,
        messages: [
          ...messages.slice(0, lastAssistantIndex),
          {
            id: assistantId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            citations: [],
          },
        ],
      });

      let targetConversationId = conversationId;

      if (!targetConversationId) {
        try {
          const created = await conversationsApi.create();
          targetConversationId = created.conversation_id;
          writeActiveConversation(targetConversationId);
          set((state) => ({
            conversationId: created.conversation_id,
            conversations: [created, ...state.conversations],
          }));
        } catch (error) {
          patchMessage(assistantId, {
            status: 'error',
            content: toUserMessage(error, 'Could not reach the server.'),
          });
          set({ isLoading: false });
          return;
        }
      }

      await streamAssistant({
        content: question.content,
        assistantId,
        conversationId: targetConversationId,
        regenerate: true,
      });
    },
  };
});
