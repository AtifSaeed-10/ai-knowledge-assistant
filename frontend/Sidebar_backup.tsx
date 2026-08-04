"use client";
import React from 'react';
import { BookOpen, MessageSquare, Settings, X } from 'lucide-react';
import { Logo } from '@/components/ui/Logo';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const navItems = [
    { name: 'Documents', icon: BookOpen, active: true },
    { name: 'Chat', icon: MessageSquare, active: false },
    { name: 'Settings', icon: Settings, active: false },
  ];

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-gray-900/50 backdrop-blur-sm z-20 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={`fixed top-0 left-0 h-full w-72 bg-white border-r border-gray-200 z-30 transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        } flex flex-col`}
      >
        <div className="h-16 flex items-center justify-between px-6 border-b border-gray-100">
          <div className="flex items-center gap-3 text-[#4A5D23]">
            <Logo className="w-8 h-8" />
            <span className="text-xl font-bold tracking-tight text-gray-900">DocuSage</span>
          </div>
          <button 
            onClick={onClose}
            className="p-1 text-gray-400 hover:bg-gray-100 rounded-md lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {navItems.map((item) => (
            <button
              key={item.name}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                item.active 
                  ? 'bg-[#4A5D23] text-white shadow-md shadow-[#4A5D23]/20' 
                  : 'text-gray-600 hover:bg-[#F6F7F4] hover:text-gray-900'
              }`}
            >
              <item.icon className={`w-5 h-5 ${item.active ? 'text-white' : 'text-gray-400'}`} />
              <span className="font-medium">{item.name}</span>
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-100">
          <div className="bg-[#F6F7F4] p-4 rounded-xl">
            <h4 className="text-sm font-semibold text-gray-900">Storage Usage</h4>
            <div className="w-full h-2 bg-gray-200 rounded-full mt-2">
              <div className="h-2 bg-[#4A5D23] rounded-full" style={{ width: '45%' }}></div>
            </div>
            <p className="text-xs text-gray-500 mt-2">450 MB / 1 GB used</p>
          </div>
        </div>
      </aside>
    </>
  );
}