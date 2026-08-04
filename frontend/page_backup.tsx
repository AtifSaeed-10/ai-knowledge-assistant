import React from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { DocumentUploader } from '@/components/documents/DocumentUploader';
import { DocumentLibrary } from '@/components/documents/DocumentLibrary';
import { ChatContainer } from '@/components/chat/ChatContainer';

export default function WorkspacePage() {
  return (
    <AppLayout>
      <div className="flex flex-col lg:flex-row gap-6 h-full min-h-[calc(100vh-8rem)]">
        
        {/* Left Column: Document Management (Compact) */}
        <div className="w-full lg:w-1/3 xl:w-[30%] flex flex-col gap-6 shrink-0">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              Knowledge Base
            </h1>
            <p className="text-sm text-gray-500">
              Upload documents to train your AI assistant.
            </p>
          </div>
          
          <div className="flex flex-col gap-6 flex-1">
            <DocumentUploader />
            <DocumentLibrary />
          </div>
        </div>

        {/* Right Column: Chat Interface (Dominant) */}
        <div className="w-full lg:w-2/3 xl:w-[70%]">
          <div className="sticky top-20 h-[calc(100vh-7.5rem)]">
            <ChatContainer />
          </div>
        </div>
        
      </div>
    </AppLayout>
  );
}