"use client";

import React, { useState } from 'react';
import { FileText, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { useDocumentStore } from '@/store/useDocumentStore';
import { Document } from '@/types';
import { ProcessingTimeline } from './ProcessingTimeline';

export function DocumentLibrary() {
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
    return 'bg-orange-500'; // Uploaded, extracting, chunking, embedding
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-white">
        <h3 className="font-semibold text-gray-800">Document Library</h3>
        <span className="text-sm text-gray-500 bg-gray-100 px-2.5 py-0.5 rounded-full">
          {documents.length} files
        </span>
      </div>

      {documents.length === 0 ? (
        <div className="p-8 text-center text-gray-500 text-sm">
          No documents uploaded yet.
        </div>
      ) : (
        <ul className="divide-y divide-gray-50">
          {documents.map((doc) => (
            <li key={doc.id} className="flex flex-col bg-white hover:bg-[#F6F7F4]/30 transition-colors">
              <div className="flex items-center justify-between p-4 px-6">
                <div className="flex items-center gap-4 flex-1 cursor-pointer" onClick={() => toggleExpand(doc.id)}>
                  <div className="p-2 bg-[#F6F7F4] rounded-lg text-[#4A5D23]">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-900">{doc.name}</h4>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-500">{formatBytes(doc.size)}</span>
                      <span className="text-gray-300">•</span>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${getStatusColor(doc.status)} ${doc.status !== 'ready' ? 'animate-pulse' : ''}`}></span>
                        <span className="text-xs capitalize text-gray-500">{doc.status.replace('-', ' ')}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
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
              </div>

              {expandedDoc === doc.id && (
                <div className="px-6 pb-4 pt-2 bg-[#F6F7F4]/50 border-t border-gray-50">
                  <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Processing Status</h5>
                  <ProcessingTimeline status={doc.status} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Delete Confirmation Dialog */}
      {docToDelete && (
        <div className="fixed inset-0 bg-gray-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 animate-in fade-in zoom-in duration-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete Document</h3>
            <p className="text-sm text-gray-600 mb-6">
              Are you sure you want to remove <span className="font-medium text-gray-900">"{docToDelete.name}"</span>? This action will remove it from the search index and cannot be undone.
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