"use client";

import React from "react";
import { Download, Menu, SquarePen } from "lucide-react";
import Link from "next/link";
import { LogoMark } from "@/components/ui/Logo";
import { UsageMeter } from "@/components/auth/UsageMeter";
import { UserMenu } from "@/components/auth/UserMenu";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { useChatStore } from "@/store/useChatStore";
import {
  conversationToMarkdown,
  downloadTextFile,
  safeFilename,
} from "@/lib/exportConversation";

interface WorkspaceHeaderProps {
  onOpenSidebar: () => void;
}

/**
 * The single header for the workspace. Everything conversation-level lives
 * here so the chat surface itself stays free of competing chrome.
 */
export function WorkspaceHeader({ onOpenSidebar }: WorkspaceHeaderProps) {
  const conversations = useChatStore((state) => state.conversations);
  const conversationId = useChatStore((state) => state.conversationId);
  const messages = useChatStore((state) => state.messages);
  const isSwitching = useChatStore((state) => state.isSwitching);
  const startNewConversation = useChatStore((state) => state.startNewConversation);

  const current = conversations.find((item) => item.conversation_id === conversationId);
  const title = conversationId ? current?.title || "Conversation" : "New chat";
  const hasMessages = messages.length > 0;

  const handleExport = () => {
    downloadTextFile(
      safeFilename(title),
      conversationToMarkdown({ title }, messages)
    );
  };

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-2 px-3 sm:h-16 sm:gap-3 sm:px-6">
      <div className="flex min-w-0 flex-1 items-center gap-1.5 sm:gap-2.5">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open workspace menu"
          className="-ml-0.5 inline-flex h-10 w-10 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface hover:text-ink lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        <Link href="/" aria-label="DocuSage home" className="hidden rounded-md sm:block lg:hidden">
          <LogoMark className="h-6 w-6 shrink-0" />
        </Link>

        <div className="min-w-0 flex-1">
          {isSwitching ? (
            <span className="skeleton block h-4 w-44 max-w-full" aria-hidden />
          ) : (
            <h1 className="truncate text-body font-semibold tracking-[-0.01em] text-ink">
              {title}
            </h1>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-0.5 sm:gap-1.5">
        <UsageMeter />

        {hasMessages && (
          <button
            type="button"
            onClick={handleExport}
            title="Export this conversation as Markdown"
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg px-2.5 text-ui font-medium text-ink-muted transition-colors hover:bg-surface hover:text-ink sm:h-auto sm:py-1.5"
          >
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline">Export</span>
          </button>
        )}

        <button
          type="button"
          onClick={startNewConversation}
          title="Start a new chat"
          className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg px-2.5 text-ui font-medium text-ink transition-colors hover:bg-surface-sunken sm:h-auto sm:py-1.5"
        >
          <SquarePen className="h-4 w-4 text-olive" />
          <span className="hidden sm:inline">New chat</span>
          <span className="sr-only sm:hidden">New chat</span>
        </button>

        <ThemeToggle />

        <UserMenu />
      </div>
    </header>
  );
}
