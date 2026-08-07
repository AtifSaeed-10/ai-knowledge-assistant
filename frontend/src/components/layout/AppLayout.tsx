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

        <main className="mx-auto w-full max-w-6xl flex-1 overflow-y-auto px-4 py-4 sm:px-8 sm:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
