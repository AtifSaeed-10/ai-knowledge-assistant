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
import {
  SEARCH_ALL_SCOPE_ID,
  lastCitedDocumentId,
  resolveDocumentScope,
  shouldRememberScopePin,
} from '@/lib/workspace/documentScope';
import { shouldSkipConversationReload } from '@/lib/workspace/workspaceView';

const ACTIVE_CONVERSATION_PREFIX = 'docusage_active_conversation';
const MODE_KEY = 'docusage_product_mode';
/** Retrieval + first token should not sit on "Searching" forever. */
const ANSWER_TIMEOUT_MS = 180_000;
const ANSWER_TIMEOUT_MESSAGE =
  'This is taking longer than usual. Try again — your question is still here.';
const EMPTY_ANSWER_MESSAGE = 'No answer came back. Try again.';
const FOCUSED_MODE_HINT =
  'Answered from that PDF. Switch the scope above to Focused to keep every question on it.';
const STOPPED_EMPTY_MESSAGE = 'Search was stopped before an answer arrived.';
const RETRY_ABORT = 'retry';
const TIMEOUT_ABORT = 'timeout';
const USER_ABORT = 'user';

type AbortReason = typeof RETRY_ABORT | typeof TIMEOUT_ABORT | typeof USER_ABORT;

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

