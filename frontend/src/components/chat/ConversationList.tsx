"use client";

import React, { useMemo, useState } from "react";
import { Check, Pencil, Search, SquarePen, Trash2, X } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { cn } from "@/lib/cn";

const SEARCH_THRESHOLD = 8;

function formatRelativeTime(value?: string): string {
  if (!value) return "";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  const minutes = Math.floor((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

interface ConversationListProps {
  isCollapsed?: boolean;
  /** Called after a conversation is opened, so the mobile sidebar can close. */
  onNavigate?: () => void;
}

export function ConversationList({ isCollapsed = false, onNavigate }: ConversationListProps) {
  const conversations = useChatStore((state) => state.conversations);
  const conversationId = useChatStore((state) => state.conversationId);
  const messages = useChatStore((state) => state.messages);
  const startNewConversation = useChatStore((state) => state.startNewConversation);
  const selectConversation = useChatStore((state) => state.selectConversation);
  const renameConversation = useChatStore((state) => state.renameConversation);
  const deleteConversation = useChatStore((state) => state.deleteConversation);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [query, setQuery] = useState("");
  const [pendingDelete, setPendingDelete] = useState<{ id: string; title: string } | null>(null);

  const isDraft = conversationId === "";

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return conversations;
    return conversations.filter((item) => item.title.toLowerCase().includes(term));
  }, [conversations, query]);

  const commitRename = async (id: string) => {
    const title = draftTitle.trim();
    setEditingId(null);

    const current = conversations.find((item) => item.conversation_id === id);
    if (!title || title === current?.title) return;

    await renameConversation(id, title);
  };

  if (isCollapsed) {
    return (
      <div className="px-2 py-2">
        <button
          type="button"
          onClick={startNewConversation}
          title="New chat"
          aria-label="New chat"
          className="flex h-9 w-full items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface-sunken hover:text-olive"
        >
          <SquarePen size={18} />
        </button>
      </div>
    );
  }

  return (
    <section className="flex min-h-0 flex-col" aria-label="Chats">
      <div className="flex shrink-0 items-center justify-between gap-2 px-5 pb-1.5 pt-3">
        <h2 className="text-label font-semibold uppercase tracking-[0.09em] text-ink-muted">
          Chats
        </h2>
        <button
          type="button"
          onClick={startNewConversation}
          className="rounded-md p-1 text-ink-icon transition-colors hover:bg-surface-sunken hover:text-olive"
          title="New chat"
          aria-label="New chat"
        >
          <SquarePen className="h-4 w-4" />
        </button>
      </div>

      {conversations.length > SEARCH_THRESHOLD && (
        <div className="shrink-0 px-3 pb-2">
          <div className="flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2 py-1.5 focus-within:border-sage">
            <Search className="h-3.5 w-3.5 shrink-0 text-ink-icon" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search chats"
              aria-label="Search chats"
              className="min-w-0 flex-1 bg-transparent text-meta text-ink outline-none placeholder:text-ink-subtle"
            />
          </div>
        </div>
      )}

      <div className="scroll-area min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {isDraft && (
          <div className="mb-0.5 flex items-center gap-2 rounded-lg bg-surface px-2.5 py-2 ring-1 ring-line">
            <SquarePen className="h-3.5 w-3.5 shrink-0 text-olive" />
            <span className="min-w-0 flex-1 truncate text-ui font-medium text-ink">New chat</span>
            <span className="shrink-0 text-meta text-ink-subtle">
              {messages.length > 0 ? "Unsaved" : "Draft"}
            </span>
          </div>
        )}

        {conversations.length === 0 && !isDraft && (
          <p className="px-2 py-3 text-meta text-ink-muted">
            Your chats will be listed here.
          </p>
        )}

        {conversations.length > 0 && filtered.length === 0 && (
          <p className="px-2 py-3 text-meta text-ink-muted">No chats match “{query}”.</p>
        )}

        <ul className="space-y-0.5">
          {filtered.map((item) => {
            const isActive = item.conversation_id === conversationId;
            const isEditing = editingId === item.conversation_id;

            if (isEditing) {
              return (
                <li key={item.conversation_id}>
                  <form
                    className="flex items-center gap-1 rounded-lg bg-surface px-2 py-1.5 ring-1 ring-sage"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void commitRename(item.conversation_id);
                    }}
                  >
                    <input
                      autoFocus
                      value={draftTitle}
                      onChange={(event) => setDraftTitle(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") {
                          event.preventDefault();
                          event.stopPropagation();
                          setEditingId(null);
                        }
                      }}
                      onBlur={() => void commitRename(item.conversation_id)}
                      aria-label={`Rename ${item.title}`}
                      className="min-w-0 flex-1 rounded border border-line bg-surface px-1.5 py-0.5 text-ui text-ink outline-none focus:border-sage"
                    />
                    <button
                      type="submit"
                      className="rounded p-1 text-olive transition-colors hover:bg-olive-soft"
                      aria-label="Save name"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => setEditingId(null)}
                      className="rounded p-1 text-ink-icon transition-colors hover:bg-surface-sunken hover:text-ink"
                      aria-label="Cancel rename"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </form>
                </li>
              );
            }

            return (
              <li key={item.conversation_id} className="group relative">
                <button
                  type="button"
                  onClick={() => {
                    void selectConversation(item.conversation_id);
                    onNavigate?.();
                  }}
                  aria-current={isActive ? "true" : undefined}
                  title={item.title}
                  className={cn(
                    "w-full rounded-lg py-2 pl-2.5 pr-16 text-left transition-colors",
                    isActive
                      ? "bg-surface ring-1 ring-line"
                      : "hover:bg-surface-sunken"
                  )}
                >
                  <span className="block truncate text-ui font-medium text-ink">
                    {item.title}
                  </span>
                  <span className="mt-0.5 block text-meta text-ink-subtle">
                    {formatRelativeTime(item.updated_at)}
                  </span>
                </button>

                <div className="pointer-events-none absolute right-1.5 top-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingId(item.conversation_id);
                      setDraftTitle(item.title);
                    }}
                    className="rounded p-1 text-ink-icon transition-colors hover:bg-surface hover:text-ink"
                    title="Rename"
                    aria-label={`Rename ${item.title}`}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPendingDelete({ id: item.conversation_id, title: item.title })
                    }
                    className="rounded p-1 text-ink-icon transition-colors hover:bg-danger-soft hover:text-danger"
                    title="Delete"
                    aria-label={`Delete ${item.title}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete chat"
        confirmLabel="Delete chat"
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          const target = pendingDelete;
          setPendingDelete(null);
          if (target) void deleteConversation(target.id);
        }}
      >
        <p>
          <span className="font-medium text-ink">“{pendingDelete?.title}”</span> and its messages
          will be removed. Your documents and their indexes are not affected.
        </p>
      </ConfirmDialog>
    </section>
  );
}
