"use client";

import React from "react";
import { Trash2, BookOpen } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { CitationDrawer } from "./CitationDrawer";

export function ChatContainer() {
  const { messages, isLoading, sendMessage, clearMessages } = useChatStore();
  const { documents } = useDocumentStore();

  const readyDocuments = documents.filter((doc) => doc.status === "ready");
  const hasReadyDocs = readyDocuments.length > 0;

  const handleSend = (content: string) => {
    sendMessage(content);
  };

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
              {hasReadyDocs
                ? `${readyDocuments.length} source${readyDocuments.length === 1 ? "" : "s"} ready`
                : "Waiting for a ready document"}
            </p>
          </div>
        </div>

        {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-[12px] font-medium text-[#6F7B6B] transition-colors hover:bg-red-50 hover:text-red-600"
            title="Clear conversation"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Clear</span>
          </button>
        )}
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
          disabled={!hasReadyDocs}
        />
      </div>

      <CitationDrawer />
    </div>
  );
}
