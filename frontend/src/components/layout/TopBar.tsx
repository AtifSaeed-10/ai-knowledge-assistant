"use client";
import React from 'react';
import { Menu, Settings } from 'lucide-react';
import { Logo } from '@/components/ui/Logo';

interface TopBarProps {
  onOpenSidebar: () => void;
}

export function TopBar({ onOpenSidebar }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between gap-4 border-b border-[#EBEFEA] bg-[#F6F7F4]/85 px-4 backdrop-blur-xl sm:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <button
          onClick={onOpenSidebar}
          aria-label="Open sidebar"
          className="-ml-1 rounded-lg p-2 text-[#6F7B6B] transition-colors hover:bg-white hover:text-[#1C241F] lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        <Logo className="w-[112px] shrink-0 [&>svg]:h-auto [&>svg]:w-full lg:hidden" />

        <div className="hidden min-w-0 flex-col justify-center lg:flex">
          <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-[#98A395]">
            Workspace
          </span>
          <span className="truncate text-sm font-semibold tracking-[-0.01em] text-[#1C241F]">
            Document Assistant
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <div className="hidden h-8 items-center gap-2 rounded-full border border-[#EBEFEA] bg-white pl-2.5 pr-3 sm:inline-flex">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full rounded-full bg-[#87AB72] opacity-50" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#4A5D23]" />
          </span>
          <span className="text-xs font-medium text-[#5B6858]">Connected</span>
        </div>

        <button
          aria-label="Settings"
          title="Settings"
          className="rounded-lg p-2 text-[#6F7B6B] transition-colors hover:bg-white hover:text-[#4A5D23]"
        >
          <Settings className="h-[18px] w-[18px]" />
        </button>
      </div>
    </header>
  );
}
