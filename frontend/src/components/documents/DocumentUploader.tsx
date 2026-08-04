"use client";
import React, { useCallback, useRef, useState } from 'react';
import { UploadCloud } from 'lucide-react';
import { useDocumentStore } from '@/store/useDocumentStore';
import { useChatStore } from '@/store/useChatStore';

export const DocumentUploader = () => {
  const { uploadDocument } = useDocumentStore();
  const { setActiveCitation } = useChatStore();
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const processFiles = useCallback((files: FileList | null) => {
    if (!files) return;
    
    // Auto-close citation drawer when interacting with new documents
    setActiveCitation(null);

    Array.from(files).forEach((file) => {
      if (file.type === 'application/pdf') {
        uploadDocument(file);
      } else {
        alert(`File ${file.name} is not a PDF.`);
      }
    });
  }, [uploadDocument, setActiveCitation]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    processFiles(e.dataTransfer.files);
  }, [processFiles]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    processFiles(e.target.files);
    if (fileInputRef.current) {
      fileInputRef.current.value = ''; // Reset input
    }
  }, [processFiles]);

  return (
    <div className="w-full">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept="application/pdf"
        multiple
        className="hidden"
      />
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`w-full p-8 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-colors ${
          isDragging
            ? 'border-[#4A5D23] bg-[#4A5D23]/5'
            : 'border-gray-200 hover:border-[#4A5D23]/50 hover:bg-gray-50'
        }`}
      >
        <UploadCloud 
          size={32} 
          className={`mb-3 ${isDragging ? 'text-[#4A5D23]' : 'text-gray-400'}`} 
        />
        <p className="text-sm font-medium text-gray-700 mb-1">
          Click or drag PDF to upload
        </p>
        <p className="text-xs text-gray-500">
          Multiple files supported
        </p>
      </div>
    </div>
  );
};