function decideQuestionScope(
  question: string,
  mode: ProductMode,
  messages: Message[],
  pinnedDocumentId: string | null
) {
  const { documents, selectedDocumentId } = useDocumentStore.getState();
  const panel = usePdfPanelStore.getState();
  return resolveDocumentScope({
    question,
    mode,
    documents,
    selectedDocumentId,
    previewDocumentId: panel.isOpen ? panel.previewDocumentId : null,
    lastCitedDocumentId: lastCitedDocumentId(messages),
    pinnedDocumentId,
  });
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
  /** One-file pin for this chat so follow-ups stay on the PDF the reader picked. */
  pinnedDocumentId: string | null;

  setActiveCitation: (citation: Citation | null) => void;
  setProductMode: (mode: ProductMode) => void;
  requestComposerFocus: () => void;
  clearDocumentPin: () => void;
  chooseDocumentScope: (documentId: string) => Promise<void>;

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
  let abortReason: AbortReason | null = null;
  let streamTimeoutId = 0;
  let hydrateGeneration = 0;

  const clearStreamTimeout = () => {
    if (streamTimeoutId) {
      window.clearTimeout(streamTimeoutId);
      streamTimeoutId = 0;
    }
  };

  const armStreamTimeout = () => {
    clearStreamTimeout();
    if (typeof window === 'undefined') return;
    streamTimeoutId = window.setTimeout(() => {
      abortReason = TIMEOUT_ABORT;
      abortController?.abort();
    }, ANSWER_TIMEOUT_MS);
  };

  const beginAnswerRequest = (): AbortSignal => {
    abortController?.abort();
    abortController = new AbortController();
    abortReason = null;
    armStreamTimeout();
    return abortController.signal;
  };

  const abortInFlight = () => {
    if (abortController) {
      abortReason = null;
      abortController.abort();
      abortController = null;
    }
    clearStreamTimeout();
  };

  const patchMessage = (id: string, patch: Partial<Message>) => {
    set((state) => ({
      messages: state.messages.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg)),
    }));
  };

  const failAssistant = (id: string, content: string) => {
    patchMessage(id, { status: 'error', content, citations: [] });
  };

  const closeAnswerRequest = () => {
    const shouldRetry = abortReason === RETRY_ABORT;
    abortReason = null;
    clearStreamTimeout();
    abortController = null;
    set({ isLoading: false });
    if (shouldRetry) void get().retryLastAnswer();
    return shouldRetry;
  };

  const recoverStartFailure = (
    assistantId: string,
    signal: AbortSignal,
    error: unknown,
    fallback: string
  ) => {
    if (signal.aborted) {
      const shouldRetry = abortReason === RETRY_ABORT;
      if (!shouldRetry) {
        failAssistant(
          assistantId,
          abortReason === TIMEOUT_ABORT ? ANSWER_TIMEOUT_MESSAGE : STOPPED_EMPTY_MESSAGE
        );
      }
      closeAnswerRequest();
      return;
    }
    failAssistant(assistantId, toUserMessage(error, fallback));
    abortReason = null;
    clearStreamTimeout();
    abortController = null;
    set({ isLoading: false });
  };

  const ensureConversationId = async (signal: AbortSignal): Promise<string> => {
    const existing = get().conversationId;
    if (existing) return existing;

    const created = await conversationsApi.create(undefined, signal);
    writeActiveConversation(created.conversation_id);
    set((state) => ({
      conversationId: created.conversation_id,
      conversations: [created, ...state.conversations],
    }));
    return created.conversation_id;
  };

  const streamAssistant = async ({
    content,
    assistantId,
    conversationId,
    regenerate,
    documentIds,
    signal,
  }: {
    content: string;
    assistantId: string;
    conversationId: string;
    regenerate: boolean;
    documentIds?: string[];
    signal: AbortSignal;
  }) => {
    try {
      const mode = get().productMode;
      const scopedIds =
        documentIds && documentIds.length > 0
          ? documentIds
          : resolveRetrievalDocumentIds(mode);

      if (scopedIds.length === 0) {
        throw new Error(
          mode === 'super_focused'
            ? 'Choose a ready document before asking in single-document mode.'
            : 'No documents are ready yet. Upload a PDF or wait for processing to finish.'
        );
      }

      await chatApi.streamMessage(
        content,
        scopedIds,
        conversationId,
        (token) => {
          armStreamTimeout();
          set((state) => ({
            messages: state.messages.map((msg) =>
              msg.id === assistantId ? { ...msg, content: msg.content + token } : msg
            ),
          }));
        },
        (citations) => {
          armStreamTimeout();
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
        (finalAnswer) => {
          armStreamTimeout();
          patchMessage(assistantId, { content: finalAnswer });
        }
      );

      const latest = get().messages.find((msg) => msg.id === assistantId);
      if (!latest?.content.trim()) {
        failAssistant(assistantId, EMPTY_ANSWER_MESSAGE);
        return;
      }

      patchMessage(assistantId, { status: 'ok' });
      void get().refreshConversations();
      void useAuthStore.getState().refreshUsage();
    } catch (error) {
      const aborted =
        signal.aborted ||
        (error instanceof DOMException && error.name === 'AbortError') ||
        (error instanceof Error && error.name === 'AbortError');

      if (aborted) {
        if (abortReason === RETRY_ABORT) return;

        const partial = get().messages.find((msg) => msg.id === assistantId);

        if (abortReason === TIMEOUT_ABORT) {
          failAssistant(assistantId, ANSWER_TIMEOUT_MESSAGE);
          return;
        }

        // Keep the bubble so the same question can be tried again.
        if (partial?.content.trim()) {
          patchMessage(assistantId, { status: 'stopped' });
        } else {
          failAssistant(assistantId, STOPPED_EMPTY_MESSAGE);
        }
        return;
      }

      failAssistant(
        assistantId,
        toUserMessage(error, 'The answer could not be generated.')
      );
    } finally {
      closeAnswerRequest();
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
    pinnedDocumentId: null,

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

    clearDocumentPin: () => set({ pinnedDocumentId: null }),

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
        pinnedDocumentId: null,
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
        pinnedDocumentId: null,
        conversationError: null,
        isLoading: false,
        isSwitching: false,
        composerFocusToken: state.composerFocusToken + 1,
      }));
    },

    selectConversation: async (id: string) => {
      const current = get();
      if (
        shouldSkipConversationReload({
          requestedId: id,
          currentId: current.conversationId,
          conversationError: current.conversationError,
          messageCount: current.messages.length,
          isSwitching: current.isSwitching,
        })
      ) {
        return;
      }

      abortInFlight();
      writeActiveConversation(id);

      // Clear immediately so the previous transcript can never be mistaken for this one.
      set({
        conversationId: id,
        messages: [],
        activeCitation: null,
        pinnedDocumentId: null,
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
        set({ conversationId: '', messages: [], activeCitation: null, pinnedDocumentId: null });
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

      const decision = decideQuestionScope(
        content,
        get().productMode,
        get().messages,
        get().pinnedDocumentId
      );

      if (decision.kind === 'clarify') {
        const stamp = Date.now();
        set((state) => ({
          messages: [
            ...state.messages,
            {
              id: `user-${stamp}-scope`,
              role: 'user',
              content,
              timestamp: new Date(),
              status: 'ok',
            },
            {
              id: `assistant-${stamp}-scope`,
              role: 'assistant',
              content: 'Which PDF should I use for this?',
              timestamp: new Date(),
              citations: [],
              status: 'ok',
              scopeChoices: [
                ...decision.candidates,
                { id: SEARCH_ALL_SCOPE_ID, name: 'Search all documents' },
              ],
              pendingQuestion: content,
            },
          ],
          isLoading: false,
        }));
        return;
      }

      const assistantId = `assistant-${Date.now()}`;
      const signal = beginAnswerRequest();

      set((state) => ({
        pinnedDocumentId: shouldRememberScopePin(decision)
          ? decision.documentIds[0]
          : state.pinnedDocumentId,
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

      try {
        const conversationId = await ensureConversationId(signal);
        await streamAssistant({
          content,
          assistantId,
          conversationId,
          regenerate: false,
          documentIds: decision.documentIds,
          signal,
        });
      } catch (error) {
        recoverStartFailure(assistantId, signal, error, 'Could not start this conversation.');
      }
    },

    chooseDocumentScope: async (documentId: string) => {
      if (get().isLoading) return;

      const messages = get().messages;
      const target = [...messages]
        .reverse()
        .find((item) => item.role === 'assistant' && item.scopeChoices?.length);
      const question = target?.pendingQuestion?.trim();
      if (!target || !question) return;

      const readyDocuments = useDocumentStore
        .getState()
        .documents.filter((doc) => doc.status === 'ready');
      const searchAll = documentId === SEARCH_ALL_SCOPE_ID;
      const picked = readyDocuments.find((doc) => doc.id === documentId) || null;
      if (!searchAll && !picked) return;

      const documentIds = searchAll ? readyDocuments.map((doc) => doc.id) : [picked!.id];
      if (documentIds.length === 0) return;

      if (picked) {
        useDocumentStore.getState().selectDocument(picked.id);
        usePdfPanelStore.getState().open({ documentId: picked.id, pinned: true });
      }

      const assistantId = target.id;
      const signal = beginAnswerRequest();
      set({
        pinnedDocumentId: searchAll ? null : picked!.id,
        activeCitation: null,
        isLoading: true,
        messages: messages.map((item) =>
          item.id === assistantId
            ? {
                ...item,
                content: '',
                citations: [],
                scopeChoices: undefined,
                pendingQuestion: undefined,
                // Having to ask means the library was ambiguous; Focused mode
                // is the way to stop being asked again.
                scopeHint: picked ? FOCUSED_MODE_HINT : undefined,
              }
            : item
        ),
      });

      try {
        const conversationId = await ensureConversationId(signal);
        await streamAssistant({
          content: question,
          assistantId,
          conversationId,
          regenerate: false,
          documentIds,
          signal,
        });
      } catch (error) {
        recoverStartFailure(assistantId, signal, error, 'Could not start this conversation.');
      }
    },

    stopGeneration: () => {
      abortReason = USER_ABORT;
      if (abortController) {
        abortController.abort();
        return;
      }

      clearStreamTimeout();
      const last = get().messages[get().messages.length - 1];
      if (last?.role === 'assistant' && !last.content.trim() && last.status !== 'error') {
        failAssistant(last.id, STOPPED_EMPTY_MESSAGE);
      }
      set({ isLoading: false });
    },

    retryLastAnswer: async () => {
      const { messages, isLoading, conversationId } = get();
      if (messages.length === 0) return;

      if (isLoading) {
        abortReason = RETRY_ABORT;
        if (abortController) {
          abortController.abort();
          return;
        }
        clearStreamTimeout();
        set({ isLoading: false });
      }

      const current = get().messages;
      let lastAssistantIndex = -1;
      for (let i = current.length - 1; i >= 0; i -= 1) {
        if (current[i].role === 'assistant') {
          lastAssistantIndex = i;
          break;
        }
      }
      if (lastAssistantIndex <= 0) return;
      if (current[lastAssistantIndex].scopeChoices?.length) return;

      const question = current[lastAssistantIndex - 1];
      if (!question || question.role !== 'user') return;

      const decision = decideQuestionScope(
        question.content,
        get().productMode,
        current.slice(0, lastAssistantIndex - 1),
        get().pinnedDocumentId
      );
      if (decision.kind === 'clarify') return;
      if (shouldRememberScopePin(decision)) {
        set({ pinnedDocumentId: decision.documentIds[0] });
      }

      const assistantId = `assistant-${Date.now()}`;
      const signal = beginAnswerRequest();

      set({
        activeCitation: null,
        isLoading: true,
        messages: [
          ...current.slice(0, lastAssistantIndex),
          {
            id: assistantId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            citations: [],
          },
        ],
      });

      try {
        let targetConversationId = conversationId || get().conversationId;
        if (!targetConversationId) {
          targetConversationId = await ensureConversationId(signal);
        }
        await streamAssistant({
          content: question.content,
          assistantId,
          conversationId: targetConversationId,
          regenerate: true,
          documentIds: decision.documentIds,
          signal,
        });
      } catch (error) {
        recoverStartFailure(assistantId, signal, error, 'Could not reach the server.');
      }
    },
  };
});
