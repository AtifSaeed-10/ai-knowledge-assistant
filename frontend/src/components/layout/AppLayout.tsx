"use client";
import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#F6F7F4] text-[#1C241F]">
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      <div className="flex h-screen min-w-0 flex-1 flex-col">
        <TopBar onOpenSidebar={() => setIsSidebarOpen(true)} />

        <main className="mx-auto flex w-full max-w-6xl min-h-0 flex-1 flex-col overflow-hidden px-4 py-3 sm:px-6 sm:py-4">
          {children}
        </main>
      </div>
    </div>
  );
}
