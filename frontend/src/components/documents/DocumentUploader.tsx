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
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        className={`group flex w-full cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-6 py-10 text-center transition-all duration-200 ${
          isDragging
            ? 'border-[#4A5D23] bg-[#4A5D23]/[0.04] shadow-[inset_0_0_0_1px_rgba(74,93,35,0.12)]'
            : 'border-[#D8DED5] bg-[#FBFBFA] hover:border-[#87AB72] hover:bg-white'
        }`}
      >
        <span
          className={`mb-3.5 flex h-11 w-11 items-center justify-center rounded-xl border transition-colors duration-200 ${
            isDragging
              ? 'border-[#4A5D23]/20 bg-white text-[#4A5D23]'
              : 'border-[#EBEFEA] bg-white text-[#98A395] group-hover:border-[#D8DED5] group-hover:text-[#4A5D23]'
          }`}
        >
          <FileUp size={20} strokeWidth={1.75} />
        </span>

        <p className="text-[14px] font-semibold tracking-[-0.01em] text-[#1C241F]">
          {isDragging ? 'Drop PDFs to upload' : 'Drop PDFs here, or click to browse'}
        </p>
        <p className="mt-1.5 max-w-[240px] text-[13px] leading-relaxed text-[#6F7B6B]">
          Multiple files supported. Documents are indexed automatically after upload.
        </p>
      </div>
    </div>
  );
};
