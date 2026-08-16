"use client";

import React, { useState } from "react";
import { MessageSquarePlus, Pencil, Trash2, Check, X } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";

function formatRelativeTime(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ConversationList({ isCollapsed = false }: { isCollapsed?: boolean }) {
  const conversations = useChatStore((state) => state.conversations);
  const conversationId = useChatStore((state) => state.conversationId);
  const createConversation = useChatStore((state) => state.createConversation);
  const selectConversation = useChatStore((state) => state.selectConversation);
  const renameConversation = useChatStore((state) => state.renameConversation);
  const deleteConversation = useChatStore((state) => state.deleteConversation);
  const isLoading = useChatStore((state) => state.isLoading);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const startRename = (id: string, title: string) => {
    setEditingId(id);
    setDraftTitle(title);
  };

  const commitRename = async () => {
    if (!editingId) return;
    const title = draftTitle.trim();
    if (title) {
      await renameConversation(editingId, title);
    }
    setEditingId(null);
  };

  if (isCollapsed) {
    return (
      <div className="px-2 pb-2">
        <button
          type="button"
          onClick={() => void createConversation()}
          title="New conversation"
          className="flex h-9 w-full items-center justify-center rounded-lg text-[#6F7B6B] transition-colors hover:bg-[#EFF1EC] hover:text-[#4A5D23]"
        >
          <MessageSquarePlus size={18} />
        </button>
      </div>
    );
  }

  return (
    <div className="px-3 pb-3">
      <div className="mb-2 flex items-center justify-between px-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#98A395]">
          Conversations
        </span>
        <button
          type="button"
          onClick={() => void createConversation()}
          className="rounded-md p-1 text-[#98A395] transition-colors hover:bg-[#EFF1EC] hover:text-[#4A5D23]"
          title="New conversation"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
        </button>
      </div>

      {conversations.length === 0 ? (
        <p className="px-2 py-3 text-[12px] text-[#98A395]">
          Start a chat to keep history here.
        </p>
      ) : (
        <ul className="space-y-0.5">
          {conversations.map((item) => {
            const isActive = item.conversation_id === conversationId;
            const isEditing = editingId === item.conversation_id;
            return (
              <li key={item.conversation_id}>
                <div
                  className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 ${
                    isActive ? "bg-white ring-1 ring-[#EBEFEA]" : "hover:bg-[#F1F3EF]"
                  }`}
                >
                  {isEditing ? (
                    <form
                      className="flex min-w-0 flex-1 items-center gap-1"
                      onSubmit={(event) => {
                        event.preventDefault();
                        void commitRename();
                      }}
                    >
                      <input
                        autoFocus
                        value={draftTitle}
                        onChange={(event) => setDraftTitle(event.target.value)}
                        className="min-w-0 flex-1 rounded border border-[#EBEFEA] px-1.5 py-0.5 text-[12px] text-[#1C241F] outline-none focus:border-[#87AB72]"
                      />
                      <button
                        type="submit"
                        className="rounded p-1 text-[#4A5D23] hover:bg-[#EFF1EC]"
                        aria-label="Save name"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="rounded p-1 text-[#98A395] hover:bg-[#EFF1EC]"
                        aria-label="Cancel rename"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </form>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => void selectConversation(item.conversation_id)}
                        className="min-w-0 flex-1 text-left"
                        title={item.title}
                      >
                        <span className="block truncate text-[12.5px] font-medium text-[#1C241F]">
                          {item.title}
                        </span>
                        <span className="block text-[10.5px] text-[#98A395]">
                          {formatRelativeTime(item.updated_at)}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => startRename(item.conversation_id, item.title)}
                        className="rounded p-1 text-[#98A395] opacity-0 transition-opacity hover:bg-white hover:text-[#1C241F] group-hover:opacity-100"
                        title="Rename"
                        aria-label={`Rename ${item.title}`}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setPendingDeleteId(item.conversation_id)}
                        className="rounded p-1 text-[#98A395] opacity-0 transition-opacity hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
                        title="Delete"
                        aria-label={`Delete ${item.title}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {pendingDeleteId && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-[#1C241F]/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-xl border border-[#EBEFEA] bg-white p-5 shadow-2xl">
            <h3 className="text-[15px] font-semibold text-[#1C241F]">
              Delete conversation
            </h3>
            <p className="mt-2 text-sm text-[#6F7B6B]">
              This removes the conversation from history. Document indexes are not affected.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setPendingDeleteId(null)}
                className="rounded-lg px-3.5 py-2 text-[13px] font-medium text-[#5B6858] hover:bg-[#F1F3EF]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const id = pendingDeleteId;
                  setPendingDeleteId(null);
                  if (id) void deleteConversation(id);
                }}
                className="rounded-lg bg-red-600 px-3.5 py-2 text-[13px] font-medium text-white hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
