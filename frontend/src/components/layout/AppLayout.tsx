"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { SignupModal } from "@/components/auth/SignupModal";
import { WorkspaceTour } from "@/components/workspace/tour/WorkspaceTour";
import { Toaster } from "@/components/ui/Toaster";
import { useAuthStore } from "@/store/useAuthStore";
import { useChatStore } from "@/store/useChatStore";
import { usePdfPanelStore } from "@/store/usePdfPanelStore";
import { useSupabaseSession } from "@/lib/supabase/useSupabaseSession";
import { useKeyboardInset } from "@/hooks/useKeyboardInset";
import { cn } from "@/lib/cn";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [tourWantsSidebar, setTourWantsSidebar] = useState(false);
  const initializeConversations = useChatStore((state) => state.initializeConversations);
  const initSession = useAuthStore((state) => state.initSession);
  const pdfOpen = usePdfPanelStore((state) => state.isOpen);

  const closeSidebar = useCallback(() => setIsSidebarOpen(false), []);

  // Establish identity (guest id or restored token) before anything else, so
  // the first API call already carries it.
  useSupabaseSession();
  useKeyboardInset();

  useEffect(() => {
    initSession();
  }, [initSession]);

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

  // On phones the document list lives in the drawer, so the tour has to slide
  // it in for that step and put it back afterwards.
  useEffect(() => {
    if (!tourWantsSidebar) return;
    if (window.matchMedia("(min-width: 1024px)").matches) return;

    setIsSidebarOpen(true);
    return () => setIsSidebarOpen(false);
  }, [tourWantsSidebar]);

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-paper text-ink pt-[env(safe-area-inset-top)]">
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={closeSidebar}
        forceExpanded={tourWantsSidebar}
      />

      <div className="flex h-full min-w-0 flex-1 flex-col">
        <WorkspaceHeader onOpenSidebar={() => setIsSidebarOpen(true)} />

        <main
          className={cn(
            "mx-auto flex w-full min-h-0 max-w-5xl flex-1 flex-col overflow-hidden px-2 pb-[max(0.75rem,env(safe-area-inset-bottom),var(--keyboard-inset,0px))] pt-1 sm:px-6 sm:pb-5 sm:pt-2",
            pdfOpen && "lg:mx-0 lg:max-w-none lg:px-4"
          )}
        >
          {children}
        </main>
      </div>

      <SignupModal />
      <WorkspaceTour onNeedsSidebar={setTourWantsSidebar} />
      <Toaster />
    </div>
  );
}
