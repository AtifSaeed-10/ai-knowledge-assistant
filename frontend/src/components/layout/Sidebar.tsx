"use client";
import React, { useState, useEffect, useCallback } from 'react';
import { X, PanelLeftClose, PanelLeft, Plus } from 'lucide-react';
import { Logo } from '@/components/ui/Logo';
import { DocumentLibrary } from '@/components/documents/DocumentLibrary';
import { DocumentUploader } from '@/components/documents/DocumentUploader';
import { useDocumentStore } from '@/store/useDocumentStore';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const documents = useDocumentStore((state) => state.documents);
  
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [width, setWidth] = useState(300);
  const [isResizing, setIsResizing] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  // Restore states
  useEffect(() => {
    const storedWidth = sessionStorage.getItem('docusage_sidebar_width');
    const storedCollapsed = sessionStorage.getItem('docusage_sidebar_collapsed');
    if (storedWidth) setWidth(Number(storedWidth));
    if (storedCollapsed) setIsCollapsed(storedCollapsed === 'true');
  }, []);

  const handleCollapseToggle = () => {
    const newState = !isCollapsed;
    setIsCollapsed(newState);
    sessionStorage.setItem('docusage_sidebar_collapsed', String(newState));
  };

  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      let newWidth = e.clientX;
      if (newWidth < 240) newWidth = 240;
      if (newWidth > 380) newWidth = 380;
      
      setWidth(newWidth);
      sessionStorage.setItem('docusage_sidebar_width', String(newWidth));
      
      if (isCollapsed && newWidth > 240) {
        setIsCollapsed(false);
        sessionStorage.setItem('docusage_sidebar_collapsed', 'false');
      }
    };
    const handleMouseUp = () => setIsResizing(false);

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, isCollapsed]);

  // Close upload modal dynamically when upload begins
  const prevDocsLength = React.useRef(documents.length);
  useEffect(() => {
    if (isUploadModalOpen && documents.length > prevDocsLength.current) {
      setIsUploadModalOpen(false);
    }
    prevDocsLength.current = documents.length;
  }, [documents.length, isUploadModalOpen]);

  const currentWidth = isCollapsed ? 80 : width;

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-gray-900/50 backdrop-blur-sm z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        style={{ width: isOpen ? 280 : currentWidth }} // Mobile is fixed, desktop is dynamic
        className={`fixed lg:relative top-0 left-0 h-full bg-white border-r border-gray-200 z-40 transform transition-all duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        } flex flex-col ${isResizing ? 'transition-none cursor-col-resize select-none' : ''}`}
      >
        {/* Header */}
        <div className={`h-16 flex items-center px-4 border-b border-gray-100 shrink-0 ${isCollapsed ? 'justify-center lg:px-2' : 'justify-between'}`}>
          {!isCollapsed && (
            <div className="flex items-center gap-3 text-[#4A5D23] overflow-hidden">
              <Logo className="w-8 h-8 shrink-0" />
              <span className="text-xl font-bold tracking-tight text-gray-900 truncate">DocuSage</span>
            </div>
          )}
          
          <button 
            onClick={handleCollapseToggle}
            className="hidden lg:flex p-1.5 text-gray-400 hover:bg-gray-100 rounded-md transition-colors shrink-0"
            title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            {isCollapsed ? <PanelLeft size={20} /> : <PanelLeftClose size={20} />}
          </button>
          
          <button 
            onClick={onClose}
            className="p-1 text-gray-400 hover:bg-gray-100 rounded-md lg:hidden shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Region */}
        <div className="flex-1 overflow-y-auto flex flex-col py-4">
          <DocumentLibrary isCollapsed={isCollapsed} />
        </div>

        {/* Footer Area */}
        {documents.length > 0 && (
          <div className="p-4 border-t border-gray-100 shrink-0 flex flex-col gap-4">
            {!isCollapsed && (
              <div className="bg-[#F6F7F4] p-4 rounded-xl">
                <h4 className="text-sm font-semibold text-gray-900">Storage Usage</h4>
                <div className="w-full h-2 bg-gray-200 rounded-full mt-2">
                  <div className="h-2 bg-[#4A5D23] rounded-full" style={{ width: '45%' }}></div>
                </div>
                <p className="text-xs text-gray-500 mt-2">450 MB / 1 GB used</p>
              </div>
            )}
            
            <button
              onClick={() => setIsUploadModalOpen(true)}
              className={`flex items-center justify-center gap-2 w-full bg-white border shadow-sm border-gray-200 hover:border-[#4A5D23] hover:text-[#4A5D23] text-gray-700 transition-colors rounded-xl ${
                isCollapsed ? 'p-3' : 'py-2.5 px-4'
              }`}
            >
              <Plus size={20} className={isCollapsed ? '' : 'text-[#4A5D23]'} />
              {!isCollapsed && <span className="font-medium text-sm whitespace-nowrap">Upload PDF</span>}
            </button>
          </div>
        )}

        {/* Resizer Edge Handler */}
        {!isCollapsed && (
          <div 
            onMouseDown={startResizing}
            className="hidden lg:block absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-[#4A5D23]/30 active:bg-[#4A5D23]/50 transition-colors z-50"
          />
        )}
      </aside>

      {/* Upload Modal Overlay */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-gray-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl relative flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-5 border-b border-gray-100 bg-gray-50/50">
              <h2 className="text-lg font-semibold text-gray-900">Upload Documents</h2>
              <button 
                onClick={() => setIsUploadModalOpen(false)}
                className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            <div className="p-6">
              <DocumentUploader />
            </div>
          </div>
        </div>
      )}
    </>
  );
}