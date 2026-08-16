"use client";

import React, { useEffect } from "react";
import { MessageSquarePlus, BookOpen, Download } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { CitationDrawer } from "./CitationDrawer";
import { ModeSwitcher } from "./ModeSwitcher";
import {
  conversationToMarkdown,
  downloadTextFile,
  safeFilename,
} from "@/lib/exportConversation";

export function ChatContainer() {
  const { messages, isLoading, sendMessage, clearMessages, productMode, conversations, conversationId } = useChatStore();
  const { documents, selectedDocumentId } = useDocumentStore();

  useEffect(() => {
    void useChatStore.getState().initializeConversations();
  }, []);

  const readyDocuments = documents.filter((doc) => doc.status === "ready");
  const hasReadyDocs = readyDocuments.length > 0;
  const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId) || null;
  const superFocusedReady =
    productMode !== "super_focused" ||
    Boolean(selectedDocument && selectedDocument.status === "ready");
  const canSend = hasReadyDocs && superFocusedReady;

  const handleSend = (content: string) => {
    sendMessage(content);
  };

  const handleExport = () => {
    const current = conversations.find((item) => item.conversation_id === conversationId);
    const title = current?.title || "Conversation";
    const markdown = conversationToMarkdown({ title }, messages);
    downloadTextFile(safeFilename(title), markdown);
  };

  const sourceLabel = (() => {
    if (productMode === "super_focused") {
      if (selectedDocument?.status === "ready") {
        return `Super Focused · ${selectedDocument.name}`;
      }
      return "Super Focused · select a ready document";
    }
    if (hasReadyDocs) {
      return `${readyDocuments.length} source${readyDocuments.length === 1 ? "" : "s"} ready`;
    }
    return "Waiting for a ready document";
  })();

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-[#EBEFEA] bg-white">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-[#EBEFEA] px-4 py-2.5 sm:px-5">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[#F6F7F4] text-[#4A5D23]">
            <BookOpen className="h-3.5 w-3.5" strokeWidth={1.75} />
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-[13px] font-semibold tracking-[-0.01em] text-[#1C241F]">
              Research
            </h3>
            <p className="truncate text-[11px] text-[#6F7B6B]">
              {sourceLabel}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <ModeSwitcher />
          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleExport}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-[12px] font-medium text-[#6F7B6B] transition-colors hover:bg-[#F1F3EF] hover:text-[#1C241F]"
              title="Export conversation"
            >
              <Download className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Export</span>
            </button>
          )}
          {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-[12px] font-medium text-[#6F7B6B] transition-colors hover:bg-[#F1F3EF] hover:text-[#1C241F]"
            title="New conversation"
          >
            <MessageSquarePlus className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">New</span>
          </button>
        )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#FBFBFA]">
        <MessageList
          messages={messages}
          isLoading={isLoading}
          onSelectPrompt={handleSend}
        />
      </div>

      <div className="shrink-0 border-t border-[#EBEFEA] bg-white px-3 py-3 sm:px-4 sm:py-3.5">
        <ChatInput
          onSend={handleSend}
          isLoading={isLoading}
          disabled={!canSend}
        />
      </div>

      <CitationDrawer />
    </div>
  );
}
