"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { Toaster } from "@/components/ui/Toaster";
import { useChatStore } from "@/store/useChatStore";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const initializeConversations = useChatStore((state) => state.initializeConversations);

  const closeSidebar = useCallback(() => setIsSidebarOpen(false), []);

  // Chat history belongs to the workspace, not to the chat surface: the
  // sidebar must be correct even before any document exists.
  useEffect(() => {
    void initializeConversations();
  }, [initializeConversations]);

  useEffect(() => {
    if (!isSidebarOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeSidebar();
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isSidebarOpen, closeSidebar]);

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-paper text-ink">
      <Sidebar isOpen={isSidebarOpen} onClose={closeSidebar} />

      <div className="flex h-full min-w-0 flex-1 flex-col">
        <WorkspaceHeader onOpenSidebar={() => setIsSidebarOpen(true)} />

        <main className="mx-auto flex w-full min-h-0 max-w-5xl flex-1 flex-col overflow-hidden px-3 pb-3 pt-3 sm:px-6 sm:pb-5">
          {children}
        </main>
      </div>

      <Toaster />
    </div>
  );
}
