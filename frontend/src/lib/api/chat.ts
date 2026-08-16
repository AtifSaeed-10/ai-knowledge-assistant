import { Message, Citation } from "@/types";
import { ProductMode } from "@/types/mode";
import { API_CONFIG, delay } from "./client";

interface ApiSource {
  document_id?: string;
  filename?: string;
  page?: number | null;
  page_number?: number | null;
  chunk_id?: string;
  relevance?: number;
}

interface ChatApiResponse {
  answer?: string;
  response?: string;
  sources?: ApiSource[];
}

export function mapSourceToCitation(src: ApiSource, idx: number): Citation {
  const rawPage = src.page ?? src.page_number;
  const pageNumber =
    typeof rawPage === "number" && Number.isFinite(rawPage) && rawPage >= 1
      ? Math.floor(rawPage)
      : null;

  return {
    id: src.chunk_id || `cit-${Date.now()}-${idx}`,
    documentName: src.filename || "Unknown Document",
    pageNumber,
    relevance: src.relevance ?? null,
    chunk_id: src.chunk_id ?? null,
    documentId: src.document_id ?? null,
  };
}

export const chatApi = {


  async sendMessage(
    content: string,
    documentIds: string[],
    conversationId: string,
    mode: ProductMode = "normal"
  ): Promise<Message> {


    if (API_CONFIG.useMock) {

      await delay(1200);

      return {
        id: `msg-${Date.now()}`,
        role: "assistant",
        content: "Mock",
        timestamp: new Date(),
      };

    }



    const response = await fetch(
      `${API_CONFIG.baseUrl}/chat`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          question: content,
          conversation_id: conversationId,
          document_ids: documentIds,
          mode,
        }),
      }
    );



    if (!response.ok) {

      throw new Error(
        "Failed to fetch chat response"
      );

    }



    const data = (await response.json()) as ChatApiResponse;



    const mappedCitations: Citation[] =
      (data.sources || []).map(mapSourceToCitation);



    return {

      id:
        `msg-${Date.now()}`,

      role:
        "assistant",

      content:
        data.answer ||
        data.response ||
        "No response received.",

      citations:
        mappedCitations,

      timestamp:
        new Date(),

    };

  },





async streamMessage(
  content: string,
  documentIds: string[],
  conversationId: string,
  onChunk: (chunk: string) => void,
  onComplete: (citations: Citation[]) => void,
  mode: ProductMode = "normal",
  signal?: AbortSignal,
  regenerate: boolean = false
): Promise<void> {


  const response = await fetch(
    `${API_CONFIG.baseUrl}/chat/stream`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        question: content,
        conversation_id: conversationId,
        document_ids: documentIds,
        mode,
        regenerate,
      }),
      signal,
    }
  );


  if (!response.ok) {
    throw new Error(
      "Failed to stream response"
    );
  }


  const reader =
    response.body?.getReader();


  if (!reader) {
    throw new Error(
      "No stream available"
    );
  }


  const decoder =
    new TextDecoder();


  let buffer = "";


  let citationsSent = false;



  while (true) {


    const {
      done,
      value
    } =
    await reader.read();



    if (done) break;



    buffer += decoder.decode(
      value,
      {
        stream:true
      }
    );



    // Extract citations

    if (!citationsSent &&
        buffer.includes("__END_CITATIONS__")) {


      const start =
        buffer.indexOf(
          "__CITATIONS__"
        );


      const end =
        buffer.indexOf(
          "__END_CITATIONS__"
        );



      if(start !== -1 && end !== -1) {


        const citationText =
          buffer.substring(
            start + "__CITATIONS__".length,
            end
          );



        try {

          const raw = JSON.parse(citationText) as ApiSource[];

          const mapped = raw.map(mapSourceToCitation);


          onComplete(mapped);

          citationsSent = true;


        }
        catch(error){

          console.error(
            "Citation parse error:",
            error
          );

        }



        buffer =
          buffer.substring(
            end + "__END_CITATIONS__".length
          );

      }

    }



    // only stream answer text

    if(buffer.length > 0) {


      onChunk(buffer);

      buffer = "";

    }


  }



  // finish loading
  if(!citationsSent){

    onComplete([]);

  }

}

};