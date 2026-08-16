import { create } from 'zustand';
import { Message, Citation } from '@/types';
import { ProductMode } from '@/types/mode';
import { ConversationSummary } from '@/types/conversation';
import { chatApi, mapSourceToCitation } from '@/lib/api/chat';
import { conversationsApi } from '@/lib/api/conversations';
import { useDocumentStore } from './useDocumentStore';

const STORAGE_KEY = 'docusage_active_conversation';


function resolveRetrievalDocumentIds(mode: ProductMode): string[] {
  const { documents, selectedDocumentId } = useDocumentStore.getState();
  const readyDocuments = documents.filter((doc) => doc.status === "ready");

  if (mode === "super_focused") {
    if (
      selectedDocumentId &&
      readyDocuments.some((doc) => doc.id === selectedDocumentId)
    ) {
      return [selectedDocumentId];
    }
    return [];
  }

  return readyDocuments.map((doc) => doc.id);
}


function mapStoredMessages(raw: Array<{
  id?: number | string;
  role: string;
  content: string;
  citations?: unknown;
  created_at?: string;
}>): Message[] {
  return raw.map((item, index) => {
    const citations = Array.isArray(item.citations)
      ? (item.citations as Parameters<typeof mapSourceToCitation>[0][]).map(
          mapSourceToCitation
        )
      : [];

    return {
      id: String(item.id ?? `msg-${index}`),
      role: item.role === "assistant" ? "assistant" : "user",
      content: item.content,
      timestamp: item.created_at ? new Date(item.created_at) : new Date(),
      citations: citations as Citation[],
    };
  });
}


interface ChatState {
  conversationId: string;
  conversations: ConversationSummary[];
  messages: Message[];
  isLoading: boolean;
  isHydrating: boolean;
  productMode: ProductMode;
  activeCitation: Citation | null;
  setActiveCitation: (citation: Citation | null) => void;
  setProductMode: (mode: ProductMode) => void;
  initializeConversations: () => Promise<void>;
  createConversation: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  stopGeneration: () => void;
  regenerateLast: () => Promise<void>;
  refreshConversations: () => Promise<void>;
  clearMessages: () => void;
}


