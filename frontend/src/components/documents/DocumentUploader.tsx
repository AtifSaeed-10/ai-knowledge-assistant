"use client";
import React, { useCallback, useRef, useState } from 'react';
import { FileUp } from 'lucide-react';
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
      fileInputRef.current.value = '';
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
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        className={`group flex w-full cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-6 py-9 text-center transition-all duration-200 ${
          isDragging
            ? 'border-[#4A5D23] bg-[#4A5D23]/[0.04] shadow-[inset_0_0_0_1px_rgba(74,93,35,0.1)]'
            : 'border-[#D0D7CB] bg-white hover:border-[#87AB72] hover:bg-[#FBFBFA]'
        }`}
      >
        <span
          className={`mb-3 flex h-10 w-10 items-center justify-center rounded-full transition-colors duration-200 ${
            isDragging
              ? 'bg-[#4A5D23] text-white'
              : 'bg-[#F6F7F4] text-[#4A5D23] group-hover:bg-[#EFF1EC]'
          }`}
        >
          <FileUp size={18} strokeWidth={1.75} />
        </span>

        <p className="text-[14px] font-semibold tracking-[-0.01em] text-[#1C241F]">
          {isDragging ? 'Drop to upload' : 'Drop PDFs here or browse'}
        </p>
        <p className="mt-1 text-[12px] text-[#6F7B6B]">
          PDF only · multiple files supported
        </p>
      </div>
    </div>
  );
};
