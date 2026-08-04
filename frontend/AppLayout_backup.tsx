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
    <div className="min-h-screen bg-[#F6F7F4] text-gray-900 font-sans flex">
      <Sidebar 
        isOpen={isSidebarOpen} 
        onClose={() => setIsSidebarOpen(false)} 
      />
      
      <div className="flex-1 flex flex-col lg:pl-72 min-h-screen">
        <TopBar onOpenSidebar={() => setIsSidebarOpen(true)} />
        <main className="flex-1 p-4 sm:p-8 max-w-6xl mx-auto w-full">
          {children}
        </main>
      </div>
    </div>
  );
}