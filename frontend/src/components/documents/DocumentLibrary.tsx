"use client";

import React, { useState } from 'react';
import { FileText, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { useDocumentStore } from '@/store/useDocumentStore';
import { Document } from '@/types';
import { ProcessingTimeline } from './ProcessingTimeline';

interface DocumentLibraryProps {
  isCollapsed?: boolean;
}

export function DocumentLibrary({ isCollapsed = false }: DocumentLibraryProps) {
  const documents = useDocumentStore((state) => state.documents);
  const deleteDocument = useDocumentStore((state) => state.deleteDocument);
  
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);
  const [docToDelete, setDocToDelete] = useState<Document | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedDoc(expandedDoc === id ? null : id);
  };

  const confirmDelete = () => {
    if (docToDelete) {
      deleteDocument(docToDelete.id);
      setDocToDelete(null);
    }
  };

  const getStatusColor = (status: string) => {
    if (status === 'ready') return 'bg-green-500';
    if (status === 'indexing') return 'bg-yellow-500';
    return 'bg-orange-500'; 
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (documents.length === 0) {
    if (isCollapsed) return null;
    return (
      <div className="px-4">
        <div className="p-6 text-center text-gray-500 text-sm border-2 border-dashed border-gray-200 rounded-xl bg-gray-50/50">
          No documents uploaded yet.
        </div>
      </div>
    );
  }

  return (
    <div className={`px-2 ${isCollapsed ? 'px-2' : 'px-4'}`}>
      {!isCollapsed && (
        <div className="px-2 mb-3 text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center justify-between">
          <span>Documents</span>
          <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{documents.length}</span>
        </div>
      )}

      <ul className="space-y-1">
        {documents.map((doc) => (
          <li key={doc.id} className="flex flex-col bg-transparent group">
            <div className={`flex items-center rounded-xl transition-colors hover:bg-gray-100 ${isCollapsed ? 'justify-center p-2' : 'justify-between p-2'}`}>
              
              <div 
                className={`flex items-center gap-3 cursor-pointer ${isCollapsed ? 'justify-center' : 'flex-1 min-w-0'}`} 
                onClick={() => !isCollapsed && toggleExpand(doc.id)}
                title={doc.name}
              >
                <div className="relative p-2 rounded-lg text-gray-500 group-hover:text-[#4A5D23] transition-colors shrink-0 bg-gray-50 group-hover:bg-white border border-gray-100">
                  <FileText className="w-5 h-5" />
                  {isCollapsed && (
                    <span className={`absolute -top-1 -right-1 w-2.5 h-2.5 border-2 border-white rounded-full ${getStatusColor(doc.status)} ${doc.status !== 'ready' ? 'animate-pulse' : ''}`}></span>
                  )}
                </div>
                
                {!isCollapsed && (
                  <div className="min-w-0 flex-1">
                    <h4 className={`text-sm font-medium truncate ${doc.status === 'ready' ? 'text-gray-800' : 'text-gray-500'}`}>
                      {doc.name}
                    </h4>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-gray-400">{formatBytes(doc.size)}</span>
                      <span className="text-gray-300">•</span>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${getStatusColor(doc.status)} ${doc.status !== 'ready' ? 'animate-pulse' : ''}`}></span>
                        <span className="text-[10px] capitalize text-gray-500">{doc.status.replace('-', ' ')}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {!isCollapsed && (
                <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button 
                    onClick={() => toggleExpand(doc.id)}
                    className="p-1.5 text-gray-400 hover:text-gray-700 rounded-md transition-colors"
                  >
                    {expandedDoc === doc.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                  <button 
                    onClick={() => setDocToDelete(doc)}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                    title="Delete document"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>

            {!isCollapsed && expandedDoc === doc.id && (
              <div className="mx-2 mt-1 mb-2 px-3 pb-3 pt-2 bg-gray-50 rounded-lg border border-gray-100">
                <h5 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">Processing Status</h5>
                <ProcessingTimeline status={doc.status} />
              </div>
            )}
          </li>
        ))}
      </ul>

      {/* Delete Confirmation Dialog */}
      {docToDelete && (
        <div className="fixed inset-0 bg-gray-900/40 backdrop-blur-sm z-[110] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 animate-in fade-in zoom-in duration-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete Document</h3>
            <p className="text-sm text-gray-600 mb-6">
              Are you sure you want to remove <span className="font-medium text-gray-900">&quot;{docToDelete.name}&quot;</span>? This action will remove it from the search index and cannot be undone.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button 
                onClick={() => setDocToDelete(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={confirmDelete}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors shadow-sm"
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