export const useChatStore = create<ChatState>((set, get) => {
  let abortController: AbortController | null = null;

  const streamAssistant = async ({
    content,
    assistantId,
    regenerate,
  }: {
    content: string;
    assistantId: string;
    regenerate: boolean;
  }) => {
    abortController?.abort();
    abortController = new AbortController();

    try {
      const conversationId = get().conversationId;
      const mode = get().productMode;
      const documentIds = resolveRetrievalDocumentIds(mode);

      if (documentIds.length === 0) {
        throw new Error(
          mode === "super_focused"
            ? "Select a ready document for Super Focused mode."
            : "No ready documents available."
        );
      }

      await chatApi.streamMessage(
        content,
        documentIds,
        conversationId,
        (token) => {
          set((state) => ({
            messages: state.messages.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + token }
                : msg
            ),
          }));
        },
        (citations) => {
          set((state) => ({
            messages: state.messages.map((msg) =>
              msg.id === assistantId ? { ...msg, citations } : msg
            ),
          }));
        },
        mode,
        abortController.signal,
        regenerate
      );
      void get().refreshConversations();
    } catch (error) {
      const aborted =
        (error instanceof DOMException && error.name === "AbortError") ||
        (error instanceof Error && error.name === "AbortError");

      if (aborted) {
        set((state) => ({
          messages: state.messages.filter((msg) => msg.id !== assistantId),
          isLoading: false,
        }));
        return;
      }

      console.error("Streaming failed:", error);
      const message =
        error instanceof Error
          ? error.message
          : "Sorry, I encountered an error communicating with the server.";

      set((state) => ({
        messages: state.messages.map((msg) =>
          msg.id === assistantId
            ? {
                ...msg,
                content:
                  message.startsWith("Select a ready document") ||
                  message.startsWith("No ready documents")
                    ? message
                    : "Sorry, I encountered an error communicating with the server.",
              }
            : msg
        ),
      }));
    } finally {
      abortController = null;
      set({ isLoading: false });
    }
  };

  return {
  conversationId: "",
  conversations: [],
  messages: [],
  isLoading: false,
  isHydrating: false,
  productMode: "normal",
  activeCitation: null,

  setActiveCitation: (citation) => set({ activeCitation: citation }),

  setProductMode: (mode) =>
    set({
      productMode: mode === "agentic" ? get().productMode : mode,
    }),

  refreshConversations: async () => {
    try {
      const conversations = await conversationsApi.list();
      set({ conversations });
    } catch (error) {
      console.error("Failed to list conversations:", error);
    }
  },

  initializeConversations: async () => {
    if (get().isHydrating) return;
    set({ isHydrating: true });
    try {
      let conversations = await conversationsApi.list();
      const storedId =
        typeof window !== "undefined"
          ? window.localStorage.getItem(STORAGE_KEY)
          : null;
      let activeId =
        (storedId &&
          conversations.some((item) => item.conversation_id === storedId) &&
          storedId) ||
        conversations[0]?.conversation_id ||
        "";

      if (!activeId) {
        const created = await conversationsApi.create();
        conversations = [created, ...conversations];
        activeId = created.conversation_id;
      }

      const detail = await conversationsApi.get(activeId);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, activeId);
      }
      set({
        conversations,
        conversationId: activeId,
        messages: mapStoredMessages(detail.messages || []),
      });
    } catch (error) {
      console.error("Failed to initialize conversations:", error);
      if (!get().conversationId) {
        set({ conversationId: `conv-${Date.now().toString(36)}` });
      }
    } finally {
      set({ isHydrating: false });
    }
  },

  createConversation: async () => {
    const created = await conversationsApi.create();
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, created.conversation_id);
    }
    set((state) => ({
      conversations: [created, ...state.conversations],
      conversationId: created.conversation_id,
      messages: [],
      activeCitation: null,
    }));
  },

  selectConversation: async (id: string) => {
    if (!id || id === get().conversationId) {
      const current = get().conversations.find(
        (item) => item.conversation_id === id
      );
      if (current && get().messages.length > 0) return;
    }
    const detail = await conversationsApi.get(id);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, id);
    }
    set({
      conversationId: id,
      messages: mapStoredMessages(detail.messages || []),
      activeCitation: null,
    });
  },

  renameConversation: async (id: string, title: string) => {
    const updated = await conversationsApi.rename(id, title);
    set((state) => ({
      conversations: state.conversations.map((item) =>
        item.conversation_id === id
          ? { ...item, title: updated.title }
          : item
      ),
    }));
  },

  deleteConversation: async (id: string) => {
    await conversationsApi.remove(id);
    const remaining = get().conversations.filter(
      (item) => item.conversation_id !== id
    );
    if (get().conversationId === id) {
      if (remaining.length > 0) {
        await get().selectConversation(remaining[0].conversation_id);
        set({ conversations: remaining });
      } else {
        const created = await conversationsApi.create();
        set({
          conversations: [created],
          conversationId: created.conversation_id,
          messages: [],
          activeCitation: null,
        });
        if (typeof window !== "undefined") {
          window.localStorage.setItem(STORAGE_KEY, created.conversation_id);
        }
      }
    } else {
      set({ conversations: remaining });
    }
  },

  sendMessage: async (content: string) => {
    set({ activeCitation: null });

    let conversationId = get().conversationId;
    if (!conversationId) {
      await get().initializeConversations();
      conversationId = get().conversationId;
    }

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date(),
    };

    const assistantId = `assistant-${Date.now()}`;
    const emptyAssistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
      citations: [],
    };

    set((state) => ({
      messages: [...state.messages, userMessage, emptyAssistantMessage],
      isLoading: true,
    }));

    await streamAssistant({
      content,
      assistantId,
      regenerate: false,
    });
  },

  stopGeneration: () => {
    abortController?.abort();
  },

  regenerateLast: async () => {
    const messages = get().messages;
    if (get().isLoading || messages.length === 0) return;

    let lastAssistantIndex = -1;
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "assistant") {
        lastAssistantIndex = i;
        break;
      }
    }
    if (lastAssistantIndex <= 0) return;

    const previous = messages[lastAssistantIndex - 1];
    if (!previous || previous.role !== "user") return;

    const assistantId = `assistant-${Date.now()}`;
    const emptyAssistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
      citations: [],
    };

    set({
      activeCitation: null,
      isLoading: true,
      messages: [...messages.slice(0, lastAssistantIndex), emptyAssistantMessage],
    });

    await streamAssistant({
      content: previous.content,
      assistantId,
      regenerate: true,
    });
  },

  clearMessages: () => {
    void get().createConversation();
  },
  };
});
