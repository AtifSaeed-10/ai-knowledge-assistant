"use client";
import React from 'react';
import { Menu, Settings } from 'lucide-react';
import { Logo } from '@/components/ui/Logo';

interface TopBarProps {
  onOpenSidebar: () => void;
}

export function TopBar({ onOpenSidebar }: TopBarProps) {
  return (
    <header className="sticky top-0 z-10 h-16 bg-white/80 backdrop-blur-md border-b border-gray-200 px-4 sm:px-6 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <button
          onClick={onOpenSidebar}
          className="p-2 -ml-2 text-gray-600 hover:bg-gray-100 rounded-lg lg:hidden"
          aria-label="Open sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="lg:hidden flex items-center gap-2">
          <Logo className="w-6 h-6 text-[#4A5D23]" />
          <h2 className="text-lg font-semibold text-gray-800">DocuSage</h2>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-[#F6F7F4] rounded-full text-sm text-gray-600 font-medium border border-gray-200">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          Backend Connected
        </div>
        
        <button className="p-2 text-gray-500 hover:text-[#4A5D23] hover:bg-[#F6F7F4] rounded-full transition-colors">
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
}