import { Document, Message, Citation } from '@/types';

// Helper to simulate network delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const api = {
  documents: {
    // Simulates the initial upload
    async upload(file: File): Promise<Document> {
      await delay(800);
      return {
        id: Math.random().toString(36).substring(7),
        name: file.name,
        size: file.size,
        status: 'uploading',
        uploadedAt: new Date().toISOString(),
      };
    },
    
    // Simulates fetching the document library
    async getLibrary(): Promise<Document[]> {
      await delay(500);
      return [
        {
          id: 'doc_1',
          name: 'Machine_Learning_Fundamentals.pdf',
          size: 2450000,
          status: 'ready',
          uploadedAt: new Date(Date.now() - 86400000).toISOString(),
        }
      ];
    },

    async delete(id: string): Promise<boolean> {
      await delay(600);
      return true;
    }
  },

  chat: {
    // Simulates sending a query and getting a RAG response
    async sendMessage(query: string, activeDocumentIds: string[]): Promise<Message> {
      await delay(1500); // Simulate processing time
      
      const mockCitations: Citation[] = [
        {
          documentId: 'doc_1',
          documentName: 'Machine_Learning_Fundamentals.pdf',
          pageNumber: 12,
          relevanceScore: 94,
          snippet: "Transformer architectures rely heavily on self-attention mechanisms to weigh the significance of different parts of the input data.",
        }
      ];

      return {
        id: Math.random().toString(36).substring(7),
        role: 'assistant',
        content: `Based on your documents, here is the answer to: "${query}". \n\nThe documents indicate that this concept is fundamental to the underlying architecture. I've included a citation below for more context.`,
        citations: activeDocumentIds.length > 0 ? mockCitations : [],
        timestamp: new Date().toISOString(),
      };
    }
  }
};